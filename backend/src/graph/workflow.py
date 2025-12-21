from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode

from src.graph.state import MultiAgentState
from src.agents import email_agent, calendar_agent, sheet_agent, memory_agent
from src.graph.consts import *
from src.graph.nodes import *
from src.graph.router import *


def build_graph():
    # 1. Initialize Graph
    graph = StateGraph(MultiAgentState)

    # 2. Add Nodes
    graph.add_node(RETRIEVE_MEMORY_NODE, retrieve_memory)
    graph.add_node(SUPERVISOR_NODE, call_supervisor)
    graph.add_node(EMAIL_AGENT_NODE, call_email_agent)
    graph.add_node(CALENDAR_AGENT_NODE, call_calendar_agent)
    graph.add_node(SHEET_AGENT_NODE, call_sheet_agent)
    graph.add_node(BROWSER_AGENT_NODE, call_browser_agent)
    graph.add_node(MEMORY_AGENT_NODE, call_memory_agent)
    graph.add_node(REVIEWER_NODE, call_reviewer_agent)
    graph.add_node(CLEAR_STATE_NODE, clear_sub_agents_state)

    # 3. Add Tool Nodes
    graph.add_node(EMAIL_TOOL_NODE, ToolNode(email_agent.tools))
    graph.add_node(CALENDAR_TOOL_NODE, ToolNode(calendar_agent.tools))
    graph.add_node(SHEET_TOOL_NODE, ToolNode(sheet_agent.tools))
    graph.add_node(MEMORY_TOOL_NODE, ToolNode(memory_agent.tools))

    # 4. Set Entry
    graph.set_entry_point(RETRIEVE_MEMORY_NODE)

    
    # Supervisor Logic
    graph.add_conditional_edges(
        SUPERVISOR_NODE,
        supervisor_should_continue,
        {
            EMAIL_AGENT_NODE: EMAIL_AGENT_NODE,
            CALENDAR_AGENT_NODE: CALENDAR_AGENT_NODE,
            SHEET_AGENT_NODE: SHEET_AGENT_NODE,
            BROWSER_AGENT_NODE: BROWSER_AGENT_NODE,
            "end": MEMORY_AGENT_NODE
        }
    )

    #Email Agent
    graph.add_conditional_edges(EMAIL_AGENT_NODE,sub_agent_should_continue, {
        REVIEWER_NODE:REVIEWER_NODE,
        EMAIL_TOOL_NODE: EMAIL_TOOL_NODE,
        CLEAR_STATE_NODE:CLEAR_STATE_NODE
    })

    #Calendar Agent 
    graph.add_conditional_edges(CALENDAR_AGENT_NODE, sub_agent_should_continue,{
        CALENDAR_TOOL_NODE:CALENDAR_TOOL_NODE,
        CLEAR_STATE_NODE:CLEAR_STATE_NODE
    })

    #Sheet Agent
    graph.add_conditional_edges(SHEET_AGENT_NODE, sub_agent_should_continue,{
        SHEET_TOOL_NODE:SHEET_TOOL_NODE,
        CLEAR_STATE_NODE:CLEAR_STATE_NODE
    })

    # Reviewer Logic
    graph.add_conditional_edges(
        REVIEWER_NODE,
        reviewer_should_continue,
        {
            EMAIL_TOOL_NODE: EMAIL_TOOL_NODE,
            EMAIL_AGENT_NODE: EMAIL_AGENT_NODE,
            CLEAR_STATE_NODE: CLEAR_STATE_NODE
        }
    )

    # Memory Logic
    graph.add_conditional_edges(
        MEMORY_AGENT_NODE, 
        memory_should_continue, 
        {MEMORY_TOOL_NODE: MEMORY_TOOL_NODE, "end": END}
    )
    graph.add_edge(RETRIEVE_MEMORY_NODE, SUPERVISOR_NODE)
    graph.add_edge(CLEAR_STATE_NODE, SUPERVISOR_NODE)
    graph.add_edge(BROWSER_AGENT_NODE, CLEAR_STATE_NODE)

    graph.add_edge(EMAIL_TOOL_NODE, EMAIL_AGENT_NODE)
    graph.add_edge(CALENDAR_TOOL_NODE, CALENDAR_AGENT_NODE)
    graph.add_edge(SHEET_TOOL_NODE, SHEET_AGENT_NODE)

    graph.add_edge(MEMORY_TOOL_NODE, MEMORY_AGENT_NODE)

    return graph.compile(checkpointer=MemorySaver())
