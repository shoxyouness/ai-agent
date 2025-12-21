from src.graph.state import MultiAgentState
from src.graph.consts import *
from src.agents import email_agent, calendar_agent, sheet_agent, memory_agent

def _get_last_tool_name(messages):
    if not messages: return None
    last = messages[-1]
    if not getattr(last, "tool_calls", None): return None
    return last.tool_calls[-1]["name"].lower()

# Build tool name sets dynamically
EMAIL_TOOLS = {t.name.lower() for t in email_agent.tools}
CAL_TOOLS = {t.name.lower() for t in calendar_agent.tools}
SHEET_TOOLS = {t.name.lower() for t in sheet_agent.tools}
MEMORY_TOOLS = {t.name.lower() for t in memory_agent.tools}


def sub_agent_should_continue(state: MultiAgentState) -> str:
    tool_name = _get_last_tool_name(state.get("messages"))
    
    if not tool_name:
        return CLEAR_STATE_NODE # Back to supervisor

    if tool_name in SENSITIVE_EMAIL_TOOLS:
        return REVIEWER_NODE
    if tool_name in EMAIL_TOOLS:
        return EMAIL_TOOL_NODE
    if tool_name in CAL_TOOLS:
        return CALENDAR_TOOL_NODE
    if tool_name in SHEET_TOOLS:
        return SHEET_TOOL_NODE

    return CLEAR_STATE_NODE


def supervisor_should_continue(state: MultiAgentState) -> str:
    """
    Returns the specific Node Name if a route exists, 
    otherwise returns 'end' to signal transition to Memory Agent.
    """
    route = state.get("route", "none")
    
    if route == "email_agent":
        return EMAIL_AGENT_NODE
    elif route == "calendar_agent":
        return CALENDAR_AGENT_NODE
    elif route == "sheet_agent":
        return SHEET_AGENT_NODE
    elif route == "browser_agent":
        return BROWSER_AGENT_NODE
        
    return "end"

def reviewer_should_continue(state: MultiAgentState) -> str:
    decision = (state.get("review_decision") or "").lower()
    if decision == "approved":
        return EMAIL_TOOL_NODE
    if decision == "change_requested":
        return EMAIL_AGENT_NODE
    return CLEAR_STATE_NODE


def memory_should_continue(state: MultiAgentState) -> str:
    tool_name = _get_last_tool_name(state.get("messages"))
    return MEMORY_TOOL_NODE if tool_name in MEMORY_TOOLS else "end"

