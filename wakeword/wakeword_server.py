"""
=============================================================================
openWakeWord Voice Pipeline Server
=============================================================================

This service continuously listens for a wake word and orchestrates the full
voice pipeline when activated:

    Wake Word → STT (Whisper) → AI (Ollama) → TTS (Piper)

Flow:
    1. Continuously listen for wake word (e.g., "Hey Jarvis")
    2. When detected, play an acknowledgment sound
    3. Record user's command (5 seconds)
    4. Send to Whisper STT for transcription
    5. Send transcription to Ollama AI
    6. Send AI response to Piper TTS
    7. Resume wake word listening

Usage:
    uvicorn wakeword_server:app --host 0.0.0.0 --port 5000

Environment Variables:
    WAKE_WORD_MODEL     - Wake word model (default: hey_jarvis)
    DETECTION_THRESHOLD - Confidence threshold (default: 0.5)
    STT_URL             - Whisper STT service URL
    AI_URL              - Ollama AI service URL
    TTS_URL             - Piper TTS service URL
    AUDIO_DEVICE        - Microphone device (default: plughw:3,0)
    SAMPLE_RATE         - Audio sample rate (default: 16000)
=============================================================================
"""

import os
import sys
import time
import json
import logging
import threading
import subprocess
import numpy as np
from typing import Optional
from pathlib import Path

import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Configure logging with timestamps
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

# Wake word configuration
WAKE_WORD_MODEL = os.getenv("WAKE_WORD_MODEL", "hey_jarvis")
DETECTION_THRESHOLD = float(os.getenv("DETECTION_THRESHOLD", "0.5"))

# Service URLs (Docker internal network)
STT_URL = os.getenv("STT_URL", "http://whisper-stt:5000")
AI_URL = os.getenv("AI_URL", "http://ollama:8000")
TTS_URL = os.getenv("TTS_URL", "http://piper-tts:5000")

# Audio configuration
AUDIO_DEVICE = os.getenv("AUDIO_DEVICE", "plughw:3,0")
SAMPLE_RATE = int(os.getenv("SAMPLE_RATE", "16000"))
CHUNK_SIZE = 1280  # 80ms at 16kHz (required by openWakeWord)

# Recording configuration
COMMAND_DURATION = int(os.getenv("COMMAND_DURATION", "5"))  # seconds to record after wake word

# =============================================================================
# FASTAPI APPLICATION
# =============================================================================

app = FastAPI(
    title="Wake Word Voice Pipeline",
    description="Hands-free voice assistant using openWakeWord",
    version="1.0.0"
)

# Global state
pipeline_state = {
    "running": False,
    "listening": False,
    "last_wake_word": None,
    "last_command": None,
    "last_response": None,
    "wake_word_count": 0,
    "errors": []
}

# Wake word model (loaded on startup)
oww_model = None
pipeline_thread = None
stop_event = threading.Event()


# =============================================================================
# MODELS
# =============================================================================

class PipelineStatus(BaseModel):
    running: bool
    listening: bool
    wake_word_model: str
    threshold: float
    last_wake_word: Optional[str]
    last_command: Optional[str]
    last_response: Optional[str]
    wake_word_count: int


class StartRequest(BaseModel):
    wake_word: Optional[str] = None
    threshold: Optional[float] = None


# =============================================================================
# AUDIO CAPTURE
# =============================================================================

