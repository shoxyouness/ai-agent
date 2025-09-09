from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_google_genai import ChatGoogleGenerativeAI
import os
from dotenv import load_dotenv
from datetime import datetime

# Brave (Playwright MCP) tools
from src.tools.brave_tools import (
    browser_navigate,
    browser_snapshot,
    browser_click,
    browser_type,
    browser_evaluate,
    browser_take_screenshot,
    browser_navigate_back,
    browser_navigate_forward,
    browser_tab_new,
    browser_tab_select,
)
from langchain_openai import ChatOpenAI
load_dotenv()

# --- Load the prompt text for the brave agent ---
# Create this file (example content below)
with open("src/prompts/brave_agent_prompt.txt", "r", encoding="utf-8") as f:
    prompt_template_str = f.read()

# --- LLM (same setup you used for email agent) ---
llm = ChatOpenAI(
    model="gpt-4o",
    temperature=0,
    api_key=os.getenv("OPENAI_API_KEY"),
)

# --- Bind the Brave tools to the LLM ---
tools = [
    browser_navigate,
    browser_snapshot,
    browser_click,
    browser_type,
    browser_evaluate,
    browser_take_screenshot,
    browser_navigate_back,
    browser_navigate_forward,
    browser_tab_new,
    browser_tab_select,
]

llm_with_tools = llm.bind_tools(tools=tools)

tools_description = "\n".join([f"- {tool.name}: {tool.description}" for tool in tools])

brave_agent_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", prompt_template_str),
        MessagesPlaceholder(variable_name="messages"),
    ]
).partial(
    tools=tools_description,
    current_date_time=datetime.now().strftime("%I:%M %p %Z, %A, %B %d, %Y"),
)

brave_agent_chain = brave_agent_prompt | llm_with_tools
