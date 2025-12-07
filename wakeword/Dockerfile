# =============================================================================
# Wake Word Detection Service Dockerfile
# =============================================================================
# 
# This Dockerfile creates a container for the openWakeWord voice pipeline.
# It continuously listens for a wake word and orchestrates the full pipeline:
#   Wake Word → STT → AI → TTS
#
# Build:
#   docker buildx build --platform linux/arm64 -t wakeword -f wakeword/Dockerfile .
#
# Run:
#   docker run -d --device /dev/snd -p 5003:5000 wakeword
#
# =============================================================================

FROM python:3.11-slim

# =============================================================================
# METADATA
# =============================================================================
LABEL maintainer="Prometheus RPI Chatbot"
LABEL description="Wake word detection with openWakeWord"
LABEL version="1.0.0"

# =============================================================================
# SYSTEM DEPENDENCIES
# =============================================================================

# Install system packages:
# - alsa-utils: For audio recording (arecord) and playback (aplay)
# - curl: For healthcheck
# - libgomp1: Required for ONNX Runtime (OpenMP support)
# - libportaudio2: Audio library (alternative to ALSA)
# - libsndfile1: Sound file library for audio processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    alsa-utils \
    curl \
    libgomp1 \
    libportaudio2 \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# =============================================================================
# WORKING DIRECTORY
# =============================================================================

WORKDIR /app

# Create models directory for wake word models
RUN mkdir -p /app/models

# =============================================================================
# PYTHON DEPENDENCIES
# =============================================================================

# Copy requirements first (for better Docker caching)
COPY wakeword/requirements.txt /app/requirements.txt

# Install Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Download ALL required openWakeWord models during build
# openWakeWord needs: melspectrogram model + embedding model + wake word models
RUN MODELS_DIR=/usr/local/lib/python3.11/site-packages/openwakeword/resources/models && \
    mkdir -p $MODELS_DIR && \
    cd $MODELS_DIR && \
    echo "Downloading preprocessing models..." && \
    curl -L -o melspectrogram.onnx "https://github.com/dscripka/openWakeWord/releases/download/v0.5.1/melspectrogram.onnx" && \
    curl -L -o embedding_model.onnx "https://github.com/dscripka/openWakeWord/releases/download/v0.5.1/embedding_model.onnx" && \
    echo "Downloading wake word models..." && \
    curl -L -o hey_jarvis_v0.1.onnx "https://github.com/dscripka/openWakeWord/releases/download/v0.5.1/hey_jarvis_v0.1.onnx" && \
    curl -L -o alexa_v0.1.onnx "https://github.com/dscripka/openWakeWord/releases/download/v0.5.1/alexa_v0.1.onnx" && \
    echo "Models downloaded:" && \
    ls -la $MODELS_DIR/

# =============================================================================
# APPLICATION CODE
# =============================================================================

# Copy the server code
COPY wakeword/wakeword_server.py /app/wakeword_server.py

# =============================================================================
# CONFIGURATION
# =============================================================================

# Environment variables (can be overridden in docker-compose)
ENV WAKE_WORD_MODEL=hey_jarvis
ENV DETECTION_THRESHOLD=0.5
ENV STT_URL=http://whisper-stt:5000
ENV AI_URL=http://ollama:8000
ENV TTS_URL=http://piper-tts:5000
ENV AUDIO_DEVICE=plughw:3,0
ENV SAMPLE_RATE=16000
ENV COMMAND_DURATION=5
ENV AUTO_START=false

# =============================================================================
# EXPOSE PORT
# =============================================================================

# The FastAPI server runs on port 5000 inside the container
# docker-compose maps this to 5003 on the host
EXPOSE 5000

# =============================================================================
# HEALTHCHECK
# =============================================================================

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# =============================================================================
# ENTRYPOINT
# =============================================================================

# Run the FastAPI server with uvicorn
# --host 0.0.0.0  : Listen on all interfaces
# --port 5000     : Port to listen on
# --workers 1     : Single worker (wake word needs dedicated thread)
CMD ["uvicorn", "wakeword_server:app", "--host", "0.0.0.0", "--port", "5000", "--workers", "1"]

