from typing import List, TypedDict, Annotated
from langgraph.graph import add_messages
from langchain_core.messages import BaseMessage
class MultiAgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    route: str  
    final_response: str

