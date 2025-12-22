# src/api.py
import uvicorn
import json
import asyncio
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any

from langchain_core.messages import HumanMessage, AIMessageChunk, ToolMessage
from langgraph.types import Command

# Import your graph builder
from src.graph.workflow import build_graph

app = FastAPI(title="Multi-Agent Orchestrator API")

# Allow CORS for your Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load the Graph
graph = build_graph()

# --- Request Models ---
class ChatRequest(BaseModel):
    message: Optional[str] = None
    thread_id: str = "default_thread"
    resume_action: Optional[str] = None  # User's approval/feedback (e.g., "approved")

# --- Stream Generator ---
async def stream_generator(request: ChatRequest):
    """
    Yields SSE events:
    - agent_start: When a new agent takes the floor.
    - token: Real-time text output.
    - tool_call: When a tool is invoked.
    - interrupt: When human review is needed.
    - done: When the workflow finishes.
    """
    thread_id = request.thread_id
    config = {"configurable": {"thread_id": thread_id}}
    
    # 1. Determine Input (New Message OR Resume Command)
    if request.resume_action:
        # We are resuming from an interrupt (Reviewer)
        print(f"🔄 Resuming thread {thread_id} with action: {request.resume_action}")
        inputs = Command(resume=request.resume_action)
    else:
        # We are starting a new turn
        print(f"▶️ Starting new turn for thread {thread_id}")
        inputs = {
            "messages": [HumanMessage(content=request.message)],
            "core_messages": [HumanMessage(content=request.message)]
        }

    last_agent = None

    try:
        # 2. Stream the Graph
        async for msg, metadata in graph.astream(inputs, config, stream_mode="messages"):
            
            # --- Detect Active Agent ---
            current_agent = metadata.get("langgraph_node", "unknown")
            
            # Filter out internal LangGraph nodes if you want cleaner UI
            if current_agent == "_read": continue 
            
            if current_agent != last_agent:
                yield {
                    "event": "agent_start",
                    "data": json.dumps({"agent": current_agent})
                }
                last_agent = current_agent

            # --- Stream Content (Tokens) ---
            if isinstance(msg, AIMessageChunk) and msg.content:
                yield {
                    "event": "token",
                    "data": json.dumps({
                        "agent": current_agent,
                        "text": msg.content
                    })
                }
            
            # --- Stream Tool Calls (Optional visualization) ---
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    yield {
                        "event": "tool_call",
                        "data": json.dumps({
                            "agent": current_agent,
                            "tool": tc["name"],
                            "args": tc["args"]
                        })
                    }

        # 3. Check for Interrupts (Human-in-the-Loop)
        # We check the state after the stream finishes (or pauses)
        snapshot = graph.get_state(config)
        
        if snapshot.next:
            # Check if there is an interrupt payload available
            if snapshot.tasks and snapshot.tasks[0].interrupts:
                interrupt_value = snapshot.tasks[0].interrupts[0].value
                print(f"⚠️ Interrupt detected: {interrupt_value}")
                
                yield {
                    "event": "interrupt",
                    "data": json.dumps({
                        "type": "review_required",
                        "payload": str(interrupt_value) # The Draft Email Text
                    })
                }
            else:
                # Just a standard pause or transition
                pass
        else:
            # Workflow complete
            yield {"event": "done", "data": "success"}

    except Exception as e:
        print(f"❌ API Error: {e}")
        yield {
            "event": "error",
            "data": json.dumps({"error": str(e)})
        }

# --- Endpoints ---

@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    Main endpoint for Frontend.
    Use POST to send data, returns an SSE stream.
    """
    return EventSourceResponse(stream_generator(request))

@app.get("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run("src.api.api:app", host="0.0.0.0", port=8000, reload=True)