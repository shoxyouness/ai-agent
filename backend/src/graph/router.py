from src.graph.state import MultiAgentState
from src.graph.consts import *
from src.agents import email_agent, calendar_agent, sheet_agent, memory_agent, deep_research_agent
from langchain_core.messages import ToolMessage
from langgraph.graph import END

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

RESEARCH_TOOLS = {t.name.lower() for t in deep_research_agent.tools}

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
    if tool_name in RESEARCH_TOOLS:
        return DEEP_RESEARCH_TOOL_NODE


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
    elif route == "deep_research_agent":
        return DEEP_RESEARCH_AGENT_NODE
        
    return "end"

def reviewer_should_continue(state: MultiAgentState) -> str:
    decision = (state.get("review_decision") or "").lower()
    if decision == "approved":
        return EMAIL_TOOL_NODE
    if decision == "change_requested":
        return EMAIL_AGENT_NODE
    return CLEAR_STATE_NODE


def memory_should_continue(state: MultiAgentState) -> str:
    """
    Determines if memory agent should continue.
    Includes a HARD STOP to prevent infinite recursion loops.
    """
    messages = state.get("messages", [])
    if not messages:
        return "end"

    # 1. Check if the agent actually wants to call a tool
    last_msg = messages[-1]
    has_tool_calls = hasattr(last_msg, "tool_calls") and bool(last_msg.tool_calls)
    
    if has_tool_calls:
        # 2. CHECK HISTORY for previous tool executions
        # We look at the memory_agent's specific history
        memory_history = state.get("memory_messages", [])
        
        # Count how many times tools have ALREADY run in this memory session
        tool_output_count = sum(1 for m in memory_history if isinstance(m, ToolMessage))
        
        # 3. THE SAFETY VALVE
        # If we have already processed 2 tool outputs, we force a stop.
        # This allows: Agent -> Search -> Agent -> Add -> STOP.
        if tool_output_count >= 2:
            print("🛑 Memory Agent recursion limit hit (2 attempts). Forcing END.")
            return "end"

        # 4. Check if the tool is actually a memory tool (Double check)
        tool_name = last_msg.tool_calls[0]["name"].lower()
        if tool_name in MEMORY_TOOLS:
            return MEMORY_TOOL_NODE
    
    return "end"

