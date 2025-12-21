"""
FastAPI server for the Multi-Agent System
Provides REST API endpoints for web interface interaction
"""
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import asyncio
import json
from langchain_core.messages import HumanMessage, AIMessage

# Import your multi-agent system
from src.graph.main import app as multi_agent_app, get_agent_by_name
from src.agents import (
    email_agent,
    calendar_agent,
    sheet_agent,
    supervisor_agent,
    memory_agent,
)
from src.tools.memory_tools import search_memory, get_all_memories
from src.utils.memory_manager import get_memory_manager

# Initialize FastAPI
api = FastAPI(
    title="Multi-Agent Personal Assistant API",
    description="REST API for interacting with the multi-agent system",
    version="1.0.0"
)

# CORS middleware for web interface
api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# Request/Response Models
# ============================================================

class ChatRequest(BaseModel):
    message: str = Field(..., description="User message to send to the agent")
    thread_id: Optional[str] = Field(None, description="Thread ID for conversation continuity")

class ChatResponse(BaseModel):
    response: str = Field(..., description="Agent's response")
    thread_id: str = Field(..., description="Thread ID for this conversation")
    supervisor_thoughts: Optional[str] = Field(None, description="Supervisor's reasoning")
    route_taken: Optional[str] = Field(None, description="Which agent was used")
    timestamp: str = Field(..., description="Response timestamp")

class AgentInfo(BaseModel):
    name: str
    description: str
    capabilities: List[str]
    tools: List[str]
    temperature: float

class SystemStatus(BaseModel):
    status: str
    agents: List[str]
    timestamp: str

class MemorySearchRequest(BaseModel):
    query: str = Field(..., description="Search query for memories")
    limit: int = Field(5, description="Maximum number of results")

class MemoryAddRequest(BaseModel):
    content: str = Field(..., description="Memory content to store")
    category: Optional[str] = Field(None, description="Memory category")
    importance: Optional[str] = Field(None, description="Importance level")

class ConversationHistoryResponse(BaseModel):
    thread_id: str
    messages: List[Dict[str, Any]]
    message_count: int

# ============================================================
# In-memory storage for demo (use Redis/DB in production)
# ============================================================
conversation_store: Dict[str, List[Dict[str, Any]]] = {}

# ============================================================
# Helper Functions
# ============================================================

def get_or_create_thread_id(thread_id: Optional[str] = None) -> str:
    """Get existing thread ID or create a new one"""
    if thread_id and thread_id in conversation_store:
        return thread_id
    new_id = f"thread_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
    conversation_store[new_id] = []
    return new_id

def store_message(thread_id: str, role: str, content: str, metadata: Optional[Dict] = None):
    """Store a message in conversation history"""
    if thread_id not in conversation_store:
        conversation_store[thread_id] = []
    
    message = {
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat(),
        "metadata": metadata or {}
    }
    conversation_store[thread_id].append(message)

def extract_response_data(agent_response: Dict[str, Any], snapshot: Any) -> Dict[str, Any]:
    """Extract useful information from agent response"""
    # Get supervisor response
    supervisor_response = agent_response.get("supervisor_response") or \
                         snapshot.values.get("supervisor_response")
    
    # Get final message
    if "messages" in agent_response and agent_response["messages"]:
        final_message = agent_response["messages"][-1]
        final_text = final_message.content if hasattr(final_message, 'content') else str(final_message)
    else:
        final_text = supervisor_response or "No response generated"
    
    # Get route information
    route = snapshot.values.get("route", "unknown")
    
    return {
        "response": supervisor_response or final_text,
        "route_taken": route,
        "supervisor_thoughts": snapshot.values.get("supervisor_response"),
        "state_info": {
            "email_response": snapshot.values.get("email_agent_response"),
            "calendar_response": snapshot.values.get("calendar_agent_response"),
            "sheet_response": snapshot.values.get("sheet_agent_response"),
        }
    }

# ============================================================
# API Endpoints
# ============================================================

