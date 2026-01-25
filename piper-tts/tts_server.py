"""
=============================================================================
Piper TTS Server - Text-to-Speech HTTP API for Prometheus
=============================================================================

This FastAPI server wraps the Piper TTS binary, providing an HTTP API for
converting text to speech. It's designed to run in a Docker container on
a Raspberry Pi.

Architecture:
    WhatsApp Bridge → HTTP POST /speak → This Server → Piper → Speaker

Endpoints:
    POST /speak     - Convert text to speech and play through speaker
    POST /synthesize - Convert text to speech and return audio file
    GET /health     - Health check
    GET /voices     - List available voice models

Environment Variables:
    PIPER_BINARY    - Path to Piper executable (default: /app/piper/piper)
    VOICE_MODEL     - Path to voice model .onnx file
    SAMPLE_RATE     - Audio sample rate (default: 22050)

Usage:
    uvicorn tts_server:app --host 0.0.0.0 --port 5000

=============================================================================
"""

import os
import subprocess
import tempfile
import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

# -----------------------------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------------------------

# Path to Piper binary - can be overridden with environment variable
PIPER_BINARY = os.getenv("PIPER_BINARY", "/app/piper/piper")

# Path to voice model - MUST be set via environment variable
VOICE_MODEL = os.getenv("VOICE_MODEL", "/app/voices/en_GB-alba-medium.onnx")

# Audio settings
SAMPLE_RATE = int(os.getenv("SAMPLE_RATE", "22050"))  # Piper default

# Audio device for playback (ALSA device name)
# Use "plughw:X,0" format where X is the card number
# Find your card number with: aplay -l
AUDIO_DEVICE = os.getenv("AUDIO_DEVICE", "plughw:2,0")  # Default: USB speaker on card 2

# Silence prefix duration (milliseconds) to wake up USB speaker before speech
# USB audio devices need time to "wake up" from low-power state
# Increase this if first word is still being cut off
SILENCE_PREFIX_MS = int(os.getenv("SILENCE_PREFIX_MS", "500"))

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
    title="Piper TTS Server",
    description="Text-to-Speech API for Prometheus AI using Piper",
    version="1.0.0"
)

# -----------------------------------------------------------------------------
# REQUEST/RESPONSE MODELS
# -----------------------------------------------------------------------------

class SpeakRequest(BaseModel):
    """Request body for /speak endpoint"""
    text: str                           # Text to convert to speech
    voice: Optional[str] = None         # Optional: override default voice model
    play_audio: bool = True             # Whether to play through speaker


class SynthesizeRequest(BaseModel):
    """Request body for /synthesize endpoint"""
    text: str                           # Text to convert to speech
    voice: Optional[str] = None         # Optional: override default voice model
    output_format: str = "wav"          # Output format: "wav" or "raw"


class TTSResponse(BaseModel):
    """Response for /speak endpoint"""
    success: bool
    message: str
    text: str
    duration_ms: Optional[float] = None


# -----------------------------------------------------------------------------
# HELPER FUNCTIONS
# -----------------------------------------------------------------------------

def get_voice_model(voice_override: Optional[str] = None) -> str:
    """
    Get the path to the voice model to use.
    
    Args:
        voice_override: Optional path to override the default voice
        
    Returns:
        Path to the .onnx voice model file
        
    Raises:
        HTTPException: If voice model file doesn't exist
    """
    voice_path = voice_override if voice_override else VOICE_MODEL
    
    if not os.path.exists(voice_path):
        raise HTTPException(
            status_code=500,
            detail=f"Voice model not found: {voice_path}"
        )
    
    return voice_path


def run_piper(text: str, voice_model: str, output_file: Optional[str] = None) -> subprocess.CompletedProcess:
    """
    Run Piper TTS to convert text to speech.
    
    Args:
        text: The text to convert to speech
        voice_model: Path to the .onnx voice model
        output_file: Optional path to save WAV file (if None, outputs raw PCM)
        
    Returns:
        CompletedProcess with the result
        
    Raises:
        HTTPException: If Piper fails
    """
    # Build command
    cmd = [
        PIPER_BINARY,
        "--model", voice_model,
    ]
    
    if output_file:
        cmd.extend(["--output_file", output_file])
    else:
        cmd.append("--output-raw")
    
    logger.info(f"Running Piper: {' '.join(cmd)}")
    logger.info(f"Text: {text[:100]}{'...' if len(text) > 100 else ''}")
    
    try:
        # Run Piper with text as stdin
        result = subprocess.run(
            cmd,
            input=text,
            capture_output=True,
            text=True,
            timeout=60  # 60 second timeout
        )
        
        if result.returncode != 0:
            logger.error(f"Piper failed: {result.stderr}")
            raise HTTPException(
                status_code=500,
                detail=f"Piper TTS failed: {result.stderr}"
            )
        
        return result
        
    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=500,
            detail="Piper TTS timed out"
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=500,
            detail=f"Piper binary not found at: {PIPER_BINARY}"
        )


