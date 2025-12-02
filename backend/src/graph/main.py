from dotenv import load_dotenv
from langgraph.prebuilt import ToolNode
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage, AIMessage
from pprint import pprint
import json
from langchain_core.messages import AIMessage, ToolMessage

from src.agents import (
    email_agent,
    calendar_agent,
    sheet_agent,
    supervisor_agent,
    memory_agent,
)

from src.schema.multi_agent_schema import MultiAgentState
# TODO
from src.tools.memory_tools import search_memory

load_dotenv()

email_tools =email_agent.tools
calendar_tools = calendar_agent.tools
sheet_tools = sheet_agent.tools
memory_tools = memory_agent.tools

print(f"✓ Initialized {supervisor_agent.name}")
print(f"✓ Initialized {email_agent.name} with {len(email_agent.tools)} tools")
print(f"✓ Initialized {calendar_agent.name} with {len(calendar_agent.tools)} tools")
print(f"✓ Initialized {sheet_agent.name} with {len(sheet_agent.tools)} tools")

# ============================================================
# Step 2: Define agent call functions
# ============================================================

def retrieve_memory(state: MultiAgentState):
    """Retrieve relevant memories based on the current user message."""
    current_user_message = state["messages"][-1].content

    retrieved_memory =  search_memory.invoke({"query": current_user_message, "limit": 1, "more": True})

    return {"retrieved_memory": retrieved_memory, "current_user_message": current_user_message}



def call_memory_agent(state: MultiAgentState):
    """Memory agent to manage long-term memory operations."""
    
    memory_history = state.get("memory_messages", [])
    
    
    retrieved_memory_context=state.get("retrieved_memory", "No relevant Context found.")
    all_messages = state.get("messages", [])
    print("supervisor messages:", all_messages)
    for msg in reversed(all_messages):
            if isinstance(msg, HumanMessage):
                next_msg = msg
                break
    supervisor_agent_message = state.get("supervisor_response", "")
    print("==========================================================")
    print("supervisor message to memory agent:", supervisor_agent_message)
    print("==========================================================")
    print("==========================================================")   
    print("user message to memory agent:", next_msg.content) 
    print("==========================================================")
    response = memory_agent.invoke(messages=memory_history,retrieved_memory_context= retrieved_memory_context, user_message=next_msg.content, supervisor_agent_message=supervisor_agent_message) 
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

def call_supervisor(state: MultiAgentState):
    """Supervisor analyzes messages and decides next step."""
    # Prefer cleaned history if present, otherwise fall back to raw messages
    messages = state.get("core_messages") 
    retrieved_memory_context = state.get("retrieved_memory", "No relevant Context found.")

    response = supervisor_agent.invoke(
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


def call_email_agent(state: MultiAgentState):
    email_history = state.get("email_messages", [])
    next_msg = state.get("message_to_next_agent")

    if next_msg is None:
        next_msg = state["messages"][-1]

    input_msgs = email_history + [next_msg]
    response = email_agent.invoke(input_msgs)

    return {
        "messages": state["messages"]+ [response],
        "core_messages": state["core_messages"] + [response],
        "email_messages": email_history + [next_msg, response],
        "email_agent_response": response.content,
        "message_to_next_agent": None,
        "calendar_agent_response": None,
        "sheet_agent_response": None,
    }

def call_calendar_agent(state: MultiAgentState):
    cal_history = state.get("calendar_messages", [])
    next_msg = state.get("message_to_next_agent")

    if next_msg is None:
        next_msg = state["messages"][-1]

    print("Calling calendar agent with:", next_msg)

    input_msgs = cal_history + [next_msg]
    response = calendar_agent.invoke(input_msgs)

    return {
        "messages": [response],
        "core_messages": state["core_messages"] + [response],
        "calendar_messages": cal_history + [next_msg, response],
        "calendar_agent_response": response.content,
        "message_to_next_agent": None,
        "email_agent_response": None,
        "sheet_agent_response": None,
    }

def call_sheet_agent(state: MultiAgentState):
    sheet_history = state.get("sheet_messages", [])
    next_msg = state.get("message_to_next_agent")

    if next_msg is None:
        next_msg = state["messages"][-1]

    print("Calling sheet agent with:", next_msg)

    input_msgs = sheet_history + [next_msg]
    response = sheet_agent.invoke(input_msgs)


    return {
        "messages": [response],
        "core_messages": state["core_messages"] + [response],
        "sheet_messages": sheet_history + [next_msg, response],
        "sheet_agent_response": response.content if response else "zzzz",
        "message_to_next_agent": None,
        "email_agent_response": None,
        "calendar_agent_response": None,
    }


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
    """
    Determine if sub-agent should call tools or return to supervisor.
    """
    msgs = state.get("messages") or []
    if not msgs:
        return "back_to_supervisor"
    
    last = msgs[-1]
    tcs = getattr(last, "tool_calls", None) or []
    
    if not tcs:
        return "back_to_supervisor"
    
    last_tc_name = _get_tc_name(tcs[-1])
    print(f"[router] last tool call: {last_tc_name}")
    
    # Route to appropriate tool node based on tool name
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

    return "end"

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
# Supervisor conditional edges
graph.add_conditional_edges(
    "supervisor",
    supervisor_agent_should_continue,
    {
        "to_email_agent": "email_agent",
        "to_calendar_agent": "calendar_agent",
        "to_sheet_agent": "sheet_agent",
        "end": "memory_agent"
    },
)

# Email agent conditional edges
graph.add_conditional_edges(
    "email_agent",
    sub_agent_should_continue,
    {
        "to_email_tool": "email_tool_node",
        "back_to_supervisor": "clear_state"
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
    
    # Check for command line arguments
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "info":
            # Show info for all agents
            for name in ["email_agent", "calendar_agent", "sheet_agent", "supervisor"]:
                inspect_agent(name)
        
        elif command == "reload":
            # Reload all prompts
            reload_all_prompts()
        
        elif command.startswith("inspect:"):
            # Inspect specific agent
            agent_name = command.split(":", 1)[1]
            inspect_agent(agent_name)
        
        else:
            print(f"Unknown command: {command}")
            print("Available commands: info, reload, inspect:<agent_name>")
    
    else:
        # Run the interactive agent
        run_multi_agent()
