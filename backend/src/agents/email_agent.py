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
from src.chains.email_agent_chain import email_agent_chain
from langchain_core.messages import HumanMessage

load_dotenv()


def call_model(state: AgentState):
    """The primary node that calls the LLM."""
    messages = state["messages"]
    response = email_agent_chain.invoke(messages)
   
    return {"messages": [response]}


tools = [get_unread_emails, send_email, reply_to_email, mark_email_as_read, get_calendar_events, create_calendar_event, update_calendar_event]
tool_node = ToolNode(tools = tools)


def should_continue(state: AgentState) -> str:
    """
    Determines the next step.
    If the LLM made a tool call, we execute it.
    Otherwise, we end the conversation.
    """
    last_message = state["messages"][-1]
 
    if last_message.tool_calls:
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

# Then in run_email_agent:
def run_email_agent():
    print("Email Agent is running. Type your request or 'exit' to quit.")
    
    thread_id = "email_thread"  
    
    while True:
        user_input = input("You: ")
        if user_input.lower() == 'exit':
            break
        
        inputs = {"messages": [HumanMessage(content=user_input)]}
        
        print("\nAgent:")
        config = {"configurable": {"thread_id": thread_id}}  # Resume from saved state
        agent_response = app.invoke(inputs, config=config)
        
        # Print as before
        print(agent_response["messages"][-1].content if "messages" in agent_response else agent_response)
        
        print("\n\n--- Agent finished ---")