def prepend_silence_to_wav(wav_file: str, silence_ms: int = SILENCE_PREFIX_MS):
    """
    Prepend silence to a WAV file to prevent first word being cut off.
    
    USB audio devices need a moment to "wake up" from low-power state.
    By prepending silence to the audio file itself, we ensure the speaker
    is active before the actual speech begins.
    
    Args:
        wav_file: Path to the WAV file to modify
        silence_ms: Duration of silence in milliseconds
    """
    import wave
    import struct
    
    try:
        # Read original WAV file
        with wave.open(wav_file, 'rb') as original:
            params = original.getparams()
            original_frames = original.readframes(original.getnframes())
        
        # Calculate silence frames
        # silence_samples = (sample_rate * silence_ms) / 1000
        silence_samples = int(params.framerate * silence_ms / 1000)
        # Each sample is 2 bytes (16-bit) * number of channels
        bytes_per_sample = params.sampwidth * params.nchannels
        silence_bytes = b'\x00' * (silence_samples * bytes_per_sample)
        
        # Write new WAV with silence prepended
        with wave.open(wav_file, 'wb') as modified:
            modified.setparams(params)
            modified.writeframes(silence_bytes + original_frames)
        
        logger.debug(f"Prepended {silence_ms}ms silence to audio")
        
    except Exception as e:
        logger.warning(f"Failed to prepend silence: {e}")
        # Continue without silence if it fails


def play_audio_file(audio_file: str):
    """
    Play an audio file through the configured ALSA device.
    
    Args:
        audio_file: Path to the WAV file to play
        
    Raises:
        HTTPException: If playback fails
    """
    try:
        # Prepend silence to prevent first word cutoff on USB speakers
        # USB audio devices need time to "wake up" from low-power state
        prepend_silence_to_wav(audio_file, silence_ms=SILENCE_PREFIX_MS)
        
        # Use -D to specify the audio device (e.g., plughw:2,0)
        # This is required in Docker containers where default device may not work
        result = subprocess.run(
            ["aplay", "-D", AUDIO_DEVICE, audio_file],
            capture_output=True,
            text=True,
            timeout=120  # 2 minute timeout for long audio
        )
        
        if result.returncode != 0:
            logger.error(f"aplay failed: {result.stderr}")
            raise HTTPException(
                status_code=500,
                detail=f"Audio playback failed: {result.stderr}"
            )
            
    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=500,
            detail="Audio playback timed out"
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=500,
            detail="aplay not found - is alsa-utils installed?"
        )


def play_raw_audio(raw_audio: bytes):
    """
    Play raw PCM audio through the configured ALSA device.
    
    Args:
        raw_audio: Raw PCM audio bytes
        
    Raises:
        HTTPException: If playback fails
    """
    try:
        # aplay parameters for Piper's raw output:
        # -D device : Audio device (e.g., plughw:2,0)
        # -r 22050  : Sample rate (Piper default)
        # -f S16_LE : Format (16-bit signed, little-endian)
        # -c 1      : Channels (mono)
        # -q        : Quiet mode
        result = subprocess.run(
            ["aplay", "-D", AUDIO_DEVICE, "-r", str(SAMPLE_RATE), "-f", "S16_LE", "-c", "1", "-q"],
            input=raw_audio,
            capture_output=True,
            timeout=120
        )
        
        if result.returncode != 0:
            logger.error(f"aplay failed: {result.stderr}")
            raise HTTPException(
                status_code=500,
                detail=f"Audio playback failed: {result.stderr.decode()}"
            )
            
    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=500,
            detail="Audio playback timed out"
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
    # Check if Piper binary exists
    piper_exists = os.path.exists(PIPER_BINARY)
    
    # Check if voice model exists
    voice_exists = os.path.exists(VOICE_MODEL)
    
    return {
        "status": "healthy" if (piper_exists and voice_exists) else "unhealthy",
        "piper_binary": PIPER_BINARY,
        "piper_exists": piper_exists,
        "voice_model": VOICE_MODEL,
        "voice_exists": voice_exists,
        "sample_rate": SAMPLE_RATE
    }


