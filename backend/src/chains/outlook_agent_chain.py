from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_google_genai import ChatGoogleGenerativeAI  # Or your LLM
from langchain_openai import ChatOpenAI
import os
from dotenv import load_dotenv
from src.tools.email_tools import get_unread_emails, send_email, reply_to_email, mark_email_as_read # For tool binding
from src.tools.calender_tools import get_calendar_events, create_calendar_event, update_calendar_event  # For tool binding
from datetime import datetime
load_dotenv()

with open("src/prompts/outlook_agent_prompt.txt", "r") as f:
    prompt_template_str = f.read()

llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0, api_key=os.getenv("GEMINI_API_KEY"))
# llm = ChatOpenAI(model="gpt-4o", temperature=0, api_key=os.getenv("OPENAI_API_KEY")) 
tools = [get_unread_emails, send_email, reply_to_email, mark_email_as_read, get_calendar_events, create_calendar_event, update_calendar_event]



llm_with_tools = llm.bind_tools(tools= tools)


tools_description = "\n".join([f"- {tool.name}: {tool.description}" for tool in tools])
outlook_agent_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", prompt_template_str),
        MessagesPlaceholder(variable_name="messages")
    ]
).partial(
    tools=tools_description, current_date_time=datetime.now().strftime("%I:%M %p %Z, %A, %B %d, %Y"))



outlook_agent_chain = outlook_agent_prompt | llm_with_tools  