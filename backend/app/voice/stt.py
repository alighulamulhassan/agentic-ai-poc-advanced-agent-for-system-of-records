"""
Speech-to-Text using OpenAI Whisper (local).
Runs entirely on your machine - no API calls.
"""
import io
import tempfile
from pathlib import Path
from typing import Optional
import numpy as np

from app.config import settings

# Global model instance
_whisper_model = None


def get_whisper_model():
    """Load the Whisper model (cached)."""
    global _whisper_model
    
    if _whisper_model is None:
        import whisper
        print(f"📦 Loading Whisper model: {settings.whisper_model}")
        _whisper_model = whisper.load_model(settings.whisper_model)
        print(f"✅ Whisper model loaded")
    
    return _whisper_model


def transcribe_audio(audio_data: bytes, language: str = "en") -> dict:
    """
    Transcribe audio bytes to text.
    
    Args:
        audio_data: Audio file bytes (supports wav, mp3, webm, etc.)
        language: Language code (default: "en")
    
    Returns:
        dict with "text" and "language" keys
    """
    model = get_whisper_model()
    
    # Write audio to temp file (Whisper needs a file path)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
        tmp_file.write(audio_data)
        tmp_path = tmp_file.name
    
    try:
        # Transcribe
        result = model.transcribe(
            tmp_path,
            language=language if language else None,
            fp16=False  # Use FP32 for CPU compatibility
        )
        
        return {
            "text": result["text"].strip(),
            "language": result.get("language", language),
            "segments": result.get("segments", [])
        }
    finally:
        # Clean up temp file
        Path(tmp_path).unlink(missing_ok=True)


def transcribe_numpy(audio_array: np.ndarray, sample_rate: int = 16000) -> dict:
    """
    Transcribe audio from numpy array.
    
    Args:
        audio_array: Audio samples as numpy array
        sample_rate: Sample rate of the audio
    
    Returns:
        dict with "text" and "language" keys
    """
    import whisper
    
    model = get_whisper_model()
    
    # Whisper expects 16kHz audio
    if sample_rate != 16000:
        # Resample if needed
        from scipy import signal
        samples = len(audio_array)
        new_samples = int(samples * 16000 / sample_rate)
        audio_array = signal.resample(audio_array, new_samples)
    
    # Ensure float32
    audio_array = audio_array.astype(np.float32)
    
    # Normalize if needed
    if audio_array.max() > 1.0:
        audio_array = audio_array / 32768.0
    
    # Transcribe
    result = model.transcribe(audio_array, fp16=False)
    
    return {
        "text": result["text"].strip(),
        "language": result.get("language", "en")
    }


async def transcribe(audio_bytes: bytes) -> dict:
    """
    Async wrapper for transcription.
    Used by the API endpoints.
    """
    # Run in thread pool to avoid blocking
    import asyncio
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, transcribe_audio, audio_bytes)
    return result
