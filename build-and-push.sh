#!/bin/bash

# Build and push Docker images to Docker Hub
# Replace gonzalomg0 with your Docker Hub username

set -e

echo "🚀 Building Ollama + FastAPI image..."
echo ""

docker buildx build \
    --platform linux/arm64,linux/amd64 \
    -t docker.io/gonzalomg0/ollama-gemma:latest \
    -f Dockerfile.ollama \
    --push \
    .

echo ""
echo "🚀 Building WhatsApp Bridge image..."
echo ""

docker buildx build \
    --platform linux/arm64,linux/amd64 \
    -t docker.io/gonzalomg0/whatsapp-bridge:latest \
    -f Dockerfile.whatsapp \
    --push \
    .

echo ""
echo "✅ Both images built and pushed successfully!"
echo ""
echo "Deploy on Pi with: docker-compose up -d"
