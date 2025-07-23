from src.agents.email_agent import app 
from langchain_core.messages import HumanMessage
from src.agents.email_agent import run_email_agent
# def run_email_agent():
#     print("Email Agent is running. Type your request or 'exit' to quit.")
    
#     # The first time, it might ask you to authenticate with Outlook in your browser.
#     # A file 'o365_token.json' will be created to keep you logged in.
    
#     while True:
#         user_input = input("You: ")
#         if user_input.lower() == 'exit':
#             break
            
#         # The input to the graph is a dictionary with the key "messages"
#         inputs = {"messages": [HumanMessage(content=user_input)]}
        
#         print("\nAgent:")
#         # # Use .stream() to get intermediate steps
#         # for event in app.stream(inputs, stream_mode="values"):
#         #     # The event is the full state dictionary
#         #     if "messages" in event:
#         #         last_message = event["messages"][-1]
#         #         # Check for content and tool calls to print meaningful output
#         #         if last_message.content:
#         #             print(last_message.content, end="", flush=True)

#         agent_response = app.invoke(inputs)
#         print(agent_response)

#         print("\n\n--- Agent finished ---")

if __name__ == "__main__":
    run_email_agent()
