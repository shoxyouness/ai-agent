from elevenlabs.client import ElevenLabs
from elevenlabs import VoiceSettings  
import os

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
if not ELEVENLABS_API_KEY:
    raise RuntimeError("ELEVENLABS_API_KEY not set in .env")


AUDIO_INPUT_PATH = "src/audio/audio.mp3"
AUDIO_OUTPUT_PATH = "src/audio/response.mp3"


eleven_client = ElevenLabs(api_key=ELEVENLABS_API_KEY)


def transcribe_audio_file(path: str) -> str:
    """
    Use ElevenLabs Speech-to-Text (Scribe) to transcribe an audio file to text.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Audio file not found: {path}")

    with open(path, "rb") as f:
        audio_bytes = f.read()

    # Scribe v1 model – works well for generic audio
    transcription = eleven_client.speech_to_text.convert(
        model_id="scribe_v1",
        file=audio_bytes,
        # you can hint the language if you want:
        # language_code="de"  # or "en"
    )

    # transcription.text contains the plain text
    return transcription.text

def tts_to_file(text: str, out_path: str = AUDIO_OUTPUT_PATH) -> str:
    """
    Use ElevenLabs Text-to-Speech to synthesize the agent's answer to an MP3 file.
    Returns the output path.
    """
    VOICE_ID = os.getenv("VOICE_ID")

    audio_stream = eleven_client.text_to_speech.convert(
        text=text,
        voice_id=VOICE_ID,
        model_id="eleven_multilingual_v2",  # good general model
        output_format="mp3_22050_32",
        voice_settings=VoiceSettings(
            stability=0.4,
            similarity_boost=0.8,
            style=0.0,
            use_speaker_boost=True,
            speed=1.0,
        ),
    )

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "wb") as f:
        for chunk in audio_stream:
            if isinstance(chunk, bytes):
                f.write(chunk)

    return out_path

