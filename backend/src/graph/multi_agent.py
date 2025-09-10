from dotenv import load_dotenv

from langgraph.prebuilt import ToolNode
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from src.tools.email_tools import get_unread_emails, send_email, reply_to_email, mark_email_as_read
from src.tools.calender_tools import get_calendar_events, create_calendar_event, update_calendar_event

from src.schema.multi_agent_schema import MultiAgentState
from src.chains.email_agent_chain import email_agent_chain
from src.chains.calender_agent_chain import calendar_agent_chain  
from src.chains.supervisor_chain import supervisor_chain
from langchain_core.messages import HumanMessage, AIMessage

from pprint import pprint

email_tools = [get_unread_emails, send_email, reply_to_email, mark_email_as_read]
calendar_tools = [get_calendar_events, create_calendar_event, update_calendar_event]

def call_supervisor(state: MultiAgentState):
    """Supervisor analyzes messages and decides next step."""
    messages = state["messages"]
    response = supervisor_chain.invoke(messages)

    supervisor_ai_message = AIMessage(
        content=response.response, name = "Supervisor",

    )
    print("=========================================================")
    print("Supervisor decision:", response.route)
    print("=========================================================")

    return {"route": response.route.lower(), "messages": supervisor_ai_message}


def call_email_agent(state: MultiAgentState):
    """Email agent calls its chain."""
    messages = state["messages"]
    response = email_agent_chain.invoke(messages)
    return {"messages": [response]}

def call_calendar_agent(state: MultiAgentState):
    """Calendar agent calls its chain."""
    messages = state["messages"]
    response = calendar_agent_chain.invoke(messages)
    return {"messages": [response]}

email_tool_node = ToolNode(tools = email_tools)
calendar_tool_node = ToolNode(tools = calendar_tools)

EMAIL_TOOL_NAMES = {t.name.lower() for t in email_tools}
CAL_TOOL_NAMES   = {t.name.lower() for t in calendar_tools}

def _get_tc_name(tc) -> str:
    # Works for dicts or objects; returns lowercased name or ""
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
    if last_tc_name in EMAIL_TOOL_NAMES:
        return "to_email_tool"
    if last_tc_name in CAL_TOOL_NAMES:
        return "to_calendar_tool"
    return "back_to_supervisor"


def supervisor_agent_should_continue(state: MultiAgentState) -> str:
    route = state["route"]
    if route == "email_agent":
        return "to_email_agent"
    elif route == "calendar_agent":
        return "to_calendar_agent"
    return "end"

graph = StateGraph(MultiAgentState)

graph.set_entry_point("supervisor")
graph.add_node("supervisor", call_supervisor)
graph.add_node("email_agent", call_email_agent)
graph.add_node("calendar_agent", call_calendar_agent)
graph.add_node("email_tool_node", email_tool_node)
graph.add_node("calendar_tool_node", calendar_tool_node)


graph.add_conditional_edges(
    "supervisor",
    supervisor_agent_should_continue,
    {
        "to_email_agent": "email_agent",
        "to_calendar_agent": "calendar_agent",
        "end": END
    },
)
graph.add_conditional_edges(
    "email_agent",
    sub_agent_should_continue,
    {
        "to_email_tool": "email_tool_node",
        "back_to_supervisor": "supervisor"
    },
)

graph.add_conditional_edges(
    "calendar_agent",
    sub_agent_should_continue,
    {
        "to_calendar_tool": "calendar_tool_node",
        "back_to_supervisor": "supervisor"
    }, ) 
graph.add_edge("email_tool_node", "email_agent")
graph.add_edge("calendar_tool_node", "calendar_agent")


checkpointer = MemorySaver()
app = graph.compile(checkpointer=checkpointer)


def run_multi_agent():
    print("Multi-Agent System is running. Type your request or 'exit' to quit.")
    
    thread_id = "multi_agent_thread"  
    
    while True:
        user_input = input("You: ")
        if user_input.lower() == 'exit':
            break
        
        inputs = {"messages": [HumanMessage(content=user_input)]}
        
        print("\nAgent:")
        config = {"configurable": {"thread_id": thread_id}}  
        agent_response = app.invoke(input=inputs, config=config)
        print("==========================================================")
        snapshot = app.get_state(config=config)
        print("STATE VALUES:")
        pprint(snapshot.values)
        print("NEXT:", snapshot.next)  
        print("==========================================================")
        print(agent_response["messages"][-1].content if "messages" in agent_response else agent_response)
if __name__ == "__main__": 
    run_multi_agent()