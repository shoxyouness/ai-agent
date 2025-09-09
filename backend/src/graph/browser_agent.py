from browser_use.llm import ChatGoogle
from browser_use import Agent
from dotenv import load_dotenv

import asyncio
# Read GOOGLE_API_KEY into env
load_dotenv()

# Initialize the model
llm = ChatGoogle(model='gemini-2.0-flash')


async def main():
    agent = Agent(
        task="go search for Werkstundent in Dortmund as AI Engineer. and list me all the results with company name, job title, and link to the job posting.",
        llm=llm,
    )
    result = await agent.run()
    print(result)

asyncio.run(main())
