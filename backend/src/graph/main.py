from dotenv import load_dotenv
from langgraph.prebuilt import ToolNode
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage, AIMessage
from pprint import pprint
import json
from langchain_core.messages import AIMessage, ToolMessage, AIMessageChunk
import asyncio # <--- Add this

from src.agents import (
    email_agent,
    calendar_agent,
    sheet_agent,
    supervisor_agent,
    memory_agent,
    run_browser_task,
    reviewer_agent,
)

from src.schema.multi_agent_schema import MultiAgentState
# TODO
from src.tools.memory_tools import search_memory


# import audi utils for transcription and TTS
from src.utils.audio_utils import transcribe_audio_file, tts_to_file, AUDIO_INPUT_PATH, AUDIO_OUTPUT_PATH
from langgraph.types import interrupt

load_dotenv()


email_tools =email_agent.tools
calendar_tools = calendar_agent.tools
sheet_tools = sheet_agent.tools
memory_tools = memory_agent.tools

print(f"✓ Initialized {supervisor_agent.name}")
print(f"✓ Initialized {email_agent.name} with {len(email_agent.tools)} tools")
print(f"✓ Initialized {calendar_agent.name} with {len(calendar_agent.tools)} tools")
print(f"✓ Initialized {sheet_agent.name} with {len(sheet_agent.tools)} tools")


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



# ============================================================
# Step 2: Define agent call functions
# ============================================================
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

    # Run the Browser Use library
    # Note: We pass the content string to the helper function we made
    result_text = await run_browser_task(next_msg.content)
    
    response_message = AIMessage(content=result_text, name="browser_agent")

    return {
        "messages": [response_message],
        "core_messages": state["core_messages"] + [response_message],
        "browser_messages": browser_history + [next_msg, response_message],
        "browser_agent_response": result_text,
        "message_to_next_agent": None,
    }

def retrieve_memory(state: MultiAgentState):
    """Retrieve relevant memories based on the current user message."""
    current_user_message = state["messages"][-1].content

    retrieved_memory =  search_memory.invoke({"query": current_user_message, "limit": 1, "more": True})

    return {"retrieved_memory": retrieved_memory, "current_user_message": current_user_message}



async def call_memory_agent(state: MultiAgentState):
    """Memory agent to manage long-term memory operations."""
    
    memory_history = state.get("memory_messages", [])
    
    
    retrieved_memory_context=state.get("retrieved_memory", "No relevant Context found.")
    all_messages = state.get("messages", [])
    print("supervisor messages:", all_messages)
    for msg in reversed(all_messages):
            if isinstance(msg, HumanMessage) and msg.name != "Supervisor":
                next_msg = msg
                break
    supervisor_agent_message = state.get("supervisor_response", "")
    print("==========================================================")
    print("supervisor message to memory agent:", supervisor_agent_message)
    print("==========================================================")
    print("==========================================================")   
    print("user message to memory agent:", next_msg.content) 
    print("==========================================================")
    response = await memory_agent.ainvoke(messages=memory_history,retrieved_memory_context= retrieved_memory_context, user_message=next_msg.content, supervisor_agent_message=supervisor_agent_message) 
    input_msgs = memory_history + [next_msg]

    print("=========================================================")
    print("Memory Agent Output:", response.content)
    print("=========================================================")

    # Append the input and the response to the agent's internal history
    
    return {
        "messages": [response], # Append agent response to main thread
        "memory_messages": input_msgs, # Update the internal memory loop history
        "memory_agent_response": response.content,
        "message_to_next_agent": None,
    } 

async def call_supervisor(state: MultiAgentState):
    """Supervisor analyzes messages and decides next step."""
    # Prefer cleaned history if present, otherwise fall back to raw messages
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

    print("=========================================================")
    print("Supervisor thoughts:", response.thoughts)
    print("=========================================================")
    print("=========================================================")
    print("Supervisor decision:", response.route)
    print("=========================================================")

    message_to_next_agent = None
    if response.route != "none":
        message_to_next_agent = HumanMessage(
            content=response.message_to_next_agent,
            name="Supervisor",
        )

    # Update both raw and core histories
    new_core_messages = state.get("core_messages") + [supervisor_ai_message]

    return {
        "route": response.route.lower(),
        "messages":  [supervisor_ai_message]+ [message_to_next_agent] if message_to_next_agent else [],
        "core_messages": new_core_messages,
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
        "messages": state["messages"]+ [response],
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
        "sheet_agent_response": response.content if response else "zzzz",
        "message_to_next_agent": None,
        "email_agent_response": None,
        "calendar_agent_response": None,
    }


