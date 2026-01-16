# backend/src/api.py
import os
import json
import tempfile
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel
from contextlib import asynccontextmanager

from langchain_core.messages import HumanMessage, AIMessageChunk
from langgraph.types import Command

from src.graph.workflow import build_graph
from src.graph.workflow import build_graph
from src.config.memory_config import get_memory_instance
from src.database import create_db_and_tables, add_message, get_messages, clear_messages

from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    app.state.memory = get_memory_instance()
    yield


app = FastAPI(title="Multi-Agent Orchestrator API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten later
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
            "core_messages": [HumanMessage(content=request.message)],
        }
        # Save User Message
        if request.message:
            add_message(thread_id, "user", request.message)

    last_agent = None
    full_response = ""

    try:
        config["recursion_limit"] = 40
        async for msg, metadata in graph.astream(inputs, config, stream_mode="messages"):
            current_agent = metadata.get("langgraph_node", "unknown")
            if current_agent == "_read":
                continue

            if current_agent != last_agent:
                # Save previous agent's response if it was public
                PUBLIC_AGENTS = ("supervisor", "email_agent", "calendar_agent", "sheet_agent", "browser_agent", "deep_research_agent")
                if last_agent in PUBLIC_AGENTS and full_response.strip():
                     # 🛑 CRITICAL: Parse Supervisor JSON to save only the response
                     content_to_save = full_response
                     if last_agent == "supervisor":
                         try:
                             # Find JSON boundaries
                             start = full_response.find("{")
                             end = full_response.rfind("}")
                             if start != -1 and end != -1:
                                 json_str = full_response[start:end+1]
                                 parsed = json.loads(json_str)
                                 if "response" in parsed:
                                     content_to_save = parsed["response"]
                         except:
                             pass
                     
                     add_message(thread_id, "assistant", content_to_save)
                
                full_response = "" # Reset buffer for the new agent
                yield {"event": "agent_start", "data": json.dumps({"agent": current_agent})}
                last_agent = current_agent

            if isinstance(msg, AIMessageChunk) and msg.content:
                full_response += msg.content
                yield {"event": "token", "data": json.dumps({"agent": current_agent, "text": msg.content})}

            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    yield {
                        "event": "tool_call",
                        "data": json.dumps({"agent": current_agent, "tool": tc["name"], "args": tc["args"]}),
                    }

        snapshot = graph.get_state(config)

        if snapshot.next:
            if snapshot.tasks and snapshot.tasks[0].interrupts:
                interrupt_value = snapshot.tasks[0].interrupts[0].value
                yield {"event": "interrupt", "data": json.dumps({"type": "review_required", "payload": str(interrupt_value)})}
        else:
            # Save the VERY LAST agent's response if it was public
            PUBLIC_AGENTS = ("supervisor", "email_agent", "calendar_agent", "sheet_agent", "browser_agent", "deep_research_agent")
            if last_agent in PUBLIC_AGENTS and full_response.strip():
                content_to_save = full_response
                if last_agent == "supervisor":
                    try:
                        start = full_response.find("{")
                        end = full_response.rfind("}")
                        if start != -1 and end != -1:
                            json_str = full_response[start:end+1]
                            parsed = json.loads(json_str)
                            if "response" in parsed:
                                content_to_save = parsed["response"]
                    except:
                        pass
                add_message(thread_id, "assistant", content_to_save)
            yield {"event": "done", "data": "success"}

    except Exception as e:
        print(f"❌ API Error: {e}")
        import traceback
        traceback.print_exc()
        yield {"event": "error", "data": json.dumps({"error": str(e)})}


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    return EventSourceResponse(stream_generator(request))


@app.get("/chat/history")
def get_chat_history(thread_id: str = "default_thread"):
    return get_messages(thread_id, limit=20)


@app.post("/chat/clear")
def clear_chat_history(request: ChatRequest):
    clear_messages(request.thread_id)
    return {"status": "success", "message": "History cleared"}


@app.post("/audio/transcribe")
async def audio_transcribe(
    file: UploadFile = File(...),
    # If you pass "en" from frontend, it forces English and prevents Arabic auto-detect mistakes.
    language: Optional[str] = Form(None),
):
    """
    multipart/form-data:
      - file: audio blob (webm/wav/mp3)
      - language: optional (e.g. "en", "de")
    returns:
      { "text": "..." }
    """
    if not file:
        return {"text": ""}

    content = await file.read()
    print(f"🎙️ /audio/transcribe received: name={file.filename} type={file.content_type} bytes={len(content)}")

    suffix = os.path.splitext(file.filename or "")[1] or ".webm"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp_path = tmp.name
        tmp.write(content)

    try:
        with open(tmp_path, "rb") as f:
            resp = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                language=language,  # IMPORTANT: pass "en" to force English
            )

        text = getattr(resp, "text", None) or ""
        print(f"📝 Transcription length={len(text)} text={text!r}")
        return {"text": text}

    except Exception as e:
        print(f"❌ Transcribe error: {e}")
        return {"text": "", "error": str(e)}

    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass


@app.get("/health")
def health():
    return {"status": "ok"}
