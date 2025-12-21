# backend/src/utils/call_session_manager.py

import os
import json
import base64
import wave
import tempfile
import audioop
import asyncio
from typing import Dict, Optional, List
from dataclasses import dataclass, field
from datetime import datetime, timezone

from fastapi import WebSocket
from langchain_core.messages import HumanMessage

from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Connect

from src.config.llm import llm_client


# ---------------------------
# Lazy services (Windows-safe)
# ---------------------------

_whisper_model = None
_whisper_lock = asyncio.Lock()


async def get_whisper_model():
    """Lazy-init Faster-Whisper model on first use (Windows-safe)."""
    global _whisper_model
    if _whisper_model is not None:
        return _whisper_model

    async with _whisper_lock:
        if _whisper_model is None:
            from faster_whisper import WhisperModel
            _whisper_model = WhisperModel("base", device="cpu", compute_type="int8")

    return _whisper_model


def _now_utc():
    return datetime.now(timezone.utc)


def _ws_base_from_public_base_url() -> str:
    """
    PUBLIC_BASE_URL=https://xxxx.ngrok-free.app  -> wss://xxxx.ngrok-free.app
    """
    public = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
    if public.startswith("https://"):
        return "wss://" + public[len("https://"):]
    if public.startswith("http://"):
        return "ws://" + public[len("http://"):]
    return public


def _twilio_client() -> Client:
    # reuse env-loaded values from call_tools
    from src.tools.call_tools import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN
    return Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


# ---------------------------
# Data model
# ---------------------------

@dataclass
class CallSession:
    call_sid: str
    phone_number: str
    call_purpose: str
    context: Dict

    conversation_history: List[Dict] = field(default_factory=list)
    audio_buffer: bytearray = field(default_factory=bytearray)

    start_time: datetime = field(default_factory=_now_utc)
    last_activity: datetime = field(default_factory=_now_utc)
    status: str = "active"

    transcript: List[str] = field(default_factory=list)

    stream_sid: Optional[str] = None

    # Greeting guard
    greeted: bool = False

    # Prevent overlapping speak updates
    speaking: bool = False
    speak_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def add_message(self, role: str, content: str):
        self.conversation_history.append(
            {"role": role, "content": content, "timestamp": _now_utc().isoformat()}
        )
        self.transcript.append(f"{role.upper()}: {content}")
        self.last_activity = _now_utc()

    def get_duration_seconds(self) -> int:
        return int((_now_utc() - self.start_time).total_seconds())

    def get_full_transcript(self) -> str:
        return "\n".join(self.transcript)


# ---------------------------
# Manager
# ---------------------------

