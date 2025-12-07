"""
=============================================================================
Whisper STT Server - Speech-to-Text HTTP API for Prometheus
=============================================================================

This FastAPI server wraps the faster-whisper library, providing an HTTP API
for converting speech (audio) to text. It's designed to run in a Docker
container on a Raspberry Pi.

Architecture:
    Microphone → Audio File → This Server → faster-whisper → Text

Endpoints:
    POST /transcribe     - Transcribe audio file to text
    POST /listen         - Record from microphone and transcribe
    GET /health          - Health check
    GET /models          - List available Whisper models

Environment Variables:
    WHISPER_MODEL       - Model size: tiny, base, small (default: tiny)
    COMPUTE_TYPE        - Precision: int8, float16 (default: int8)
    AUDIO_DEVICE        - ALSA device for recording (default: plughw:3,0)

Usage:
    uvicorn stt_server:app --host 0.0.0.0 --port 5000

=============================================================================
"""

import os
import subprocess
import tempfile
import logging
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from faster_whisper import WhisperModel

# -----------------------------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------------------------

# Whisper model configuration
# Options: tiny, base, small (larger = more accurate but slower)
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL", "tiny")

# Compute type for inference
# int8 is fastest on CPU, float16 if you have GPU
COMPUTE_TYPE = os.getenv("COMPUTE_TYPE", "int8")

# Audio device for recording (microphone)
# Use "plughw:X,0" format where X is the card number
AUDIO_DEVICE = os.getenv("AUDIO_DEVICE", "plughw:3,0")

# Recording settings
SAMPLE_RATE = int(os.getenv("SAMPLE_RATE", "16000"))  # 16kHz is optimal for Whisper
RECORD_CHANNELS = 1  # Mono

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# FASTAPI APP
# -----------------------------------------------------------------------------

app = FastAPI(
    title="Whisper STT Server",
    description="Speech-to-Text API for Prometheus AI using faster-whisper",
    version="1.0.0"
)

# -----------------------------------------------------------------------------
# GLOBAL MODEL (loaded once at startup)
# -----------------------------------------------------------------------------

whisper_model: Optional[WhisperModel] = None

# -----------------------------------------------------------------------------
# REQUEST/RESPONSE MODELS
# -----------------------------------------------------------------------------

class TranscribeResponse(BaseModel):
    """Response for transcription endpoints"""
    success: bool
    text: str
    language: Optional[str] = None
    confidence: Optional[float] = None
    duration_ms: Optional[float] = None


class ListenRequest(BaseModel):
    """Request body for /listen endpoint"""
    duration: int = 5  # Recording duration in seconds
    language: Optional[str] = None  # Optional: force language (e.g., "en")


# -----------------------------------------------------------------------------
# HELPER FUNCTIONS
# -----------------------------------------------------------------------------

def load_whisper_model():
    """
    Load the Whisper model into memory.
    This is called once at startup to avoid reloading for each request.
    """
    global whisper_model
    
    logger.info(f"Loading Whisper model: {WHISPER_MODEL_SIZE}")
    logger.info(f"Compute type: {COMPUTE_TYPE}")
    
    start_time = time.time()
    
    try:
        # Load the model
        # device="cpu" for Raspberry Pi (no GPU)
        # compute_type="int8" for fastest CPU inference
        whisper_model = WhisperModel(
            WHISPER_MODEL_SIZE,
            device="cpu",
            compute_type=COMPUTE_TYPE,
            download_root="/app/models"
        )
        
        load_time = time.time() - start_time
        logger.info(f"✅ Whisper model loaded in {load_time:.2f}s")
        
    except Exception as e:
        logger.error(f"❌ Failed to load Whisper model: {e}")
        raise


def transcribe_audio(audio_path: str, language: Optional[str] = None) -> dict:
    """
    Transcribe an audio file using Whisper.
    
    Args:
        audio_path: Path to the audio file (WAV, MP3, etc.)
        language: Optional language code to force (e.g., "en", "es")
        
    Returns:
        Dictionary with transcription results
    """
    if whisper_model is None:
        raise HTTPException(status_code=500, detail="Whisper model not loaded")
    
    logger.info(f"🎤 Transcribing: {audio_path}")
    start_time = time.time()
    
    try:
        # Transcribe the audio
        # beam_size=1 is fastest, increase for better accuracy
        segments, info = whisper_model.transcribe(
            audio_path,
            language=language,
            beam_size=1,
            vad_filter=True,  # Voice Activity Detection - filters silence
            vad_parameters=dict(
                min_silence_duration_ms=500,  # Minimum silence to split
            )
        )
        
        # Collect all segments into a single text
        text_parts = []
        for segment in segments:
            text_parts.append(segment.text.strip())
        
        full_text = " ".join(text_parts)
        
        duration_ms = (time.time() - start_time) * 1000
        
        logger.info(f"✅ Transcription complete in {duration_ms:.0f}ms")
        logger.info(f"   Language: {info.language} (confidence: {info.language_probability:.2f})")
        logger.info(f"   Text: {full_text[:100]}...")
        
        return {
            "text": full_text,
            "language": info.language,
            "confidence": info.language_probability,
            "duration_ms": duration_ms
        }
        
    except Exception as e:
        logger.error(f"❌ Transcription failed: {e}")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")


