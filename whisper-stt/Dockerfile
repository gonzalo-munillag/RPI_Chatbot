# =============================================================================
# Dockerfile for Whisper STT Service
# =============================================================================
#
# This Dockerfile builds a container that:
#   1. Runs the faster-whisper library (speech-to-text)
#   2. Exposes a FastAPI HTTP server for STT requests
#   3. Can record audio from the host's ALSA devices (microphone)
#
# Build for ARM64 (Raspberry Pi):
#   docker buildx build --platform linux/arm64 -t whisper-stt -f whisper-stt/Dockerfile .
#
# Run:
#   docker run -d --device /dev/snd -p 5002:5000 whisper-stt
#
# The --device /dev/snd flag gives the container access to audio devices.
#
# =============================================================================

# -----------------------------------------------------------------------------
# BASE IMAGE
# -----------------------------------------------------------------------------
# Using Python 3.11 slim image - smaller than full image, has what we need
# This image supports ARM64 (Raspberry Pi 5)

FROM python:3.11-slim

# -----------------------------------------------------------------------------
# METADATA
# -----------------------------------------------------------------------------

LABEL maintainer="Prometheus AI Project"
LABEL description="Whisper STT Server for Raspberry Pi"
LABEL version="1.0"

# -----------------------------------------------------------------------------
# ENVIRONMENT VARIABLES
# -----------------------------------------------------------------------------

# Whisper model to use (tiny is fastest, base is more accurate)
# Options: tiny, base, small
ENV WHISPER_MODEL="tiny"

# Compute type for inference (int8 is fastest on CPU)
ENV COMPUTE_TYPE="int8"

# Audio device for recording (microphone)
# Use "plughw:X,0" format where X is the card number
ENV AUDIO_DEVICE="plughw:3,0"

# Sample rate for recording (16kHz is optimal for Whisper)
ENV SAMPLE_RATE="16000"

# Python settings
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# -----------------------------------------------------------------------------
# INSTALL SYSTEM DEPENDENCIES
# -----------------------------------------------------------------------------

RUN apt-get update && apt-get install -y --no-install-recommends \
    # ALSA utilities for audio recording (arecord command)
    alsa-utils \
    # Required for healthcheck
    curl \
    # Required for faster-whisper/ctranslate2
    libgomp1 \
    # Build tools for compiling Python packages
    gcc \
    g++ \
    python3-dev \
    # Required for building PyAV (av package)
    pkg-config \
    libavformat-dev \
    libavcodec-dev \
    libavdevice-dev \
    libavutil-dev \
    libswscale-dev \
    libswresample-dev \
    libavfilter-dev \
    # Clean up apt cache to reduce image size
    && rm -rf /var/lib/apt/lists/*

# -----------------------------------------------------------------------------
# CREATE APP DIRECTORY
# -----------------------------------------------------------------------------

WORKDIR /app

# -----------------------------------------------------------------------------
# CREATE MODELS DIRECTORY
# -----------------------------------------------------------------------------

# Create directory for Whisper models
# Models are downloaded on first run by faster-whisper
RUN mkdir -p /app/models

# -----------------------------------------------------------------------------
# INSTALL PYTHON DEPENDENCIES
# -----------------------------------------------------------------------------

# Copy requirements first (for Docker layer caching)
COPY whisper-stt/requirements.txt /app/requirements.txt

# Install Python packages
# Note: This will take a while as it downloads faster-whisper and dependencies
RUN pip install --no-cache-dir -r requirements.txt

# -----------------------------------------------------------------------------
# COPY APPLICATION CODE
# -----------------------------------------------------------------------------

# Copy the STT server application
COPY whisper-stt/stt_server.py /app/stt_server.py

# -----------------------------------------------------------------------------
# EXPOSE PORT
# -----------------------------------------------------------------------------

# The FastAPI server runs on port 5000
EXPOSE 5000

# -----------------------------------------------------------------------------
# HEALTH CHECK
# -----------------------------------------------------------------------------

# Check if the server is responding
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# -----------------------------------------------------------------------------
# RUN THE SERVER
# -----------------------------------------------------------------------------

# Start the FastAPI server with Uvicorn
# --host 0.0.0.0 : Listen on all interfaces (required for Docker)
# --port 5000    : Port to listen on
# --workers 1    : Single worker (RPI has limited resources)

CMD ["uvicorn", "stt_server:app", "--host", "0.0.0.0", "--port", "5000", "--workers", "1"]

