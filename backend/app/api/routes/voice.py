"""
Voice processing API endpoints.
Speech-to-Text and Text-to-Speech.
"""
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


class TranscriptionResponse(BaseModel):
    text: str
    language: str = "en"


class TTSRequest(BaseModel):
    text: str
    voice: str = "default"


@router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(audio: UploadFile = File(...)):
    """
    Transcribe audio to text using local Whisper.
    
    Supports: wav, mp3, webm, m4a, ogg
    """
    from app.voice.stt import transcribe
    
    try:
        audio_bytes = await audio.read()
        logger.info(f"Transcribing audio: {len(audio_bytes)} bytes")
        
        result = await transcribe(audio_bytes)
        
        logger.info(f"Transcription result: {result['text'][:50]}...")
        
        return TranscriptionResponse(
            text=result["text"],
            language=result.get("language", "en")
        )
    
    except Exception as e:
        logger.error(f"Transcription error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/synthesize")
async def synthesize_speech(request: TTSRequest):
    """
    Convert text to speech using local TTS.
    
    Returns: Audio file (MP3 format from gTTS, or WAV from pyttsx3)
    """
    from app.voice.tts import synthesize
    
    try:
        if not request.text.strip():
            raise HTTPException(status_code=400, detail="Text cannot be empty")
        
        logger.info(f"Synthesizing speech: {request.text[:50]}...")
        
        audio_bytes = await synthesize(request.text, request.voice)
        
        # gTTS produces MP3, pyttsx3 produces AIFF/WAV
        # Check format by looking at header
        if audio_bytes[:3] == b'ID3' or audio_bytes[:2] == b'\xff\xfb':
            media_type = "audio/mpeg"
            filename = "speech.mp3"
        else:
            media_type = "audio/wav"
            filename = "speech.wav"
        
        return Response(
            content=audio_bytes,
            media_type=media_type,
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
    
    except Exception as e:
        logger.error(f"TTS error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/voices")
async def list_voices():
    """
    List available TTS voices.
    """
    from app.voice.tts import get_available_voices
    
    try:
        voices = get_available_voices()
        return {"voices": voices}
    except Exception as e:
        return {"voices": [{"id": "default", "name": "Default"}], "error": str(e)}


@router.get("/status")
async def voice_status():
    """
    Check voice services status.
    """
    status = {
        "stt": {"available": False, "model": None},
        "tts": {"available": False, "engine": None}
    }
    
    # Check Whisper
    try:
        import whisper
        from app.config import settings
        status["stt"] = {
            "available": True,
            "model": settings.whisper_model,
            "info": "OpenAI Whisper (local)"
        }
    except ImportError:
        status["stt"]["info"] = "Whisper not installed"
    
    # Check TTS
    try:
        import pyttsx3
        status["tts"] = {
            "available": True,
            "engine": "pyttsx3",
            "info": "Local TTS engine"
        }
    except ImportError:
        try:
            from gtts import gTTS
            status["tts"] = {
                "available": True,
                "engine": "gtts",
                "info": "Google TTS (requires internet)"
            }
        except ImportError:
            status["tts"]["info"] = "No TTS engine installed"
    
    return status
