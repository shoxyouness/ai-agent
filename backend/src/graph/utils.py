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


def strip_tool_calls(history: list) -> list:
    """
    Ensures history is valid for OpenAI by removing tool_calls metadata 
    from AIMessages, unless they are followed by ToolMessages. 
    """
    cleaned = []
    for i, m in enumerate(history):
        if isinstance(m, AIMessage) and getattr(m, "tool_calls", None):
            # Check if this AI message is followed by a matching ToolMessage
            is_paired = False
            if i + 1 < len(history) and isinstance(history[i+1], ToolMessage):
                # Handle both dict-like and object-like ToolCalls
                tc_ids = []
                for tc in m.tool_calls:
                    if isinstance(tc, dict):
                        tc_ids.append(tc.get("id"))
                    else:
                        tc_ids.append(getattr(tc, "id", None))
                
                if history[i+1].tool_call_id in tc_ids:
                    is_paired = True
            
            if not is_paired:
                # Strip metadata to avoid OpenAI 400
                content = m.content
                if not content or not content.strip():
                    # Fallback: OpenAI requires either content or tool_calls
                    content = "[Delegating to sub-agent...]"
                
                new_m = AIMessage(
                    content=content,
                    name=getattr(m, "name", None),
                    id=getattr(m, "id", None)
                )
                cleaned.append(new_m)
            else:
                cleaned.append(m)
        else:
            cleaned.append(m)
    return cleaned

def filter_supervisor_history(messages: list, limit: int = 20) -> list:
    """
    Filters history for the Supervisor and cleans it.
    """
    raw_filtered = []
    # Traverse backwards to get the most recent relevant messages first
    for msg in reversed(messages):
        # 1. Keep Human Messages (EXCLUDE internal review feedback)
        if isinstance(msg, HumanMessage):
            if getattr(msg, "name", "") != "review_human":
                raw_filtered.insert(0, msg)
        
        # 2. Keep AI Messages (Strictly Supervisor or Summary)
        elif isinstance(msg, AIMessage):
            name = (getattr(msg, "name", "") or "").lower()
            if name in ("supervisor", "sub_agent_task_summary"):
                raw_filtered.insert(0, msg)
        
        # Stop if we hit the limit
        if len(raw_filtered) >= limit:
            break
            
    # Always strip tool_calls from supervisor history as a final safety measure
    return strip_tool_calls(raw_filtered)
