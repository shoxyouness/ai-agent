from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langgraph.types import interrupt

from src.graph.state import MultiAgentState
from src.tools.memory_tools import search_memory

from src.agents import (
    email_agent, calendar_agent, sheet_agent, 
    supervisor_agent, memory_agent, reviewer_agent, 
    run_browser_task
)
from src.graph.consts import SENSITIVE_EMAIL_TOOLS
from src.graph.utils import get_last_human_message, extract_last_tool_call_from_messages




def retrieve_memory(state: MultiAgentState):
    """Retrieve relevant memories based on the current user message."""
    current_user_message = state["messages"][-1].content

    retrieved_memory =  search_memory.invoke({"query": current_user_message, "limit": 1, "more": True})

    return {"retrieved_memory": retrieved_memory, "current_user_message": current_user_message}


async def call_supervisor(state: MultiAgentState):
    """Supervisor analyzes messages and decides next step."""

    messages = state.get("core_messages") 
    retrieved_memory_context = state.get("retrieved_memory", "No relevant Context found.")

    response = await supervisor_agent.ainvoke(
        messages=messages,
        retrieved_memory=retrieved_memory_context,
    )

    supervisor_ai_message = AIMessage(
        content=response.response,
        name="Supervisor",
    )


    message_to_next_agent = None
    if response.route != "none":
        message_to_next_agent = HumanMessage(
            content=response.message_to_next_agent,
            name="Supervisor",
        )


    return {
        "route": response.route.lower(),
        "messages":  [supervisor_ai_message]+ [message_to_next_agent] if message_to_next_agent else [],
        "core_messages": state.get("core_messages") + [supervisor_ai_message],
        "supervisor_response": response.response,
        "message_to_next_agent": message_to_next_agent,
    }


async def call_email_agent(state: MultiAgentState):
    email_history = state.get("email_messages", [])
    next_msg = state.get("message_to_next_agent")

    if next_msg is None:
        next_msg = state["messages"][-1]

    input_msgs = email_history + [next_msg]
    response = await email_agent.ainvoke(input_msgs)

    return {
        "messages": [response],
        "core_messages": state["core_messages"] + [response],
        "email_messages": email_history + [next_msg, response],
        "email_agent_response": response.content,
        "message_to_next_agent": None,
        "calendar_agent_response": None,
        "sheet_agent_response": None,
    }

async def call_calendar_agent(state: MultiAgentState):
    cal_history = state.get("calendar_messages", [])
    next_msg = state.get("message_to_next_agent")

    if next_msg is None:
        next_msg = state["messages"][-1]

    print("Calling calendar agent with:", next_msg)

    input_msgs = cal_history + [next_msg]
    response = await calendar_agent.ainvoke(input_msgs)

    return {
        "messages": [response],
        "core_messages": state["core_messages"] + [response],
        "calendar_messages": cal_history + [next_msg, response],
        "calendar_agent_response": response.content,
        "message_to_next_agent": None,
        "email_agent_response": None,
        "sheet_agent_response": None,
    }

async def call_sheet_agent(state: MultiAgentState):
    sheet_history = state.get("sheet_messages", [])
    next_msg = state.get("message_to_next_agent")

    if next_msg is None:
        next_msg = state["messages"][-1]

    print("Calling sheet agent with:", next_msg)

    input_msgs = sheet_history + [next_msg]
    response = await sheet_agent.ainvoke(input_msgs)


    return {
        "messages": [response],
        "core_messages": state["core_messages"] + [response],
        "sheet_messages": sheet_history + [next_msg, response],
        "sheet_agent_response": response.content,
        "message_to_next_agent": None,
        "email_agent_response": None,
        "calendar_agent_response": None,
    }

async def call_reviewer_agent(state: MultiAgentState):
    """
    Human-in-the-loop review node.":
    - show draft
    - wait for human input
    - return approved -> continue to email tool node
      change_requested -> go back to email_agent with feedback
    """
    pending = state.get("pending_email_tool_call") or extract_last_tool_call_from_messages(state.get("messages", []))
    if not pending or (pending.get("name") or "").lower() not in SENSITIVE_EMAIL_TOOLS:
        # nothing to review
        return {"review_decision": None, "review_feedback": None, "pending_email_tool_call": None}

    tool_name = (pending["name"] or "").lower()
    args = pending.get("args", {})
    tool_id = pending.get("id")

    # Build a readable draft for the human
    to = args.get("to") or args.get("recipient") or ""
    subject = args.get("subject") or ""
    body = args.get("body") or args.get("message") or ""

    draft = (
        "📧 DRAFT EMAIL FOR REVIEW\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Tool: {tool_name}\n"
        f"To: {to}\n"
        f"Subject: {subject}\n\n"
        f"{body}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Reply with:\n"
        "- 'approved' to send\n"
        "- or write your requested changes\n"
    )
    # print(draft)
    
    # 1) Show draft + pause graph (human input)
    human_text = interrupt(draft)

    # 2) Let your reviewer agent classify the human input
    review = await reviewer_agent.ainvoke(
        [
            AIMessage(content=draft, name="reviewer_agent"),
            HumanMessage(content=str(human_text)),
        ]
    )
    
    decision = review.decision
    feedback = review.feedback
    
    updates = {
        "review_decision": decision,
        "review_feedback": feedback,
        "messages": [], 
        "core_messages": state["core_messages"] + [
            AIMessage(content=f"[REVIEW] {decision}\n{feedback}", name="reviewer_agent")
        ],
    }

    if decision == "change_requested":

        
        rejection = ToolMessage(
            content=f"User rejected the email draft. Feedback: {feedback}",
            tool_call_id=tool_id,
            name=tool_name
        )
        updates["email_messages"] = [rejection]
        
        updates["messages"] = [rejection]
        
        updates["message_to_next_agent"] = HumanMessage(
            content=f"User requested changes:\n{feedback}\n\nRewrite the email draft based on this feedback.",
            name="Supervisor",
        )

    return updates



