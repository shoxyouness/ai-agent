from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import BaseMessage, AIMessage
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from datetime import datetime
from pathlib import Path
from pydantic import BaseModel

class BaseAgent(ABC):
    """
    Base class for all agents in the multi-agent system.

    Now supports providing the system prompt directly via `prompt` (preferred).
    For backward compatibility, you can still use `prompt_file`.
    If both are provided, `prompt` takes precedence.
    """

    def __init__(
        self,
        name: str,
        llm: BaseChatModel,
        tools: List[BaseTool],
        prompt: Optional[str] = None,
        prompt_file: Optional[str] = None,
        temperature: float = 0.0,
        system_context: Optional[Dict[str, Any]] = None,
        structured_output: Optional[BaseModel] = None,
    ):
        """
        Args:
            name: Agent name (e.g., "email_agent", "calendar_agent").
            llm: Language model instance.
            tools: List of tools available to this agent.
            prompt: The system prompt template string (preferred).
            prompt_file: Path to the prompt file (relative to prompts/). Used iff `prompt` is None.
            temperature: LLM temperature.
            system_context: Extra context vars injected into the prompt via `.partial(...)`.
        """
        self.name = name
        self.llm = llm
        self.tools = tools or []
        self._prompt_file = prompt_file  # keep private; might be None
        self.temperature = temperature
        self.system_context = system_context or {}
        self.structured_output = structured_output

        # Resolve the prompt template (string)
        self.prompt_template_str = self._resolve_prompt(prompt, prompt_file)

        # Build chain
        self.chain = self._create_chain()

    # ------------------------ Prompt handling ------------------------

    def _resolve_prompt(self, prompt: Optional[str], prompt_file: Optional[str]) -> str:
        """
        Returns the prompt string. Prefers `prompt` over `prompt_file`.
        """
        if isinstance(prompt, str) and prompt.strip():
            return prompt

        if prompt_file:
            # Look under .../prompts/<prompt_file>
            prompts_dir = Path(__file__).parent.parent / "prompts"
            prompt_path = prompts_dir / prompt_file
            if not prompt_path.exists():
                raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
            return prompt_path.read_text(encoding="utf-8")

        raise ValueError(
            "No prompt provided. Pass `prompt='...'` or `prompt_file='my_prompt.txt'`."
        )

    def set_prompt(self, prompt: str) -> None:
        """
        Replace the current prompt with a new string and recreate the chain.
        """
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("`prompt` must be a non-empty string.")
        self.prompt_template_str = prompt
        self.chain = self._create_chain()

    def reload_prompt_from_file(self) -> None:
        """
        Reloads the prompt from `prompt_file` (if set) and recreates the chain.
        Useful in development. Raises if no file is configured.
        """
        if not self._prompt_file:
            raise RuntimeError("No `prompt_file` configured for this agent.")
        self.prompt_template_str = self._resolve_prompt(None, self._prompt_file)
        self.chain = self._create_chain()

    # ------------------------ Chain construction ------------------------

    def _create_chain(self):
        """
        Create the agent chain with prompt, LLM, and tools.
        """
        # Bind tools to LLM (LangChain tool-calling integration)
        llm_with_tools = self.llm.bind_tools(tools=self.tools)

        # Human-readable tools list injected into the prompt if you reference {tools}
        tools_description = "\n".join(
            f"- {tool.name}: {getattr(tool, 'description', '').strip()}" for tool in self.tools
        )

        # Compose prompt
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self.prompt_template_str),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        # Inject common variables
        prompt = prompt.partial(
            user_name="Younes Mhadhbi",
            tools=tools_description,
            current_date_time=self._get_current_datetime(),
            agent_name=self.name,
            **self.system_context,
        )
        if self.structured_output:
            return prompt | llm_with_tools.with_structured_output(self.structured_output)
        
        return prompt | llm_with_tools

    def _get_current_datetime(self) -> str:
        # Keep simple; you can swap to pendulum/zoneinfo if you want true TZ strings
        return datetime.now().strftime("%Y-%m-%d %H:%M")

    # ------------------------ Invocation ------------------------

    def invoke(self, messages: List[BaseMessage], **kwargs) -> AIMessage:

        input_dict = {"messages": messages}
        input_dict.update(kwargs)
        return self.chain.invoke(input_dict)

    async def ainvoke(self, messages: List[BaseMessage]) -> AIMessage:

        return await self.chain.ainvoke({"messages": messages})

    # ------------------------ Tools helpers ------------------------

    def get_tool_by_name(self, tool_name: str) -> Optional[BaseTool]:
        return next((t for t in self.tools if t.name == tool_name), None)

    def has_tool(self, tool_name: str) -> bool:
        return self.get_tool_by_name(tool_name) is not None

    def get_tool_names(self) -> List[str]:
        return [t.name for t in self.tools]

    # ------------------------ Context ------------------------

    def update_system_context(self, **kwargs) -> None:
        self.system_context.update(kwargs)
        self.chain = self._create_chain()

    # ------------------------ Metadata ------------------------

    @abstractmethod
    def get_description(self) -> str:
        pass

    @abstractmethod
    def get_capabilities(self) -> List[str]:
        pass

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}', tools={len(self.tools)})"

    def get_info(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.get_description(),
            "capabilities": self.get_capabilities(),
            "tools": self.get_tool_names(),
            "prompt_source": "inline" if self._prompt_file is None else f"file:{self._prompt_file}",
            "temperature": self.temperature,
        }
