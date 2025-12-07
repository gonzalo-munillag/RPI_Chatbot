#!/bin/bash
# =============================================================================
# Deploy "Hey Prometheus" Wake Word Model
# =============================================================================
#
# This script trains the custom wake word model from recorded samples
# and deploys it to the wakeword Docker container.
#
# Prerequisites:
#   - Run train_hey_prometheus.sh first to record samples
#   - Samples should be in ~/prometheus_training/positive and ~/prometheus_training/negative
#
# Usage:
#   chmod +x deploy_prometheus_model.sh
#   ./deploy_prometheus_model.sh
#
# =============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
TRAINING_DIR="$HOME/prometheus_training"
POSITIVE_DIR="$TRAINING_DIR/positive"
NEGATIVE_DIR="$TRAINING_DIR/negative"
MODEL_DIR="$TRAINING_DIR/models"
MODEL_NAME="hey_prometheus"
MODEL_FILE="$MODEL_DIR/${MODEL_NAME}.onnx"

# Docker paths
DOCKER_COMPOSE_DIR="/var/www/ollama_chatbot"
DOCKER_VOLUME_PATH="/var/lib/docker/volumes/ollama_chatbot_wakeword-models/_data"
ENV_FILE="$DOCKER_COMPOSE_DIR/.env"

