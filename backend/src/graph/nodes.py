# src/graph/nodes.py
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langgraph.types import interrupt

from src.graph.state import MultiAgentState
from src.tools.memory_tools import search_memory

from src.agents import (
    email_agent, calendar_agent, sheet_agent, 
    supervisor_agent, memory_agent, reviewer_agent, 
    run_browser_task, deep_research_agent
)
from src.graph.consts import SENSITIVE_EMAIL_TOOLS
from src.graph.utils import get_last_human_message, extract_last_tool_call


from src.graph.utils import extract_all_tool_calls # Import the new helper

# --- 1. Helper for Parallel Tool Handling (Fixes 400 Error) ---
def _get_agent_inputs(state: MultiAgentState, history_key: str):
    """
    Constructs inputs for an agent.
    Fixes duplicate ToolMessage errors by checking current history state.
    """
    history = state.get(history_key, [])
    all_messages = state.get("messages", [])

    # 🛑 CRITICAL FIX: 
    # If the agent's internal history ALREADY ends with a ToolMessage (e.g. injected by Reviewer),
    # we must NOT append anything else. The Agent has what it needs to continue.
    if history and isinstance(history[-1], ToolMessage):
        return history

    # 1. Check if the global stream ended with ToolMessages (Parallel Execution)
    recent_tool_messages = []
    for msg in reversed(all_messages):
        if isinstance(msg, ToolMessage):
            # Check if this specific tool message is already in history to avoid duplication
            if history and history[-1] == msg:
                break
            recent_tool_messages.insert(0, msg)
        else:
            break
            
    # 2. If we found NEW tool results, append them
    if recent_tool_messages:
        return history + recent_tool_messages
    
    # 3. Otherwise, it's a standard message (User or Supervisor)
    next_msg = state.get("message_to_next_agent")
    if not next_msg:
        next_msg = all_messages[-1] # Fallback to last global message
        
    return history + [next_msg]

# def _get_agent_inputs(state: MultiAgentState, history_key: str):
#     """
#     Constructs inputs for an agent, ensuring valid Tool Call -> Tool Message sequences.
#     """
#     history = state.get(history_key, [])
#     all_messages = state.get("messages", [])

#     # 1. Check if history is currently "hanging" (Last message was a Tool Call with no Output)
#     if history and isinstance(history[-1], AIMessage) and history[-1].tool_calls:
#         # We MUST find the matching ToolMessage in the global stream
#         hanging_ids = {tc['id'] for tc in history[-1].tool_calls}
        
#         found_tool_outputs = []
#         for msg in reversed(all_messages):
#             if isinstance(msg, ToolMessage) and msg.tool_call_id in hanging_ids:
#                 found_tool_outputs.insert(0, msg)
        
#         # If we found outputs that aren't in history yet, append them
#         if found_tool_outputs:
#             return history + found_tool_outputs
    
#     # 2. Standard Parallel Tool Handling (from global stream)
#     # If the global stream has recent tool messages that aren't in history, grab them
#     recent_tool_messages = []
#     for msg in reversed(all_messages):
#         if isinstance(msg, ToolMessage):
#             recent_tool_messages.insert(0, msg)
#         else:
#             break
            
#     if recent_tool_messages:
#         # Check if they are already in history to avoid duplicates
#         if history and history[-1] == recent_tool_messages[-1]:
#             return history
#         return history + recent_tool_messages
    
#     # 3. Standard Case: Append Supervisor Instruction
#     next_msg = state.get("message_to_next_agent")
#     if not next_msg:
#         next_msg = all_messages[-1] 
        
#     return history + [next_msg]

# --- 2. Generic Agent Wrapper ---
async def call_agent_generic(state: MultiAgentState, agent, history_key: str, response_key: str):
    """Generic handler for Email, Calendar, and Sheet agents."""
    
    # Get inputs using the parallel-safe helper
    input_msgs = _get_agent_inputs(state, history_key)

    # Invoke Agent
    response = await agent.ainvoke(input_msgs)

    # Calculate what strictly new messages to add to the specific history
    # (We essentially append the new input + the agent response)
    # We slice input_msgs to avoid duplicating the entire history history
    new_inputs = input_msgs[len(state.get(history_key, [])):]

    return {
        "messages": [response], # Stream to global
        "core_messages": state["core_messages"] + [response],
        history_key: state.get(history_key, []) + new_inputs + [response],
        response_key: response.content,
        "message_to_next_agent": None,
    }


# --- Node Functions ---

def retrieve_memory(state: MultiAgentState):
    """Retrieve relevant memories based on the current user message."""
    last_msg = state["messages"][-1]
    # Handle edge case where message might not be text
    content = last_msg.content if hasattr(last_msg, "content") else ""

    retrieved_memory = search_memory.invoke({"query": content, "limit": 1, "more": True})
    return {"retrieved_memory": retrieved_memory, "current_user_message": content}