@app.get("/voices")
async def list_voices():
    """
    List available voice models.
    
    Returns:
        JSON with list of available voice model files
    """
    voices_dir = Path("/app/voices")
    
    if not voices_dir.exists():
        return {"voices": [], "error": "Voices directory not found"}
    
    # Find all .onnx files
    voices = [f.name for f in voices_dir.glob("*.onnx")]
    
    return {
        "voices": voices,
        "default": os.path.basename(VOICE_MODEL),
        "voices_directory": str(voices_dir)
    }


@app.post("/speak", response_model=TTSResponse)
async def speak(request: SpeakRequest):
    """
    Convert text to speech and optionally play through speaker.
    
    This is the main endpoint for the WhatsApp bridge to call when
    Prometheus needs to speak a response.
    
    Args:
        request: SpeakRequest with text and options
        
    Returns:
        TTSResponse with success status
    """
    import time
    start_time = time.time()
    
    # Validate input
    if not request.text or not request.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    
    # Get voice model
    voice_model = get_voice_model(request.voice)
    
    # Note: Speaker wake-up is handled by play_audio_file() which plays
    # a brief silence before the actual audio to prevent first word cutoff
    text_to_speak = request.text.strip()
    
    logger.info(f"🗣️ Speaking: {request.text[:50]}...")
    
    if request.play_audio:
        # Generate and play audio directly
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            # Generate audio file
            run_piper(text_to_speak, voice_model, tmp_path)
            
            # Play the audio
            play_audio_file(tmp_path)
            
        finally:
            # Cleanup temp file
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
    else:
        # Just generate (don't play) - useful for testing
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
            run_piper(text_to_speak, voice_model, tmp.name)
    
    duration_ms = (time.time() - start_time) * 1000
    
    return TTSResponse(
        success=True,
        message="Speech generated and played" if request.play_audio else "Speech generated",
        text=request.text,
        duration_ms=duration_ms
    )


@app.post("/synthesize")
async def synthesize(request: SynthesizeRequest):
    """
    Convert text to speech and return the audio file.
    
    Unlike /speak, this endpoint returns the audio data instead of
    playing it. Useful for:
    - Sending audio files via WhatsApp
    - Client-side playback
    - Testing
    
    Args:
        request: SynthesizeRequest with text and options
        
    Returns:
        WAV file as download
    """
    # Validate input
    if not request.text or not request.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    
    # Get voice model
    voice_model = get_voice_model(request.voice)
    
    logger.info(f"🎵 Synthesizing: {request.text[:50]}...")
    
    # Generate audio file
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name
    
    run_piper(request.text, voice_model, tmp_path)
    
    # Return the file
    return FileResponse(
        tmp_path,
        media_type="audio/wav",
        filename="speech.wav",
        # Note: File will be deleted after response is sent
        background=None  # FastAPI will handle cleanup
    )


# -----------------------------------------------------------------------------
# STARTUP EVENT
# -----------------------------------------------------------------------------

@app.on_event("startup")
async def startup_event():
    """Log configuration on startup"""
    logger.info("=" * 60)
    logger.info("🗣️  Piper TTS Server Starting")
    logger.info("=" * 60)
    logger.info(f"Piper binary: {PIPER_BINARY}")
    logger.info(f"Voice model: {VOICE_MODEL}")
    logger.info(f"Sample rate: {SAMPLE_RATE}")
    logger.info("=" * 60)
    
    # Verify Piper binary exists
    if not os.path.exists(PIPER_BINARY):
        logger.error(f"❌ Piper binary not found at: {PIPER_BINARY}")
    else:
        logger.info(f"✅ Piper binary found")
    
    # Verify voice model exists
    if not os.path.exists(VOICE_MODEL):
        logger.error(f"❌ Voice model not found at: {VOICE_MODEL}")
    else:
        logger.info(f"✅ Voice model found")


# -----------------------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)

