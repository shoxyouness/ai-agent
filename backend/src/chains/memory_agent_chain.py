from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from src.tools.memory_tools import MEMORY_TOOLS
from datetime import datetime
from src.config.llm import llm_client


with open("src/prompts/memory_agent_prompt.txt", "r") as f:
    prompt_template_str = f.read()

llm_with_tools = llm_client.bind_tools(tools= MEMORY_TOOLS)

tools_description = "\n".join([f"- {tool.name}: {tool.description}" for tool in MEMORY_TOOLS])
memory_agent_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", prompt_template_str),
        MessagesPlaceholder(variable_name="messages")
    ]
).partial(
    tools=tools_description, current_date_time=datetime.now().strftime("%I:%M %p %Z, %A, %B %d, %Y"))
memory_agent_chain = memory_agent_prompt | llm_with_tools