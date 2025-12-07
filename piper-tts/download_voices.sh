#!/bin/bash
# =============================================================================
# Download Voice Models for Piper TTS
# =============================================================================
#
# This script downloads voice models from Hugging Face to the local voices/
# directory. These voices will be copied into the Docker image during build.
#
# Run this script BEFORE building the Docker image:
#   ./piper-tts/download_voices.sh
#
# Then build the image:
#   ./build-and-push.sh
#
# =============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VOICES_DIR="$SCRIPT_DIR/voices"

# Base URL for Piper voices on Hugging Face
BASE_URL="https://huggingface.co/rhasspy/piper-voices/resolve/main"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Piper TTS Voice Downloader${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Create voices directory
mkdir -p "$VOICES_DIR"

# Function to download a voice
download_voice() {
    local VOICE_ID="$1"      # e.g., "en_GB-alba-medium"
    local LANG="$2"          # e.g., "en"
    local LANG_COUNTRY="$3"  # e.g., "en_GB"
    local NAME="$4"          # e.g., "alba"
    local QUALITY="$5"       # e.g., "medium"
    
    local URL_PATH="${LANG}/${LANG_COUNTRY}/${NAME}/${QUALITY}"
    local ONNX_URL="${BASE_URL}/${URL_PATH}/${VOICE_ID}.onnx"
    local JSON_URL="${BASE_URL}/${URL_PATH}/${VOICE_ID}.onnx.json"
    
    echo -e "${YELLOW}Downloading: ${VOICE_ID}${NC}"
    
    # Download .onnx model
    if wget -q --show-progress "$ONNX_URL" -O "$VOICES_DIR/${VOICE_ID}.onnx"; then
        echo -e "  ${GREEN}✅ Model downloaded${NC}"
    else
        echo -e "  ${RED}❌ Failed to download model${NC}"
        return 1
    fi
    
    # Download .json config
    if wget -q --show-progress "$JSON_URL" -O "$VOICES_DIR/${VOICE_ID}.onnx.json"; then
        echo -e "  ${GREEN}✅ Config downloaded${NC}"
    else
        echo -e "  ${RED}❌ Failed to download config${NC}"
        return 1
    fi
    
    echo ""
}

# =============================================================================
# VOICES TO DOWNLOAD
# =============================================================================
# Add or remove voices here as needed
# Format: download_voice "voice_id" "lang" "lang_country" "name" "quality"

echo -e "${YELLOW}Downloading default voice...${NC}"
echo ""

# Default voice: British English female (Alba)
download_voice "en_GB-alba-medium" "en" "en_GB" "alba" "medium"

# Uncomment to download additional voices:
download_voice "en_US-amy-medium" "en" "en_US" "amy" "medium"       # American female
download_voice "en_US-ryan-medium" "en" "en_US" "ryan" "medium"     # American male
# download_voice "en_GB-alan-medium" "en" "en_GB" "alan" "medium"     # British male
# download_voice "en_US-lessac-medium" "en" "en_US" "lessac" "medium" # American female (different)

# =============================================================================
# SUMMARY
# =============================================================================

echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}  ✅ Voice download complete!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "Downloaded voices:"
ls -lh "$VOICES_DIR"/*.onnx 2>/dev/null | while read line; do
    echo "  $line"
done
echo ""
echo "Total size:"
du -sh "$VOICES_DIR" | awk '{print "  " $1}'
echo ""
echo -e "${YELLOW}Next step:${NC} Run ./build-and-push.sh to build the Docker image"
echo ""

