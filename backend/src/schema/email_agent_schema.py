
from typing import TypedDict, Annotated, List
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

class AgentState(TypedDict):
    """
    Represents the state of our email agent.

    Attributes:
        messages: The history of messages in the conversation.
        summary: The final generated summary of the emails.
    """
    messages: Annotated[List[BaseMessage], add_messages]
    summary: str




class Email(BaseModel):
    """A schema for a single email message."""
    sender: str = Field(description="The name and email address of the sender.")
    subject: str = Field(description="The subject line of the email.")
    body_preview: str = Field(description="A snippet of the email body.")
    message_id: str = Field(description="The unique identifier of the email message.")