SENSITIVE_EMAIL_TOOLS = {"send_email", "reply_to_email"}  


def _extract_last_tool_call_from_messages(state: MultiAgentState):
    msgs = state.get("messages") or []
    if not msgs:
        return None
    last = msgs[-1]
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

async def call_reviewer_agent(state: MultiAgentState):
    """
    HITL review step:
    - show draft
    - wait for human input
    - return approved -> continue to email tool node
      change_requested -> go back to email_agent with feedback
    """
    pending = state.get("pending_email_tool_call") or _extract_last_tool_call_from_messages(state)
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
    print(draft)
    
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
    
    out = {
        "review_decision": decision,
        "review_feedback": feedback,
        "messages": [], 
        "core_messages": state["core_messages"] + [
            AIMessage(content=f"[REVIEW] {decision}\n{feedback}", name="reviewer_agent")
        ],
    }

    if decision == "change_requested":
        # ---------------------------------------------------------
        # CRITICAL FIX: Satisfy OpenAI's tool_call requirement
        # ---------------------------------------------------------
        # We must insert a ToolMessage so the history looks like:
        # AI: call_tool(id=123) -> Tool: "User rejected..."(id=123)
        
        rejection_msg = ToolMessage(
            content=f"User rejected the email draft. Feedback: {feedback}",
            tool_call_id=tool_id,
            name=tool_name
        )

        # We append this message to the 'email_messages' state so the email_agent
        # sees that its previous tool call 'completed' (albeit with a rejection).
        # Note: Since MultiAgentState uses add_messages, passing a list appends it.
        out["email_messages"] = [rejection_msg]
        
        # Also add to global messages for consistency
        out["messages"] = [rejection_msg]

        # ---------------------------------------------------------
        
        out["message_to_next_agent"] = HumanMessage(
            content=f"User requested changes:\n{feedback}\n\nRewrite the email draft based on this feedback.",
            name="Supervisor",
        )

    return out



def clear_sub_agents_state(state: MultiAgentState):
    """
    Build a cleaned 'core_messages' history containing:
    - all HumanMessages (user)
    - all Supervisor / Supervisor_System_Message messages
    and reset sub-agent state.
    """
    agent_summary = None
    if state.get("email_agent_response"):
        agent_summary = state["email_agent_response"]
    if state.get("calendar_agent_response"):
        agent_summary = state["calendar_agent_response"]
    if state.get("sheet_agent_response"):
        agent_summary = state["sheet_agent_response"]
    if state.get("browser_agent_response"):
        agent_summary = state["browser_agent_response"]
    print("agent_summary:", agent_summary)
    core_messages: list = []

    # Build cleaned history from the raw t race
    for msg in state["messages"]:
        if isinstance(msg, HumanMessage):
            core_messages.append(msg)
        else:
            name = getattr(msg, "name", None)
            if name in ("Supervisor", "sub_agent_task_summary"):
                core_messages.append(msg)

    if agent_summary:
        summary_message = AIMessage(
            content=f"[SUB_AGENT_SUMMARY]\n{agent_summary}",            name="sub_agent_task_summary",
              )
        core_messages.append(summary_message)

    return {
        "core_messages": core_messages,
        "email_messages": [],
        "calendar_messages": [],
        "sheet_messages": [],
        "message_to_next_agent": None,
    }

# ============================================================
# Step 3: Create tool nodes (no changes needed)
# ============================================================

email_tool_node = ToolNode(tools=email_tools)
calendar_tool_node = ToolNode(tools=calendar_tools)
sheet_tool_node = ToolNode(tools=sheet_tools)
memory_tool_node = ToolNode(tools=memory_tools)
# Create tool name sets for routing
EMAIL_TOOL_NAMES = {t.name.lower() for t in email_tools}
CAL_TOOL_NAMES = {t.name.lower() for t in calendar_tools}
SHEET_TOOL_NAMES = {t.name.lower() for t in sheet_tools}
MEMORY_TOOL_NAMES = {t.name.lower() for t in memory_tools}
# ============================================================
# Step 4: Define routing functions (no changes needed)
# ============================================================

def _get_tc_name(tc) -> str:
    """Works for dicts or objects; returns lowercased name or empty string."""
    if isinstance(tc, dict):
        return (tc.get("name") or "").lower()
    return (getattr(tc, "name", "") or "").lower()


