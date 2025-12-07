#!/bin/bash
# =============================================================================
# ALSA Defaults Test Script for Raspberry Pi
# =============================================================================
# This script tests that your ~/.asoundrc configuration is working correctly.
# It verifies that ALSA uses your USB speaker and microphone as defaults.
#
# Prerequisites:
#   - ~/.asoundrc file must be configured (see setup_alsa_defaults.sh)
#   - USB speaker connected (Card 2)
#   - USB microphone connected (Card 3)
#
# Usage: ./test_alsa_defaults.sh
#
# What this script does:
#   1. Tests default playback (speaker-test without -D flag)
#   2. Tests default recording (arecord without -D flag)
#   3. Tests playback of the recording (aplay without -D flag)
#   4. Cleans up test files
# =============================================================================

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

# -----------------------------------------------------------------------------
# CONFIGURATION
# -----------------------------------------------------------------------------
TEST_FILE="/tmp/alsa_defaults_test.wav"  # Temporary file for recording
RECORD_SECONDS=3                          # Recording duration

# -----------------------------------------------------------------------------
# MAIN SCRIPT
# -----------------------------------------------------------------------------

echo ""
print_step "🔊 ALSA Defaults Test Script"
echo ""

# Check if .asoundrc exists
if [[ -f ~/.asoundrc ]]; then
    print_success "Found ~/.asoundrc configuration file"
else
    print_error "~/.asoundrc not found!"
    echo "Please run setup_alsa_defaults.sh first to create the configuration."
    exit 1
fi
echo ""

# -----------------------------------------------------------------------------
# STEP 1: Test Default Playback (Speaker)
# -----------------------------------------------------------------------------
print_step "Step 1: Testing Default Playback"
echo ""
print_info "Playing test sound through DEFAULT device..."
print_info "If .asoundrc is configured correctly, you'll hear noise from your USB speaker."
print_info "(NOT from HDMI)"
echo ""

# speaker-test without -D flag = uses default device
# -c 2   : 2 channels (stereo)
# -l 1   : loop 1 time (about 3-4 seconds)
# 2>/dev/null : suppress error messages for cleaner output
# &      : run in background so we can control timing
# $!     : gets the PID (Process ID) of the last background command

speaker-test -c 2 -l 1 2>/dev/null &
SPEAKER_PID=$!      # Store the process ID
sleep 3             # Wait 3 seconds
kill $SPEAKER_PID 2>/dev/null  # Kill the process (stop the sound)

echo ""
read -p "Did you hear the test sound from your USB speaker? (y/n): " speaker_result
echo ""

# -----------------------------------------------------------------------------
# STEP 2: Test Default Recording (Microphone)
# -----------------------------------------------------------------------------
print_step "Step 2: Testing Default Recording"
echo ""
print_info "Recording from DEFAULT device for $RECORD_SECONDS seconds..."
print_info "If .asoundrc is configured correctly, it will use your USB microphone."
echo ""
echo -e "${YELLOW}🎤 Speak now! Say something into your microphone...${NC}"
echo ""

# arecord without -D flag = uses default device
# -f S16_LE  : Format - Signed 16-bit, Little Endian
# -r 44100   : Sample rate - 44100 Hz (CD quality)
# -d 3       : Duration - 3 seconds

arecord -f S16_LE -r 44100 -d $RECORD_SECONDS $TEST_FILE

# Check if file was created and has content
if [[ -f $TEST_FILE ]]; then
    FILE_SIZE=$(du -h $TEST_FILE | cut -f1)
    print_success "Recording saved! File size: $FILE_SIZE"
else
    print_error "Recording failed!"
    exit 1
fi
echo ""

# -----------------------------------------------------------------------------
# STEP 3: Test Default Playback of Recording
# -----------------------------------------------------------------------------
print_step "Step 3: Playing Back Your Recording"
echo ""
print_info "Playing back through DEFAULT device..."
print_info "You should hear your voice from the USB speaker."
echo ""

# aplay without -D flag = uses default device
aplay $TEST_FILE

echo ""
read -p "Did you hear your voice from the USB speaker? (y/n): " playback_result
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
print_step "🎉 ALSA Defaults Test Complete!"
echo ""

if [[ $speaker_result == "y" || $speaker_result == "Y" ]] && [[ $playback_result == "y" || $playback_result == "Y" ]]; then
    print_success "All tests passed! Your ALSA defaults are configured correctly."
    echo ""
    echo "What this means:"
    echo "  ✅ Applications will automatically use your USB speaker for output"
    echo "  ✅ Applications will automatically use your USB microphone for input"
    echo "  ✅ No need to specify -D flag in most commands"
    echo ""
    echo "You can now proceed to Step 2: Install Piper TTS"
else
    print_error "Some tests failed."
    echo ""
    echo "Troubleshooting:"
    echo "  1. Check ~/.asoundrc has correct card numbers"
    echo "  2. Verify cards with: aplay -l (speaker) and arecord -l (mic)"
    echo "  3. Your cards should be: Speaker=Card 2, Mic=Card 3"
    echo "  4. If different, edit ~/.asoundrc and change the card numbers"
fi
echo ""

