import requests
import json
import sys

def run_chat():
    url = "http://localhost:8000/chat/stream"
    thread_id = "test_user_1"
    
    # 1. Send Initial Request
    user_msg = input("You: ")
    payload = {"message": user_msg, "thread_id": thread_id}
    
    print("\n--- Streaming Response ---")
    
    # We use a session to keep connection logic simple
    with requests.post(url, json=payload, stream=True) as r:
        handle_stream(r, thread_id)

def handle_stream(response, thread_id):
    url = "http://localhost:8000/chat/stream"
    
    # Process SSE lines
    for line in response.iter_lines():
        if not line: continue
        decoded_line = line.decode('utf-8')
        
        if decoded_line.startswith("event:"):
            event_type = decoded_line.split(":", 1)[1].strip()
        elif decoded_line.startswith("data:"):
            data_str = decoded_line.split(":", 1)[1].strip()
            
            # --- HANDLE EVENTS ---
            if event_type == "agent_start":
                data = json.loads(data_str)
                print(f"\n\n🤖 [{data['agent']}]: ", end="", flush=True)
                
            elif event_type == "token":
                data = json.loads(data_str)
                print(data['text'], end="", flush=True)
                
            elif event_type == "interrupt":
                data = json.loads(data_str)
                print(f"\n\n⚠️ REVIEW REQUIRED:\n{data['payload']}")
                
                # --- AUTO-HANDLE RESUME FOR DEMO ---
                decision = input("\n(approved/changes): ")
                
                # Call API again with resume_action
                resume_payload = {"resume_action": decision, "thread_id": thread_id}
                print("\n--- Resuming Graph ---")
                with requests.post(url, json=resume_payload, stream=True) as r2:
                    handle_stream(r2, thread_id)
                return # Exit this loop as the new request handles the rest

if __name__ == "__main__":
    run_chat()