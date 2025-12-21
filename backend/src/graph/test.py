from langchain_core.messages import HumanMessage
from src.graph.main import app

inputs = {
    "messages": [HumanMessage(content="Call +4915906752100 to test the system")],
    "core_messages": [HumanMessage(content="Call +4915906752100 to test the system")]
}

config = {"configurable": {"thread_id": "test_call"}}

result = app.invoke(input=inputs, config=config)
print(result)
