# 🎤 Voice Setup Guide for Prometheus AI

This guide walks you through adding **voice capabilities** to your Raspberry Pi Prometheus chatbot. By the end, you'll have:

1. **Text-to-Speech (TTS)**: Prometheus speaks its responses through a speaker
2. **Speech-to-Text (STT)**: You speak to Prometheus through a microphone  
3. **Wake Word Detection**: Say "Prometheus" to activate voice interaction

---

## 📋 Table of Contents

- [Hardware Requirements](#-hardware-requirements)
- [Architecture Overview](#-architecture-overview)
- [Step 1: Detect Audio Hardware](#-step-1-detect-audio-hardware)
  - [1a. List Playback Devices (Speakers)](#1a-list-playback-devices-speakers)
  - [1b. List Recording Devices (Microphones)](#1b-list-recording-devices-microphones)
  - [1c. Check All Sound Cards](#1c-check-all-sound-cards)
  - [1d. Verify USB Connection](#1d-verify-usb-connection)
  - [Understanding Your Output](#-understanding-your-output)
- [Step 2: Test Speaker Output](#-step-2-test-speaker-output)
- [Step 3: Test Microphone Input](#-step-3-test-microphone-input)
- [Step 4: Configure ALSA Defaults](#-step-4-configure-alsa-defaults)
- [Step 5: Install Piper TTS](#-step-5-install-piper-tts)
- [Step 6: Install Whisper STT](#-step-6-install-whisper-stt)
- [Step 7: Install openWakeWord](#-step-7-install-openwakeword)
- [Step 8: Voice Pipeline Integration](#-step-8-voice-pipeline-integration)
- [Troubleshooting](#-troubleshooting)

---

## 🛒 Hardware Requirements

The Raspberry Pi 5 does **NOT** have a built-in microphone or speaker. You must purchase external USB audio devices.

### Required Hardware

| Component | Required | Notes |
|-----------|----------|-------|
| Raspberry Pi 5 | ✅ | 8GB recommended for voice + LLM |
| USB Microphone | ✅ | For voice input |
| USB Speaker | ✅ | For voice output |
| MicroSD Card | ✅ | 32GB+ recommended |

### Recommended Hardware (Tested & Working)

These are the exact devices used in this project:

#### USB Speaker
- **Model**: Jieli Technology UACDemoV1.0
- **Why**: Plug-and-play, no drivers needed, recognized as ALSA card
- **Alternative**: Any USB speaker or USB sound card with 3.5mm output

#### USB Microphone  
- **Model**: C-Media Electronics USB PnP Sound Device (Texas Instruments PCM2902 Audio Codec)
- **Why**: High compatibility with Linux, good audio quality for voice recognition
- **Alternative**: Any USB microphone or USB sound card with 3.5mm input

---

## 🏗️ Architecture Overview

### Current System (Text Only)
```
┌─────────────┐    ┌──────────────────┐    ┌─────────┐    ┌────────┐
│  WhatsApp   │───▶│  WhatsApp Bridge │───▶│ FastAPI │───▶│ Ollama │
│   (User)    │◀───│    (Node.js)     │◀───│(Python) │◀───│(Gemma) │
└─────────────┘    └──────────────────┘    └─────────┘    └────────┘
      Text               Text                 Text          Text
```

### New System (Text + Voice)
```
┌─────────────┐    ┌──────────────────┐    ┌─────────┐    ┌────────┐
│  WhatsApp   │───▶│  WhatsApp Bridge │───▶│ FastAPI │───▶│ Ollama │
│   (User)    │◀───│    (Node.js)     │◀───│(Python) │◀───│(Gemma) │
└─────────────┘    └──────────────────┘    └─────────┘    └────────┘
                                                │
                                                ▼
                                         ┌────────────┐
                                         │ Piper TTS  │───▶ 🔊 Speaker
                                         └────────────┘
                                               
┌────────────────┐     ┌──────────────────┐     ┌─────────┐
│ 🎤 "Prometheus"│ ───▶│  openWakeWord     │───▶│ Whisper │
│  (Wake Word)   │     │  (Detection)     │     │  (STT)  │
└────────────────┘     └──────────────────┘     └─────────┘
                                                │
                                                ▼
                                            ┌─────────┐    ┌────────┐    ┌────────────┐
                                            │ FastAPI │───▶│ Ollama │───▶│ Piper TTS  │───▶ 🔊 Speaker
                                            └─────────┘    └────────┘    └────────────┘
```

### Voice Pipeline Components

| Component | Purpose | Technology |
|-----------|---------|------------|
| **Wake Word Detection** | Listen for "Prometheus" trigger | [openWakeWord](https://github.com/dscripka/openWakeWord) |
| **Speech-to-Text (STT)** | Convert your voice to text | [Whisper](https://github.com/openai/whisper) (tiny/base model) |
| **LLM Processing** | Generate intelligent responses | Gemma-2-2b via Ollama |
| **Text-to-Speech (TTS)** | Convert text responses to speech | [Piper](https://github.com/rhasspy/piper) |

---

## 🔍 Step 1: Detect Audio Hardware

Before configuring audio, we need to identify what devices your Raspberry Pi recognizes.

### 1a. List Playback Devices (Speakers)

**Command:**
```bash
aplay -l
```

**What this command does:**
- `aplay` = ALSA (Advanced Linux Sound Architecture) playback utility
- `-l` = list all playback hardware devices
- Shows all devices capable of **outputting** sound

**Example output:**
```
**** List of PLAYBACK Hardware Devices ****
card 0: vc4hdmi0 [vc4-hdmi-0], device 0: MAI PCM i2s-hifi-0 [MAI PCM i2s-hifi-0]
  Subdevices: 1/1
  Subdevice #0: subdevice #0
card 1: vc4hdmi1 [vc4-hdmi-1], device 0: MAI PCM i2s-hifi-0 [MAI PCM i2s-hifi-0]
  Subdevices: 1/1
  Subdevice #0: subdevice #0
card 2: UACDemoV10 [UACDemoV1.0], device 0: USB Audio [USB Audio]
  Subdevices: 1/1
  Subdevice #0: subdevice #0
```

**Understanding the output:**
| Card | Name | What It Is |
|------|------|------------|
| card 0 | vc4hdmi0 | HDMI port 0 audio (built into RPI) |
| card 1 | vc4hdmi1 | HDMI port 1 audio (built into RPI) |
| card 2 | UACDemoV10 | **Your USB speaker** ✅ |

---

### 1b. List Recording Devices (Microphones)

**Command:**
```bash
arecord -l
```

**What this command does:**
- `arecord` = ALSA recording utility
- `-l` = list all recording hardware devices  
- Shows all devices capable of **capturing** sound

**Example output:**
```
**** List of CAPTURE Hardware Devices ****
card 3: Device [USB PnP Sound Device], device 0: USB Audio [USB Audio]
  Subdevices: 1/1
  Subdevice #0: subdevice #0
```

**Understanding the output:**
| Card | Name | What It Is |
|------|------|------------|
| card 3 | USB PnP Sound Device | **Your USB microphone** ✅ |

---

### 1c. Check All Sound Cards

**Command:**
```bash
cat /proc/asound/cards
```

**What this command does:**
- `/proc/asound/cards` = virtual file maintained by the Linux kernel
- Lists all sound cards the system recognizes
- Shows card numbers and manufacturer information

**Example output:**
```
 0 [vc4hdmi0       ]: vc4-hdmi - vc4-hdmi-0
                      vc4-hdmi-0
 1 [vc4hdmi1       ]: vc4-hdmi - vc4-hdmi-1
                      vc4-hdmi-1
 2 [UACDemoV10     ]: USB-Audio - UACDemoV1.0
                      Jieli Technology UACDemoV1.0 at usb-xhci-hcd.1-2, full speed
 3 [Device         ]: USB-Audio - USB PnP Sound Device
                      C-Media Electronics Inc. USB PnP Sound Device at usb-xhci-hcd.0-2, full speed
```

**Understanding the output:**
- Cards 0-1: Built-in HDMI audio (for monitors with speakers)
- Card 2: Your USB speaker (Jieli Technology)
- Card 3: Your USB microphone (C-Media Electronics)

---

### 1d. Verify USB Connection

**Command:**
```bash
lsusb
```

**What this command does:**
- `lsusb` = list USB devices
- Shows all devices connected to USB ports
- Displays vendor ID, product ID, and device name

**Example output:**
```
Bus 004 Device 001: ID 1d6b:0003 Linux Foundation 3.0 root hub
Bus 003 Device 002: ID 4c4a:4155 Jieli Technology UACDemoV1.0
Bus 003 Device 001: ID 1d6b:0002 Linux Foundation 2.0 root hub
Bus 002 Device 001: ID 1d6b:0003 Linux Foundation 3.0 root hub
Bus 001 Device 002: ID 08bb:2902 Texas Instruments PCM2902 Audio Codec
Bus 001 Device 001: ID 1d6b:0002 Linux Foundation 2.0 root hub
```

**Understanding the output:**
| Vendor | Product | What It Is |
|--------|---------|------------|
| Jieli Technology | UACDemoV1.0 | **Your USB speaker** ✅ |
| Texas Instruments | PCM2902 Audio Codec | **Your USB microphone** ✅ |
| Linux Foundation | root hub | USB controller (ignore) |

---

### 📊 Understanding Your Output

After running all commands, you should be able to fill in this table:

| Device Type | Card Number | Device Name | Status |
|-------------|-------------|-------------|--------|
| USB Speaker | ? | ? | ✅ / ❌ |
| USB Microphone | ? | ? | ✅ / ❌ |

**For reference, this project uses:**

| Device Type | Card Number | Device Name | Vendor |
|-------------|-------------|-------------|--------|
| USB Speaker | 2 | UACDemoV1.0 | Jieli Technology |
| USB Microphone | 3 | USB PnP Sound Device | C-Media Electronics |

> 📝 **Write down your card numbers!** You'll need them for the next steps.

---

## 🔊 Step 2: Test Speaker Output

Now that we've identified the audio devices, let's test that your speaker actually produces sound.

### Understanding ALSA (Advanced Linux Sound Architecture)

Before we run the test, let's understand how Linux handles audio:

```
┌─────────────────────────────────────────────────────────────────────┐
│                        YOUR APPLICATION                             │
│                    (aplay, Piper TTS, etc.)                         │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                           ALSA LIBRARY                              │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐  │
│  │   hw:X,Y        │    │   plughw:X,Y    │    │    default      │  │
│  │ (Direct Access) │    │ (With Plugins)  │    │ (System Default)│  │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        ALSA KERNEL DRIVER                           │
│                      (snd-usb-audio module)                         │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         USB HARDWARE                                │
│                    (Your speaker/microphone)                        │
└─────────────────────────────────────────────────────────────────────┘
```

**ALSA** is the standard Linux audio system. It provides:
- **Kernel drivers** that talk to hardware
- **User-space library** that applications use
- **Virtual devices** (`hw:`, `plughw:`, `default`) for accessing hardware

### ALSA Device Naming Convention

ALSA uses a specific naming format to identify audio devices:

```
hw:CARD,DEVICE
```

| Component | Meaning | Example |
|-----------|---------|---------|
| `hw:` | Direct hardware access (no conversion) | `hw:2,0` |
| `CARD` | Sound card number (from `aplay -l`) | `2` = your USB speaker |
| `DEVICE` | Device number within the card (usually `0`) | `0` |

**Example:** `hw:2,0` means "Card 2, Device 0" = Your USB speaker

### Speaker Test Command

**Command:**
```bash
speaker-test -c 2 -D hw:2,0
```

**Flag breakdown:**

| Flag | Value | Meaning |
|------|-------|---------|
| `-c` | `2` | Number of **channels** to test (2 = stereo: left + right) |
| `-D` | `hw:2,0` | **Device** to use (Card 2, Device 0 = your USB speaker) |

**What happens when you run this:**
1. ALSA opens direct connection to Card 2, Device 0
2. Generates "pink noise" (random audio signal)
3. Alternates between left and right channels
4. Displays timing information
5. Press `Ctrl+C` to stop

**Expected output:**
```
speaker-test 1.2.8

Playback device is hw:2,0
Stream parameters are 48000Hz, S16_LE, 2 channels
Using 16 octaves of pink noise
Rate set to 48000Hz (requested 48000Hz)
Buffer size range from 96 to 96000
Period size range from 48 to 48000
Using max buffer size 96000
Periods = 4
was set period_size = 24000
was set buffer_size = 96000
 0 - Front Left
 1 - Front Right
Time per period = 3.986285
```

**Understanding the output:**
| Parameter | Value | Meaning |
|-----------|-------|---------|
| `48000Hz` | Sample rate | 48,000 samples per second (CD quality = 44100Hz) |
| `S16_LE` | Sample format | Signed 16-bit, Little Endian |
| `2 channels` | Channel count | Stereo audio |
| `Front Left/Right` | Current channel | Which speaker is playing |

### ✅ Success Criteria

You should hear a "hissing" or "static" noise alternating between speakers (or both if mono speaker).

---

## 🎤 Step 3: Test Microphone Input

Testing the microphone involves two steps: recording audio, then playing it back.

### Understanding Audio Formats

Digital audio has several key parameters that must match between recording and playback:

#### Sample Format (Bit Depth)

| Format | Bits | Range | Quality |
|--------|------|-------|---------|
| `U8` | 8-bit unsigned | 0 to 255 | Low (telephone quality) |
| `S16_LE` | 16-bit signed | -32,768 to 32,767 | Good (CD quality) ✅ |
| `S24_LE` | 24-bit signed | -8,388,608 to 8,388,607 | High (studio quality) |
| `S32_LE` | 32-bit signed | Full 32-bit range | Professional |

**What does `S16_LE` mean?**
- `S` = **Signed** (can represent negative values, for audio waves that oscillate)
- `16` = **16 bits** per sample (65,536 possible values)
- `LE` = **Little Endian** (byte order: least significant byte first)

```
Audio Wave Visualization:

     +32767 ─┐      ╭───╮      ╭───╮
             │     ╱     ╲    ╱     ╲
         0 ──┼────╱───────╲──╱───────╲────  ← Zero crossing
             │   ╱         ╲╱         ╲
    -32768 ─┴──╯                       ╰──
             
             Each point is a 16-bit sample
```

#### Sample Rate (Frequency)

| Rate | Samples/Second | Use Case |
|------|----------------|----------|
| 8000 Hz | 8,000 | Telephone |
| 16000 Hz | 16,000 | Speech recognition ✅ |
| 22050 Hz | 22,050 | Low-quality audio |
| 44100 Hz | 44,100 | CD quality audio ✅ |
| 48000 Hz | 48,000 | Professional audio/video |

**Why does sample rate matter?**

The **Nyquist theorem** states you need at least 2x the highest frequency to capture:
- Human speech: up to ~8kHz → needs 16kHz+ sample rate
- Human hearing: up to ~20kHz → needs 44.1kHz+ sample rate

#### Channels

| Channels | Name | Description |
|----------|------|-------------|
| 1 | Mono | Single audio stream |
| 2 | Stereo | Left + Right channels |

**Most microphones are mono** (1 channel) - they capture from a single point.
**Most speakers expect stereo** (2 channels) - even if they combine them.

### The Format Mismatch Problem

When we first tried to record and play back, we encountered two issues:

#### Issue 1: Wrong Sample Format

**Failed command:**
```bash
arecord -D hw:3,0 -d 5 test.wav
```

**Error:**
```
Warning: Some sources (like microphones) may produce inaudible results
         with 8-bit sampling. Use '-f' argument to increase resolution
Recording WAVE 'test.wav' : Unsigned 8 bit, Rate 8000 Hz, Mono
arecord: set_params:1352: Sample format non available
Available formats:
- S16_LE
```

**What happened:**
1. `arecord` defaulted to 8-bit unsigned (`U8`) format
2. Your microphone only supports 16-bit signed (`S16_LE`)
3. ALSA couldn't configure the hardware → recording failed

**Fix:** Explicitly specify `-f S16_LE`

#### Issue 2: Wrong Sample Rate

**Failed command:**
```bash
arecord -D hw:3,0 -f S16_LE -r 16000 -d 5 test.wav
```

**Warning:**
```
Warning: rate is not accurate (requested = 16000Hz, got = 44100Hz)
         please, try the plug plugin
```

**What happened:**
1. We requested 16kHz sample rate
2. Microphone hardware only supports 44.1kHz
3. ALSA used 44.1kHz anyway (but warned us)

**Fix:** Use `-r 44100` to match hardware capability

#### Issue 3: Channel Count Mismatch

**Failed command:**
```bash
aplay -D hw:2,0 test.wav
```

**Error:**
```
aplay: set_params:1358: Channels count non available
```

**What happened:**
1. `test.wav` was recorded in **mono** (1 channel)
2. Speaker hardware (`hw:2,0`) only accepts **stereo** (2 channels)
3. Direct hardware access (`hw:`) doesn't convert → playback failed

**Fix:** Use `plughw:` instead of `hw:`

### hw: vs plughw: - The Critical Difference

| Device | Conversion | Use Case |
|--------|------------|----------|
| `hw:X,Y` | ❌ None | Direct hardware access, must match exactly |
| `plughw:X,Y` | ✅ Automatic | Converts format, rate, and channels |

```
┌─────────────────────────────────────────────────────────────────────┐
│                          hw:2,0 (Direct)                            │
│                                                                     │
│   App (Mono) ──────────────────────────────────────▶ Speaker        │
│                         ❌ FAILS!                    (Stereo only)  │
│              "Channels count non available"                         │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                       plughw:2,0 (With Plugin)                      │
│                                                                     │
│   App (Mono) ───▶ [ALSA Plugin] ───▶ Speaker                        │
│                   Mono → Stereo      (Stereo)                       │
│                   ✅ SUCCESS!                                       │
└─────────────────────────────────────────────────────────────────────┘
```

**The `plug` plugin automatically handles:**
- Sample format conversion (e.g., 8-bit → 16-bit)
- Sample rate conversion (e.g., 16kHz → 44.1kHz)
- Channel conversion (e.g., mono → stereo)

### Working Recording Command

**Command:**
```bash
arecord -D plughw:3,0 -f S16_LE -r 44100 -d 5 test.wav
```

**Complete flag breakdown:**

| Flag | Value | Meaning | Why This Value |
|------|-------|---------|----------------|
| `-D` | `plughw:3,0` | Device with plugin layer | Card 3 (mic) with auto-conversion |
| `-f` | `S16_LE` | Sample format | 16-bit signed, your mic's native format |
| `-r` | `44100` | Sample rate | 44.1kHz, your mic's native rate |
| `-d` | `5` | Duration in seconds | Record for 5 seconds |
| | `test.wav` | Output filename | Save as WAV file |

**What happens internally:**
```
Your Voice → Microphone → ADC → USB → ALSA Driver → plughw:3,0 → test.wav
                          │
                   Analog-to-Digital
                   Converter (built
                   into USB device)
```

**Expected output:**
```
Recording WAVE 'test.wav' : Signed 16 bit Little Endian, Rate 44100 Hz, Mono
```

### Working Playback Command

**Command:**
```bash
aplay -D plughw:2,0 test.wav
```

**Flag breakdown:**

| Flag | Value | Meaning | Why This Value |
|------|-------|---------|----------------|
| `-D` | `plughw:2,0` | Device with plugin layer | Card 2 (speaker) with auto-conversion |
| | `test.wav` | Input filename | The file we just recorded |

**What happens internally:**
```
test.wav → plughw:2,0 → [Mono→Stereo] → ALSA Driver → USB → DAC → Speaker
           (Plugin)     Conversion                         │
                                                    Digital-to-Analog
                                                    Converter
```

**Expected output:**
```
Playing WAVE 'test.wav' : Signed 16 bit Little Endian, Rate 44100 Hz, Mono
```

### Complete Test Script

Here's a complete script to test your audio setup (you can find it in the repo):

```bash
#!/bin/bash
# Audio test script for Raspberry Pi

echo "============================================"
echo "  Raspberry Pi Audio Test Script"
echo "============================================"
echo ""

# Configuration - UPDATE THESE FOR YOUR SETUP
SPEAKER_CARD="plughw:2,0"    # Your USB speaker
MIC_CARD="plughw:3,0"        # Your USB microphone
TEST_FILE="test_recording.wav"
RECORD_SECONDS=5

echo "🔊 Speaker device: $SPEAKER_CARD"
echo "🎤 Microphone device: $MIC_CARD"
echo ""

# Step 1: Test speaker with generated tone
echo "Step 1: Testing speaker..."
echo "You should hear a beep sound."
speaker-test -c 2 -D hw:2,0 -t sine -f 440 -l 1 2>/dev/null || echo "Speaker test completed"
echo ""

# Step 2: Record from microphone
echo "Step 2: Recording from microphone..."
echo "🎤 Speak now! Recording for $RECORD_SECONDS seconds..."
arecord -D $MIC_CARD -f S16_LE -r 44100 -d $RECORD_SECONDS $TEST_FILE
echo "Recording saved to: $TEST_FILE"
echo ""

# Step 3: Play back recording
echo "Step 3: Playing back your recording..."
echo "🔊 You should hear your voice now..."
aplay -D $SPEAKER_CARD $TEST_FILE
echo ""

# Cleanup
echo "Step 4: Cleaning up..."
rm -f $TEST_FILE
echo "Test file removed."
echo ""

echo "============================================"
echo "  Audio test complete!"
echo "============================================"
echo ""
echo "✅ If you heard the tone and your voice, audio is working!"
echo "❌ If not, check the troubleshooting section in VOICE_SETUP.md"
```

Send it to your rpi with:
````
scp test_audio.sh <RPI_USER>@<RPI_IP>:~/
````

### ✅ Success Criteria

| Test | Expected Result |
|------|-----------------|
| Speaker test | You hear pink noise or tone |
| Recording | File created without errors |
| Playback | You hear your own voice clearly |

---

## ⚙️ Step 4: Configure ALSA Defaults

Now that we've verified the hardware works, we need to configure ALSA to use our USB devices **by default**. This way, applications won't need to specify which device to use.

### Why Configure Defaults?

Currently, without configuration:

| Command | What Happens |
|---------|--------------|
| `speaker-test` | Uses HDMI (Card 0) - no sound from USB speaker! |
| `arecord test.wav` | Fails or uses wrong device |
| Apps like Piper TTS | Don't know which device to use |

After configuration:

| Command | What Happens |
|---------|--------------|
| `speaker-test` | Uses USB speaker (Card 2) ✅ |
| `arecord test.wav` | Uses USB microphone (Card 3) ✅ |
| Apps like Piper TTS | Automatically use correct devices ✅ |

### Understanding Dotfiles (Hidden Files)

The configuration file we'll create is called `.asoundrc` (note the dot at the beginning).

**What are dotfiles?**

In Linux/Unix systems, any file or directory starting with a `.` (dot) is **hidden**:

```bash
# Normal ls - hidden files NOT shown
$ ls
Documents  Downloads  Music  Pictures

# ls with -a flag - hidden files ARE shown
$ ls -a
.  ..  .bashrc  .config  .asoundrc  Documents  Downloads  Music  Pictures
```

**Why use dotfiles?**
- **Convention**: Configuration files are hidden to reduce clutter
- **Organization**: Your home directory stays clean
- **Safety**: Harder to accidentally delete important config files

**Common dotfiles you might recognize:**
| File | Purpose |
|------|---------|
| `.bashrc` | Bash shell configuration |
| `.gitignore` | Git ignore patterns |
| `.env` | Environment variables |
| `.ssh/` | SSH keys and config |
| `.asoundrc` | ALSA audio configuration ← We create this |

### Understanding `.asoundrc`

The `.asoundrc` file is ALSA's **user configuration file**. It lives in your home directory (`~/.asoundrc`).

**How ALSA finds configuration:**

```
┌─────────────────────────────────────────────────────────────────────┐
│                  ALSA Configuration Load Order                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. /usr/share/alsa/alsa.conf   ← System defaults (don't modify)    │
│              ↓                                                      │
│  2. /etc/asound.conf            ← System-wide overrides (optional)  │
│              ↓                                                      │
│  3. ~/.asoundrc                 ← User overrides (WE CREATE THIS)   │
│                                                                     │
│  Later files OVERRIDE earlier ones                                  │
└─────────────────────────────────────────────────────────────────────┘
```

### The Configuration File

We've created a pre-configured `.asoundrc` file in this repository. Here's what it contains:

```
# Structure of .asoundrc

pcm.!default {          # Define the default PCM (audio) device
    type asym           # Asymmetric: different devices for playback/capture
    playback.pcm "..."  # Which device for speaker output
    capture.pcm "..."   # Which device for microphone input
}

pcm.playback_device {   # Define the playback device
    type plug           # Enable automatic format conversion
    slave.pcm "hw:2,0"  # Card 2, Device 0 (USB speaker)
}

pcm.capture_device {    # Define the capture device
    type plug           # Enable automatic format conversion
    slave.pcm "hw:3,0"  # Card 3, Device 0 (USB microphone)
}

ctl.!default {          # Default mixer control (volume)
    type hw
    card 2
}
```

**Key concepts:**

| Term | Meaning |
|------|---------|
| `pcm` | Pulse Code Modulation - digital audio stream |
| `!default` | The `!` means "override" any existing default |
| `type asym` | Asymmetric - allows different input/output devices |
| `type plug` | Plugin layer that auto-converts formats |
| `slave.pcm` | The underlying device this virtual device uses |
| `hw:X,Y` | Hardware device: Card X, Device Y |
| `ctl` | Control (mixer/volume) |

### Setup Instructions

#### Step 1: Copy the configuration file to your RPI

From your local machine:

```bash
scp .asoundrc <RPI_USER>@<RPI_IP>:~/
```

#### Step 2: Verify the file exists on RPI

On the RPI:

```bash
# Check if file exists (use -a to see hidden files)
ls -la ~/.asoundrc

# View the contents
cat ~/.asoundrc
```

#### Step 3: Test the defaults

Copy the test script to your RPI:

```bash
scp test_alsa_defaults.sh <RPI_USER>@<RPI_IP>:~/
```

On the RPI, make it executable and run:

```bash
chmod +x test_alsa_defaults.sh
./test_alsa_defaults.sh
```

#### Step 4: Manual verification (alternative)

If you prefer to test manually:

```bash
# Test speaker (should use USB speaker automatically)
speaker-test -c 2 -l 1

# Test microphone (should use USB mic automatically)  
arecord -f S16_LE -r 44100 -d 3 /tmp/test.wav

# Play back (should use USB speaker automatically)
aplay /tmp/test.wav

# Cleanup
rm /tmp/test.wav
```

### If Card Numbers Are Different

If your USB devices have different card numbers than 2 and 3:

1. Find your actual card numbers:
   ```bash
   aplay -l   # Speaker card number
   arecord -l # Microphone card number
   ```

2. Edit the `.asoundrc` file:
   ```bash
   nano ~/.asoundrc
   ```

3. Change all occurrences of `hw:2,0` to your speaker card number
4. Change all occurrences of `hw:3,0` to your microphone card number
5. Save and exit (`Ctrl+X`, then `Y`, then `Enter`)

### Using Card Names Instead of Numbers

Card numbers can change after reboot. For more stability, use card **names**:

```bash
# Find card names
cat /proc/asound/cards
```

Output example:
```
 2 [UACDemoV10     ]: USB-Audio - UACDemoV1.0
 3 [Device         ]: USB-Audio - USB PnP Sound Device
```

Then in `.asoundrc`, use:
```
slave.pcm "hw:UACDemoV10,0"    # Instead of "hw:2,0"
slave.pcm "hw:Device,0"         # Instead of "hw:3,0"
```

### ✅ Success Criteria

| Test | Without .asoundrc | With .asoundrc |
|------|-------------------|----------------|
| `speaker-test` | HDMI (no USB sound) | USB speaker ✅ |
| `arecord test.wav` | Fails / wrong device | USB microphone ✅ |
| `aplay test.wav` | HDMI | USB speaker ✅ |

---

## 🗣️ Step 5: Install Piper TTS

Piper is a fast, local neural text-to-speech system that converts text into natural-sounding speech. It runs entirely on the Raspberry Pi without needing internet connectivity.

### What is Piper?

**Piper** is an open-source text-to-speech engine developed by [Rhasspy](https://github.com/rhasspy/piper). It uses neural network models to generate human-like speech from text.

**Key features:**
- 🚀 **Fast**: Real-time speech generation on Raspberry Pi 5
- 🔒 **Private**: 100% local, no data sent to cloud
- 💰 **Free**: Open-source, no API costs
- 🌐 **Offline**: Works without internet
- 🎭 **Multiple voices**: Many voice models available

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      PIPER TTS ARCHITECTURE                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐               │
│  │   WhatsApp   │    │   FastAPI    │    │    Piper     │               │
│  │    Bridge    │───▶│  TTS Server  │───▶│   Binary     │───▶ 🔊        │
│  │  (Node.js)   │    │  (Python)    │    │  (C++/ONNX)  │   Speaker     │
│  └──────────────┘    └──────────────┘    └──────────────┘               │
│         │                   │                   │                       │
│         │              POST /speak              │                       │
│         │                   │                   │                       │
│    "speak hello"      Receives text       Generates audio               │
│                       Calls Piper         Plays via ALSA                │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

**How Piper generates speech:**

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        PIPER INTERNAL FLOW                               │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  1. TEXT INPUT                                                           │
│     "Hello, I am Prometheus"                                             │
│              │                                                           │
│              ▼                                                           │
│  2. PHONEMIZATION                                                        │
│     Convert text to phonemes (speech sounds)                             │
│     "HH AH L OW , AY AE M P R AH M IY TH IY AH S"                        │
│              │                                                           │
│              ▼                                                           │
│  3. NEURAL NETWORK (VITS Model)                                          │
│     The .onnx voice model generates audio waveform                       │
│     Uses ONNX Runtime for fast inference                                 │
│              │                                                           │
│              ▼                                                           │
│  4. AUDIO OUTPUT                                                         │
│     Raw PCM audio (22050 Hz, 16-bit, mono)                               │
│     Played through USB speaker via ALSA                                  │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

### Docker Container Structure

The Piper TTS service runs in a Docker container with these components:

```
piper-tts/
├── Dockerfile           # Container build instructions
├── tts_server.py        # FastAPI HTTP server
├── requirements.txt     # Python dependencies
├── download_voices.sh   # Script to download voice models
└── voices/
    ├── en_GB-alba-medium.onnx       # Voice model (~60MB)
    └── en_GB-alba-medium.onnx.json  # Voice configuration
```

### Service Endpoints

The TTS server exposes these HTTP endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check - returns status and configuration |
| `/voices` | GET | List available voice models |
| `/speak` | POST | Convert text to speech AND play through speaker |
| `/synthesize` | POST | Convert text to speech and return audio file |

### Setup Instructions

#### Step 5a: Download Voice Models

Voice models must be downloaded locally before building the Docker image.

```bash
# Navigate to project directory
cd /path/to/RPI_Chatbot

# Make download script executable
chmod +x piper-tts/download_voices.sh

# Download default voice (British female - Alba)
./piper-tts/download_voices.sh
```

**To add more voices**, edit `piper-tts/download_voices.sh` and uncomment additional voices:

```bash
# Default voice
download_voice "en_GB-alba-medium" "en" "en_GB" "alba" "medium"

# Additional voices (uncomment to download)
download_voice "en_US-amy-medium" "en" "en_US" "amy" "medium"       # American female
download_voice "en_US-ryan-medium" "en" "en_US" "ryan" "medium"     # American male
```

**Available voices in this repo:**

| Voice ID | Accent | Gender | Quality |
|----------|--------|--------|---------|
| `en_GB-alba-medium` | British | Female | Good (default) |
| `en_US-amy-medium` | American | Female | Good |
| `en_US-ryan-medium` | American | Male | Good |
| `en_GB-alan-medium` | British | Male | Good |
| `en_US-lessac-medium` | American | Female | Good |

Browse all voices: https://huggingface.co/rhasspy/piper-voices/tree/main

#### Step 5b: Build and Push Docker Image

```bash
# Build and push all images (including piper-tts)
./build-and-push.sh
```

Or build just the Piper TTS image:

```bash
docker buildx build \
    --platform linux/arm64 \
    -t docker.io/YOUR_USERNAME/piper-tts:latest \
    -f piper-tts/Dockerfile \
    --push \
    .
```

#### Step 5c: Deploy on Raspberry Pi

```bash
# Copy docker-compose.yml to Pi
scp docker-compose.yml user@pi:/var/www/ollama_chatbot/

# On the Pi:
cd /var/www/ollama_chatbot
sudo docker-compose pull piper-tts
sudo docker-compose up -d piper-tts
```

#### Step 5d: Test the TTS Service

**Check health:**
```bash
curl http://localhost:5000/health
```

Expected response:
```json
{
  "status": "healthy",
  "piper_binary": "/app/piper/piper",
  "piper_exists": true,
  "voice_model": "/app/voices/en_GB-alba-medium.onnx",
  "voice_exists": true,
  "sample_rate": 22050
}
```

**Test speech generation:**
```bash
curl -X POST http://localhost:5000/speak \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello! I am Prometheus, your AI assistant."}'
```

You should hear the speech through your USB speaker! 🔊

**Test with different voice:**
```bash
curl -X POST http://localhost:5000/speak \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello from Ryan!", "voice": "/app/voices/en_US-ryan-medium.onnx"}'
```

### WhatsApp Integration

The WhatsApp bridge is configured to call the TTS service when you use the `speak` keyword.

**Trigger keywords:**

| Chat Type | Command | Result |
|-----------|---------|--------|
| Private | `speak Hello` | Text reply + spoken audio 🔊 |
| Private | `Hello` | Text reply only |
| Group | `Prometheus speak Hello` | Text reply + spoken audio 🔊 |
| Group | `Prometheus Hello` | Text reply only |

**What happens when you say "speak":**

1. WhatsApp bridge detects `speak` keyword
2. Keyword is removed, message sent to Ollama AI
3. AI generates response
4. Response sent back to WhatsApp (text)
5. Response also sent to Piper TTS service
6. Piper converts text to speech
7. Audio plays through USB speaker

**Emoji filtering:**

Emojis are automatically removed before sending to TTS (they don't sound good when read aloud).

### Configuration

**Environment variables in `docker-compose.yml`:**

```yaml
piper-tts:
  environment:
    - VOICE_MODEL=/app/voices/en_GB-alba-medium.onnx  # Default voice
    - SAMPLE_RATE=22050                                # Audio sample rate
    - AUDIO_DEVICE=plughw:2,0                          # ALSA device for playback
```

**To change default voice:**

1. Edit `.env` on the Pi:
   ```bash
   VOICE_MODEL=/app/voices/en_US-ryan-medium.onnx
   ```

2. Restart the service:
   ```bash
   sudo docker-compose up -d piper-tts
   ```

**Audio device (usually no change needed):**

The audio device defaults to `plughw:2,0` (USB speaker on card 2) which is set in `docker-compose.yml`. This works for most setups.

If your USB speaker is on a **different** card number:

1. Find your card number:
   ```bash
   aplay -l
   ```

2. Add to `.env` on the Pi (only if card ≠ 2):
   ```bash
   AUDIO_DEVICE=plughw:X,0  # Replace X with your card number
   ```

3. Restart: `sudo docker-compose up -d piper-tts`

> **Note**: The `.asoundrc` file on the Pi configures the **host's** default audio device. The Docker container uses the `AUDIO_DEVICE` environment variable instead because containers don't automatically inherit the host's ALSA configuration.

### Adjusting Speaker Volume

If the TTS audio is too quiet, use `alsamixer` to adjust the volume:

```bash
# Launch interactive volume control
alsamixer
```

**Controls:**
- `F6` - Select your USB sound card (e.g., "UACDemoV10")
- `↑` / `↓` - Increase / decrease volume
- `M` - Mute / unmute
- `Esc` - Exit

**Make volume persistent:**
```bash
sudo alsactl store
```

> **Note**: The `amixer` command-line tool may not work with all USB sound cards. Use `alsamixer` for best compatibility.

### Troubleshooting

#### "Voice model not found"

```bash
# Check if voice files exist in container
sudo docker exec piper-tts ls -la /app/voices/

# If empty, rebuild the image after downloading voices locally
./piper-tts/download_voices.sh
./build-and-push.sh
```

#### "Audio playback failed: error 524"

This means the container can't access the audio device properly.

```bash
# Check if container can see audio devices
sudo docker exec piper-tts aplay -l

# Test direct playback
sudo docker exec piper-tts aplay -D plughw:2,0 /dev/urandom -d 1 -f S16_LE -r 44100
```

If test playback works but TTS fails, check the `AUDIO_DEVICE` environment variable.

#### "Container unhealthy"

```bash
# Check container logs
sudo docker logs piper-tts

# Check health endpoint
curl http://localhost:5000/health
```

#### TTS is slow

Piper should generate speech in near real-time on RPI5. If it's slow:

1. Check CPU usage: `htop`
2. Ensure you're using a "medium" quality voice (not "high")
3. Check if other containers are consuming resources

### ✅ Success Criteria

| Test | Expected Result |
|------|-----------------|
| `curl http://localhost:5000/health` | `"status": "healthy"` |
| `curl -X POST .../speak -d '{"text": "Test"}'` | Audio plays through speaker |
| WhatsApp: `speak Hello` | Text reply + audio plays |
| Container status | `Up (healthy)` |

---

## 👂 Step 6: Install Whisper STT

Whisper STT (Speech-to-Text) converts spoken audio from your microphone into text that the AI can understand.

### What is Whisper?

**Whisper** is OpenAI's open-source speech recognition model, released in 2022. It's trained on 680,000 hours of multilingual audio and supports:
- 99 languages
- Automatic language detection
- Punctuation and formatting
- Robust handling of accents and background noise

**Why faster-whisper?**

We use [faster-whisper](https://github.com/SYSTRAN/faster-whisper) instead of the original OpenAI Whisper because:
- **4x faster** inference using CTranslate2 optimization
- **Lower memory** usage (crucial for RPI5's 8GB RAM)
- **int8 quantization** for efficient CPU inference
- Same accuracy as the original model

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      WHISPER STT ARCHITECTURE                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐               │
│  │  Microphone  │    │   FastAPI    │    │   Whisper    │               │
│  │    (USB)     │───▶│  STT Server  │───▶│   Model      │               │
│  │  plughw:3,0  │    │  (Python)    │    │  (tiny/int8) │               │
│  └──────────────┘    └──────────────┘    └──────────────┘               │
│         │                   │                   │                       │
│    Audio Input         Port 5002            Transcription               │
│    (16kHz mono)        (external)              Output                   │
│                        Port 5000                                        │
│                        (internal)                                       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Port Mapping

```
┌─────────────────────────────────────────────────────────────────┐
│                     RASPBERRY PI (Host)                         │
│                                                                 │
│   curl http://localhost:5002/listen                             │
│                            │                                    │
│                            ▼                                    │
│                     Port 5002 (Host)                            │
│                            │                                    │
│   ┌────────────────────────┼────────────────────────────────┐   │
│   │        DOCKER CONTAINER (whisper-stt)                   │   │
│   │                        │                                │   │
│   │                        ▼                                │   │
│   │                  Port 5000 (Container)                  │   │
│   │                        │                                │   │
│   │                        ▼                                │   │
│   │              Uvicorn Server listening                   │   │
│   │                                                         │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

| Service | External Port (Pi) | Internal Port (Container) |
|---------|-------------------|--------------------------|
| Piper TTS | 5000 | 5000 |
| **Whisper STT** | **5002** | **5000** |

> **Note**: We use port 5002 externally because 5001 may be used by other services (e.g., socat tunnels).

### Whisper Model Sizes

| Model | Size | VRAM | Relative Speed | RPI5 Suitable |
|-------|------|------|----------------|---------------|
| **tiny** | 39 MB | ~1 GB | ~32x | ✅ Recommended |
| base | 74 MB | ~1 GB | ~16x | ✅ Good |
| small | 244 MB | ~2 GB | ~6x | ⚠️ Slower |
| medium | 769 MB | ~5 GB | ~2x | ❌ Too slow |
| large | 1550 MB | ~10 GB | 1x | ❌ Won't fit |

We use **tiny** by default for best latency (~2 seconds on RPI5).

### Files Created

```
whisper-stt/
├── Dockerfile           # Container build instructions
├── stt_server.py        # FastAPI HTTP server
├── requirements.txt     # Python dependencies
└── models/
    └── .gitkeep         # Models downloaded on first run
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/listen` | POST | Record from mic & transcribe |
| `/transcribe` | POST | Upload audio file & transcribe |
| `/models` | GET | List available models |

### Setup Steps

The Whisper STT service is already built into the Docker image. Just deploy:

**1. Pull and start the service:**
```bash
# On Pi
cd /var/www/ollama_chatbot
sudo docker-compose pull whisper-stt
sudo docker-compose up -d whisper-stt
```

**2. Check container status:**
```bash
sudo docker ps | grep whisper
# Should show: Up (healthy)
```

**3. Check logs (model downloads on first run):**
```bash
sudo docker logs whisper-stt -f
```

You'll see:
```
🎤 Whisper STT Server Starting
Loading Whisper model: tiny
✅ Whisper model loaded in 12.23s
✅ Whisper STT Server Ready
Uvicorn running on http://0.0.0.0:5000
```

### Testing

**Test 1: Health Check**
```bash
curl http://localhost:5002/health
```

Expected:
```json
{
  "status": "healthy",
  "model": "tiny",
  "compute_type": "int8",
  "audio_device": "plughw:3,0",
  "sample_rate": 16000
}
```

**Test 2: Record and Transcribe (speak into your mic!)**
```bash
curl -X POST http://localhost:5002/listen \
  -H "Content-Type: application/json" \
  -d '{"duration": 5}'
```

Say something during the 5 seconds! Expected:
```json
{
  "success": true,
  "text": "Hello, this is a test of the speech recognition system.",
  "language": "en",
  "confidence": 0.85,
  "duration_ms": 1948
}
```

**Test 3: Transcribe an audio file**
```bash
# First record a test file
arecord -D plughw:3,0 -f S16_LE -r 16000 -d 5 /tmp/test_stt.wav

# Then transcribe it
curl -X POST http://localhost:5002/transcribe \
  -F "file=@/tmp/test_stt.wav"
```

### Configuration

**Change Whisper model** (in `.env` on Pi):
```bash
# Options: tiny, base, small
WHISPER_MODEL=base
```

Then restart:
```bash
sudo docker-compose up -d --force-recreate whisper-stt
```

**Change microphone device** (if card ≠ 3):
```bash
# In .env
AUDIO_DEVICE_MIC=plughw:X,0  # Replace X with your mic card number
```

### docker-compose.yml Configuration

```yaml
# Service 4: Whisper STT (Speech-to-Text)
whisper-stt:
  image: ${DOCKER_USERNAME}/whisper-stt:latest
  container_name: whisper-stt
  ports:
    - "127.0.0.1:5002:5000"   # STT API (localhost only)
  devices:
    - /dev/snd:/dev/snd       # Access to audio devices (microphone)
  volumes:
    - whisper-models:/app/models  # Persist downloaded Whisper models
  restart: unless-stopped
  environment:
    - WHISPER_MODEL=${WHISPER_MODEL:-tiny}    # Model size
    - COMPUTE_TYPE=int8                        # Fastest on CPU
    - AUDIO_DEVICE=${AUDIO_DEVICE_MIC:-plughw:3,0}  # Microphone
    - SAMPLE_RATE=16000                        # 16kHz optimal for Whisper
  group_add:
    - audio                   # Add to audio group for microphone access
  networks:
    - chatbot-network
```

### Troubleshooting

#### "Connection reset by peer"

The container is crashing. Check logs:
```bash
sudo docker logs whisper-stt --tail 50
```

Common causes:
- Port mismatch between Dockerfile and docker-compose
- Model failed to download (network issue)

#### "Recording failed"

```bash
# Test microphone from inside container
sudo docker exec whisper-stt arecord -D plughw:3,0 -f S16_LE -r 16000 -d 3 /tmp/test.wav
sudo docker exec whisper-stt aplay -D plughw:2,0 /tmp/test.wav
```

If this fails, check:
1. Microphone card number: `arecord -l`
2. Update `AUDIO_DEVICE_MIC` in `.env`

#### GPU Warning (Safe to Ignore)

```
GPU device discovery failed: device_discovery.cc:89
```

This is normal - Whisper is trying to find a GPU but falls back to CPU. Performance is still good.

#### Slow Transcription

If transcription takes > 5 seconds:
1. Ensure you're using `tiny` model
2. Check CPU usage: `htop`
3. Try reducing audio duration

### ✅ Success Criteria

| Test | Expected Result |
|------|-----------------|
| `curl http://localhost:5002/health` | `"status": "healthy"` |
| `curl -X POST .../listen -d '{"duration":5}'` | Your spoken words transcribed |
| Container status | `Up (healthy)` |
| Transcription latency | < 3 seconds for 5s audio |

---

## 🎯 Step 7: Install openWakeWord

*Coming in next step...*

---

## 🔗 Step 8: Voice Pipeline Integration

*Coming in next step...*

---

## 🔧 Troubleshooting

### No Playback Devices Found
```bash
# Check if ALSA is installed
sudo apt install alsa-utils

# Reload sound modules
sudo modprobe snd-usb-audio
```

### No Recording Devices Found
1. Unplug and replug your USB microphone
2. Try a different USB port
3. Check kernel messages: `dmesg | tail -20`

### USB Device Not Recognized
```bash
# Check kernel messages for USB errors
dmesg | grep -i usb | tail -20

# List USB devices with verbose output
lsusb -v 2>/dev/null | grep -A 5 "Audio"
```

### Card Numbers Change After Reboot
USB device card numbers can change between reboots. We'll configure fixed defaults in Step 4.

---

## 📚 References

- [ALSA Documentation](https://www.alsa-project.org/wiki/Main_Page)
- [openWakeWord GitHub](https://github.com/dscripka/openWakeWord)
- [Piper TTS GitHub](https://github.com/rhasspy/piper)
- [OpenAI Whisper GitHub](https://github.com/openai/whisper)

---

*This guide is part of the [Prometheus RPI Chatbot](README.md) project.*