async def call_supervisor(state: MultiAgentState):
    """Supervisor analyzes messages and decides next step."""
    messages = state.get("core_messages") 
    print(f"DEBUG: Supervisor seeing {len(messages)} messages.")

    retrieved_memory_context = state.get("retrieved_memory", "No relevant Context found.")

    response = await supervisor_agent.ainvoke(
        messages=messages,
        retrieved_memory=retrieved_memory_context,
    )

    supervisor_ai_message = AIMessage(content=response.response, name="Supervisor")
    message_to_next_agent = None
    
    if response.route != "none":
        message_to_next_agent = HumanMessage(
            content=response.message_to_next_agent,
            name="Supervisor",
        )

    return {
        "route": response.route.lower(),
        "messages": [supervisor_ai_message] + ([message_to_next_agent] if message_to_next_agent else []),
        "core_messages": state.get("core_messages") + [supervisor_ai_message],
        "supervisor_response": response.response,
        "message_to_next_agent": message_to_next_agent,
    }


# --- Specific Agent Nodes (Refactored) ---

async def call_email_agent(state: MultiAgentState):
    return await call_agent_generic(state, email_agent, "email_messages", "email_agent_response")

async def call_calendar_agent(state: MultiAgentState):
    return await call_agent_generic(state, calendar_agent, "calendar_messages", "calendar_agent_response")

async def call_sheet_agent(state: MultiAgentState):
    return await call_agent_generic(state, sheet_agent, "sheet_messages", "sheet_agent_response")


async def call_reviewer_agent(state: MultiAgentState):
    """Human-in-the-loop review node with Auto-Approval logic."""
    
    # 1. CHECK AUTO-APPROVAL FLAG
    # If the user previously approved a batch, skip the UI and auto-approve.
    if state.get("bulk_approval_active") is True:
        return {"review_decision": "approved"}

    pending = state.get("pending_email_tool_call") or extract_last_tool_call(state.get("messages", []))
    
    if not pending or (pending.get("name") or "").lower() not in SENSITIVE_EMAIL_TOOLS:
        return {"review_decision": None}

    tool_name = (pending["name"] or "").lower()
    args = pending.get("args", {})
    tool_id = pending.get("id")

    # Build Draft
    draft = (
        "# 📧 DRAFT EMAIL FOR REVIEW\n"
        f"**To:** `{args.get('to', '') or args.get('recipient', '')}`\n"
        f"**Subject:** `{args.get('subject', '')}`\n"
        "──────────────────────────────\n\n"
        f"{args.get('body', '') or args.get('message', '')}\n"
        "\n──────────────────────────────\n"
        "**Tip:** Type 'approved' to send this and auto-approve subsequent emails in this task."
    )
    
    # 2. Interrupt for Human
    human_text = interrupt(draft)

    # 3. Reviewer Agent Logic
    review = await reviewer_agent.ainvoke([
        AIMessage(content=draft, name="reviewer_agent"),
        HumanMessage(content=str(human_text)),
    ])
    
    updates = {
        "review_decision": review.decision,
        "review_feedback": review.feedback,
        "core_messages": state["core_messages"] + [
            AIMessage(content=f"[REVIEW] {review.decision}\n{review.feedback}", name="reviewer_agent")
        ],
    }

    # 4. SET AUTO-APPROVAL FLAG
    # If the user approved this email, we assume they trust the agent for the rest of THIS specific task sequence.
    if review.decision == "approved":
        updates["bulk_approval_active"] = True

    if review.decision == "change_requested":
        rejection_msg = ToolMessage(
            content=f"User rejected draft. Feedback: {review.feedback}. Please Rewrite.",
            tool_call_id=tool_id,
            name=tool_name
        )
        updates["email_messages"] = state.get("email_messages", []) + [rejection_msg]
        updates["messages"] = [rejection_msg]
        updates["message_to_next_agent"] = None 
        # Crucial: If they reject one, turn OFF auto-approval just in case
        updates["bulk_approval_active"] = False

    return updates