@api.get("/", tags=["System"])
async def root():
    """Root endpoint with API information"""
    return {
        "name": "Multi-Agent Personal Assistant API",
        "version": "1.0.0",
        "status": "operational",
        "endpoints": {
            "chat": "/api/chat",
            "agents": "/api/agents",
            "status": "/api/status",
            "memory": "/api/memory",
            "history": "/api/history/{thread_id}"
        }
    }

@api.get("/api/status", response_model=SystemStatus, tags=["System"])
async def get_status():
    """Get system status and available agents"""
    agents = [
        email_agent.name,
        calendar_agent.name,
        sheet_agent.name,
        supervisor_agent.name,
        memory_agent.name
    ]
    
    return SystemStatus(
        status="operational",
        agents=agents,
        timestamp=datetime.now().isoformat()
    )

@api.get("/api/agents", response_model=List[AgentInfo], tags=["Agents"])
async def get_agents():
    """Get information about all available agents"""
    agents = [email_agent, calendar_agent, sheet_agent, supervisor_agent, memory_agent]
    
    return [
        AgentInfo(
            name=agent.name,
            description=agent.get_description(),
            capabilities=agent.get_capabilities(),
            tools=[tool.name for tool in agent.tools],
            temperature=agent.temperature
        )
        for agent in agents
    ]

@api.get("/api/agents/{agent_name}", response_model=AgentInfo, tags=["Agents"])
async def get_agent_info(agent_name: str):
    """Get detailed information about a specific agent"""
    agent = get_agent_by_name(agent_name)
    
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")
    
    return AgentInfo(
        name=agent.name,
        description=agent.get_description(),
        capabilities=agent.get_capabilities(),
        tools=[tool.name for tool in agent.tools],
        temperature=agent.temperature
    )

class StreamEvent(BaseModel):
    event_type: str = Field(..., description="Type of event: 'agent_start', 'agent_thinking', 'agent_complete', 'tool_call', 'final_response'")
    agent_name: Optional[str] = Field(None, description="Name of the agent")
    content: str = Field(..., description="Event content")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    timestamp: str = Field(..., description="Event timestamp")

