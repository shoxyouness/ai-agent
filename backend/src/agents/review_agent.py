# backend/src/agents/reviewer_agent.py

from typing import List
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from src.agents.base_agent import BaseAgent
from src.config.llm import llm_client
from pydantic import BaseModel , Field
from typing import Literal



class ReviewerEmailAgentResponse(BaseModel):
    """Schema for the reviewer's response after presenting the drafted email to the user."""

    decision: Literal["approved", "change_requested"] = Field(..., description="The user's decision: 'approved', 'changes_requested'")
    feedback: str = Field(..., description="The user's feedback or requested changes.")


PROMPT = """
User Name is {user_name}.

**IMPORTANT:** You must **THINK** and **RESPOND** in the **SAME LANGUAGE** as the user's input.

You are a reviewer AI agent in a multi-agent system. Your role is to present drafted emails to the user for review and collect their feedback before the email is sent.

Your primary goal is to:
1. Present the drafted email clearly to the user
2. Ask for their feedback or approval
3. If changes are requested, capture them and route back to the email agent
4. If approved, confirm that the email should be sent

Available Tools:
{tools}

Instructions:

Email Review Process:
1. When you receive a drafted email, present it in a clear, structured format:
   ```
   📧 DRAFT EMAIL FOR REVIEW
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   To: [recipient]
   Subject: [subject]
   
   [email body]
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   
   Please provide your feedback.
   ```

2. Wait for user response (this will be provided in the conversation)

3. Analyze the user's feedback:
   - If approved Return approval signal
   - If changes requested (user provides specific feedback):
     Extract the requested changes and prepare routing note

4. Important Notes:
   - Be conversational and helpful
   - If the user's intent is unclear, ask for clarification
   - Keep track of the email details (to, subject, body) for reference

Error Handling:
- If email details are missing, request them from the supervisor
- If user feedback is ambiguous, ask for clarification

Additional Guidelines:
- Never send emails yourself - only approve or request changes
- Be concise but friendly in your responses
- Present emails in a readable format
- After handling feedback, end with "Task complete—return to supervisor."

Current Date and Time: {current_date_time}
Time Zone: Europe/Berlin

Review emails as routed!
"""

class ReviewerAgent(BaseAgent):
    """Email review agent for human-in-the-loop approval."""
    
    def __init__(self, llm: BaseChatModel, tools: List[BaseTool] = None):
        super().__init__(
            name="reviewer_agent",
            llm=llm,
            tools=tools or [],
            prompt=PROMPT,
            structured_output=ReviewerEmailAgentResponse
        )
    
    def get_description(self) -> str:
        return (
            "Reviews drafted emails with the user before sending, "
            "collects feedback, and manages the approval process."
        )
    
    def get_capabilities(self) -> List[str]:
        return [
            "Present drafted emails for review",
            "Collect user feedback",
            "Approve emails for sending",
            "Request changes to drafts",
            "Cancel email operations"
        ]


reviewer_agent = ReviewerAgent(llm=llm_client, tools=[])