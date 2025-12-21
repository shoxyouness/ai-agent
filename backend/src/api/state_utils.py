# src/api/state_utils.py

from typing import Any, Dict
from langchain_core.messages import BaseMessage

def serialize_message(msg: BaseMessage) -> Dict[str, Any]:
    """Turn a LangChain BaseMessage into a JSON-serializable dict."""
    return {
        "type": msg.type,                  # "human", "ai", "system", "tool", ...
        "content": msg.content,
        "name": getattr(msg, "name", None),
        "id": getattr(msg, "id", None),
        "additional_kwargs": getattr(msg, "additional_kwargs", {}),
        "response_metadata": getattr(msg, "response_metadata", {}),
    }

def serialize_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """Serialize MultiAgentState (with BaseMessage lists) into pure JSON."""
    def _serialize_value(v: Any):
        if isinstance(v, BaseMessage):
            return serialize_message(v)
        if isinstance(v, list):
            return [_serialize_value(item) for item in v]
        if isinstance(v, dict):
            return {k: _serialize_value(val) for k, val in v.items()}
        return v

    return {k: _serialize_value(v) for k, v in state.items()}