def capture_audio_chunk(duration_ms: int = 80) -> Optional[np.ndarray]:
    """
    Capture audio from microphone using arecord with plughw for resampling.
    
    The microphone only supports 44100Hz natively, but plughw: handles
    automatic conversion to our target 16kHz sample rate.
    
    Args:
        duration_ms: Duration to capture in milliseconds (minimum 1000ms due to arecord)
        
    Returns:
        Numpy array of audio samples (16-bit signed, 16kHz mono)
    """
    global _arecord_process
    
    try:
        # For continuous wake word detection, we need a streaming approach
        # Record 1 second chunks and extract what we need
        cmd = [
            "arecord",
            "-D", AUDIO_DEVICE,  # plughw:3,0 handles resampling
            "-f", "S16_LE",
            "-r", str(SAMPLE_RATE),
            "-c", "1",
            "-t", "raw",
            "-q",
            "-d", "1"  # 1 second recording
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=5
        )
        
        if result.returncode != 0:
            stderr = result.stderr.decode() if result.stderr else "Unknown error"
            logger.error(f"arecord failed: {stderr}")
            return None
        
        # Convert bytes to numpy array
        audio = np.frombuffer(result.stdout, dtype=np.int16)
        
        # openWakeWord expects 80ms chunks (1280 samples at 16kHz)
        # Return the full 1 second of audio - the model will process it
        return audio
        
    except subprocess.TimeoutExpired:
        logger.error("arecord timed out")
        return None
    except Exception as e:
        logger.error(f"Audio capture error: {e}")
        return None


