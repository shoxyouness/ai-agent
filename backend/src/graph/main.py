# backend/src/graph/multi_agent.py
"""
Multi-agent graph refactored to use BaseAgent.
"""

from dotenv import load_dotenv
from langgraph.prebuilt import ToolNode
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage, AIMessage
from pprint import pprint
import json
from langchain_core.messages import AIMessage, ToolMessage

# Import BaseAgent and concrete agent classes
from src.agents import (
    EmailAgent,
    CalendarAgent,
    SheetAgent,
    SupervisorAgent,
)

# Import tools
from src.tools.email_tools import get_unread_emails, send_email, reply_to_email, mark_email_as_read
from src.tools.calender_tools import get_calendar_events, create_calendar_event, update_calendar_event
from src.tools.sheet_tools import GOOGLE_SHEETS_CONTACT_TOOLS
from src.tools.memory_tools import MEMORY_TOOLS
from src.schema.multi_agent_schema import MultiAgentState
from src.config.llm import llm_client

load_dotenv()

# ============================================================
# Step 1: Initialize agents using BaseAgent
# ============================================================

# Define tool lists
email_tools = [get_unread_emails, send_email, reply_to_email, mark_email_as_read]
calendar_tools = [get_calendar_events, create_calendar_event, update_calendar_event]
sheet_tools = GOOGLE_SHEETS_CONTACT_TOOLS

# Create agent instances
email_agent = EmailAgent(llm=llm_client, tools=email_tools)
calendar_agent = CalendarAgent(llm=llm_client, tools=calendar_tools)
sheet_agent = SheetAgent(llm=llm_client, tools=sheet_tools)
supervisor_agent = SupervisorAgent(llm=llm_client,tools =[] )

print(f"✓ Initialized {email_agent.name} with {len(email_agent.tools)} tools")
print(f"✓ Initialized {calendar_agent.name} with {len(calendar_agent.tools)} tools")
print(f"✓ Initialized {sheet_agent.name} with {len(sheet_agent.tools)} tools")
print(f"✓ Initialized {supervisor_agent.name}")


# ============================================================
# Step 2: Define node functions using BaseAgent instances
# ============================================================


def call_supervisor(state: "MultiAgentState"):
    """
    Supervisor analyzes messages and decides the next step.
    Handles both JSON outputs and tool call invocations.
    """
    messages = state["messages"]

    response = supervisor_agent.invoke(messages)
    print(response) 

    if getattr(response, "tool_calls", None):
        print("🧩 Supervisor issued tool calls:", response.tool_calls)
        supervisor_ai_message = AIMessage(
            content=response.content or "",
            name="Supervisor",
            tool_calls=response.tool_calls,
        )
        return {
            "messages":[supervisor_ai_message],
        }

    raw_content = (response.content or "").strip()
    route = "none"
    thoughts = ""
    user_response = ""

    if raw_content:
        try:
            parsed = json.loads(raw_content)
            route = parsed.get("route", "none").lower()
            thoughts = parsed.get("thoughts", "")
            user_response = parsed.get("response", "")
        except json.JSONDecodeError:
            print("⚠️ Supervisor returned non-JSON output:", raw_content)
            thoughts = "Failed to parse JSON response."
            user_response = raw_content

    else:
        print("⚠️ Supervisor returned empty content.")
        user_response = "I'm sorry, I couldn't generate a response."

    print("=========================================================")
    print(f"Supervisor decision: {route}")
    print("Thoughts:", thoughts)
    print("=========================================================")

    # Build message
    supervisor_ai_message = AIMessage(
        content=user_response,
        name="Supervisor"
    )

    return {
        "route": route,
        "messages": state["messages"] + [supervisor_ai_message],
    }


def call_email_agent(state: MultiAgentState):
    """Email agent calls its chain."""
    messages = state["messages"]
    
    response = email_agent.invoke(messages)
    
    return {"messages": [response]}


def call_calendar_agent(state: MultiAgentState):
    """Calendar agent calls its chain."""
    messages = state["messages"]
    
    # Use the calendar agent's invoke method
    response = calendar_agent.invoke(messages)
    
    return {"messages": [response]}


