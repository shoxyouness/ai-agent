from typing import List, TypedDict, Annotated, Optional, Dict, Any  
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
    call_messages: Annotated[List[BaseMessage], add_messages]  # NEW

    browser_messages: List[BaseMessage] 
    browser_agent_response: Optional[str]


    retrieved_memory : str

    message_to_next_agent: BaseMessage | None
    supervisor_response: str
    email_agent_response: str
    calendar_agent_response: str
    sheet_agent_response: str
    memory_agent_response: str

    pending_email_tool_call: Optional[Dict[str, Any]]  # {"name": str, "args": dict, "id": str}
    review_decision: Optional[str]                     # "approved" | "change_requested"
    review_feedback: Optional[str]
    reviewed_tool_args: Optional[Dict[str, Any]]       # if you later support "edit"

    call_agent_response: str  # NEW
    active_call_sid: Optional[str]