async def call_memory_agent(state: MultiAgentState):
    """
    Memory agent node.
    FIXED: Now properly includes ToolMessages in the history so the agent knows it finished.
    """
    memory_history = state.get("memory_messages", [])
    supervisor_agent_message = state.get("supervisor_response", "")
    retrieved_memory_context = state.get("retrieved_memory", "No relevant Context found.")
    user_msg = get_last_human_message(state.get("messages", []))

    # --- FIX START: DETECT TOOL OUTPUTS ---
    # Check if the global stream has a ToolMessage that isn't in our local history yet
    all_messages = state.get("messages", [])
    recent_tool_messages = []
    
    if all_messages and isinstance(all_messages[-1], ToolMessage):
        # We found a tool output! This means we are looping back.
        # Grab strictly the ToolMessages at the end of the chain
        for msg in reversed(all_messages):
            if isinstance(msg, ToolMessage):
                recent_tool_messages.insert(0, msg)
            else:
                break
    
    # Construct the input history
    if recent_tool_messages:
        # If we just ran a tool, append the result to history
        input_msgs = memory_history + recent_tool_messages
    else:
        # First run: Standard input
        input_msgs = memory_history + [user_msg]
    # --- FIX END ---

    # Call the Agent
    response = await memory_agent.ainvoke(
        messages=input_msgs, 
        retrieved_memory_context=retrieved_memory_context, 
        user_message=user_msg.content, 
        supervisor_agent_message=supervisor_agent_message
    ) 
    
    # Update State
    # We append the new inputs (if any) + the agent's new response
    new_history = input_msgs + [response]
    
    return {
        "messages": [response], 
        "memory_messages": new_history, 
        "memory_agent_response": response.content,
        "message_to_next_agent": None,
    }

async def call_browser_agent(state: MultiAgentState):
    browser_history = state.get("browser_messages", [])
    next_msg = state.get("message_to_next_agent")
    if next_msg is None:
        next_msg = state["messages"][-1]

    print(f"🌍 Browser Agent working on: {next_msg.content}")

    result_text = await run_browser_task(next_msg.content)
    response = AIMessage(content=result_text, name="browser_agent")

    return {
        "messages": [response],
        "core_messages": state["core_messages"] + [response],
        "browser_messages": browser_history + [next_msg, response],
        "browser_agent_response": result_text,
        "message_to_next_agent": None,
    }


# --- 3. Fix for the Infinite Loop (Supervisor Amnesia) ---
def clear_sub_agents_state(state: MultiAgentState):
    """
    Resets sub-agent history but creates a detailed summary for the Supervisor.
    Crucially, it marks tasks as COMPLETED so the Supervisor doesn't loop.
    """
    core = [m for m in state["messages"] 
            if isinstance(m, HumanMessage) or m.name in ("Supervisor", "sub_agent_task_summary")]
    
    summary_parts = []

    # Helper to extract the last Tool Result
    def get_tool_results_text(history):
        results = [m.content for m in reversed(history) if isinstance(m, ToolMessage)]
        if results:
            return " | ".join(results)
        return None

    # Check Email
    if state.get("email_agent_response"):
        agent_res = state["email_agent_response"]
        tool_res = get_tool_results_text(state.get("email_messages", []))
        summary_parts.append(f"Email Agent Status: {agent_res}")
        if tool_res: 
            summary_parts.append(f"✅ ACTION COMPLETED (Tool Output): {tool_res}")

    # Check Calendar
    if state.get("calendar_agent_response"):
        agent_res = state["calendar_agent_response"]
        tool_res = get_tool_results_text(state.get("calendar_messages", []))
        summary_parts.append(f"Calendar Agent Status: {agent_res}")
        if tool_res: 
            summary_parts.append(f"✅ ACTION COMPLETED (Tool Output): {tool_res}")

    # Check Sheet
    if state.get("sheet_agent_response"):
        summary_parts.append(f"Sheet Agent: {state['sheet_agent_response']}")
    
    # Check Browser
    if state.get("browser_agent_response"):
        summary_parts.append(f"Browser Agent: {state['browser_agent_response']}")

    if state.get("research_agent_response"):
        summary_parts.append(f"Deep Research Agent Findings: {state['research_agent_response']}")

    # Create the detailed summary message
    if summary_parts:
        content = "\n".join(summary_parts)
        
        # AGGRESSIVE SYSTEM INSTRUCTION TO STOP LOOPS
        final_summary = (
            "### SUBSYSTEM REPORT ###\n"
            f"{content}\n"
            "------------------------\n"
            "⚠️ SYSTEM INSTRUCTION TO SUPERVISOR:\n"
            "1. Analyze the 'ACTION COMPLETED' lines above.\n"
            "2. If an action (like canceling meetings or sending email) is marked ✅, IT IS DONE.\n"
            "3. DO NOT route back to the agent to do it again.\n"
            "4. Proceed to the next step or finish."
        )
        
        summary_message = AIMessage(
            content=final_summary, 
            name="sub_agent_task_summary"
        )
        core.append(summary_message)

    return {
        "core_messages": core,
        "email_messages": [],
        "calendar_messages": [],
        "sheet_messages": [],
        "message_to_next_agent": None,
        "bulk_approval_active": False 
    }


async def call_deep_research_agent(state: MultiAgentState):
    """
    Handler for the Deep Research Agent.
    Uses the generic agent wrapper to handle the ReAct loop (Agent -> Tool -> Agent).
    """
    print("🔎 Deep Research Agent is working...")
    return await call_agent_generic(
        state, 
        deep_research_agent, 
        "research_messages", 
        "research_agent_response"
    )