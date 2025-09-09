import os
from dotenv import load_dotenv
from langchain_core.messages import ToolMessage
from langgraph.prebuilt import ToolNode
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from src.tools.email_tools import get_unread_emails, send_email, reply_to_email, mark_email_as_read
from src.tools.calender_tools import get_calendar_events, create_calendar_event, update_calendar_event
from src.schema.email_agent_schema import AgentState
from src.chains.outlook_agent_chain import outlook_agent_chain
from langchain_core.messages import HumanMessage
import pprint
load_dotenv()


def call_model(state: AgentState):
    """The primary node that calls the LLM."""
    messages = state["messages"]
    response = outlook_agent_chain.invoke({"messages": messages})
    return {"messages": [response]}


tools = [get_unread_emails, send_email, reply_to_email, mark_email_as_read, get_calendar_events, create_calendar_event, update_calendar_event]
tool_node = ToolNode(tools = tools)


def should_continue(state: AgentState) -> str:
    last_message = state["messages"][-1]
    # prüfe defensiv auf Attribut
    has_tool_calls = getattr(last_message, "tool_calls", None)
    if has_tool_calls:
        return "continue_to_tool"
    return "end"


workflow = StateGraph(AgentState)

workflow.add_node("agent", call_model)
workflow.add_node("tool_node", tool_node)

workflow.set_entry_point("agent")


workflow.add_conditional_edges(
    "agent",          
    should_continue,  
    {
        "continue_to_tool": "tool_node", 
        "end": END
    },
)
workflow.add_edge("tool_node", "agent")

checkpointer = MemorySaver()
app = workflow.compile(checkpointer=checkpointer)  


def run_outlook_agent():
    print("Outlook Agent is running. Type your request or 'exit' to quit.")
    
    thread_id = "outlook_thread"  
    
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
        pprint.pprint(snapshot.values)
        print("NEXT:", snapshot.next)  
        print("==========================================================")


        
        print(agent_response["messages"][-1].content if "messages" in agent_response else agent_response)
        
        print("\n\n--- Agent finished ---")

if __name__ == "__main__":
    run_outlook_agent()