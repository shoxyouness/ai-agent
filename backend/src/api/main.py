# src/api/main.py
import json
import uuid
from typing import Optional
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessageChunk, ToolMessage

# Import the async app
from src.graph.main import app as agent_app

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str
    thread_id: Optional[str] = None
    user_id: str = "default_user"

@app.post("/stream")
async def stream_chat(request: ChatRequest):
    async def event_generator():
        thread_id = request.thread_id or f"thread_{uuid.uuid4().hex[:8]}"
        yield json.dumps({"type": "start", "thread_id": thread_id}) + "\n"

        inputs = {
            "messages": [HumanMessage(content=request.message)],
            "core_messages": [HumanMessage(content=request.message)]
        }
        
        config = {"configurable": {"thread_id": thread_id, "user_id": request.user_id}}

        try:
            # stream_mode="messages" captures LLM tokens and Tool calls
            async for msg, metadata in agent_app.astream(inputs, config, stream_mode="messages"):
                
                node_name = metadata.get("langgraph_node", "unknown")

                # 1. Handle Text Content
                if isinstance(msg, AIMessageChunk) and msg.content:
                    yield json.dumps({
                        "type": "token",
                        "content": msg.content,
                        "node": node_name
                    }) + "\n"

                # 2. Handle Tool Calls (When agent says "Open Calendar")
                # This prevents the "It stops" issue by sending an event
                if isinstance(msg, AIMessageChunk) and msg.tool_calls:
                    for tool in msg.tool_calls:
                        yield json.dumps({
                            "type": "tool_start",
                            "tool_name": tool["name"],
                            "node": node_name
                        }) + "\n"

                # 3. Handle Tool Outputs (When Calendar returns data)
                if isinstance(msg, ToolMessage):
                    yield json.dumps({
                        "type": "tool_end",
                        "output": str(msg.content)[:200] + "...",
                        "node": node_name
                    }) + "\n"

        except Exception as e:
            print(f"Server Error: {e}")
            yield json.dumps({"type": "error", "error": str(e)}) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8009)