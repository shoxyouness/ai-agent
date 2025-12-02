# backend/src/graph/email_graph.py
from __future__ import annotations

from typing import Dict, Any, TypedDict, List

from langgraph.prebuilt import ToolNode
from langchain_core.messages import BaseMessage, HumanMessage

from src.graph.base_graph import BaseGraph
from src.schema.multi_agent_schema import MultiAgentState  # reuse same state
from src.agents import email_agent


# If you want a dedicated state, define it; for now we reuse MultiAgentState.
EmailAgentState = MultiAgentState


def _get_tc_name(tc) -> str:
    if isinstance(tc, dict):
        return (tc.get("name") or "").lower()
    return (getattr(tc, "name", "") or "").lower()


class EmailAgentGraph(BaseGraph):
    """
    LangGraph wrapper around email_agent chain + its tools.

    Entry:
        - expects "messages" and optional "email_messages", "message_to_next_agent"

    Behavior:
        - runs email_agent.invoke
        - if tools are requested, loops through ToolNode
        - returns updated state (messages + email_messages + email_agent_response)
    """

    def __init__(self):
        self.email_tools = email_agent.tools
        self.email_tool_node = ToolNode(tools=self.email_tools)
        self.EMAIL_TOOL_NAMES = {t.name.lower() for t in self.email_tools}
        super().__init__(EmailAgentState, name="EmailAgentGraph")

    # -------- Node functions --------

    def _call_email_agent(self, state: EmailAgentState) -> Dict[str, Any]:
        email_history: List[BaseMessage] = state.get("email_messages", [])
        next_msg: BaseMessage | None = state.get("message_to_next_agent")

        if next_msg is None:
            if not state["messages"]:
                raise ValueError("EmailAgentGraph: no messages in state.")
            next_msg = state["messages"][-1]

        input_msgs = email_history + [next_msg]

        # call original email_agent chain
        response = email_agent.invoke(input_msgs)

        # IMPORTANT: append, don't overwrite global messages
        new_messages = state.get("messages", []) + [response]
        new_email_history = email_history + [next_msg, response]

        return {
            "messages": new_messages,
            "email_messages": new_email_history,
            "email_agent_response": response.content,
            "message_to_next_agent": None,
        }

    def _email_should_continue(self, state: EmailAgentState) -> str:
        msgs = state.get("messages") or []
        if not msgs:
            return "back_to_supervisor"

        last = msgs[-1]
        tcs = getattr(last, "tool_calls", None) or []
        if not tcs:
            return "back_to_supervisor"

        last_tc_name = _get_tc_name(tcs[-1])
        print(f"[email_router] last tool call: {last_tc_name}")

        if last_tc_name in self.EMAIL_TOOL_NAMES:
            return "to_email_tool"

        return "back_to_supervisor"

    # -------- Build graph --------

    def build_graph(self, graph):
        # Nodes
        graph.add_node("email_llm", self._call_email_agent)
        graph.add_node("email_tool_node", self.email_tool_node)

        # Entry point
        graph.set_entry_point("email_llm")

        # LLM -> tools or back
        graph.add_conditional_edges(
            "email_llm",
            self._email_should_continue,
            {
                "to_email_tool": "email_tool_node",
                "back_to_supervisor": "__end__",  # we will alias this to END in parent
            },
        )

        # tools -> back to llm
        graph.add_edge("email_tool_node", "email_llm")
