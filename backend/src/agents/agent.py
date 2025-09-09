from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage
from langchain_core.messages.tool import ToolCall
import re
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from langchain_core.tools import tool
import asyncio
load_dotenv()

class Agent():
    def __init__(self, name: str, llm, tools, description, main_task, process, notes):
        self.name = name
        self.llm = llm
        self.tools = tools
        self.description = description
        self.main_task = main_task
        self.process = process
        self.notes = notes
        

    async def __call__(self, state):
        return await self.run(state)
    async def ainvoke(self, state):
        return await self.run(state)
    

    def create_prompt(self, state):
        tool_descriptions = "\n".join([f"{tool.name}: {tool.description}" for tool in self.tools])
        tool_calls = "\n".join([f"{tool.name}({{input}})" for tool in self.tools])
        
        prompt = f"""
        You are {self.name}. Your main task is: {self.main_task}
        Your process is as follows: {self.process}
        Here are some additional notes about your behavior: {self.notes}
        You have access to the following tools:
        {tool_descriptions}
        Only use the tools listed above. If you want to respond to the user, use the format:
        AI: {{your response here}}
        Here is the current conversation state:
        {state}
        """

        return prompt.strip()

    async def run(self, state):
        prompt = self.create_prompt(state)
        if self.tools:
            self.llm.bind_tools(self.tools)
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
        else:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
        content = response.content

        return AIMessage(content=content)
    
@tool
def sum_numbers(numbers: list[int]) -> int:
    """Sums a list of numbers."""
    return sum(numbers)

async def main():
    agent  = Agent(
        name="TestAgent", llm = ChatOpenAI(model="gpt-4o", temperature=0),
        tools=[sum_numbers],
        description="A test agent that can sum numbers.",
        main_task="Sum a list of numbers provided by the user.",
        process="1. Understand the user's request. 2. If it involves summing numbers, use the sum_numbers tool. 3. Provide the result to the user.",
        notes="Be concise and clear in your responses."
    )
    response = await agent.ainvoke("User wants to sum the numbers 1, 2, and 3.")
    print(response)

if __name__ == "__main__":
    asyncio.run(main())

    