def record_audio(duration: int, output_path: str):
    """
    Record audio from the microphone using ALSA.
    
    Args:
        duration: Recording duration in seconds
        output_path: Path to save the WAV file
    """
    logger.info(f"🎤 Recording for {duration} seconds from {AUDIO_DEVICE}")
    
    try:
        # Use arecord to capture audio
        # -D device    : ALSA device
        # -f S16_LE    : Format (16-bit signed, little-endian)
        # -r 16000     : Sample rate (16kHz optimal for Whisper)
        # -c 1         : Mono channel
        # -d duration  : Recording duration
        result = subprocess.run(
            [
                "arecord",
                "-D", AUDIO_DEVICE,
                "-f", "S16_LE",
                "-r", str(SAMPLE_RATE),
                "-c", str(RECORD_CHANNELS),
                "-d", str(duration),
                output_path
            ],
            capture_output=True,
            text=True,
            timeout=duration + 10  # Allow extra time for processing
        )
        
        if result.returncode != 0:
            logger.error(f"arecord failed: {result.stderr}")
            raise HTTPException(
                status_code=500,
                detail=f"Recording failed: {result.stderr}"
            )
        
        logger.info(f"✅ Recording saved to {output_path}")
        
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Recording timed out")
    except FileNotFoundError:
        raise HTTPException(
            status_code=500,
            detail="arecord not found - is alsa-utils installed?"
        )


# -----------------------------------------------------------------------------
# API ENDPOINTS
# -----------------------------------------------------------------------------

@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    
    Returns:
        JSON with status and configuration info
    """
    return {
        "status": "healthy" if whisper_model is not None else "unhealthy",
        "model": WHISPER_MODEL_SIZE,
        "compute_type": COMPUTE_TYPE,
        "audio_device": AUDIO_DEVICE,
        "sample_rate": SAMPLE_RATE
    }


@app.get("/models")
async def list_models():
    """
    List available Whisper model sizes.
    """
    return {
        "available_models": [
            {"name": "tiny", "size": "39MB", "speed": "fastest", "accuracy": "good"},
            {"name": "base", "size": "74MB", "speed": "fast", "accuracy": "better"},
            {"name": "small", "size": "244MB", "speed": "slow", "accuracy": "great"},
        ],
        "current_model": WHISPER_MODEL_SIZE,
        "note": "For RPI5, 'tiny' or 'base' recommended"
    }


@app.post("/transcribe", response_model=TranscribeResponse)
async def transcribe(
    file: UploadFile = File(...),
    language: Optional[str] = None
):
    """
    Transcribe an uploaded audio file to text.
    
    This endpoint accepts audio files (WAV, MP3, etc.) and returns
    the transcribed text.
    
    Args:
        file: Audio file to transcribe
        language: Optional language code (e.g., "en") to force detection
        
    Returns:
        TranscribeResponse with the transcribed text
    """
    # Save uploaded file to temp location
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name
        content = await file.read()
        tmp.write(content)
    
    try:
        # Transcribe
        result = transcribe_audio(tmp_path, language)
        
        return TranscribeResponse(
            success=True,
            text=result["text"],
            language=result["language"],
            confidence=result["confidence"],
            duration_ms=result["duration_ms"]
        )
        
    finally:
        # Cleanup temp file
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@app.post("/listen", response_model=TranscribeResponse)
async def listen(request: ListenRequest):
    """
    Record audio from microphone and transcribe it.
    
    This endpoint records audio from the configured microphone device
    for the specified duration, then transcribes it to text.
    
    Args:
        request: ListenRequest with duration and optional language
        
    Returns:
        TranscribeResponse with the transcribed text
    """
    # Validate duration
    if request.duration < 1 or request.duration > 30:
        raise HTTPException(
            status_code=400,
            detail="Duration must be between 1 and 30 seconds"
        )
    
    # Create temp file for recording
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name
    
    try:
        # Record audio
        record_audio(request.duration, tmp_path)
        
        # Transcribe
        result = transcribe_audio(tmp_path, request.language)
        
        return TranscribeResponse(
            success=True,
            text=result["text"],
            language=result["language"],
            confidence=result["confidence"],
            duration_ms=result["duration_ms"]
        )
        
    finally:
        # Cleanup temp file
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


# -----------------------------------------------------------------------------
# STARTUP EVENT
# -----------------------------------------------------------------------------

@app.on_event("startup")
async def startup_event():
    """Load Whisper model on startup"""
    logger.info("=" * 60)
    logger.info("🎤 Whisper STT Server Starting")
    logger.info("=" * 60)
    logger.info(f"Model: {WHISPER_MODEL_SIZE}")
    logger.info(f"Compute type: {COMPUTE_TYPE}")
    logger.info(f"Audio device: {AUDIO_DEVICE}")
    logger.info(f"Sample rate: {SAMPLE_RATE}")
    logger.info("=" * 60)
    
    # Load the model
    load_whisper_model()
    
    logger.info("✅ Whisper STT Server Ready")


# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)

