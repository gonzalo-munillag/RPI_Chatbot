#!/bin/bash
# =============================================================================
# Audio Test Script for Raspberry Pi
# =============================================================================
# This script tests your USB speaker and microphone setup.
# It will:
#   1. Play a test tone through your speaker
#   2. Record audio from your microphone
#   3. Play back the recording so you can verify it worked
#
# Usage: ./test_audio.sh
#
# Before running, make sure to:
#   1. Update SPEAKER_CARD and MIC_CARD below with your card numbers
#   2. Run: chmod +x test_audio.sh
# =============================================================================

# -----------------------------------------------------------------------------
# CONFIGURATION - UPDATE THESE FOR YOUR SETUP
# -----------------------------------------------------------------------------
# Find your card numbers by running: aplay -l (for speaker) and arecord -l (for mic)
# Format: plughw:CARD_NUMBER,DEVICE_NUMBER
# We use 'plughw' instead of 'hw' to enable automatic format conversion

SPEAKER_CARD="plughw:2,0"    # Your USB speaker (Card 2, Device 0) # Change 2 to your speaker card number
MIC_CARD="plughw:3,0"        # Your USB microphone (Card 3, Device 0) # Change 3 to your microphone card number

# Recording settings
TEST_FILE="/tmp/test_recording.wav"  # Temporary file for the recording
RECORD_SECONDS=5                      # How long to record (in seconds)
SAMPLE_RATE=44100                     # Sample rate in Hz (44100 = CD quality)
SAMPLE_FORMAT="S16_LE"                # 16-bit signed, little endian

# -----------------------------------------------------------------------------
# COLORS FOR OUTPUT
# -----------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# -----------------------------------------------------------------------------
# HELPER FUNCTIONS
# -----------------------------------------------------------------------------

# Print a colored message
print_step() {
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}$1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if a command exists
check_command() {
    if ! command -v $1 &> /dev/null; then
        print_error "$1 is not installed. Install it with: sudo apt install alsa-utils"
        exit 1
    fi
}

# -----------------------------------------------------------------------------
# MAIN SCRIPT
# -----------------------------------------------------------------------------

echo ""
print_step "🎵 Raspberry Pi Audio Test Script"
echo ""

# Display configuration
echo "Configuration:"
echo "  🔊 Speaker device:    $SPEAKER_CARD"
echo "  🎤 Microphone device: $MIC_CARD"
echo "  📁 Test file:         $TEST_FILE"
echo "  ⏱️  Record duration:   $RECORD_SECONDS seconds"
echo "  🎼 Sample rate:       $SAMPLE_RATE Hz"
echo "  📊 Sample format:     $SAMPLE_FORMAT"
echo ""

# Check required commands are available
print_info "Checking required tools..."
check_command aplay
check_command arecord
check_command speaker-test
print_success "All required tools are installed"
echo ""

# -----------------------------------------------------------------------------
# STEP 1: Test Speaker with Pink Noise
# -----------------------------------------------------------------------------
print_step "Step 1: Testing Speaker (Pink Noise)"
echo ""
print_info "You should hear a hissing/static noise alternating between channels."
print_info "Press Ctrl+C after a few seconds to continue..."
echo ""

# speaker-test flags:
#   -c 2        : Test 2 channels (stereo)
#   -D hw:2,0   : Use direct hardware device (Card 2, Device 0)
#   -l 2        : Loop 2 times (about 6 seconds total)
# Note: We use hw: here because speaker-test works better with direct access
speaker-test -c 2 -D hw:2,0 -l 2 2>/dev/null

echo ""
read -p "Did you hear the test sound? (y/n): " speaker_result
if [[ $speaker_result == "y" || $speaker_result == "Y" ]]; then
    print_success "Speaker test passed!"
else
    print_error "Speaker test failed. Check your speaker connection and card number."
    echo "  Try running: aplay -l    to see available playback devices"
fi
echo ""

# -----------------------------------------------------------------------------
# STEP 2: Record from Microphone
# -----------------------------------------------------------------------------
print_step "Step 2: Recording from Microphone"
echo ""
print_info "Recording for $RECORD_SECONDS seconds..."
print_info "🎤 Speak now! Say something like: 'Hello, this is a test of Prometheus voice system'"
echo ""

# arecord flags:
#   -D plughw:3,0  : Device with plugin layer (allows format conversion)
#   -f S16_LE      : Sample format (Signed 16-bit, Little Endian)
#   -r 44100       : Sample rate (44100 Hz = CD quality)
#   -d 5           : Duration in seconds
#   test.wav       : Output filename
arecord -D $MIC_CARD -f $SAMPLE_FORMAT -r $SAMPLE_RATE -d $RECORD_SECONDS $TEST_FILE

# Check if recording was successful
if [[ -f $TEST_FILE ]]; then
    FILE_SIZE=$(du -h $TEST_FILE | cut -f1)
    print_success "Recording saved! File size: $FILE_SIZE"
else
    print_error "Recording failed. Check your microphone connection and card number."
    echo "  Try running: arecord -l    to see available recording devices"
    exit 1
fi
echo ""

# -----------------------------------------------------------------------------
# STEP 3: Playback Recording
# -----------------------------------------------------------------------------
print_step "Step 3: Playing Back Your Recording"
echo ""
print_info "🔊 You should hear your voice now..."
echo ""

# aplay flags:
#   -D plughw:2,0  : Device with plugin layer (converts mono to stereo)
#   test.wav       : Input filename
aplay -D $SPEAKER_CARD $TEST_FILE

echo ""
read -p "Did you hear your voice clearly? (y/n): " playback_result
if [[ $playback_result == "y" || $playback_result == "Y" ]]; then
    print_success "Playback test passed!"
else
    print_error "Playback test failed."
    echo "  - If recording worked but playback didn't, check speaker volume"
    echo "  - If audio was distorted, try a different sample rate"
fi
echo ""

# -----------------------------------------------------------------------------
# STEP 4: Cleanup
# -----------------------------------------------------------------------------
print_step "Step 4: Cleanup"
echo ""
print_info "Removing test file..."
rm -f $TEST_FILE
print_success "Test file removed"
echo ""

# -----------------------------------------------------------------------------
# SUMMARY
# -----------------------------------------------------------------------------
print_step "🎉 Audio Test Complete!"
echo ""

if [[ $speaker_result == "y" || $speaker_result == "Y" ]] && [[ $playback_result == "y" || $playback_result == "Y" ]]; then
    print_success "All tests passed! Your audio setup is working correctly."
    echo ""
    echo "Your working configuration:"
    echo "  Speaker:    $SPEAKER_CARD"
    echo "  Microphone: $MIC_CARD"
    echo ""
    echo "You can now proceed to the next step: Configure ALSA Defaults"
else
    print_error "Some tests failed. Please check the troubleshooting section in VOICE_SETUP.md"
    echo ""
    echo "Common issues:"
    echo "  1. Wrong card numbers - run 'aplay -l' and 'arecord -l' to verify"
    echo "  2. USB devices not connected properly - try unplugging and replugging"
    echo "  3. Permission issues - try running with 'sudo'"
fi
echo ""

