import asyncio
from browser_use import Agent, Browser,ChatOpenAI

llm = ChatOpenAI(
    model="gpt-4o",
    temperature=0,
)


async def run_browser_task(task: str) -> str:
    """
    Executes a browser task using the browser-use library.
    """
    print(f"\n🌍 [Browser Agent] Starting task: {task}")
    try:
        browser = Browser(
        headless=False,
        )
    except TypeError:
        browser = Browser(headless=False)
    try:
        agent = Agent(
            task=task + " IMPORTANT: You must THINK and RESPOND in the language of the user's request.",
            llm=llm,
            browser=browser,
        )

        history = await agent.run(max_steps=50)

        result = history.final_result()

        print(f"   Duration: {history.total_duration_seconds()}s")
        print(f"   Steps: {history.number_of_steps()}")

        if not result:
            if history.has_errors():
                return f"Browser finished with errors: {history.errors()}"
            return "Task completed visually, but no text summary was returned."
        
        return result

    except Exception as e:
        return f"Error executing browser task: {str(e)}"

name = "browser_agent"
description = "A web browsing agent capable of navigating websites, searching Google, planning trips, checking prices, and extracting information using a real browser."