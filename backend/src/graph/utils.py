from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

def extract_all_tool_calls(messages):
    """Extracts ALL tool calls from the last message, not just one."""
    if not messages:
        return []
    last_msg = messages[-1]
    tool_calls = getattr(last_msg, "tool_calls", [])
    return tool_calls


def get_last_human_message(messages):
    """Finds the last message from a human that isn't the Supervisor."""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage) and msg.name != "Supervisor":
            return msg
    return HumanMessage(content="")

def get_tc_name(tc) -> str:
    """Works for dicts or objects; returns lowercased name or empty string."""
    if isinstance(tc, dict):
        return (tc.get("name") or "").lower()
    return (getattr(tc, "name", "") or "").lower()


def extract_last_tool_call(messages):
    
    if not messages:
        return None
    last = messages[-1]
    tcs = getattr(last, "tool_calls", None) or []
    if not tcs:
        return None

    tc = tcs[-1]
    # ToolCall can be dict-like or object-like depending on version
    if isinstance(tc, dict):
        return {"name": tc.get("name"), "args": tc.get("args") or {}, "id": tc.get("id")}
    return {
        "name": getattr(tc, "name", None),
        "args": getattr(tc, "args", None) or {},
        "id": getattr(tc, "id", None),
    }


def strip_tool_calls(history):
    """Remove AI messages with tool_calls to avoid OpenAI 400 during rewrite."""
    cleaned = []
    for m in history:
        if isinstance(m, AIMessage) and getattr(m, "tool_calls", None):
            # drop it (it's an unfulfilled tool call)
            continue
        if isinstance(m, ToolMessage):
            # also drop tool messages if you dropped their call (optional)
            continue
        cleaned.append(m)
    return cleaned

def filter_supervisor_history(messages: list, limit: int = 20) -> list:
    """
    Filters history for the Supervisor to reduce noise.
    Keeps:
    - HumanMessages
    - AIMessages from 'Supervisor'
    - AIMessages from 'sub_agent_task_summary' (critical state updates)
    
    Removes:
    - ToolMessages
    - AIMessages from other agents (e.g. 'email_agent') unless it's a summary
    """
    filtered = []
    # Traverse backwards to get the most recent relevant messages first
    for msg in reversed(messages):
        # 1. Keep Human Messages
        if isinstance(msg, HumanMessage):
            filtered.insert(0, msg)
        
        # 2. Keep AI Messages (Strictly Supervisor or Summary)
        elif isinstance(msg, AIMessage):
            name = (getattr(msg, "name", "") or "").lower()
            if name in ("supervisor", "sub_agent_task_summary"):
                filtered.insert(0, msg)
        
        # Stop if we hit the limit
        if len(filtered) >= limit:
            break
            
    return filtered
