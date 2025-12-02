# backend/src/graph/base_graph.py
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type

from langgraph.graph import StateGraph
from langgraph.checkpoint.memory import MemorySaver


class BaseGraph(ABC):
    """
    Abstract base for all graphs (multi-agent + sub-graphs).

    - Wraps LangGraph's StateGraph + compiled app
    - Enforces a build_graph(...) method
    - Exposes invoke/stream/get_state helpers
    """

    def __init__(
        self,
        state_type: Type[dict],
        *,
        name: Optional[str] = None,
        checkpointer: Optional[MemorySaver] = None,
    ) -> None:
        self.name = name or self.__class__.__name__
        self.state_type = state_type
        self._builder = StateGraph(self.state_type)
        self._checkpointer = checkpointer or MemorySaver()

        # let subclass add nodes/edges/entrypoint
        self.build_graph(self._builder)

        # compile
        self._app = self._builder.compile(checkpointer=self._checkpointer)

    @abstractmethod
    def build_graph(self, graph: StateGraph) -> None:
        """
        Subclass must:
        - add nodes
        - set entry point
        - add edges / conditional edges
        """
        ...

    # --- Public API that makes this usable as a node in other graphs ---

    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        So a BaseGraph instance can be registered as a node:
        graph.add_node("email_agent", email_graph)
        """
        return self._app.invoke(state)

    def invoke(self, input: Dict[str, Any], config: Optional[Dict[str, Any]] = None):
        return self._app.invoke(input=input, config=config or {})

    def stream(self, input: Dict[str, Any], config: Optional[Dict[str, Any]] = None):
        return self._app.stream(input=input, config=config or {})

    def get_state(self, config: Optional[Dict[str, Any]] = None):
        return self._app.get_state(config=config or {})

    @property
    def app(self):
        """Access to the underlying compiled graph if needed."""
        return self._app
