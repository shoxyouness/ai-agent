import os
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import ToolMessage
from langgraph.prebuilt import ToolNode
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
# Import our custom components
from src.tools.email_tools import get_unread_emails, send_email, reply_to_email, mark_email_as_read
from src.tools.calender_tools import get_calendar_events, create_calendar_event, update_calendar_event
from typing import Annotated, List
from langchain_google_genai import ChatGoogleGenerativeAI
from src.chains.email_agent_chain import email_agent_chain  # Existing email chain
# NEW: Import or define specialized chains
from src.chains.supervisor_chain import supervisor_chain  # To be created: Supervisor routing chain
from src.chains.calender_agent_chain import calendar_agent_chain  # Existing calendar chain
from langgraph.graph import add_messages
from langchain_core.messages import HumanMessage, AIMessage
load_dotenv()

email_tools = [get_unread_emails, send_email, reply_to_email, mark_email_as_read]
calendar_tools = [get_calendar_events, create_calendar_event, update_calendar_event]


# src.schema.email_agent_schema.py
from typing import List, TypedDict
from langchain_core.messages import BaseMessage

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    route: str  # Add route field to track "both", "email", etc.
    final_response: str  


def call_supervisor(state: AgentState):
    """Supervisor analyzes messages and decides next step."""
    messages = state["messages"]
    response = supervisor_chain.invoke(messages)

    supervisor_ai_message = AIMessage(
        content=response.response, name = "Supervisor",
        #
    )
    return {"route": response.route.lower(), "messages": supervisor_ai_message}


def call_email_agent(state: AgentState):
    """Email agent calls its chain."""
    messages = state["messages"]
    response = email_agent_chain.invoke(messages)
    return {"messages": [response]}


def call_calendar_agent(state: AgentState):
    """Calendar agent calls its chain."""
    messages = state["messages"]
    response = calendar_agent_chain.invoke(messages)
    return {"messages": [response]}


# Custom tool nodes to set name in ToolMessage
def custom_tool_node(state: AgentState, tools: list):
    messages = state["messages"]
    last_message = messages[-1]
    outputs = []
    tool_map = {t.name: t for t in tools}
    for tc in last_message.tool_calls:
        tool = tool_map[tc["name"]]
        output = tool.invoke(tc["args"])
        outputs.append(ToolMessage(
            content=str(output),
            name=tc["name"],
            tool_call_id=tc["id"],
        ))
    return {"messages": outputs}

def email_tool_node(state: AgentState):
    return custom_tool_node(state, email_tools)

def calendar_tool_node(state: AgentState):
    return custom_tool_node(state, calendar_tools)


def supervisor_should_route(state: AgentState) -> str:
    decision = state.get("route", "end").lower()
    # Map decision to the appropriate branch
    if decision == "both":
        return "both"
    elif decision == "email_agent":
        return "email_agent"
    elif decision == "calendar_agent":
        return "calendar_agent"
    else:
        last_message = state.get("messages", [{}])[-1]
        final_content = getattr(last_message, 'content', "No response available.")
        state['final_response'] = final_content
        return "end"  # Default to end if no valid route is found


def sub_agent_should_continue(state: AgentState, agent_type: str) -> str:
    print(f" agent_type={agent_type}")
    if not state.get("messages") or not isinstance(state["messages"], list) or len(state["messages"]) == 0:
        print("No messages, returning back_to_supervisor")
        return "back_to_supervisor"
    last_message = state["messages"][-1]
    print(f"Last message: {last_message}")
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        print(f"Returning {agent_type}_tool")
        return f"{agent_type}_tool"
    print("Returning back_to_supervisor")
    return "back_to_supervisor"

# --- 4. Assemble the Graph ---

workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("supervisor", call_supervisor)
workflow.add_node("email_agent", call_email_agent)
workflow.add_node("calendar_agent", call_calendar_agent)
workflow.add_node("email_tool", email_tool_node)
workflow.add_node("calendar_tool", calendar_tool_node)

# Entry point: Start with supervisor
workflow.set_entry_point("supervisor")

# Supervisor conditional edges
workflow.add_conditional_edges(
    "supervisor",
    supervisor_should_route,
    {
        "email_agent": "email_agent",
        "calendar_agent": "calendar_agent",
        "both": "email_agent",  
        "end": END
    },
)

# Combined email agent routing logic
def email_agent_router(state: AgentState) -> str:
    # Check for "both" flow in state (set by supervisor if needed)
    if state.get("route") == "both":
        return "calendar_agent"  # After email, go to calendar for "both" flow
    return sub_agent_should_continue(state, "email")

# Email agent edges
workflow.add_conditional_edges(
    "email_agent",
    email_agent_router,
    {
        "email_tool": "email_tool",
        "back_to_supervisor": "supervisor",
        "calendar_agent": "calendar_agent"  # For "both" flow
    },
)
workflow.add_edge("email_tool", "email_agent")  # Loop back to email agent

# Calendar agent edges
workflow.add_conditional_edges(
    "calendar_agent",
    lambda state: sub_agent_should_continue(state, "calendar"),
    {
        "calendar_tool": "calendar_tool",
        "back_to_supervisor": "supervisor"
    },
)
workflow.add_edge("calendar_tool", "calendar_agent")  # Loop back to calendar agent

# Compile
checkpointer = MemorySaver()
app = workflow.compile(checkpointer=checkpointer)

# --- Run Function (Minor Updates) ---

def run_agent():
    print("Multi-Agent Email System is running. Type your request or 'exit' to quit.")
    
    thread_id = "multi_agent_thread"  # Unique per session
    
    while True:
        user_input = input("You: ")
        if user_input.lower() == 'exit':
            break
        
        inputs = {"messages": [HumanMessage(content=user_input)]}
        
        print("\nSystem:")
        config = {"configurable": {"thread_id": thread_id}}
        agent_response = app.invoke(inputs, config=config)
        # Print final response (from supervisor or last agent)
        print(agent_response["messages"][-1].content if "messages" in agent_response else agent_response)
        
        print("\n\n--- System finished ---")