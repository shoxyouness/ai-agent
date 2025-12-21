"""
Client examples for interacting with the Multi-Agent API.
Shows how to use both chat and stream endpoints.
"""

import requests
import json
import sseclient  # pip install sseclient-py
from typing import Iterator

# API Configuration
BASE_URL = "http://localhost:8000"

# =========================
# Example 1: Synchronous Chat
# =========================

def chat_sync(message: str, thread_id: str = None) -> dict:
    """
    Send a message using the synchronous chat endpoint.
    Returns the complete response with state.
    """
    url = f"{BASE_URL}/chat"
    
    payload = {
        "message": message,
        "thread_id": thread_id,
        "user_id": "default_user"
    }
    
    response = requests.post(url, json=payload)
    response.raise_for_status()
    
    return response.json()

def example_chat_sync():
    """Example: Synchronous chat request."""
    print("=" * 70)
    print("EXAMPLE 1: Synchronous Chat")
    print("=" * 70)
    
    # First message
    result = chat_sync("Check my emails")
    
    print(f"\nThread ID: {result['thread_id']}")
    print(f"\nResponse: {result['response']}")
    print(f"\nState Keys: {list(result['state'].keys())}")
    print(f"\nMetadata: {json.dumps(result['metadata'], indent=2)}")
    
    # Follow-up message (same thread)
    thread_id = result['thread_id']
    result2 = chat_sync("Now check my calendar for today", thread_id=thread_id)
    
    print(f"\n--- Follow-up in same thread ---")
    print(f"Response: {result2['response']}")
    print(f"Total Messages: {result2['metadata']['message_count']}")

# =========================
# Example 2: Streaming Chat
# =========================

def chat_stream(message: str, thread_id: str = None) -> Iterator[dict]:
    """
    Send a message using the streaming endpoint.
    Yields state updates as they arrive.
    """
    url = f"{BASE_URL}/stream"
    
    payload = {
        "message": message,
        "thread_id": thread_id,
        "user_id": "default_user"
    }
    
    response = requests.post(url, json=payload, stream=True)
    response.raise_for_status()
    
    # Parse Server-Sent Events
    client = sseclient.SSEClient(response)
    
    for event in client.events():
        if event.data:
            yield json.loads(event.data)

def example_chat_stream():
    """Example: Streaming chat request."""
    print("\n" + "=" * 70)
    print("EXAMPLE 2: Streaming Chat")
    print("=" * 70)
    
    thread_id = None
    
    for event in chat_stream("Book a meeting with Alice tomorrow at 2 PM"):
        event_type = event.get("type")
        
        if event_type == "start":
            thread_id = event.get("thread_id")
            print(f"\n🚀 Started stream (Thread: {thread_id})")
        
        elif event_type == "node":
            node_name = event.get("node")
            print(f"\n📍 Node: {node_name}")
            
            # Show relevant state updates
            state = event.get("state", {})
            if state.get("supervisor_response"):
                print(f"   Supervisor: {state['supervisor_response'][:100]}...")
            
            if state.get("calendar_agent_response"):
                print(f"   Calendar: {state['calendar_agent_response'][:100]}...")
        
        elif event_type == "complete":
            print(f"\n✅ Complete!")
            print(f"   Final Response: {event.get('response')}")
            print(f"   Thread ID: {event.get('thread_id')}")
            
            # Access complete state
            complete_state = event.get("state", {})
            print(f"   State Keys: {list(complete_state.keys())}")
            print(f"   Metadata: {json.dumps(event.get('metadata'), indent=2)}")
        
        elif event_type == "error":
            print(f"\n❌ Error: {event.get('error')}")

# =========================
# Example 3: Get State
# =========================

def get_thread_state(thread_id: str) -> dict:
    """Get the current state of a thread."""
    url = f"{BASE_URL}/state/{thread_id}"
    
    response = requests.get(url)
    response.raise_for_status()
    
    return response.json()

def example_get_state():
    """Example: Retrieve thread state."""
    print("\n" + "=" * 70)
    print("EXAMPLE 3: Get Thread State")
    print("=" * 70)
    
    # First, create a conversation
    result = chat_sync("What meetings do I have today?")
    thread_id = result['thread_id']
    
    print(f"\nCreated thread: {thread_id}")
    
    # Now retrieve the state
    state_data = get_thread_state(thread_id)
    
    print(f"\nRetrieved State:")
    print(f"  Next Node: {state_data.get('next_node')}")
    print(f"  Message Count: {state_data['metadata']['message_count']}")
    print(f"  State Keys: {list(state_data['state'].keys())}")
    
    # Access specific parts of state
    messages = state_data['state'].get('messages', [])
    print(f"\nConversation History ({len(messages)} messages):")
    for msg in messages:
        print(f"  - {msg['type']}: {msg['content'][:80]}...")

# =========================
# Example 4: List Agents
# =========================

def list_available_agents() -> dict:
    """Get information about available agents."""
    url = f"{BASE_URL}/agents"
    
    response = requests.get(url)
    response.raise_for_status()
    
    return response.json()

def example_list_agents():
    """Example: List available agents."""
    print("\n" + "=" * 70)
    print("EXAMPLE 4: Available Agents")
    print("=" * 70)
    
    agents = list_available_agents()
    
    for agent in agents['agents']:
        print(f"\n📌 {agent['name'].upper()}")
        print(f"   Description: {agent['description']}")
        print(f"   Capabilities:")
        for cap in agent['capabilities']:
            print(f"     • {cap}")
        print(f"   Tools ({len(agent['tools'])}): {', '.join(agent['tools'][:3])}...")

# =========================
# Example 5: Multi-turn Conversation
# =========================

def example_multiturn_conversation():
    """Example: Multi-turn conversation with state persistence."""
    print("\n" + "=" * 70)
    print("EXAMPLE 5: Multi-turn Conversation")
    print("=" * 70)
    
    thread_id = None
    
    conversation = [
        "Check my unread emails",
        "Reply to the first one saying I'll get back to them tomorrow",
        "Now check if I have any meetings today",
        "Book a meeting with John for next Monday at 10 AM"
    ]
    
    for i, message in enumerate(conversation, 1):
        print(f"\n--- Turn {i} ---")
        print(f"User: {message}")
        
        result = chat_sync(message, thread_id=thread_id)
        thread_id = result['thread_id']
        
        print(f"Assistant: {result['response'][:150]}...")
        print(f"Messages in thread: {result['metadata']['message_count']}")

# =========================
# Example 6: Health Check
# =========================

def check_health() -> dict:
    """Check API health status."""
    url = f"{BASE_URL}/health"
    
    response = requests.get(url)
    response.raise_for_status()
    
    return response.json()

def example_health_check():
    """Example: Health check."""
    print("\n" + "=" * 70)
    print("EXAMPLE 6: Health Check")
    print("=" * 70)
    
    health = check_health()
    print(f"\nAPI Status: {health['status']}")
    print(f"Version: {health['version']}")
    print(f"Timestamp: {health['timestamp']}")

# =========================
# Run All Examples
# =========================

def main():
    """Run all examples."""
    try:
        # Check if API is running
        example_health_check()
        
        # Run examples
        example_chat_sync()
        example_chat_stream()
        example_get_state()
        example_list_agents()
        example_multiturn_conversation()
        
        print("\n" + "=" * 70)
        print("✅ All examples completed successfully!")
        print("=" * 70)
        
    except requests.exceptions.ConnectionError:
        print("\n❌ Error: Could not connect to API.")
        print("Make sure the server is running:")
        print("  uvicorn backend.src.api.main:app --reload --port 8000")
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()