def sub_agent_should_continue(state: MultiAgentState) -> str:
    msgs = state.get("messages") or []
    if not msgs:
        return "back_to_supervisor"

    last = msgs[-1]
    tcs = getattr(last, "tool_calls", None) or []
    if not tcs:
        return "back_to_supervisor"

    last_tc_name = _get_tc_name(tcs[-1])
    print(f"[router] last tool call: {last_tc_name}")

    # ✅ intercept sensitive email actions
    if last_tc_name in SENSITIVE_EMAIL_TOOLS:
        return "to_reviewer_agent"

    if last_tc_name in EMAIL_TOOL_NAMES:
        return "to_email_tool"
    if last_tc_name in CAL_TOOL_NAMES:
        return "to_calendar_tool"
    if last_tc_name in SHEET_TOOL_NAMES:
        return "to_sheet_tool"

    return "back_to_supervisor"


def memory_agent_should_continue(state: MultiAgentState) -> str:
    """
    Determine if memory agent should call tools or return to supervisor.
    """
    msgs = state.get("messages") or []
    if not msgs:
        return "end"
    
    last = msgs[-1]
    tcs = getattr(last, "tool_calls", None) or []
    
    if not tcs:
        return "end"
    
    last_tc_name = _get_tc_name(tcs[-1])
    print(f"[router] last tool call: {last_tc_name}")
    
    if last_tc_name in MEMORY_TOOL_NAMES:
        return "to_memory_tool"
    
    return "end"

def supervisor_agent_should_continue(state: "MultiAgentState") -> str:

    route = state.get("route", "none")

    if route == "email_agent":
        return "to_email_agent"
    elif route == "calendar_agent":
        return "to_calendar_agent"
    elif route == "sheet_agent":
        return "to_sheet_agent"
    elif route == "browser_agent":
        return "to_browser_agent"

    return "end"

def reviewer_should_continue(state: MultiAgentState) -> str:
    decision = (state.get("review_decision") or "").lower()
    if decision == "approved":
        return "to_email_tool"          # ✅ go execute tool now
    if decision == "change_requested":
        return "back_to_email_agent"
    return "back_to_supervisor"


# ============================================================
# Step 5: Build the graph (no changes needed)
# ============================================================

graph = StateGraph(MultiAgentState)

# Set entry point
graph.set_entry_point("retrieve_memory")

# Add nodes
graph.add_node("retrieve_memory", retrieve_memory)
graph.add_node("supervisor", call_supervisor)
graph.add_node("email_agent", call_email_agent)
graph.add_node("calendar_agent", call_calendar_agent)
graph.add_node("sheet_agent", call_sheet_agent)
graph.add_node("email_tool_node", email_tool_node)
graph.add_node("calendar_tool_node", calendar_tool_node)
graph.add_node("sheet_tool_node", sheet_tool_node)
graph.add_node("memory_tool_node", memory_tool_node)
graph.add_node("clear_state", clear_sub_agents_state)
graph.add_node("memory_agent", call_memory_agent)
graph.add_node("browser_agent", call_browser_agent)

graph.add_node("reviewer_agent", call_reviewer_agent)


# Supervisor conditional edges
graph.add_conditional_edges(
    "supervisor",
    supervisor_agent_should_continue,
    {
        "to_email_agent": "email_agent",
        "to_calendar_agent": "calendar_agent",
        "to_sheet_agent": "sheet_agent",
        "to_browser_agent": "browser_agent",
        "end": "memory_agent"
    },
)

# Email agent conditional edges
graph.add_conditional_edges(
    "email_agent",
    sub_agent_should_continue,
    {
        "to_reviewer_agent": "reviewer_agent",
        "to_email_tool": "email_tool_node",
        "back_to_supervisor": "clear_state"
    },
)

graph.add_conditional_edges(
    "reviewer_agent",
    reviewer_should_continue,
    {
        "to_email_tool": "email_tool_node",
        "back_to_email_agent": "email_agent",
        "back_to_supervisor": "clear_state",
    },
)

# Calendar agent conditional edges
graph.add_conditional_edges(
    "calendar_agent",
    sub_agent_should_continue,
    {
        "to_calendar_tool": "calendar_tool_node",
        "back_to_supervisor": "clear_state"
    },
)

# Sheet agent conditional edges
graph.add_conditional_edges(
    "sheet_agent",
    sub_agent_should_continue,
    {
        "to_sheet_tool": "sheet_tool_node",
        "back_to_supervisor": "clear_state"
    },
)

# Tool nodes back to their respective agents

graph.add_edge("email_tool_node", "email_agent")
graph.add_edge("calendar_tool_node", "calendar_agent")
graph.add_edge("sheet_tool_node", "sheet_agent")
graph.add_edge("memory_tool_node", "memory_agent")
graph.add_edge("clear_state", "supervisor")
graph.add_edge("browser_agent", "clear_state")

