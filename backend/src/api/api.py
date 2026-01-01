# src/api.py
import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel
from typing import Optional

from langchain_core.messages import HumanMessage, AIMessageChunk
from langgraph.types import Command

# Import your graph builder
from src.graph.workflow import build_graph
from fastapi import FastAPI
from contextlib import asynccontextmanager
from src.config.memory_config import get_memory_instance

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.memory = get_memory_instance()  
    yield


app = FastAPI(title="Multi-Agent Orchestrator API",lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

graph = build_graph()

class ChatRequest(BaseModel):
    message: Optional[str] = None
    thread_id: str = "default_thread"
    resume_action: Optional[str] = None

async def stream_generator(request: ChatRequest):
    thread_id = request.thread_id
    config = {"configurable": {"thread_id": thread_id}}
    
    if request.resume_action:
        print(f"🔄 Resuming thread {thread_id} with action: {request.resume_action}")
        inputs = Command(resume=request.resume_action)
    else:
        print(f"▶️ Starting new turn for thread {thread_id}")
        inputs = {
            "messages": [HumanMessage(content=request.message)],
            "core_messages": [HumanMessage(content=request.message)]
        }

    last_agent = None

    try:
        async for msg, metadata in graph.astream(inputs, config, stream_mode="messages"):
            current_agent = metadata.get("langgraph_node", "unknown")
            if current_agent == "_read": continue 
            
            if current_agent != last_agent:
                yield {"event": "agent_start", "data": json.dumps({"agent": current_agent})}
                last_agent = current_agent

            if isinstance(msg, AIMessageChunk) and msg.content:
                yield {"event": "token", "data": json.dumps({"agent": current_agent, "text": msg.content})}
            
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    yield {"event": "tool_call", "data": json.dumps({"agent": current_agent, "tool": tc["name"], "args": tc["args"]})}

        snapshot = graph.get_state(config)
        
        if snapshot.next:
            if snapshot.tasks and snapshot.tasks[0].interrupts:
                interrupt_value = snapshot.tasks[0].interrupts[0].value
                yield {"event": "interrupt", "data": json.dumps({"type": "review_required", "payload": str(interrupt_value)})}
        else:
            yield {"event": "done", "data": "success"}

    except Exception as e:
        print(f"❌ API Error: {e}")
        import traceback
        traceback.print_exc()
        yield {"event": "error", "data": json.dumps({"error": str(e)})}

@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    return EventSourceResponse(stream_generator(request))

@app.get("/health")
def health():
    return {"status": "ok"}