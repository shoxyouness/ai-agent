"""
Run Browser-Use MCP server from LangGraph with correct MultiServerMCPClient usage.
Target server: https://github.com/co-browser/browser-use-mcp-server
Tested with: langchain-mcp-adapters >= 0.1.0
"""

import asyncio
import os
from typing import Dict, Any, List

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode

# langchain-mcp-adapters 0.1.x API
from langchain_mcp_adapters.client import (
    MultiServerMCPClient,
    load_mcp_tools,
)

load_dotenv()


def build_graph_with_tools(tools: List[Any]):
    """Build a LangGraph that can use the provided tools."""
    model = ChatOpenAI(
        model="gpt-4o-mini",
        api_key=os.environ["OPENAI_API_KEY"],
        temperature=0,
    )
    model_with_tools = model.bind_tools(tools)
    tool_node = ToolNode(tools)

    async def call_model(state: MessagesState) -> Dict[str, Any]:
        response = await model_with_tools.ainvoke(state["messages"])
        return {"messages": [response]}

    def should_continue(state: MessagesState) -> str:
        last_message = state["messages"][-1]
        tool_calls = getattr(last_message, "tool_calls", None)
        return "tools" if tool_calls else END

    builder = StateGraph(MessagesState)
    builder.add_node("call_model", call_model)
    builder.add_node("tools", tool_node)
    builder.add_edge(START, "call_model")
    builder.add_conditional_edges("call_model", should_continue)
    builder.add_edge("tools", "call_model")

    return builder.compile()


async def run_agent():
    # Use the co-browser "browser-use-mcp-server" in stdio mode via its CLI.
    # Reference stdio config (command/args/env) comes from the project docs.  :contentReference[oaicite:1]{index=1}
    client = MultiServerMCPClient(
    {
        "browser-use": {
            "command": "browser-use-mcp-server",
            "args": [
                "run", "server",
                "--port", "8000",      # SSE port used internally
                "--stdio",             # tell it to use stdio mode
                "--proxy-port", "9000" # requires mcp-proxy on PATH
            ],
            "transport": "stdio",
            "env": {
                "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY", ""),
                # Optional, helps on Windows:
                # "CHROME_PATH": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                # You can also set "PATIENT": "true" if you want the server to wait for task completion.
            },
        }
    }
)

    # Keep the session alive during the whole run
    async with client.session("browser-use") as session:
        tools = await load_mcp_tools(session)
        
        print("Loaded tools:", [tool.name for tool in tools])
        graph = build_graph_with_tools(tools)

        # Prompt
        user_message = {
            "role": "user",
            "content": (
                "Go to amazon.com and search for me a good phone case for an "
                "iPhone 15 Pro Max with price under 20 EUR."
            ),
        }

        result = await graph.ainvoke({"messages": [user_message]})
        assistant_reply = result["messages"][-1]
        print("Assistant reply:\n", assistant_reply)


def main():
    try:
        asyncio.run(run_agent())
    except KeyboardInterrupt:
        print("Execution interrupted by user.")


if __name__ == "__main__":
    main()