graph.add_edge("retrieve_memory", "supervisor")
graph.add_conditional_edges("memory_agent",
    memory_agent_should_continue,
    {
        "to_memory_tool": "memory_tool_node",
        "end": END
    },)

# Compile the graph
checkpointer = MemorySaver()
app = graph.compile(checkpointer=checkpointer)


# ============================================================
# Step 6: Run function (no changes needed)
# ============================================================
from langgraph.types import Command

async def run_multi_agent_with_streaming():
    thread_id = "multi_agent_thread"
    config = {"configurable": {"thread_id": thread_id}}

    while True:
        user_input = input("\nYou: ").strip()
        if user_input.lower() == "exit":
            break
        if not user_input:
            continue

        # ✅ Start normal run
        inputs = {
            "messages": [HumanMessage(content=user_input)],
            "core_messages": [HumanMessage(content=user_input)],
        }

        await _run_stream(app, inputs, config)

        # ✅ If graph is waiting at an interrupt, RESUME instead of starting a new chat
        while True:
            snapshot = app.get_state(config)
            # If your reviewer node interrupted, snapshot.next will still include that node
            # (exact content depends on version, but snapshot.next being non-empty is a key signal)
            if not snapshot.next:
                break

            # Ask human for the interrupt response (approve / changes)
            human_reply = input("\n🧍 Review required. Type 'approved' or your changes:\n> ").strip()

            # 🔥 Resume the same run (same thread_id) with Command(resume=...)
            await _run_stream(app, Command(resume=human_reply), config)


async def _run_stream(app, inputs_or_command, config):
    last_node_name = None
    async for msg, metadata in app.astream(inputs_or_command, config, stream_mode="messages"):
        if isinstance(msg, AIMessageChunk) and msg.content:
            node_name = metadata.get("langgraph_node", "Agent")
            if node_name != last_node_name:
                print(f"\n\n🤖 {node_name.upper()}: ", end="", flush=True)
                last_node_name = node_name
            print(msg.content, end="", flush=True)
    print()
    
def run_multi_agent():
    """Run the multi-agent system interactively."""
    print("\n" + "="*70)
    print(" "*15 + "MULTI-AGENT SYSTEM RUNNING")
    print("="*70)
    
    # Display agent information
    print("\n📋 Active Agents:")
    for agent in [email_agent, calendar_agent, sheet_agent, supervisor_agent]:
        print(f"\n  • {agent.name.upper()}")
        print(f"    Description: {agent.get_description()}")
        print(f"    Tools: {len(agent.tools)}")
    
    print("\n" + "="*70)
    print("Type your request or 'exit' to quit.")
    print("="*70 + "\n")
    
    thread_id = "multi_agent_thread"  
    
    while True:
        user_input = input("You: ").strip()
        
        if user_input.lower() == 'exit':
            print("\n👋 Goodbye!\n")
            break
        
        if not user_input:
            continue
        
        inputs = {"messages": [HumanMessage(content=user_input)], "core_messages": [HumanMessage(content=user_input)]}
        
        print("\nAgent:")
        config = {"configurable": {"thread_id": thread_id}}  
        
        try:
            agent_response = app.invoke(input=inputs, config=config)

            print("==========================================================")
            snapshot = app.get_state(config=config)
            print("STATE VALUES:")
            pprint(snapshot.values)
            print("NEXT:", snapshot.next)
            print("==========================================================")

            # --- 1️⃣ Extract Supervisor response if available ---
            supervisor_response = None
            # Case A: it was returned explicitly by supervisor node
            if "supervisor_response" in agent_response:
                supervisor_response = agent_response["supervisor_response"]
            # Case B: still in state memory
            elif "supervisor_response" in snapshot.values:
                supervisor_response = snapshot.values["supervisor_response"]

            if supervisor_response:
                print("\n🧠 SUPERVISOR RESPONSE:\n" + "-" * 50)
                print(supervisor_response)
                print("-" * 50 + "\n")

            # --- 2️⃣ Then show final output message (user-facing summary) ---
            if "messages" in agent_response and agent_response["messages"]:
                final_message = agent_response["messages"][-1]
                print(f"\n💬 FINAL AGENT OUTPUT:\n{final_message.content}\n")
            else:
                print(f"\n💬 FINAL AGENT OUTPUT:\n{agent_response}\n")

        except Exception as e:
            print(f"\n❌ Error: {str(e)}\n")
            import traceback
            traceback.print_exc()