print_header() {
    echo ""
    echo -e "${BLUE}=============================================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}=============================================================================${NC}"
    echo ""
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# =============================================================================
# STEP 1: Verify samples exist
# =============================================================================

print_header "Step 1: Verifying Training Samples"

if [ ! -d "$POSITIVE_DIR" ]; then
    print_error "Positive samples directory not found: $POSITIVE_DIR"
    echo "Run train_hey_prometheus.sh first to record samples."
    exit 1
fi

if [ ! -d "$NEGATIVE_DIR" ]; then
    print_error "Negative samples directory not found: $NEGATIVE_DIR"
    echo "Run train_hey_prometheus.sh first to record samples."
    exit 1
fi

POSITIVE_COUNT=$(ls -1 "$POSITIVE_DIR"/*.wav 2>/dev/null | wc -l)
NEGATIVE_COUNT=$(ls -1 "$NEGATIVE_DIR"/*.wav 2>/dev/null | wc -l)

echo "Found samples:"
echo "  Positive (Hey Prometheus): $POSITIVE_COUNT"
echo "  Negative (other phrases):  $NEGATIVE_COUNT"

if [ "$POSITIVE_COUNT" -lt 10 ]; then
    print_error "Not enough positive samples (need at least 10, have $POSITIVE_COUNT)"
    exit 1
fi

if [ "$NEGATIVE_COUNT" -lt 10 ]; then
    print_error "Not enough negative samples (need at least 10, have $NEGATIVE_COUNT)"
    exit 1
fi

print_success "Samples verified!"

# =============================================================================
# STEP 2: Install training dependencies
# =============================================================================

print_header "Step 2: Installing Training Dependencies"

echo "Installing openwakeword..."
pip3 install --quiet openwakeword 2>/dev/null || pip3 install openwakeword

print_success "Dependencies installed!"

# =============================================================================
# STEP 3: Train the model
# =============================================================================

print_header "Step 3: Training Wake Word Model"

echo "This may take 10-30 minutes on Raspberry Pi..."
echo ""

mkdir -p "$MODEL_DIR"

# Create training script
cat > /tmp/train_model.py << 'PYTHON_SCRIPT'
import sys
import os

# Add paths
positive_dir = sys.argv[1]
negative_dir = sys.argv[2]
output_path = sys.argv[3]
model_name = sys.argv[4]

print(f"Training wake word model: {model_name}")
print(f"  Positive samples: {positive_dir}")
print(f"  Negative samples: {negative_dir}")
print(f"  Output: {output_path}")
print("")

try:
    # Try the newer API first
    from openwakeword.utils import train_custom_model
    
    print("Using openwakeword training API...")
    train_custom_model(
        positive_dir=positive_dir,
        negative_dir=negative_dir,
        output_path=output_path,
        model_name=model_name,
        epochs=50,
        batch_size=32
    )
    print(f"✅ Model saved to: {output_path}")
    
except ImportError as e:
    print(f"Training API not available: {e}")
    print("")
    print("Alternative: Use the web-based trainer at:")
    print("  https://github.com/dscripka/openWakeWord#training-custom-models")
    print("")
    print("Or install training dependencies:")
    print("  pip3 install openwakeword[training]")
    sys.exit(1)
    
except Exception as e:
    print(f"Training error: {e}")
    print("")
    print("If training fails, you can use the pre-trained 'hey_jarvis' model")
    print("and train a custom model later using the web interface.")
    sys.exit(1)
PYTHON_SCRIPT

# Run training
python3 /tmp/train_model.py "$POSITIVE_DIR" "$NEGATIVE_DIR" "$MODEL_FILE" "$MODEL_NAME"

if [ ! -f "$MODEL_FILE" ]; then
    print_warning "Model file not created by training script."
    echo ""
    echo "Would you like to continue with the pre-trained 'hey_jarvis' model instead? (y/n)"
    read -p "> " use_jarvis
    
    if [ "$use_jarvis" = "y" ]; then
        echo "Using hey_jarvis model..."
        MODEL_FILE=""  # Will skip copy step
        WAKE_WORD_MODEL="hey_jarvis"
    else
        print_error "Training failed. Please check the error messages above."
        exit 1
    fi
else
    print_success "Model trained successfully!"
    WAKE_WORD_MODEL="/app/models/${MODEL_NAME}.onnx"
fi

# =============================================================================
# STEP 4: Stop wakeword service
# =============================================================================

print_header "Step 4: Stopping Wakeword Service"

cd "$DOCKER_COMPOSE_DIR"
sudo docker-compose stop wakeword 2>/dev/null || true

print_success "Wakeword service stopped!"

# =============================================================================
# STEP 5: Copy model to Docker volume
# =============================================================================

print_header "Step 5: Deploying Model to Docker"

if [ -n "$MODEL_FILE" ] && [ -f "$MODEL_FILE" ]; then
    echo "Creating Docker volume directory..."
    sudo mkdir -p "$DOCKER_VOLUME_PATH"
    
    echo "Copying model to Docker volume..."
    sudo cp "$MODEL_FILE" "$DOCKER_VOLUME_PATH/"
    
    # Verify
    if sudo ls "$DOCKER_VOLUME_PATH/${MODEL_NAME}.onnx" > /dev/null 2>&1; then
        print_success "Model copied to Docker volume!"
        sudo ls -la "$DOCKER_VOLUME_PATH/"
    else
        print_error "Failed to copy model to Docker volume"
        exit 1
    fi
else
    echo "Skipping model copy (using built-in model)"
fi

# =============================================================================
# STEP 6: Update .env file
# =============================================================================

print_header "Step 6: Updating Environment Configuration"

# Remove old WAKE_WORD_MODEL if exists
if [ -f "$ENV_FILE" ]; then
    sudo sed -i '/^WAKE_WORD_MODEL=/d' "$ENV_FILE"
fi

# Add new WAKE_WORD_MODEL
echo "WAKE_WORD_MODEL=$WAKE_WORD_MODEL" | sudo tee -a "$ENV_FILE" > /dev/null

print_success "Updated .env with: WAKE_WORD_MODEL=$WAKE_WORD_MODEL"

# Show current .env
echo ""
echo "Current .env contents:"
cat "$ENV_FILE" | grep -v "^#" | grep -v "^$"

# =============================================================================
# STEP 7: Restart wakeword service
# =============================================================================

print_header "Step 7: Starting Wakeword Service"

cd "$DOCKER_COMPOSE_DIR"
sudo docker-compose up -d wakeword

# Wait for it to start
echo "Waiting for service to start..."
sleep 5

# Check if running
if sudo docker ps | grep -q wakeword; then
    print_success "Wakeword service started!"
else
    print_error "Service failed to start. Check logs:"
    echo "  sudo docker logs wakeword"
    exit 1
fi

# =============================================================================
# STEP 8: Start listening
# =============================================================================

print_header "Step 8: Activating Wake Word Detection"

echo "Starting wake word listener..."
curl -s -X POST http://localhost:5003/start | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Status: {d.get(\"status\", \"unknown\")}')" 2>/dev/null || curl -X POST http://localhost:5003/start

sleep 2

# Check status
echo ""
echo "Service status:"
curl -s http://localhost:5003/status | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'  Running: {d.get(\"running\", False)}'); print(f'  Listening: {d.get(\"listening\", False)}'); print(f'  Wake Word: {d.get(\"wake_word_model\", \"unknown\")}')" 2>/dev/null || curl http://localhost:5003/status

# =============================================================================
# DONE!
# =============================================================================

print_header "🎉 Deployment Complete!"

echo "Your wake word is now active!"
echo ""
if [ "$WAKE_WORD_MODEL" = "hey_jarvis" ]; then
    echo "Say: \"Hey Jarvis\" to activate the assistant"
else
    echo "Say: \"Hey Prometheus\" to activate the assistant"
fi
echo ""
echo "To view logs:"
echo "  sudo docker logs wakeword -f"
echo ""
echo "To stop:"
echo "  sudo docker-compose stop wakeword"
echo ""

