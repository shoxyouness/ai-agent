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

from src.schema.email_agent_schema import AgentState
from langchain_google_genai import ChatGoogleGenerativeAI
from src.chains.email_agent_chain import email_agent_chain  # Existing email chain
# NEW: Import or define specialized chains
from src.chains.supervisor_chain import supervisor_chain  # To be created: Supervisor routing chain
from src.chains.calendar_agent_chain import calendar_agent_chain  # To be created: Calendar-specific chain


load_dotenv()

email_tools = [get_unread_emails, send_email, reply_to_email, mark_email_as_read]
calendar_tools = [get_calendar_events, create_calendar_event, update_calendar_event]

def call_supervisor(state: AgentState):
    """Supervisor analyzes messages and decides next step."""
    messages = state["messages"]
    response = supervisor_chain.invoke(messages)
    return {"messages": [response]}


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


email_tool_node = ToolNode(tools=email_tools)
calendar_tool_node = ToolNode(tools=calendar_tools)



# NEW: Supervisor routing logic
def supervisor_should_route(state: AgentState) -> str:
    """
    Supervisor decides: route to email, calendar, both (sequential), or end.
    Based on last message content (e.g., assume supervisor adds a 'route' key or uses content classification).
    """
    last_message = state["messages"][-1]
    # Example: Parse supervisor's response for routing decision (e.g., if content starts with "EMAIL:", etc.)
    # For simplicity, assume supervisor's response.content indicates route (customize based on your prompt)
    if "email" in last_message.content.lower() and "calendar" in last_message.content.lower():
        return "both"  # Sequential: email then calendar
    elif "email" in last_message.content.lower():
        return "email_agent"
    elif "calendar" in last_message.content.lower():
        return "calendar_agent"
    elif last_message.tool_calls:
        return "supervisor_tool"  # If supervisor needs tools (optional)
    return "end"

# Sub-agent continuation (similar to original)
def sub_agent_should_continue(state: AgentState, agent_type: str) -> str:
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return f"{agent_type}_tool"
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
        "both": "email_agent",  # Start sequence with email
        "end": END
    },
)

# Email agent edges
workflow.add_conditional_edges(
    "email_agent",
    lambda state: sub_agent_should_continue(state, "email"),
    {
        "email_tool": "email_tool",
        "back_to_supervisor": "supervisor"
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

# For "both": After email, go to calendar
workflow.add_conditional_edges(
    "email_agent",  # Override for "both" flow
    lambda state: "calendar_agent" if "both" in state.get("route", "") else sub_agent_should_continue(state, "email"),  # Track route in state if needed
    {"calendar_agent": "calendar_agent", "email_tool": "email_tool", "back_to_supervisor": "supervisor"}
)

# Compile
checkpointer = MemorySaver()
app = workflow.compile(checkpointer=checkpointer)

# --- Run Function (Minor Updates) ---

def run_email_agent():
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