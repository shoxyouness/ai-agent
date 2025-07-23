from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_google_genai import ChatGoogleGenerativeAI  # Or your LLM
import os
from dotenv import load_dotenv
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Literal
load_dotenv()

class Supervisor(BaseModel):
   next: Literal["EMAIL_AGENT", "CALENDER_AGENT"] = Field(
    description="Determines which specialist to activate next in the workflow sequence:"
    "'EMAIL_AGENT' when the task is primarily email-related, "
    "'CALENDER_AGENT' when the task is primarily calendar-related."
   )

with open("src/prompts/supervisor_agent_prompt.txt", "r") as f:
    prompt_template_str = f.read()

llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0, api_key=os.getenv("GEMINI_API_KEY"))


supervisor_agent_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", prompt_template_str),
        MessagesPlaceholder(variable_name="messages")
    ]
).partial(
     current_date_time=datetime.now().strftime("%I:%M %p %Z, %A, %B %d, %Y")
)

supervisor_chain = supervisor_agent_prompt | llm.with_structured_output(
    Supervisor, )