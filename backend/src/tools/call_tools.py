# backend/src/tools/call_tools.py - FINAL FIX: Complete TwiML from the start

import os
import re
import json
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Connect

from src.utils.call_session_manager import call_session_manager
from dotenv import load_dotenv
load_dotenv()


# ---------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------

E164_REGEX = re.compile(r"^\+[1-9]\d{7,14}$")

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "").strip()
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")


def _ws_base_from_public_base_url() -> str:
    """Convert https:// to wss://"""
    if PUBLIC_BASE_URL.startswith("https://"):
        return "wss://" + PUBLIC_BASE_URL[len("https://"):]
    if PUBLIC_BASE_URL.startswith("http://"):
        return "ws://" + PUBLIC_BASE_URL[len("http://"):]
    return PUBLIC_BASE_URL


def _require_env(name: str, value: str) -> None:
    if not value:
        raise RuntimeError(f"Missing required env var {name}. Set it in your .env")


def _twilio_client() -> Client:
    _require_env("TWILIO_ACCOUNT_SID", TWILIO_ACCOUNT_SID)
    _require_env("TWILIO_AUTH_TOKEN", TWILIO_AUTH_TOKEN)
    return Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


def _validate_e164(phone_number: str) -> None:
    if not E164_REGEX.match(phone_number.strip()):
        raise ValueError(
            f"Invalid phone number format: {phone_number}. "
            f"Use E.164 format like +491234567890."
        )


# ---------------------------------------------------------------------
# Tool input schemas
# ---------------------------------------------------------------------

class InitiateCallArgs(BaseModel):
    to_number: str = Field(..., description="Recipient number in E.164 format")
    call_purpose: str = Field(..., description="Reason for the call")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Optional extra context")


class EndCallArgs(BaseModel):
    call_sid: str = Field(..., description="Twilio CallSid")


class GetSummaryArgs(BaseModel):
    call_sid: str = Field(..., description="CallSid to retrieve summary for")


# ---------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------

@tool("initiate_call", args_schema=InitiateCallArgs)
def initiate_call(
    to_number: str,
    call_purpose: str,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Initiate an outbound phone call via Twilio with complete inline TwiML.
    
    Strategy:
    1. Build complete TwiML (greeting + WebSocket) BEFORE creating call
    2. Use a callback URL that will handle dynamic call_sid mapping
    3. Create call with the complete TwiML
    4. Register session immediately after getting call_sid
    """

    # Normalize inputs
    if context is None:
        context = {}
    elif not isinstance(context, dict):
        try:
            context = json.loads(context)
        except Exception:
            context = {}

    context.setdefault("user_name", "Younes")

    # Validate
    _require_env("TWILIO_FROM_NUMBER", TWILIO_FROM_NUMBER)
    _require_env("PUBLIC_BASE_URL", PUBLIC_BASE_URL)
    _validate_e164(to_number)

    print(f"\n{'='*70}")
    print(f"📞 INITIATING CALL WITH COMPLETE TWIML")
    print(f"{'='*70}")
    print(f"To: {to_number}")
    print(f"From: {TWILIO_FROM_NUMBER}")
    print(f"Purpose: {call_purpose}")
    print(f"Context: {context}")
    print(f"{'='*70}\n")

    # Build greeting
    user_name = context.get("user_name", "my user")
    greeting = (
        f"Hello, this is an automated assistant calling on behalf of {user_name}. "
        f"I'm calling to {call_purpose}. "
        "Is this a good time to talk?"
    )
    
    print(f"🗣️ Greeting: {greeting}\n")

    # Build WebSocket base URL
    ws_base = _ws_base_from_public_base_url()
    
    # CRITICAL: Use the callback endpoint that will handle any call_sid
    # We'll use a special endpoint that redirects to the correct WebSocket
    callback_url = f"{PUBLIC_BASE_URL}/call/connect"
    
    print(f"📡 Using callback URL: {callback_url}\n")
    
    # Build TwiML that requests the callback URL
    # This URL will be called AFTER the call is answered with the real call_sid
    vr = VoiceResponse()
    vr.pause(length=1)
    vr.say(greeting, voice="alice", language="en-US")
    vr.redirect(callback_url, method="POST")
    
    twiml_str = str(vr)
    print(f"📄 Initial TwiML ({len(twiml_str)} bytes):")
    print(twiml_str)
    print()

    # Create Twilio call with complete TwiML
    client = _twilio_client()
    
    status_url = f"{PUBLIC_BASE_URL}/call/status" if PUBLIC_BASE_URL else None
    
    create_kwargs: Dict[str, Any] = {
        "to": to_number,
        "from_": TWILIO_FROM_NUMBER,
        "twiml": twiml_str,  # Complete TwiML with greeting
    }

    if status_url:
        create_kwargs["status_callback"] = status_url
        create_kwargs["status_callback_event"] = ["initiated", "ringing", "answered", "completed"]
        create_kwargs["status_callback_method"] = "POST"

    print(f"🚀 Creating Twilio call...")
    call = client.calls.create(**create_kwargs)
    call_sid = call.sid

    print(f"✅ Twilio call created: {call_sid}")
    print(f"   Status: {call.status}\n")

    # Register session with REAL call_sid
    session = call_session_manager.create_session(
        call_sid=call_sid,
        phone_number=to_number,
        call_purpose=call_purpose,
        context=context,
    )
    session.add_message("assistant", greeting)
    
    print(f"✅ Session registered: {call_sid}\n")

    print(f"{'='*70}")
    print(f"✅ CALL SETUP COMPLETE")
    print(f"   Call SID: {call_sid}")
    print(f"   1. Greeting will play when answered")
    print(f"   2. Then Twilio will request: {callback_url}")
    print(f"   3. We'll connect WebSocket for conversation")
    print(f"{'='*70}\n")

    return {
        "ok": True,
        "call_sid": call_sid,
        "to": to_number,
        "from": TWILIO_FROM_NUMBER,
        "status": call.status,
        "call_purpose": call_purpose,
        "message": f"Call initiated to {to_number}. Greeting: '{greeting[:50]}...'",
    }


@tool("end_call", args_schema=EndCallArgs)
def end_call(call_sid: str) -> Dict[str, Any]:
    """End an ongoing call via Twilio (hang up)."""
    client = _twilio_client()

    try:
        call = client.calls(call_sid).update(status="completed")
    except Exception as e:
        return {"ok": False, "call_sid": call_sid, "error": str(e)}

    call_session_manager.end_session(call_sid)

    return {
        "ok": True,
        "call_sid": call_sid,
        "status": getattr(call, "status", "completed"),
        "message": "Call ended.",
    }


@tool("get_call_summary", args_schema=GetSummaryArgs)
def get_call_summary(call_sid: str) -> Dict[str, Any]:
    """Retrieve the structured summary for a call."""
    return call_session_manager.get_call_summary(call_sid)


@tool("list_active_call_sessions")
def list_active_call_sessions() -> Dict[str, Any]:
    """List currently active call sessions."""
    sessions: List[Dict[str, Any]] = []
    for sid, s in call_session_manager.sessions.items():
        sessions.append({
            "call_sid": sid,
            "phone_number": s.phone_number,
            "purpose": s.call_purpose,
            "duration_seconds": s.get_duration_seconds(),
            "status": s.status,
            "turns": len(s.conversation_history),
        })
    return {"active_sessions": len(sessions), "sessions": sessions}


CALL_TOOLS = [
    initiate_call,
    end_call,
    get_call_summary,
    list_active_call_sessions,
]