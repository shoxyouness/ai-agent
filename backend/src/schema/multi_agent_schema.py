from typing import List, TypedDict, Annotated
from langgraph.graph import add_messages
from langchain_core.messages import BaseMessage

class MultiAgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]

    # Cleaned conversation that the supervisor + memory agent use:
    core_messages: List[BaseMessage]

    route: str  
    final_response: str
    current_user_message: BaseMessage

    sheet_messages: Annotated[List[BaseMessage], add_messages]
    email_messages: Annotated[List[BaseMessage], add_messages]
    calendar_messages: Annotated[List[BaseMessage], add_messages]
    memory_messages: Annotated[List[BaseMessage], add_messages]

    retrieved_memory : str

    message_to_next_agent: BaseMessage | None
    supervisor_response: str
    email_agent_response: str
    calendar_agent_response: str
    sheet_agent_response: str
    memory_agent_response: str