async def call_memory_agent(state: MultiAgentState):
    """Memory agent to manage long-term memory operations."""
    
    memory_history = state.get("memory_messages", [])
    supervisor_agent_message = state.get("supervisor_response", "")
    retrieved_memory_context=state.get("retrieved_memory", "No relevant Context found.")
    user_msg = get_last_human_message(state.get("messages", []))


    response = await memory_agent.ainvoke(messages=memory_history, retrieved_memory_context= retrieved_memory_context, user_message=user_msg.content, supervisor_agent_message=supervisor_agent_message) 
    input_msgs = memory_history + [user_msg]

    
    return {
        "messages": [response], 
        "memory_messages": input_msgs, 
        "memory_agent_response": response.content,
        "message_to_next_agent": None,
    } 


async def call_browser_agent(state: MultiAgentState):
    """
    Node to execute the browser-use agent.
    """
    browser_history = state.get("browser_messages", [])
    
    # Get the task from the Supervisor
    next_msg = state.get("message_to_next_agent")
    if next_msg is None:
        next_msg = state["messages"][-1] # Fallback to user message

    print(f"🌍 Browser Agent working on: {next_msg.content}")

    result_text = await run_browser_task(next_msg.content)
    
    response_message = AIMessage(content=result_text, name="browser_agent")

    return {
        "messages": [response_message],
        "core_messages": state["core_messages"] + [response_message],
        "browser_messages": browser_history + [next_msg, response_message],
        "browser_agent_response": result_text,
        "message_to_next_agent": None,
    }

def clear_sub_agents_state(state: MultiAgentState):
    """Resets sub-agent specific history and cleans core history."""
    core = [m for m in state["messages"] 
            if isinstance(m, HumanMessage) or m.name in ("Supervisor", "sub_agent_task_summary")]
    
    # Collect summaries
    summaries = []
    for key in ["email_agent_response", "calendar_agent_response", "sheet_agent_response", "browser_agent_response"]:
        if state.get(key):
            summaries.append(state[key])

    if summaries:
        core.append(AIMessage(content=f"[SUMMARY] {' '.join(summaries)}", name="sub_agent_task_summary"))

    return {
        "core_messages": core,
        "email_messages": [],
        "calendar_messages": [],
        "sheet_messages": [],
        "message_to_next_agent": None,
    }


# def clear_sub_agents_state(state: MultiAgentState):
#     """
#     Build a cleaned 'core_messages' history containing:
#     - all HumanMessages (user)
#     - all Supervisor / Supervisor_System_Message messages
#     and reset sub-agent state.
#     """
#     agent_summary = None
#     if state.get("email_agent_response"):
#         agent_summary = state["email_agent_response"]
#     if state.get("calendar_agent_response"):
#         agent_summary = state["calendar_agent_response"]
#     if state.get("sheet_agent_response"):
#         agent_summary = state["sheet_agent_response"]
#     if state.get("browser_agent_response"):
#         agent_summary = state["browser_agent_response"]
#     print("agent_summary:", agent_summary)
#     core_messages: list = []

#     # Build cleaned history from the raw t race
#     for msg in state["messages"]:
#         if isinstance(msg, HumanMessage):
#             core_messages.append(msg)
#         else:
#             name = getattr(msg, "name", None)
#             if name in ("Supervisor", "sub_agent_task_summary"):
#                 core_messages.append(msg)

#     if agent_summary:
#         summary_message = AIMessage(
#             content=f"[SUB_AGENT_SUMMARY]\n{agent_summary}",            name="sub_agent_task_summary",
#               )
#         core_messages.append(summary_message)

#     return {
#         "core_messages": core_messages,
#         "email_messages": [],
#         "calendar_messages": [],
#         "sheet_messages": [],
#         "message_to_next_agent": None,
#     }





