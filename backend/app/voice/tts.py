"""
Text-to-Speech using local options.
Supports multiple backends: pyttsx3 (built-in), gTTS (Google), or system TTS.

For the lightweight stack, we use pyttsx3 which works offline.
For better quality, you can install piper-tts or use gTTS (requires internet).
"""
import io
import tempfile
from pathlib import Path
from typing import Optional
import asyncio

from app.config import settings

# Available TTS backends
TTS_BACKEND = "pyttsx3"  # Options: "pyttsx3", "gtts", "piper"


def synthesize_pyttsx3(text: str, rate: int = 150) -> bytes:
    """
    Synthesize speech using pyttsx3 (offline, cross-platform).
    Works on macOS, Windows, and Linux without additional setup.
    """
    import pyttsx3
    
    engine = pyttsx3.init()
    engine.setProperty('rate', rate)
    
    # Save to temp file
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
        tmp_path = tmp_file.name
    
    try:
        engine.save_to_file(text, tmp_path)
        engine.runAndWait()
        
        # Read the file
        with open(tmp_path, 'rb') as f:
            audio_bytes = f.read()
        
        return audio_bytes
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def synthesize_gtts(text: str, lang: str = "en") -> bytes:
    """
    Synthesize speech using Google TTS (requires internet).
    Better quality than pyttsx3 but needs network.
    """
    from gtts import gTTS
    
    tts = gTTS(text=text, lang=lang, slow=False)
    
    # Save to bytes
    audio_buffer = io.BytesIO()
    tts.write_to_fp(audio_buffer)
    audio_buffer.seek(0)
    
    return audio_buffer.read()


def synthesize_text(text: str, voice: str = None) -> bytes:
    """
    Main TTS function - synthesizes text to audio bytes.
    
    Args:
        text: The text to synthesize
        voice: Voice identifier (backend-specific)
    
    Returns:
        Audio bytes (WAV or MP3 format depending on backend)
    """
    if not text or not text.strip():
        raise ValueError("Text cannot be empty")
    
    # Try gTTS first (better quality, MP3 format works in browsers)
    # Fall back to pyttsx3 if no internet
    backends = ["gtts", "pyttsx3"]
    
    for backend in backends:
        try:
            if backend == "gtts":
                return synthesize_gtts(text)
            elif backend == "pyttsx3":
                return synthesize_pyttsx3(text)
        except ImportError:
            continue
        except Exception as e:
            print(f"TTS backend {backend} failed: {e}")
            continue
    
    raise RuntimeError("No TTS backend available. Install pyttsx3 or gtts.")


async def synthesize(text: str, voice: str = None) -> bytes:
    """
    Async wrapper for TTS synthesis.
    Used by the API endpoints.
    """
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, synthesize_text, text, voice)
    return result


def get_available_voices() -> list:
    """Get list of available voices."""
    try:
        import pyttsx3
        engine = pyttsx3.init()
        voices = engine.getProperty('voices')
        return [{"id": v.id, "name": v.name} for v in voices]
    except:
        return [{"id": "default", "name": "Default Voice"}]
