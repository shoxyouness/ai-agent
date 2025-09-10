from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import os
from dotenv import load_dotenv
from src.tools.sheet_tools import GOOGLE_SHEETS_CONTACT_TOOLS
from datetime import datetime
from src.config.llm import llm_client
load_dotenv()

with open("src/prompts/sheet_agent_prompt.txt", "r") as f:
    prompt_template_str = f.read()

# llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0, api_key=os.getenv("GEMINI_API_KEY"))

# Bind the tools to the LLM
tools = GOOGLE_SHEETS_CONTACT_TOOLS

llm_with_tools = llm_client.bind_tools(tools= tools)


tools_description = "\n".join([f"- {tool.name}: {tool.description}" for tool in tools])
sheet_agent_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", prompt_template_str),
        MessagesPlaceholder(variable_name="messages")
    ]
).partial(
    tools=tools_description, current_date_time=datetime.now().strftime("%I:%M %p %Z, %A, %B %d, %Y"))



sheet_agent_chain = sheet_agent_prompt | llm_with_tools  