#!/bin/bash

# Build and push Docker images to Docker Hub
# Reads DOCKER_USERNAME from .env file

set -e

# Load environment variables from .env file
if [ -f .env ]; then
    export $(grep -v '^#' .env | grep DOCKER_USERNAME | xargs)
else
    echo "❌ Error: .env file not found!"
    echo "Please create a .env file with your DOCKER_USERNAME"
    exit 1
fi

# Check if DOCKER_USERNAME is set
if [ -z "$DOCKER_USERNAME" ]; then
    echo "❌ Error: DOCKER_USERNAME not found in .env file!"
    echo "Please add: DOCKER_USERNAME=your_dockerhub_username"
    exit 1
fi

echo "🚀 Building images for Docker Hub user: $DOCKER_USERNAME"
echo ""

echo "🚀 Building Ollama + FastAPI image..."
echo ""

docker buildx build \
    --platform linux/arm64,linux/amd64 \
    -t docker.io/$DOCKER_USERNAME/ollama-gemma:latest \
    -f Dockerfile.ollama \
    --push \
    .

echo ""
echo "🚀 Building WhatsApp Bridge image..."
echo ""

docker buildx build \
    --platform linux/arm64,linux/amd64 \
    -t docker.io/$DOCKER_USERNAME/whatsapp-bridge:latest \
    -f Dockerfile.whatsapp \
    --push \
    .

echo ""
echo "🚀 Building Piper TTS image..."
echo ""

docker buildx build \
    --platform linux/arm64,linux/amd64 \
    -t docker.io/$DOCKER_USERNAME/piper-tts:latest \
    -f piper-tts/Dockerfile \
    --push \
    .

echo ""
echo "✅ All images built and pushed successfully!"
echo "   Images: $DOCKER_USERNAME/ollama-gemma:latest"
echo "           $DOCKER_USERNAME/whatsapp-bridge:latest"
echo "           $DOCKER_USERNAME/piper-tts:latest"
echo ""
echo "Deploy on Pi with: docker-compose up -d"
