# src/agents/simple_chat_agent.py

from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from src.tools.memory_tools import MEMORY_TOOLS
import os
from dotenv import load_dotenv

load_dotenv()


def create_simple_agent():
    """Create a simple working agent."""
    
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.7,
        openai_api_key=os.getenv("OPENAI_API_KEY")
    )
    
    prompt = PromptTemplate.from_template(
        """Answer the following questions as best you can. You have access to the following tools:

{tools}

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Begin!

Question: {input}
Thought:{agent_scratchpad}"""
    )
    
    agent = create_react_agent(llm, MEMORY_TOOLS, prompt)
    
    return AgentExecutor(
        agent=agent,
        tools=MEMORY_TOOLS,
        verbose=True,
        handle_parsing_errors=True
    )


def main():
    print("\n" + "="*70)
    print("SIMPLE MEMORY AGENT")
    print("="*70 + "\n")
    
    agent = create_simple_agent()
    
    while True:
        user_input = input("\n💬 You: ").strip()
        
        if not user_input:
            continue
            
        if user_input.lower() in ['exit', 'quit']:
            print("\n👋 Goodbye!\n")
            break
        
        try:
            result = agent.invoke({"input": user_input})
            print(f"\n🤖 Assistant: {result['output']}\n")
        except Exception as e:
            print(f"\n❌ Error: {str(e)}\n")


if __name__ == "__main__":
    main()