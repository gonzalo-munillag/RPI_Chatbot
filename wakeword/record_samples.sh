#!/bin/bash
# =============================================================================
# Record Samples for "Hey Prometheus" Wake Word
# =============================================================================
#
# This script records audio samples on your Raspberry Pi for training
# a custom "Hey Prometheus" wake word model.
#
# NOTE: This script only RECORDS samples. To TRAIN the model, run:
#       ./train_and_deploy.sh
#
# Usage:
#   chmod +x record_samples.sh
#   ./record_samples.sh
#
# =============================================================================

set -e

# -----------------------------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------------------------

# Microphone device (change if your mic is on a different card)
MIC_DEVICE="plughw:3,0"

# Audio format settings
# Note: Most USB mics only support 44100Hz natively
# We record at 44100Hz - the model training will handle resampling
SAMPLE_RATE=44100
FORMAT="S16_LE"
CHANNELS=1
DURATION=2  # seconds per sample

# Number of samples to record
POSITIVE_SAMPLES=50
NEGATIVE_SAMPLES=30

# Output directories (relative to current working directory)
WORKING_DIR="$(pwd)"
BASE_DIR="$WORKING_DIR/prometheus_training"
POSITIVE_DIR="$BASE_DIR/positive"
NEGATIVE_DIR="$BASE_DIR/negative"
MODEL_DIR="$BASE_DIR/models"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# -----------------------------------------------------------------------------
# HELPER FUNCTIONS
# -----------------------------------------------------------------------------

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

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

countdown() {
    local seconds=$1
    local j  # Use different variable name to avoid conflict with main loop
    for j in $(seq $seconds -1 1); do
        echo -ne "\r   Starting in ${j}..."
        sleep 1
    done
    echo -ne "\r   🎤 RECORDING NOW!   \n"
}

# -----------------------------------------------------------------------------
# MAIN SCRIPT
# -----------------------------------------------------------------------------

print_header "🎯 Hey Prometheus Wake Word Training"

echo "This script will help you record audio samples to train a custom"
echo "'Hey Prometheus' wake word model."
echo ""
echo "Requirements:"
echo "  - USB Microphone connected"
echo "  - Quiet environment"
echo "  - ~10 minutes of your time"
echo ""

# -----------------------------------------------------------------------------
# STEP 1: Check microphone
# -----------------------------------------------------------------------------

print_header "Step 1: Checking Microphone"

echo "Testing microphone on device: $MIC_DEVICE"
echo ""

# Quick test recording (disable set -e temporarily for this test)
TEST_FILE="/tmp/mic_test.wav"
set +e  # Disable exit on error for the test
arecord -D $MIC_DEVICE -f $FORMAT -r $SAMPLE_RATE -c $CHANNELS -d 1 $TEST_FILE 2>&1
ARECORD_RESULT=$?
set -e  # Re-enable exit on error

if [ $ARECORD_RESULT -eq 0 ] && [ -f "$TEST_FILE" ] && [ -s "$TEST_FILE" ]; then
    print_success "Microphone working!"
    rm -f $TEST_FILE
else
    print_error "Microphone test failed (exit code: $ARECORD_RESULT)"
    echo ""
    echo "Available recording devices:"
    arecord -l
    echo ""
    echo "Trying to diagnose..."
    echo "Testing with different sample rates..."
    
    # Try 44100Hz
    if arecord -D $MIC_DEVICE -f $FORMAT -r 44100 -c $CHANNELS -d 1 /tmp/test44100.wav 2>&1; then
        echo "✅ 44100Hz works! Updating sample rate..."
        SAMPLE_RATE=44100
        rm -f /tmp/test44100.wav
    # Try 48000Hz
    elif arecord -D $MIC_DEVICE -f $FORMAT -r 48000 -c $CHANNELS -d 1 /tmp/test48000.wav 2>&1; then
        echo "✅ 48000Hz works! Updating sample rate..."
        SAMPLE_RATE=48000
        rm -f /tmp/test48000.wav
    else
        print_error "Could not find a working sample rate"
        echo "Update MIC_DEVICE at the top of this script if needed."
        exit 1
    fi
    
    print_success "Found working configuration: $SAMPLE_RATE Hz"
