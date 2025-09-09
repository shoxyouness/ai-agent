import os
from crewai import Agent, Task, Crew, Process
from crewai_tools import MCPServerAdapter
from mcp import StdioServerParameters
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
def main():
    """
    Demonstrates how to use the Playwright MCP server in stdio mode with CrewAI.
    The MCP server will be started via `npx @playwright/mcp@latest` as a child
    process, and its tools will be available to the agent.
    """

    server_params = StdioServerParameters(
        command="npx",
        args=["@playwright/mcp@latest"],
        env=os.environ
    )

    with MCPServerAdapter(server_params, connect_timeout=60) as mcp_tools:
        available_tools = [tool.name for tool in mcp_tools]
        print("Playwright MCP Tools available:", available_tools)
        o_llm = ChatOpenAI(
            model="gpt-4o",        
            api_key=os.environ["OPENAI_API_KEY"],
            temperature=0,
    )   
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            api_key=os.environ["GEMINI_API_KEY"],
            temperature=0,
        )
        
        browser_agent = Agent(
            role="Browser Agent",
            goal="Use Playwright MCP tools to navigate and interact with websites.",
            backstory="I use Playwright's MCP to open pages, click links and close the browser.",
            tools=mcp_tools,
            reasoning=True,
            verbose=True, 
            llm=o_llm,
        )

        browse_task = Task(
            description=(
                "Go to amazon.com and search for me a good phone case for an iPhone 15 Pro Max with price under 20 EUR. "
            ),
            expected_output="The page is opened and then closed without errors.",
            agent=browser_agent
        )


        crew = Crew(
            agents=[browser_agent],
            tasks=[browse_task],
            process=Process.sequential
        )

        result = crew.kickoff()
        print("Result:", result)

if __name__ == "__main__":
    main()