def record_command(duration: int = 5) -> Optional[str]:
    """
    Record a command from the microphone.
    
    Uses the Whisper STT service to transcribe.
    
    Args:
        duration: Seconds to record
        
    Returns:
        Transcribed text or None if failed
    """
    try:
        logger.info(f"🎤 Recording command for {duration} seconds...")
        
        # Call Whisper STT service
        response = requests.post(
            f"{STT_URL}/listen",
            json={"duration": duration},
            timeout=duration + 30  # Extra time for processing
        )
        
        if response.status_code == 200:
            result = response.json()
            text = result.get("text", "").strip()
            logger.info(f"📝 Transcribed: {text}")
            return text
        else:
            logger.error(f"STT error: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"Recording/transcription error: {e}")
        return None


# =============================================================================
# AI AND TTS
# =============================================================================

def get_ai_response(text: str) -> Optional[str]:
    """
    Send text to AI and get response.
    
    Args:
        text: User's command/question
        
    Returns:
        AI response text or None if failed
    """
    try:
        logger.info(f"🤖 Asking AI: {text}")
        
        response = requests.post(
            f"{AI_URL}/chat",
            json={"message": text},
            timeout=120
        )
        
        if response.status_code == 200:
            result = response.json()
            ai_text = result.get("response", "")
            logger.info(f"🤖 AI response: {ai_text[:100]}...")
            return ai_text
        else:
            logger.error(f"AI error: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"AI request error: {e}")
        return None


def strip_emojis_and_symbols(text: str) -> str:
    """
    Remove emojis, asterisks, and special symbols from text.
    This prevents TTS from trying to verbalize these characters.
    """
    import re
    
    # First, remove asterisks used for formatting (bold/emphasis)
    # Replace ** or * with nothing
    text = re.sub(r'\*+', '', text)
    
    # Remove other common formatting symbols
    text = re.sub(r'[_~`#]+', '', text)
    
    # Regex to match most common emojis and unicode symbols
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags
        "\U00002702-\U000027B0"  # dingbats
        "\U000024C2-\U0001F251"  # enclosed characters
        "\U0001F900-\U0001F9FF"  # supplemental symbols
        "\U0001FA00-\U0001FA6F"  # chess symbols
        "\U0001FA70-\U0001FAFF"  # symbols and pictographs extended-A
        "\U00002600-\U000026FF"  # misc symbols
        "\U00002700-\U000027BF"  # dingbats
        "]+", 
        flags=re.UNICODE
    )
    text = emoji_pattern.sub('', text)
    
    # Clean up extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text


def speak_response(text: str) -> bool:
    """
    Send text to TTS and play through speaker.
    Strips emojis before speaking.
    
    Args:
        text: Text to speak
        
    Returns:
        True if successful
    """
    try:
        # Strip emojis, asterisks, and special symbols
        clean_text = strip_emojis_and_symbols(text)
        
        logger.info(f"🔊 Speaking: {clean_text[:100]}...")
        
        response = requests.post(
            f"{TTS_URL}/speak",
            json={"text": clean_text, "play_audio": True},
            timeout=60
        )
        
        if response.status_code == 200:
            logger.info("🔊 TTS completed")
            return True
        else:
            logger.error(f"TTS error: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"TTS request error: {e}")
        return False


def play_acknowledgment():
    """
    Play a short beep to acknowledge wake word detection.
    Uses aplay with a generated tone.
    """
    try:
        # Generate a short beep (440Hz for 200ms)
        # Using raw audio generation with numpy
        duration = 0.2  # seconds
        frequency = 880  # Hz (higher pitch for acknowledgment)
        t = np.linspace(0, duration, int(SAMPLE_RATE * duration), False)
        tone = np.sin(2 * np.pi * frequency * t) * 0.3  # 30% volume
        tone = (tone * 32767).astype(np.int16)
        
        # Play using aplay
        process = subprocess.Popen(
            ["aplay", "-D", "plughw:2,0", "-f", "S16_LE", "-r", str(SAMPLE_RATE), "-c", "1", "-q"],
            stdin=subprocess.PIPE
        )
        process.communicate(input=tone.tobytes(), timeout=2)
        
    except Exception as e:
        logger.warning(f"Could not play acknowledgment: {e}")


# =============================================================================
# WAKE WORD DETECTION PIPELINE
# =============================================================================

def run_pipeline():
    """
    Main pipeline loop:
    1. Listen for wake word
    2. When detected, record command
    3. Get AI response
    4. Speak response
    5. Repeat
    """
    global oww_model, pipeline_state
    
    try:
        # Import openwakeword here to handle import errors gracefully
        from openwakeword.model import Model
        
        logger.info(f"🎯 Loading wake word model: {WAKE_WORD_MODEL}")
        oww_model = Model(
            wakeword_models=[WAKE_WORD_MODEL],
            inference_framework="onnx"
        )
        logger.info("✅ Wake word model loaded")
        
    except Exception as e:
        logger.error(f"❌ Failed to load wake word model: {e}")
        pipeline_state["errors"].append(str(e))
        return
    
    pipeline_state["running"] = True
    pipeline_state["listening"] = True
    
    logger.info("=" * 60)
    logger.info(f"🎤 Listening for wake word: '{WAKE_WORD_MODEL}'")
    logger.info(f"   Threshold: {DETECTION_THRESHOLD}")
    logger.info(f"   Say '{WAKE_WORD_MODEL.replace('_', ' ')}' to activate!")
    logger.info("=" * 60)
    
    # Continuous listening loop
    while not stop_event.is_set():
        try:
            # Capture audio chunk (80ms)
            audio = capture_audio_chunk(80)
            
            if audio is None:
                time.sleep(0.1)
                continue
            
            # Run wake word detection
            prediction = oww_model.predict(audio)
            
            # Check for wake word activation
            for model_name, score in prediction.items():
                if score >= DETECTION_THRESHOLD:
                    logger.info(f"🎯 WAKE WORD DETECTED: {model_name} (score: {score:.2f})")
                    
                    pipeline_state["listening"] = False
                    pipeline_state["last_wake_word"] = model_name
                    pipeline_state["wake_word_count"] += 1
                    
                    # Play acknowledgment beep
                    play_acknowledgment()
                    
                    # Record user's command
                    command = record_command(COMMAND_DURATION)
                    
                    if command:
                        pipeline_state["last_command"] = command
                        
                        # Get AI response
                        response = get_ai_response(command)
                        
                        if response:
                            pipeline_state["last_response"] = response
                            
                            # Speak the response
                            speak_response(response)
                    
                    # Resume listening
                    pipeline_state["listening"] = True
                    logger.info(f"🎤 Resuming wake word detection...")
                    
                    # Reset the model state
                    oww_model.reset()
            
        except Exception as e:
            logger.error(f"Pipeline error: {e}")
            pipeline_state["errors"].append(str(e))
            time.sleep(1)
    
    pipeline_state["running"] = False
    pipeline_state["listening"] = False
    logger.info("🛑 Pipeline stopped")


# =============================================================================
# API ENDPOINTS
# =============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "wake_word_model": WAKE_WORD_MODEL,
        "threshold": DETECTION_THRESHOLD,
        "stt_url": STT_URL,
        "ai_url": AI_URL,
        "tts_url": TTS_URL,
        "audio_device": AUDIO_DEVICE
    }


@app.get("/status", response_model=PipelineStatus)
async def get_status():
    """Get current pipeline status."""
    return PipelineStatus(
        running=pipeline_state["running"],
        listening=pipeline_state["listening"],
        wake_word_model=WAKE_WORD_MODEL,
        threshold=DETECTION_THRESHOLD,
        last_wake_word=pipeline_state["last_wake_word"],
        last_command=pipeline_state["last_command"],
        last_response=pipeline_state["last_response"],
        wake_word_count=pipeline_state["wake_word_count"]
    )


@app.post("/start")
async def start_pipeline(request: StartRequest = None):
    """Start the wake word detection pipeline."""
    global pipeline_thread, stop_event
    
    if pipeline_state["running"]:
        return {"status": "already_running"}
    
    # Reset stop event
    stop_event.clear()
    
    # Start pipeline in background thread
    pipeline_thread = threading.Thread(target=run_pipeline, daemon=True)
    pipeline_thread.start()
    
    # Wait a moment for it to start
    time.sleep(1)
    
    return {
        "status": "started",
        "wake_word": WAKE_WORD_MODEL,
        "threshold": DETECTION_THRESHOLD
    }


@app.post("/stop")
async def stop_pipeline():
    """Stop the wake word detection pipeline."""
    global stop_event
    
    if not pipeline_state["running"]:
        return {"status": "not_running"}
    
    stop_event.set()
    
    # Wait for thread to stop
    if pipeline_thread:
        pipeline_thread.join(timeout=5)
    
    return {"status": "stopped"}


@app.get("/models")
async def list_models():
    """List available wake word models."""
    # Pre-trained models available in openwakeword
    models = [
        {"name": "alexa", "description": "Amazon Alexa wake word"},
        {"name": "hey_jarvis", "description": "Hey Jarvis wake word"},
        {"name": "hey_mycroft", "description": "Hey Mycroft wake word"},
        {"name": "hey_rhasspy", "description": "Hey Rhasspy wake word"},
        {"name": "ok_nabu", "description": "OK Nabu wake word"},
    ]
    return {
        "current": WAKE_WORD_MODEL,
        "available": models
    }


@app.post("/test")
async def test_pipeline():
    """
    Test the full pipeline without wake word detection.
    Records for 5 seconds, transcribes, gets AI response, and speaks.
    """
    logger.info("🧪 Testing full pipeline...")
    
    # Record command
    command = record_command(COMMAND_DURATION)
    
    if not command:
        raise HTTPException(status_code=500, detail="Failed to record/transcribe")
    
    # Get AI response
    response = get_ai_response(command)
    
    if not response:
        raise HTTPException(status_code=500, detail="Failed to get AI response")
    
    # Speak response
    speak_response(response)
    
    return {
        "success": True,
        "command": command,
        "response": response
    }


# =============================================================================
# STARTUP
# =============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize on startup."""
    logger.info("=" * 60)
    logger.info("🎯 Wake Word Voice Pipeline Starting")
    logger.info("=" * 60)
    logger.info(f"Wake word model: {WAKE_WORD_MODEL}")
    logger.info(f"Detection threshold: {DETECTION_THRESHOLD}")
    logger.info(f"STT URL: {STT_URL}")
    logger.info(f"AI URL: {AI_URL}")
    logger.info(f"TTS URL: {TTS_URL}")
    logger.info(f"Audio device: {AUDIO_DEVICE}")
    logger.info("=" * 60)
    
    # Optionally auto-start the pipeline
    if os.getenv("AUTO_START", "false").lower() == "true":
        logger.info("Auto-starting pipeline...")
        stop_event.clear()
        global pipeline_thread
        pipeline_thread = threading.Thread(target=run_pipeline, daemon=True)
        pipeline_thread.start()


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)