fi

# -----------------------------------------------------------------------------
# STEP 2: Create directories
# -----------------------------------------------------------------------------

print_header "Step 2: Setting Up Directories"

mkdir -p "$POSITIVE_DIR"
mkdir -p "$NEGATIVE_DIR"
mkdir -p "$MODEL_DIR"

print_success "Created: $BASE_DIR"
echo "  └── positive/  (for 'Hey Prometheus' samples)"
echo "  └── negative/  (for non-wake-word samples)"
echo "  └── models/    (for trained model)"

# -----------------------------------------------------------------------------
# STEP 3: Record positive samples
# -----------------------------------------------------------------------------

print_header "Step 3: Record POSITIVE Samples (Hey Prometheus)"

echo "You will record ${POSITIVE_SAMPLES} samples of yourself saying:"
echo ""
echo -e "   ${GREEN}\"Hey Prometheus\"${NC}"
echo ""
echo "Tips for good samples:"
echo "  - Vary your tone slightly (normal, louder, softer)"
echo "  - Speak naturally, as you would in real use"
echo "  - Keep consistent distance from microphone"
echo "  - Record in your typical environment"
echo ""
read -p "Press ENTER when ready to start recording positive samples..."

existing_positive=$(ls -1 "$POSITIVE_DIR"/*.wav 2>/dev/null | wc -l)
if [ "$existing_positive" -gt 0 ]; then
    echo ""
    print_warning "Found $existing_positive existing positive samples."
    read -p "Continue from where you left off? (y/n): " continue_choice
    if [ "$continue_choice" = "y" ]; then
        start_index=$((existing_positive + 1))
    else
        echo "Clearing existing samples..."
        rm -f "$POSITIVE_DIR"/*.wav
        start_index=1
    fi
else
    start_index=1
fi

echo ""
echo "DEBUG: Starting loop from $start_index to $POSITIVE_SAMPLES"

recorded_count=0
for i in $(seq $start_index $POSITIVE_SAMPLES); do
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "Sample ${GREEN}$i${NC} of ${POSITIVE_SAMPLES}"
    echo -e "Say: ${GREEN}\"Hey Prometheus\"${NC}"
    echo ""
    
    countdown 3
    
    # Record (disable set -e for recording)
    OUTPUT_FILE="$POSITIVE_DIR/positive_$(printf "%03d" $i).wav"
    echo "DEBUG: Recording to $OUTPUT_FILE"
    
    set +e
    arecord -D $MIC_DEVICE -f $FORMAT -r $SAMPLE_RATE -c $CHANNELS -d $DURATION "$OUTPUT_FILE"
    RECORD_RESULT=$?
    set -e
    
    echo "DEBUG: arecord exit code: $RECORD_RESULT"
    
    if [ $RECORD_RESULT -eq 0 ] && [ -f "$OUTPUT_FILE" ]; then
        print_success "Saved: $OUTPUT_FILE"
        recorded_count=$((recorded_count + 1))
    else
        print_error "Recording failed for sample $i (exit code: $RECORD_RESULT)"
        if [ -f "$OUTPUT_FILE" ]; then
            echo "DEBUG: File exists but arecord returned error"
            ls -la "$OUTPUT_FILE"
        else
            echo "DEBUG: File does not exist"
        fi
    fi
    
    # Brief pause between recordings
    sleep 0.5
    
    # Show progress every 10 samples
    if [ $((i % 10)) -eq 0 ]; then
        echo ""
        echo "DEBUG: Progress - $recorded_count samples recorded so far"
        ls "$POSITIVE_DIR"/*.wav 2>/dev/null | wc -l
        echo ""
    fi
done

echo ""
echo "DEBUG: Loop complete. Files in directory:"
ls -la "$POSITIVE_DIR"/ | head -20

print_success "Recorded $recorded_count positive samples!"

# -----------------------------------------------------------------------------
# STEP 4: Record negative samples
# -----------------------------------------------------------------------------

print_header "Step 4: Record NEGATIVE Samples (NOT Hey Prometheus)"

echo "Now record ${NEGATIVE_SAMPLES} samples of phrases that are NOT 'Hey Prometheus'"
echo ""
echo "Suggested phrases (say different ones each time):"
echo -e "  ${YELLOW}• \"Hey\"${NC}"
echo -e "  ${YELLOW}• \"Prometheus\"${NC}"
echo -e "  ${YELLOW}• \"Hello\"${NC}"
echo -e "  ${YELLOW}• \"Hey there\"${NC}"
echo -e "  ${YELLOW}• \"Hey Siri\"${NC}"
echo -e "  ${YELLOW}• \"OK Google\"${NC}"
echo -e "  ${YELLOW}• \"Hi Prometheus\"${NC}"
echo -e "  ${YELLOW}• Random conversation${NC}"
echo -e "  ${YELLOW}• Silence / background noise${NC}"
echo ""
read -p "Press ENTER when ready to start recording negative samples..."

existing_negative=$(ls -1 "$NEGATIVE_DIR"/*.wav 2>/dev/null | wc -l)
if [ "$existing_negative" -gt 0 ]; then
    echo ""
    print_warning "Found $existing_negative existing negative samples."
    read -p "Continue from where you left off? (y/n): " continue_choice
    if [ "$continue_choice" = "y" ]; then
        start_index=$((existing_negative + 1))
    else
        echo "Clearing existing samples..."
        rm -f "$NEGATIVE_DIR"/*.wav
        start_index=1
    fi
else
    start_index=1
fi

echo ""
for i in $(seq $start_index $NEGATIVE_SAMPLES); do
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "Sample ${YELLOW}$i${NC} of ${NEGATIVE_SAMPLES}"
    echo -e "Say: ${YELLOW}Something that is NOT 'Hey Prometheus'${NC}"
    echo ""
    
    countdown 3
    
    # Record (disable set -e for recording)
    OUTPUT_FILE="$NEGATIVE_DIR/negative_$(printf "%03d" $i).wav"
    set +e
    arecord -D $MIC_DEVICE -f $FORMAT -r $SAMPLE_RATE -c $CHANNELS -d $DURATION "$OUTPUT_FILE" 2>&1
    RECORD_RESULT=$?
    set -e
    
    if [ $RECORD_RESULT -eq 0 ] && [ -f "$OUTPUT_FILE" ]; then
        print_success "Saved: $OUTPUT_FILE"
    else
        print_error "Recording failed for sample $i (exit code: $RECORD_RESULT)"
        echo "Retrying..."
        continue
    fi
    
    # Brief pause between recordings
    if [ $i -lt $NEGATIVE_SAMPLES ]; then
        sleep 0.5
    fi
done

print_success "Recorded $NEGATIVE_SAMPLES negative samples!"

# -----------------------------------------------------------------------------
# STEP 5: Summary and next steps
# -----------------------------------------------------------------------------

print_header "🎉 Recording Complete!"

echo "Sample counts:"
positive_count=$(ls -1 "$POSITIVE_DIR"/*.wav 2>/dev/null | wc -l)
negative_count=$(ls -1 "$NEGATIVE_DIR"/*.wav 2>/dev/null | wc -l)
echo "  Positive samples: $positive_count"
echo "  Negative samples: $negative_count"
echo ""
echo "Samples saved to: $BASE_DIR"
echo ""

print_header "📋 Next Step: Train & Deploy"

echo "Now run the training script to train the model and deploy it:"
echo ""
echo "  ./train_and_deploy.sh"
echo ""
echo "This will:"
echo "  1. Verify your samples"
echo "  2. Train the wake word model (10-30 minutes on Pi)"
echo "  3. Deploy to the wakeword Docker container"
echo "  4. Start listening for 'Hey Prometheus'"
echo ""

