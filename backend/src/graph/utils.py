from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

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