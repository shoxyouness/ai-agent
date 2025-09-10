from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import os
from dotenv import load_dotenv
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Literal
from src.config.llm import llm_client
load_dotenv()

class Supervisor(BaseModel):
    route: Literal["email_agent", "calendar_agent","sheet_agent", "none"] = Field(
        description="Determines which specialist to activate next in the workflow sequence:"
        "'email_agent' when the task is primarily email-related, "
        "'calendar_agent' when the task is primarily calendar-related,"
        "''sheet_agent' when the task is primarily sheet_related,"
        "'none' if the task does not require any agent."
    )
    response: str = Field(
        description=(
            "A polished, user-facing response. If routing to an agent, this can be a confirmation "
            "(e.g., 'Checking your calendar...'). If the route is 'end', this MUST be a comprehensive final answer "
            "summarizing all the information gathered."
        ),
    )

with open("src/prompts/supervisor_agent_prompt.txt", "r") as f:
    prompt_template_str = f.read()

# llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0, api_key=os.getenv("GEMINI_API_KEY"))

supervisor_agent_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", prompt_template_str),
        MessagesPlaceholder(variable_name="messages")
    ]
).partial(
     current_date_time=datetime.now().strftime("%I:%M %p %Z, %A, %B %d, %Y")
)

supervisor_chain = supervisor_agent_prompt | llm_client.with_structured_output(Supervisor)