def call_sheet_agent(state: MultiAgentState):
    """Sheet agent calls its chain."""
    messages = state["messages"]
    
    # Use the sheet agent's invoke method
    response = sheet_agent.invoke(messages)

    return {"messages": [response]}


# ============================================================
# Step 3: Create tool nodes (no changes needed)
# ============================================================

email_tool_node = ToolNode(tools=email_tools)
calendar_tool_node = ToolNode(tools=calendar_tools)
sheet_tool_node = ToolNode(tools=sheet_tools)
memory_tool_node = ToolNode(tools=MEMORY_TOOLS)
# Create tool name sets for routing
EMAIL_TOOL_NAMES = {t.name.lower() for t in email_tools}
CAL_TOOL_NAMES = {t.name.lower() for t in calendar_tools}
SHEET_TOOL_NAMES = {t.name.lower() for t in sheet_tools}
MEMORY_TOOL_NAMES = {t.name.lower() for t in MEMORY_TOOLS}

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



def supervisor_agent_should_continue(state: "MultiAgentState") -> str:
    """
    Determine which agent the supervisor should route to next.
    - If the last message is a tool call → route to 'tool_node'
    - Otherwise → use the 'route' field set by the supervisor.
    """
    messages = state.get("messages") or []
    route = state.get("route", "none")

    # --- Check if the last message involves a tool call ---
    if messages:
        last_msg = messages[-1]

        # Case 1: LLM initiated a tool call (AIMessage with tool_calls)
        if isinstance(last_msg, AIMessage) and getattr(last_msg, "tool_calls") and last_msg.tool_calls > 0:
            return "to_memory_tools"

        # Case 2: Tool message explicitly present
        if isinstance(last_msg, ToolMessage):
            return "to_memory_tools"

    # --- Otherwise use supervisor’s routing decision ---
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
graph.set_entry_point("supervisor")

# Add nodes
graph.add_node("supervisor", call_supervisor)
graph.add_node("email_agent", call_email_agent)
graph.add_node("calendar_agent", call_calendar_agent)
graph.add_node("sheet_agent", call_sheet_agent)
graph.add_node("email_tool_node", email_tool_node)
graph.add_node("calendar_tool_node", calendar_tool_node)
graph.add_node("sheet_tool_node", sheet_tool_node)
graph.add_node("memory_tool_node", memory_tool_node)

# Supervisor conditional edges
graph.add_conditional_edges(
    "supervisor",
    supervisor_agent_should_continue,
    {
        "to_email_agent": "email_agent",
        "to_calendar_agent": "calendar_agent",
        "to_sheet_agent": "sheet_agent",
        "to_memory_tools": "memory_tool_node",
        "end": END
    },
)

# Email agent conditional edges
graph.add_conditional_edges(
    "email_agent",
    sub_agent_should_continue,
    {
        "to_email_tool": "email_tool_node",
        "back_to_supervisor": "supervisor"
    },
)

# Calendar agent conditional edges
graph.add_conditional_edges(
    "calendar_agent",
    sub_agent_should_continue,
    {
        "to_calendar_tool": "calendar_tool_node",
        "back_to_supervisor": "supervisor"
    },
)

# Sheet agent conditional edges
graph.add_conditional_edges(
    "sheet_agent",
    sub_agent_should_continue,
    {
        "to_sheet_tool": "sheet_tool_node",
        "back_to_supervisor": "supervisor"
    },
)

# Tool nodes back to their respective agents
graph.add_edge("email_tool_node", "email_agent")
graph.add_edge("calendar_tool_node", "calendar_agent")
graph.add_edge("sheet_tool_node", "sheet_agent")
graph.add_edge("memory_tool_node", "supervisor")

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
        
        inputs = {"messages": [HumanMessage(content=user_input)]}
        
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
            
            # Print final response
            if "messages" in agent_response and agent_response["messages"]:
                final_message = agent_response["messages"][-1]
                print(f"\n{final_message.content}\n")
            else:
                print(f"\n{agent_response}\n")
                
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