@api.post("/api/chat/stream", tags=["Chat"])
async def chat_stream(request: ChatRequest):
    """
    Stream the multi-agent processing in real-time
    Returns Server-Sent Events (SSE) with processing updates
    """
    from fastapi.responses import StreamingResponse
    import json
    
    async def event_generator():
        try:
            thread_id = get_or_create_thread_id(request.thread_id)
            
            # Send initial event
            yield f"data: {json.dumps({'event_type': 'start', 'content': 'Processing your request...', 'timestamp': datetime.now().isoformat()})}\n\n"
            
            inputs = {
                "messages": [HumanMessage(content=request.message)],
                "core_messages": [HumanMessage(content=request.message)]
            }
            
            config = {"configurable": {"thread_id": thread_id}}
            
            # Stream through the graph
            last_node = None
            for event in multi_agent_app.stream(inputs, config=config):
                for node_name, node_data in event.items():
                    if node_name == "__start__" or node_name == "__end__":
                        continue
                    
                    # Detect agent transitions
                    if node_name != last_node:
                        agent_display_name = node_name.replace("_", " ").title()
                        
                        # Agent started
                        event_data = {
                            "event_type": "agent_start",
                            "agent_name": node_name,
                            "content": f"🤖 {agent_display_name} is working...",
                            "timestamp": datetime.now().isoformat()
                        }
                        yield f"data: {json.dumps(event_data)}\n\n"
                        await asyncio.sleep(0.1)
                        last_node = node_name
                    
                    # Check for supervisor thoughts
                    if node_name == "supervisor" and "messages" in node_data:
                        messages = node_data.get("messages", [])
                        if messages:
                            last_msg = messages[-1] if isinstance(messages, list) else messages
                            if hasattr(last_msg, 'content'):
                                event_data = {
                                    "event_type": "supervisor_thinking",
                                    "agent_name": "supervisor",
                                    "content": last_msg.content,
                                    "metadata": {
                                        "route": node_data.get("route"),
                                    },
                                    "timestamp": datetime.now().isoformat()
                                }
                                yield f"data: {json.dumps(event_data)}\n\n"
                                await asyncio.sleep(0.1)
                    
                    # Check for tool calls
                    if "messages" in node_data:
                        messages = node_data.get("messages", [])
                        if messages:
                            last_msg = messages[-1] if isinstance(messages, list) else messages
                            if hasattr(last_msg, 'tool_calls') and last_msg.tool_calls:
                                for tool_call in last_msg.tool_calls:
                                    tool_name = tool_call.get('name') if isinstance(tool_call, dict) else getattr(tool_call, 'name', 'unknown')
                                    event_data = {
                                        "event_type": "tool_call",
                                        "agent_name": node_name,
                                        "content": f"🔧 Using tool: {tool_name}",
                                        "metadata": {"tool_name": tool_name},
                                        "timestamp": datetime.now().isoformat()
                                    }
                                    yield f"data: {json.dumps(event_data)}\n\n"
                                    await asyncio.sleep(0.1)
                    
                    # Check for agent responses
                    agent_response_keys = [
                        "email_agent_response",
                        "calendar_agent_response", 
                        "sheet_agent_response",
                        "memory_agent_response"
                    ]
                    
                    for key in agent_response_keys:
                        if key in node_data and node_data[key]:
                            agent_name = key.replace("_response", "").replace("_", " ").title()
                            event_data = {
                                "event_type": "agent_complete",
                                "agent_name": key.replace("_response", ""),
                                "content": f"✅ {agent_name} completed",
                                "metadata": {"response": node_data[key][:200] + "..." if len(node_data[key]) > 200 else node_data[key]},
                                "timestamp": datetime.now().isoformat()
                            }
                            yield f"data: {json.dumps(event_data)}\n\n"
                            await asyncio.sleep(0.1)
            
            # Get final state
            snapshot = multi_agent_app.get_state(config=config)
            supervisor_response = snapshot.values.get("supervisor_response", "Task completed")
            
            # Send final response
            event_data = {
                "event_type": "final_response",
                "agent_name": "supervisor",
                "content": supervisor_response,
                "metadata": {
                    "thread_id": thread_id,
                    "route": snapshot.values.get("route")
                },
                "timestamp": datetime.now().isoformat()
            }
            yield f"data: {json.dumps(event_data)}\n\n"
            
        except Exception as e:
            error_data = {
                "event_type": "error",
                "content": f"Error: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }
            yield f"data: {json.dumps(error_data)}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@api.post("/api/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(request: ChatRequest):
    """
    Send a message to the multi-agent system and get a response
    
    This endpoint handles the full conversation flow:
    1. Routes the message through the supervisor
    2. Delegates to appropriate specialized agents
    3. Returns the final response with metadata
    """
    try:
        # Get or create thread ID
        thread_id = get_or_create_thread_id(request.thread_id)
        
        # Store user message
        store_message(thread_id, "user", request.message)
        
        # Prepare input for multi-agent system
        inputs = {
            "messages": [HumanMessage(content=request.message)],
            "core_messages": [HumanMessage(content=request.message)]
        }
        
        config = {"configurable": {"thread_id": thread_id}}
        
        # Invoke multi-agent system
        agent_response = multi_agent_app.invoke(input=inputs, config=config)
        snapshot = multi_agent_app.get_state(config=config)
        
        # Extract response data
        response_data = extract_response_data(agent_response, snapshot)
        
        # Store assistant message
        store_message(
            thread_id, 
            "assistant", 
            response_data["response"],
            metadata={
                "route": response_data["route_taken"],
                "supervisor_thoughts": response_data["supervisor_thoughts"]
            }
        )
        
        return ChatResponse(
            response=response_data["response"],
            thread_id=thread_id,
            supervisor_thoughts=response_data["supervisor_thoughts"],
            route_taken=response_data["route_taken"],
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")

@api.get("/api/history/{thread_id}", response_model=ConversationHistoryResponse, tags=["Chat"])
async def get_conversation_history(thread_id: str):
    """Get conversation history for a specific thread"""
    if thread_id not in conversation_store:
        raise HTTPException(status_code=404, detail=f"Thread '{thread_id}' not found")
    
    messages = conversation_store[thread_id]
    
    return ConversationHistoryResponse(
        thread_id=thread_id,
        messages=messages,
        message_count=len(messages)
    )

@api.delete("/api/history/{thread_id}", tags=["Chat"])
async def clear_conversation_history(thread_id: str):
    """Clear conversation history for a specific thread"""
    if thread_id not in conversation_store:
        raise HTTPException(status_code=404, detail=f"Thread '{thread_id}' not found")
    
    conversation_store[thread_id] = []
    return {"message": f"Conversation history cleared for thread '{thread_id}'"}

@api.get("/api/threads", tags=["Chat"])
async def list_threads():
    """List all active conversation threads"""
    threads = []
    for thread_id, messages in conversation_store.items():
        threads.append({
            "thread_id": thread_id,
            "message_count": len(messages),
            "last_activity": messages[-1]["timestamp"] if messages else None
        })
    
    return {"threads": threads, "total": len(threads)}

# ============================================================
# Memory Endpoints
# ============================================================

@api.post("/api/memory/search", tags=["Memory"])
async def search_memories(request: MemorySearchRequest):
    """Search long-term memory for relevant information"""
    try:
        result = search_memory.invoke({
            "query": request.query,
            "limit": request.limit
        })
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching memories: {str(e)}")

@api.post("/api/memory/add", tags=["Memory"])
async def add_memory(request: MemoryAddRequest):
    """Add new information to long-term memory"""
    try:
        memory_manager = get_memory_manager()
        metadata = {}
        if request.category:
            metadata['category'] = request.category
        if request.importance:
            metadata['importance'] = request.importance
        
        result = memory_manager.add_memory(request.content, metadata=metadata if metadata else None)
        return {"message": "Memory added successfully", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error adding memory: {str(e)}")

@api.get("/api/memory/all", tags=["Memory"])
async def get_all_memory():
    """Retrieve all stored memories"""
    try:
        result = get_all_memories.invoke({})
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving memories: {str(e)}")

# ============================================================
# WebSocket for Real-time Chat
# ============================================================

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

manager = ConnectionManager()

@api.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """
    WebSocket endpoint for real-time chat
    Send JSON: {"message": "your message", "thread_id": "optional_thread_id"}
    """
    await manager.connect(websocket)
    thread_id = None
    
    try:
        while True:
            # Receive message
            data = await websocket.receive_text()
            request_data = json.loads(data)
            
            user_message = request_data.get("message")
            thread_id = request_data.get("thread_id") or get_or_create_thread_id()
            
            # Send acknowledgment
            await manager.send_message(
                json.dumps({"status": "processing", "thread_id": thread_id}),
                websocket
            )
            
            # Process with multi-agent system
            inputs = {
                "messages": [HumanMessage(content=user_message)],
                "core_messages": [HumanMessage(content=user_message)]
            }
            
            config = {"configurable": {"thread_id": thread_id}}
            agent_response = multi_agent_app.invoke(input=inputs, config=config)
            snapshot = multi_agent_app.get_state(config=config)
            
            response_data = extract_response_data(agent_response, snapshot)
            
            # Send response
            await manager.send_message(
                json.dumps({
                    "status": "complete",
                    "response": response_data["response"],
                    "thread_id": thread_id,
                    "route": response_data["route_taken"],
                    "timestamp": datetime.now().isoformat()
                }),
                websocket
            )
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        await manager.send_message(
            json.dumps({"status": "error", "message": str(e)}),
            websocket
        )
        manager.disconnect(websocket)

# ============================================================
# Health Check
# ============================================================

@api.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "agents_loaded": 5,
        "active_threads": len(conversation_store)
    }

# ============================================================
# Run Server
# ============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api:api",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )