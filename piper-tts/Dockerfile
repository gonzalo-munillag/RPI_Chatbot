# =============================================================================
# Dockerfile for Piper TTS Service
# =============================================================================
#
# This Dockerfile builds a container that:
#   1. Runs the Piper TTS binary (text-to-speech)
#   2. Exposes a FastAPI HTTP server for TTS requests
#   3. Can play audio through the host's ALSA devices (speaker)
#
# Build for ARM64 (Raspberry Pi):
#   docker buildx build --platform linux/arm64 -t piper-tts -f piper-tts/Dockerfile .
#
# Run:
#   docker run -d --device /dev/snd -p 5000:5000 piper-tts
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
LABEL description="Piper TTS Server for Raspberry Pi"
LABEL version="1.0"

# -----------------------------------------------------------------------------
# ENVIRONMENT VARIABLES
# -----------------------------------------------------------------------------

# Piper version to download
ENV PIPER_VERSION="2023.11.14-2"

# Voice model to use (can be overridden at runtime)
ENV VOICE_MODEL="/app/voices/en_GB-alba-medium.onnx"

# Piper binary location
ENV PIPER_BINARY="/app/piper/piper"

# Audio sample rate (Piper default)
ENV SAMPLE_RATE="22050"

# Python settings
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# -----------------------------------------------------------------------------
# INSTALL SYSTEM DEPENDENCIES
# -----------------------------------------------------------------------------

RUN apt-get update && apt-get install -y --no-install-recommends \
    # ALSA utilities for audio playback (aplay command)
    alsa-utils \
    # Required for downloading Piper binary
    wget \
    # Required for healthcheck
    curl \
    # CA certificates for HTTPS downloads
    ca-certificates \
    # Clean up apt cache to reduce image size
    && rm -rf /var/lib/apt/lists/*

# -----------------------------------------------------------------------------
# CREATE APP DIRECTORY
# -----------------------------------------------------------------------------

WORKDIR /app

# -----------------------------------------------------------------------------
# DOWNLOAD AND INSTALL PIPER
# -----------------------------------------------------------------------------

# Download Piper binary for ARM64 (Raspberry Pi)
# The tar.gz contains a 'piper' directory with the binary and libraries
RUN wget -q "https://github.com/rhasspy/piper/releases/download/${PIPER_VERSION}/piper_linux_aarch64.tar.gz" \
    && tar -xzf piper_linux_aarch64.tar.gz \
    && rm piper_linux_aarch64.tar.gz \
    # Verify the binary exists
    && ls -la /app/piper/ \
    # Make sure it's executable
    && chmod +x /app/piper/piper

# -----------------------------------------------------------------------------
# COPY VOICE MODELS (downloaded locally before build)
# -----------------------------------------------------------------------------

# Create voices directory
RUN mkdir -p /app/voices

# Copy voice models from local piper-tts/voices/ directory
# These must be downloaded locally before building (run: ./piper-tts/download_voices.sh)
# The .dockerignore does NOT ignore these files so they're included in build context
COPY piper-tts/voices/*.onnx /app/voices/
COPY piper-tts/voices/*.json /app/voices/

# Verify voices were copied
RUN ls -la /app/voices/

# -----------------------------------------------------------------------------
# INSTALL PYTHON DEPENDENCIES
# -----------------------------------------------------------------------------

# Copy requirements first (for Docker layer caching)
COPY piper-tts/requirements.txt /app/requirements.txt

# Install Python packages
RUN pip install --no-cache-dir -r requirements.txt

# -----------------------------------------------------------------------------
# COPY APPLICATION CODE
# -----------------------------------------------------------------------------

# Copy the TTS server application
COPY piper-tts/tts_server.py /app/tts_server.py

# -----------------------------------------------------------------------------
# EXPOSE PORT
# -----------------------------------------------------------------------------

# The FastAPI server runs on port 5000
EXPOSE 5000

# -----------------------------------------------------------------------------
# HEALTH CHECK
# -----------------------------------------------------------------------------

# Check if the server is responding
# Using curl with GET request (wget --spider uses HEAD which FastAPI doesn't support by default)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# -----------------------------------------------------------------------------
# RUN THE SERVER
# -----------------------------------------------------------------------------

# Start the FastAPI server with Uvicorn
# --host 0.0.0.0 : Listen on all interfaces (required for Docker)
# --port 5000    : Port to listen on
# --workers 1    : Single worker (RPI has limited resources)

CMD ["uvicorn", "tts_server:app", "--host", "0.0.0.0", "--port", "5000", "--workers", "1"]