class CallSessionManager:
    def __init__(self):
        self.sessions: Dict[str, CallSession] = {}
        self.websockets: Dict[str, WebSocket] = {}

        self.chunk_seconds = 2.5
        self.bytes_threshold = int(8000 * self.chunk_seconds)  # PCMU 8kHz ~8000 bytes/sec

        # avoid responding too often
        self.min_turn_gap_seconds = 1.0
        self._last_response_at: Dict[str, float] = {}

    def create_session(self, call_sid: str, phone_number: str, call_purpose: str, context: Dict) -> CallSession:
        session = CallSession(
            call_sid=call_sid,
            phone_number=phone_number,
            call_purpose=call_purpose,
            context=context or {},
        )
        self.sessions[call_sid] = session
        return session

    def get_session(self, call_sid: str) -> Optional[CallSession]:
        return self.sessions.get(call_sid)

    def end_session(self, call_sid: str) -> Optional[CallSession]:
        session = self.sessions.pop(call_sid, None)
        self.websockets.pop(call_sid, None)
        if session:
            session.status = "completed"
        return session


    def _build_greeting(self, session: CallSession) -> str:
        ctx = session.context or {}
        user_name = ctx.get("user_name", "my user")
        greeting = (
            f"Hello, this is an automated assistant calling on behalf of {user_name}. "
            f"I'm calling to {session.call_purpose}. "
            "Is this a good time to talk?"
        )
        session.add_message("assistant", greeting)
        return greeting

    async def handle_media_stream(self, websocket: WebSocket, call_sid: str):
        """Handle Twilio Media Stream WebSocket connection"""
        print(f"🔌 Accepting WebSocket for call: {call_sid}")
        await websocket.accept()
        
        print(f"✅ WebSocket accepted for: {call_sid}")
        self.websockets[call_sid] = websocket

        # Handle both temp and real call_sids
        session = self.get_session(call_sid)
        
        # If not found with exact match, check if this is a temp_sid scenario
        if not session:
            # Look for TEMP_ sessions (in case WS connects before we update to real SID)
            for sid, sess in self.sessions.items():
                if sid.startswith("TEMP_"):
                    print(f"🔄 Found temp session {sid}, will update to {call_sid}")
                    session = sess
                    # Update session with real call_sid
                    self.sessions[call_sid] = session
                    session.call_sid = call_sid
                    del self.sessions[sid]
                    break
        
        if not session:
            print(f"❌ ERROR: No session found for call_sid: {call_sid}")
            print(f"   Available sessions: {list(self.sessions.keys())}")
            await websocket.close()
            return

        print(f"✅ Session found for {call_sid}")
        print(f"   Purpose: {session.call_purpose}")
        print(f"   Phone: {session.phone_number}")
        print(f"   Status: {session.status}")

        try:
            event_count = 0
            while True:
                raw = await websocket.receive_text()
                event_count += 1
                data = json.loads(raw)
                event_type = data.get("event")

                if event_count <= 5 or event_type != "media":
                    print(f"[WS Event #{event_count}] {event_type} - call={call_sid}")

                if event_type == "connected":
                    print(f"🎉 WebSocket CONNECTED for call: {call_sid}")
                    protocol = data.get("protocol", "unknown")
                    version = data.get("version", "unknown")
                    print(f"   Protocol: {protocol}, Version: {version}")

                elif event_type == "start":
                    print(f"🎙️ Stream STARTED for call: {call_sid}")
                    session.stream_sid = data.get("streamSid")
                    session.status = "active"
                    
                    stream_data = data.get("start", {})
                    print(f"   Stream SID: {session.stream_sid}")
                    print(f"   Account SID: {stream_data.get('accountSid')}")
                    print(f"   Call SID: {stream_data.get('callSid')}")
                    print(f"   Media Format: {stream_data.get('mediaFormat', {})}")
                    
                    # The greeting should already have been said by TwiML
                    # So we just wait for user audio now
                    print(f"🎧 Listening for caller audio...")

                elif event_type == "media":
                    payload = data.get("media", {}).get("payload")
                    if not payload:
                        continue

                    # Ignore audio while we're speaking
                    if session.speaking:
                        continue

                    # Buffer audio
                    session.audio_buffer.extend(base64.b64decode(payload))

                    # Process when we have enough
                    if len(session.audio_buffer) >= self.bytes_threshold:
                        print(f"🎤 Processing audio buffer ({len(session.audio_buffer)} bytes)")
                        await self._process_audio_buffer(session)

                elif event_type == "stop":
                    print(f"🛑 Stream STOPPED for call: {call_sid}")
                    session.status = "completed"
                    break

                elif event_type == "mark":
                    # Mark events are sent after TwiML audio completes
                    mark_name = data.get("mark", {}).get("name")
                    print(f"✅ Mark event: {mark_name}")

        except Exception as e:
            print(f"❌ WebSocket error for {call_sid}: {e}")
            import traceback
            traceback.print_exc()
            session.status = "failed"
        finally:
            try:
                await websocket.close()
            except Exception:
                pass
            print(f"🔌 WebSocket closed for {call_sid}")


    async def _process_audio_buffer(self, session: CallSession):
        """Process accumulated audio buffer: PCMU -> WAV -> Whisper -> LLM -> TTS"""
        if not session.audio_buffer or session.speaking:
            session.audio_buffer.clear()
            return

        print(f"🎵 Processing audio ({len(session.audio_buffer)} bytes)")

        ulaw_bytes = bytes(session.audio_buffer)
        session.audio_buffer.clear()

        # Convert PCMU to PCM16
        pcm16 = audioop.ulaw2lin(ulaw_bytes, 2)

        # Save to temporary WAV file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            wav_path = tmp.name

        try:
            with wave.open(wav_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(8000)
                wf.writeframes(pcm16)

            print(f"💾 Saved audio to: {wav_path}")

            # Transcribe with Whisper
            print(f"🎙️ Transcribing with Whisper...")
            whisper = await get_whisper_model()
            segments, _info = whisper.transcribe(wav_path, language="en")
            text = " ".join(seg.text for seg in segments).strip()

            if not text:
                print(f"⚠️ No text transcribed")
                return

            print(f"📝 Transcribed: '{text}'")
            session.add_message("user", text)

            # Check rate limiting
            now = asyncio.get_event_loop().time()
            last = self._last_response_at.get(session.call_sid, 0.0)
            if (now - last) < self.min_turn_gap_seconds:
                print(f"⏱️ Skipping response (too soon, {now - last:.1f}s < {self.min_turn_gap_seconds}s)")
                return

            # Get LLM response
            print(f"🤖 Getting LLM response...")
            reply = await self._get_llm_response(session)
            if not reply:
                print(f"⚠️ No LLM response generated")
                return

            print(f"💬 LLM Reply: '{reply}'")
            session.add_message("assistant", reply)

            self._last_response_at[session.call_sid] = now

            # Speak response
            await self._speak(session, reply)

        except Exception as e:
            print(f"❌ Error processing audio: {e}")
            import traceback
            traceback.print_exc()

        finally:
            try:
                os.remove(wav_path)
            except Exception:
                pass


    async def _speak(self, session: CallSession, text: str):
        """Speak text to caller using Twilio TwiML update"""
        if not text:
            return

        ws_base = _ws_base_from_public_base_url()
        
        async with session.speak_lock:
            session.speaking = True
            try:
                print(f"🗣️ Speaking to caller: '{text[:100]}...'")
                
                client = _twilio_client()

                # Build TwiML
                vr = VoiceResponse()
                vr.say(text, voice="alice", language="en-US")

                # Reconnect stream after speaking
                connect = Connect()
                connect.stream(url=f"{ws_base}/call/media-stream/{session.call_sid}")
                vr.append(connect)

                twiml_str = str(vr)
                print(f"📄 Updating call with TwiML ({len(twiml_str)} bytes)")

                # Update the live call
                call = client.calls(session.call_sid).update(twiml=twiml_str)
                print(f"✅ Call updated, status: {call.status}")

                # Estimate speech duration
                word_count = len(text.split())
                estimated_duration = max(2.0, word_count / 2.5)
                
                print(f"⏳ Waiting {estimated_duration:.1f}s for speech to complete...")
                await asyncio.sleep(estimated_duration + 1.0)

            except Exception as e:
                print(f"❌ Error speaking: {e}")
                import traceback
                traceback.print_exc()

            finally:
                session.speaking = False
                session.audio_buffer.clear()
                print(f"✅ Speaking complete, listening for response...")



    async def _get_llm_response(self, session: CallSession) -> str:
        """
        Get LLM response based on conversation history.
        Improved with better context and instructions.
        """
        # Build conversation context
        conv_text = "\n".join([
            f"{m['role']}: {m['content']}" 
            for m in session.conversation_history[-10:]  # Last 10 turns
        ])

        prompt = f"""
    You are conducting a phone call with the following purpose: {session.call_purpose}

    Context: {json.dumps(session.context, ensure_ascii=False)}

    Recent conversation:
    {conv_text}

    Instructions:
    - Respond naturally and conversationally
    - Keep responses BRIEF (1-2 sentences maximum)
    - Stay focused on: {session.call_purpose}
    - If user confirms/agrees, acknowledge and prepare to end
    - If user reschedules, note the new time
    - If user declines, thank them and end politely
    - Be professional but friendly

    Your response (brief, 1-2 sentences):
    """.strip()

        try:
            resp = await llm_client.ainvoke([HumanMessage(content=prompt)])
            response_text = (resp.content or "").strip()
            
            # Ensure response isn't too long
            if len(response_text.split()) > 40:
                # Truncate if LLM is too verbose
                words = response_text.split()[:40]
                response_text = " ".join(words) + "..."
            
            return response_text
        except Exception as e:
            print(f"[llm] error: {e}")
            return "Sorry, I'm having technical difficulties. Could you repeat that?"



    def get_call_summary(self, call_sid: str) -> Dict:
        session = self.sessions.get(call_sid)
        if not session:
            return {"error": "Session not found"}

        transcript = session.get_full_transcript().lower()

        outcome = "no_response"
        if any(w in transcript for w in ["yes", "confirm", "correct", "sounds good"]):
            outcome = "confirmed"
        elif any(w in transcript for w in ["reschedule", "change", "different time"]):
            outcome = "rescheduled"
        elif any(w in transcript for w in ["no", "can't", "unable", "cancel"]):
            outcome = "declined"
        elif len(session.conversation_history) > 2:
            outcome = "info_gathered"

        sentiment = "neutral"
        if any(w in transcript for w in ["thank", "great", "perfect", "appreciate"]):
            sentiment = "positive"
        elif any(w in transcript for w in ["sorry", "unfortunately", "problem", "issue"]):
            sentiment = "negative"

        return {
            "call_sid": call_sid,
            "status": session.status,
            "duration_seconds": session.get_duration_seconds(),
            "outcome": outcome,
            "sentiment": sentiment,
            "transcript": session.get_full_transcript(),
            "conversation_turns": len(session.conversation_history),
        }


call_session_manager = CallSessionManager()