def run_multi_agent_from_audio():
    """
    One-shot test:
    - Read src/audio/audio.mp3
    - Transcribe it with ElevenLabs (Speech-to-Text)
    - Run multi-agent graph with that text as user input
    - Generate TTS answer to src/audio/response.mp3
    """
    print("\n" + "="*70)
    print("        MULTI-AGENT AUDIO TEST (ElevenLabs)")
    print("="*70)

    # 1️⃣ Transcribe input audio
    print(f"\n🎙  Transcribing audio from: {AUDIO_INPUT_PATH}")
    user_text = transcribe_audio_file(AUDIO_INPUT_PATH)
    print(f"\n📝 TRANSCRIBED TEXT:\n{user_text}\n")

    # 2️⃣ Run your graph with this as the user message
    thread_id = "multi_agent_audio_thread"

    inputs = {
        "messages": [HumanMessage(content=user_text)],
        "core_messages": [HumanMessage(content=user_text)],
    }
    config = {"configurable": {"thread_id": thread_id}}

    print("🤖 Running multi-agent graph...")
    agent_response = app.invoke(input=inputs, config=config)

    # For debugging, keep your snapshot logging if you want
    snapshot = app.get_state(config=config)
    print("==========================================================")
    print("STATE VALUES:")
    pprint(snapshot.values)
    print("NEXT:", snapshot.next)
    print("==========================================================")

    # 3️⃣ Extract supervisor + final output (like in run_multi_agent)
    supervisor_response = agent_response.get("supervisor_response") or snapshot.values.get("supervisor_response")
    if supervisor_response:
        print("\n🧠 SUPERVISOR RESPONSE:\n" + "-" * 50)
        print(supervisor_response)
        print("-" * 50 + "\n")

    if "messages" in agent_response and agent_response["messages"]:
        final_message = agent_response["messages"][-1]
        final_text = final_message.content
    else:
        final_text = str(agent_response)

    print(f"\n💬 FINAL AGENT OUTPUT (TEXT):\n{final_text}\n")

    # 4️⃣ Convert final answer to audio
    print("🔊 Generating TTS answer with ElevenLabs...")
    out_path = tts_to_file(supervisor_response)
    print(f"✅ Audio response saved to: {out_path}")


# ============================================================
# Optional: Utility functions for agent management
# ============================================================

def get_agent_by_name(name: str):
    """Get agent instance by name."""
    agents = {
        "email_agent": email_agent,
        "calendar_agent": calendar_agent,
        "sheet_agent": sheet_agent,
        "supervisor": supervisor_agent
    }
    return agents.get(name)


def reload_all_prompts():
    """Reload prompts for all agents (useful during development)."""
    print("\n🔄 Reloading all agent prompts...")
    for agent in [email_agent, calendar_agent, sheet_agent, supervisor_agent]:
        try:
            agent.reload_prompt()
            print(f"  ✓ Reloaded {agent.name}")
        except Exception as e:
            print(f"  ✗ Failed to reload {agent.name}: {e}")
    print("✓ All prompts reloaded!\n")


def inspect_agent(agent_name: str):
    """Inspect agent details."""
    agent = get_agent_by_name(agent_name)
    if not agent:
        print(f"Agent '{agent_name}' not found.")
        return
    
    info = agent.get_info()
    print(f"\n{'='*60}")
    print(f"Agent: {info['name']}")
    print(f"{'='*60}")
    print(f"Description: {info['description']}")
    print(f"\nCapabilities:")
    for cap in info['capabilities']:
        print(f"  - {cap}")
    print(f"\nTools ({len(info['tools'])}):")
    for tool in info['tools']:
        print(f"  - {tool}")
    print(f"\nPrompt File: {info['prompt_file']}")
    print(f"Temperature: {info['temperature']}")
    print(f"{'='*60}\n")


# ============================================================
# Main entry point
# ============================================================

if __name__ == "__main__":
    import sys

    # If you want to keep CLI commands:
    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "info":
            for name in ["email_agent", "calendar_agent", "sheet_agent", "supervisor"]:
                inspect_agent(name)

        elif command == "reload":
            reload_all_prompts()

        elif command.startswith("inspect:"):
            agent_name = command.split(":", 1)[1]
            inspect_agent(agent_name)

        elif command == "audio":
            # NEW: audio-based test
            run_multi_agent_from_audio()

        else:
            print(f"Unknown command: {command}")
            print("Available commands: info, reload, inspect:<agent_name>, audio")
    else:
        # Default: interactive text mode
        asyncio.run(run_multi_agent_with_streaming())
