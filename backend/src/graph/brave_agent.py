import os
from dotenv import load_dotenv

from langchain_core.messages import HumanMessage
from langgraph.prebuilt import ToolNode
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from src.schema.email_agent_schema import AgentState
from src.chains.brave_agent_chain import brave_agent_chain 
# Playwright MCP-backed tools
from src.tools.brave_tools import (
    browser_navigate, browser_snapshot, browser_click, browser_type,
    browser_evaluate, browser_take_screenshot, browser_navigate_back,
    browser_navigate_forward, browser_tab_new, browser_tab_select
)

load_dotenv()

def call_model(state: AgentState):
    response = brave_agent_chain.invoke(state["messages"])
    return {"messages": [response]}

tools = [
    browser_navigate, browser_snapshot, browser_click, browser_type,
    browser_evaluate, browser_take_screenshot, browser_navigate_back,
    browser_navigate_forward, browser_tab_new, browser_tab_select
]
tool_node = ToolNode(tools=tools)

def should_continue(state: AgentState) -> str:
    last = state["messages"][-1]
    return "continue_to_tool" if getattr(last, "tool_calls", None) else "end"

workflow = StateGraph(AgentState)
workflow.add_node("agent", call_model)
workflow.add_node("tool_node", tool_node)
workflow.set_entry_point("agent")
workflow.add_conditional_edges("agent", should_continue, {
    "continue_to_tool": "tool_node", "end": END
})
workflow.add_edge("tool_node", "agent")
app = workflow.compile(checkpointer=MemorySaver())

def run_brave_agent():
    print("Brave Agent is running. Type your request or 'exit' to quit.")
    thread_id = "brave_thread"
    while True:
        user_input = input("You: ")
        if user_input.lower() == "exit":
            break
        inputs = {"messages": [HumanMessage(content=user_input)]}
        print("\nAgent:")
        config = {"configurable": {"thread_id": thread_id}}
        out = app.invoke(inputs, config=config)
        print(out["messages"][-1].content if "messages" in out else out)
        print("\n\n--- Agent finished ---")

if __name__ == "__main__":
    run_brave_agent()