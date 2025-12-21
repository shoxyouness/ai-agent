import asyncio
import os

from browser_use import Agent, Browser, ChatOpenAI


async def main():
    # Make sure OPENAI_API_KEY is set in your environment
    llm = ChatOpenAI(
        model="gpt-4o",
        temperature=0,
    )

    browser = Browser(
        headless=False,
    )

    agent = Agent(
        task=(
            "open weakpedia and search for 'LangGraph'. "
          
        ),
        llm=llm,        # ⬅ LangChain model now passed directly
        browser=browser,
    )

    history = await agent.run(max_steps=50)
    print ("\n=== FULL HISTORY ===")
    print(history)

    print("\n=== FINAL RESULT ===")
    print(history.final_result())

    print("\nDuration (s):", history.total_duration_seconds())
    print("Steps:", history.number_of_steps())

    if history.has_errors():
        print("\n=== ERRORS ===")
        print(history.errors())


if __name__ == "__main__":
    asyncio.run(main())
