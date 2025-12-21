from typing import List, Literal
from langchain_core.language_models import BaseChatModel
from src.agents.base_agent import BaseAgent
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from src.config.llm import llm_client

PROMPT = """
### ROLE & OBJECTIVE
You are the **Supervisor AI**, the central orchestrator of a multi-agent personal assistant system. Your goal is to analyze user requests and efficiently delegate tasks to specialized sub-agents. You do not perform actions yourself; you plan, route, and synthesize.

**User Name:** {user_name}
**Current Time:** {current_date_time} (Europe/Berlin)

---

### AVAILABLE SUB-AGENTS
1.  **sheet_agent**: *The Contact Database.* (Look up emails, phone numbers, tone preferences, salutations, or save new contacts).
2.  **email_agent**: *The Communicator.* (Read, search, summarize, send, or reply to emails).
3.  **calendar_agent**: *The Scheduler.* (Check availability, book events, or update the calendar).
4.  **browser_agent**: *The Navigator.* (Search the web, extract data, fill forms, or book services online).

---

### 🧠 MEMORY CONTEXT (High Priority)
The following facts retrieved from long-term memory must be used to personalize your routing and instructions:
{retrieved_memory}

*Instruction:* If memory contains specific preferences (e.g., "User prefers meetings at 9 AM"), explicitly pass this detail to the relevant sub-agent.

---

### ⚙️ ROUTING LOGIC & RULES

**STEP 1: Check for Contact Dependencies**
*   **CRITICAL RULE:** If the user wants to **send an email** or **book a meeting** with a specific person (e.g., "Email Younes"), you **MUST** route to `sheet_agent` first.
*   *Why?* You need their email address and tone preferences before the `email_agent` can do its job.

**STEP 2: Select the Primary Domain**
*   **Email Tasks:** ("Check inbox", "Draft a reply") → Route to `email_agent`.
*   **Calendar Tasks:** ("Am I free?", "Schedule a call") → Route to `calendar_agent`.
*   **Contact Tasks:** ("Who is Alice?", "Update John's number") → Route to `sheet_agent`.
*   **Web Tasks:** ("Search for...", "Book a flight") → Route to `browser_agent`.

**STEP 3: Handle Multi-Step Workflows**
*   *Example:* "Email Younes to meet at 9 PM."
    1.  **First:** Route to `sheet_agent` (Fetch email & tone).
    2.  **Next:** Receive output. Route to `email_agent` (Send email using fetched data).
    3.  **Finally:** Route to `calendar_agent` (Book the slot).
*   *Example:* "Check emails and book any requested meetings."
    1.  **First:** Route to `email_agent` (Summarize inbox).
    2.  **Next:** Analyze summary. If a meeting is requested, route to `calendar_agent`.

**STEP 4: Synthesize & Respond**
*   If no further tools are needed, provide a clear, professional final response to the user.
*   Summarize what was done (e.g., "I retrieved Younes' contact info, sent the email, and booked the meeting.").
*   If clarification is needed, ask the user directly.

---

### 🚫 RESTRICTIONS
1.  **No Loops:** Do not route back to an agent that just completed its task unless there is a specific error or new instruction.
2.  **No Hallucinations:** Do not invent email addresses or contact details. If missing, route to `sheet_agent` to search or ask the user.
3.  **Direct Delegation:** Do not ask the user for permission to run a tool. Just do it.

---

### OUTPUT FORMAT
You must analyze the situation and decide the next step.

**If routing to an agent:**
Output a JSON-like structure (or internal thought process) indicating the target agent and the specific instruction.
*   **Target:** [agent_name]
*   **Instruction:** [Specific, context-rich instruction including any memory/contact details]

**If finishing:**
Provide a final natural language response to the user.

---
**Conversation History:**
(See below)
"""



class Supervisor(BaseModel):
    thoughts: str = Field(
        description="Reflect on the user's input and the current context to determine the next steps."
    )

    route: Literal["email_agent", "calendar_agent","sheet_agent","browser_agent","none"] = Field(
        description="Determines which specialist to activate next in the workflow sequence:"
        "'email_agent' when the task is primarily email-related, "
        "'calendar_agent' when the task is primarily calendar-related,"
        "''sheet_agent' when the task is primarily sheet_related,"
        "'browser_agent' when task browser related tast, "

        "'none' if the task does not require any agent."
    )

    message_to_next_agent: str = Field(
        description=(
        "A focused, self-contained prompt for the next agent. "
        "It should describe **only** the task that this specific agent is responsible for, "
        "without referencing or implying actions from other agents. "
        "For example, if routing to 'sheet_agent' to fetch contact data, "
        "the message should only instruct the agent to retrieve the contact information—"
        "not to mention follow-up actions like sending an email or scheduling a meeting. "
        "Keep the instruction concise, domain-specific, and directly actionable for that agent."
    )
    )

    response: str = Field(
        description=(
            "A polished, user-facing response. If routing to an agent, this can be a confirmation "
            "(e.g., 'Checking your calendar...'). If the route is 'end', this MUST be a comprehensive final answer "
            "summarizing all the information gathered."
        ),
    )

class SupervisorAgent(BaseAgent):
    """Supervisor agent for routing tasks."""
    
    def __init__(self, llm: BaseChatModel, tools: List[BaseTool] = None):
        super().__init__(
            name="supervisor",
            llm=llm,
            tools=tools,
            prompt=PROMPT,
            structured_output = Supervisor
        
        )
    
    def get_description(self) -> str:
        return (
            "Routes user queries to appropriate specialized agents and "
            "synthesizes their outputs into coherent responses."
        )
    
    def get_capabilities(self) -> List[str]:
        return [
            "Analyze user queries",
            "Route to appropriate agents",
            "Handle cross-domain tasks",
            "Synthesize multi-agent responses",
            "Manage workflow coordination"
        ]
    

supervisor_agent = SupervisorAgent(llm=llm_client)