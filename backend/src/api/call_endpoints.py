# backend/src/api/call_endpoints.py - COMPLETE FIXED VERSION

import os
from fastapi import APIRouter, WebSocket, Form, Request
from fastapi.responses import Response
from twilio.twiml.voice_response import VoiceResponse, Connect
from src.utils.call_session_manager import call_session_manager
from typing import Optional, Dict, Any
from fastapi import APIRouter
from src.tools.call_tools import initiate_call
from pydantic import BaseModel
router = APIRouter(prefix="/call", tags=["call"])
class StartCallBody(BaseModel):
    to_number: str
    call_purpose: str
    context: Optional[Dict[str, Any]] = None

@router.post("/start")
async def start_call(body: StartCallBody):
    # IMPORTANT: start call inside the SAME uvicorn process
    result = initiate_call.invoke(body.model_dump())
    return result


PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")

def _ws_base_from_public_base_url() -> str:
    """Convert https:// to wss://"""
    if PUBLIC_BASE_URL.startswith("https://"):
        return "wss://" + PUBLIC_BASE_URL[len("https://"):]
    if PUBLIC_BASE_URL.startswith("http://"):
        return "ws://" + PUBLIC_BASE_URL[len("http://"):]
    return PUBLIC_BASE_URL


@router.post("/connect")
async def connect_call_websocket(
    request: Request,
    CallSid: str = Form(...),
    To: str = Form(None),
    From: str = Form(None),
    CallStatus: str = Form(None),
):
    """
    This endpoint is called AFTER the greeting plays.
    It returns TwiML that connects the WebSocket for bidirectional conversation.
    """
    print("\n" + "="*60)
    print("🔗 /call/connect ENDPOINT HIT (Post-Greeting)")
    print("="*60)
    print(f"CallSid: {CallSid}")
    print(f"To: {To}")
    print(f"From: {From}")
    print(f"CallStatus: {CallStatus}")
    
    # Log all form data
    form_data = await request.form()
    print(f"All form data: {dict(form_data)}")
    print("="*60 + "\n")
    
    # Get session
    session = call_session_manager.get_session(CallSid)
    if not session:
        print(f"⚠️ No session found for {CallSid}")
        return Response(
            content="<Response><Say>Session not found</Say><Hangup/></Response>",
            media_type="application/xml"
        )
    
    print(f"✅ Found session for {CallSid}")
    print(f"   Purpose: {session.call_purpose}")
    print(f"   Greeted: {session.greeted}")

    # Build TwiML with WebSocket connection
    ws_base = _ws_base_from_public_base_url()
    
    vr = VoiceResponse()
    connect = Connect()
    stream_url = f"{ws_base}/call/media-stream/{CallSid}"
    print(f"📡 WebSocket Stream URL: {stream_url}")
    connect.stream(url=stream_url)
    vr.append(connect)

    twiml_output = str(vr)
    print(f"📄 TwiML Response ({len(twiml_output)} bytes):")
    print(twiml_output)
    print("\n" + "="*60 + "\n")

    return Response(content=twiml_output, media_type="application/xml")


@router.websocket("/media-stream/{call_sid}")
async def media_stream_websocket(websocket: WebSocket, call_sid: str):
    """
    WebSocket endpoint for Twilio Media Streams.
    Receives real-time audio from the call.
    """
    print("\n" + "="*60)
    print(f"🔌 WebSocket CONNECTION ATTEMPT")
    print(f"   Call SID: {call_sid}")
    print("="*60 + "\n")
    
    try:
        await call_session_manager.handle_media_stream(websocket, call_sid)
    except Exception as e:
        print(f"❌ WebSocket error for {call_sid}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print(f"\n🔌 WebSocket CLOSED for {call_sid}\n")


@router.post("/status")
async def call_status_webhook(
    CallSid: str = Form(...),
    CallStatus: str = Form(...),
    CallDuration: str = Form(None),
    From: str = Form(None),
    To: str = Form(None),
):
    """
    Twilio sends status updates here throughout the call lifecycle.
    """
    print(f"📞 [Status Callback] {CallSid}: {CallStatus} (duration: {CallDuration}s)")
    print(f"   From: {From} → To: {To}")
    
    session = call_session_manager.get_session(CallSid)
    
    if CallStatus in ["completed", "failed", "busy", "no-answer"]:
        if session:
            session.status = CallStatus
            print(f"✅ Updated session status to: {CallStatus}")
        else:
            print(f"⚠️ No session found for {CallSid}")
    
    return {"status": "received"}


@router.get("/session/{call_sid}")
async def get_session_status(call_sid: str):
    """Debug endpoint to check session status"""
    session = call_session_manager.get_session(call_sid)
    if not session:
        return {"error": "Session not found", "call_sid": call_sid}
    
    return {
        "call_sid": call_sid,
        "status": session.status,
        "duration_seconds": session.get_duration_seconds(),
        "conversation_turns": len(session.conversation_history),
        "greeted": session.greeted,
        "speaking": session.speaking,
        "has_websocket": call_sid in call_session_manager.websockets,
        "phone_number": session.phone_number,
        "call_purpose": session.call_purpose,
        "last_activity": session.last_activity.isoformat(),
        "recent_conversation": session.conversation_history[-3:] if session.conversation_history else [],
    }


@router.get("/sessions")
async def list_sessions():
    """Debug endpoint to list all active sessions"""
    sessions = []
    for sid, session in call_session_manager.sessions.items():
        sessions.append({
            "call_sid": sid,
            "status": session.status,
            "duration": session.get_duration_seconds(),
            "turns": len(session.conversation_history),
            "phone": session.phone_number,
            "purpose": session.call_purpose,
            "has_ws": sid in call_session_manager.websockets,
        })
    
    return {
        "count": len(sessions),
        "sessions": sessions,
        "websockets_count": len(call_session_manager.websockets),
    }


@router.get("/test")
async def test_endpoint():
    """Test endpoint to verify the API is working"""
    return {
        "status": "ok",
        "message": "Call endpoints are working",
        "public_base_url": PUBLIC_BASE_URL,
        "ws_base": _ws_base_from_public_base_url(),
    }