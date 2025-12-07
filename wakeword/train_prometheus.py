#!/usr/bin/env python3
"""
=============================================================================
Train Custom "Hey Prometheus" Wake Word
=============================================================================

This script trains a custom wake word model for "Hey Prometheus" using
openWakeWord's training capabilities.

Two approaches:
1. Synthetic Training - Generate audio samples using TTS (recommended)
2. Real Recording Training - Record yourself saying "Hey Prometheus"

Requirements:
    pip install openwakeword[training]

Usage:
    python train_prometheus.py

The trained model will be saved to: ./models/hey_prometheus.onnx
=============================================================================
"""

import os
import sys
import subprocess
from pathlib import Path

# =============================================================================
# CONFIGURATION
# =============================================================================

WAKE_WORD = "hey prometheus"
MODEL_NAME = "hey_prometheus"
OUTPUT_DIR = Path("./models")
SAMPLES_DIR = Path("./training_samples")

# Number of synthetic samples to generate
NUM_SYNTHETIC_SAMPLES = 500

# TTS voices to use for synthetic samples (diversity helps accuracy)
TTS_VOICES = [
    "en_US-amy-medium",
    "en_US-ryan-medium",
    "en_GB-alba-medium",
    "en_GB-semaine-medium",
]


def check_dependencies():
    """Check if required packages are installed."""
    try:
        import openwakeword
        print("✅ openwakeword installed")
    except ImportError:
        print("❌ openwakeword not installed")
        print("   Run: pip install openwakeword[training]")
        return False
    
    try:
        from piper import PiperVoice
        print("✅ piper-tts installed")
    except ImportError:
        print("⚠️  piper not installed (optional, for local TTS generation)")
        print("   Will use online TTS services instead")
    
    return True


def generate_synthetic_samples_with_piper():
    """
    Generate synthetic audio samples using Piper TTS.
    This creates diverse samples by varying:
    - Voice (different speakers)
    - Speed (slightly faster/slower)
    - Pitch (if supported)
    """
    print(f"\n🎤 Generating {NUM_SYNTHETIC_SAMPLES} synthetic samples...")
    
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    positive_dir = SAMPLES_DIR / "positive"
    positive_dir.mkdir(exist_ok=True)
    
    # Check if Piper TTS is available via the container
    try:
        import requests
        response = requests.get("http://localhost:5000/health", timeout=5)
        if response.status_code == 200:
            print("✅ Using local Piper TTS service")
            generate_with_piper_service(positive_dir)
            return True
    except:
        pass
    
    print("⚠️  Local Piper TTS not available")
    print("   Please use manual recording method instead")
    return False


def generate_with_piper_service(output_dir: Path):
    """Generate samples using the Piper TTS Docker service."""
    import requests
    import time
    
    variations = [
        "hey prometheus",
        "Hey Prometheus",
        "HEY PROMETHEUS",
        "hey, prometheus",
        "hey prometheus!",
    ]
    
    count = 0
    for i in range(NUM_SYNTHETIC_SAMPLES // len(variations)):
        for variation in variations:
            try:
                # Request synthesis (without playback)
                response = requests.post(
                    "http://localhost:5000/synthesize",
                    json={"text": variation},
                    timeout=30
                )
                
                if response.status_code == 200:
                    # Save the audio
                    output_file = output_dir / f"sample_{count:04d}.wav"
                    with open(output_file, "wb") as f:
                        f.write(response.content)
                    count += 1
                    
                    if count % 50 == 0:
                        print(f"   Generated {count} samples...")
                        
            except Exception as e:
                print(f"   Error generating sample: {e}")
            
            time.sleep(0.1)  # Don't overwhelm the service
    
    print(f"✅ Generated {count} positive samples in {output_dir}")


def generate_negative_samples():
    """
    Generate negative samples (audio that is NOT the wake word).
    These help the model learn what to ignore.
    """
    print("\n🔇 Generating negative samples...")
    
    negative_dir = SAMPLES_DIR / "negative"
    negative_dir.mkdir(exist_ok=True)
    
    # Negative phrases (similar but not the wake word)
    negative_phrases = [
        "hey",
        "prometheus",
        "hey there",
        "hey siri",
        "hey google",
        "hello",
        "hi prometheus",
        "hey prometheus system",
        "the prometheus project",
        "prometheus monitoring",
    ]
    
    try:
        import requests
        
        count = 0
        for i in range(50):  # Generate multiple of each
            for phrase in negative_phrases:
                try:
                    response = requests.post(
                        "http://localhost:5000/synthesize",
                        json={"text": phrase},
                        timeout=30
                    )
                    
                    if response.status_code == 200:
                        output_file = negative_dir / f"negative_{count:04d}.wav"
                        with open(output_file, "wb") as f:
                            f.write(response.content)
                        count += 1
                        
                except Exception as e:
                    pass
        
        print(f"✅ Generated {count} negative samples in {negative_dir}")
        
    except Exception as e:
        print(f"⚠️  Could not generate negative samples: {e}")


def train_model():
    """
    Train the wake word model using openWakeWord's training pipeline.
    """
    print("\n🏋️ Training wake word model...")
    
    try:
        from openwakeword.train import train_model as oww_train
        
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        
        # Training configuration
        config = {
            "model_name": MODEL_NAME,
            "positive_samples": str(SAMPLES_DIR / "positive"),
            "negative_samples": str(SAMPLES_DIR / "negative"),
            "output_dir": str(OUTPUT_DIR),
            "epochs": 100,
            "batch_size": 32,
        }
        
        # Run training
        oww_train(**config)
        
        model_path = OUTPUT_DIR / f"{MODEL_NAME}.onnx"
        if model_path.exists():
            print(f"✅ Model trained successfully: {model_path}")
            return True
        else:
            print("❌ Training completed but model file not found")
            return False
            
    except ImportError:
        print("❌ Training module not available")
        print("   Install with: pip install openwakeword[training]")
        return False
    except Exception as e:
        print(f"❌ Training failed: {e}")
        return False


def manual_recording_instructions():
    """
    Print instructions for manual recording approach.
    """
    print("""
=============================================================================
📝 MANUAL RECORDING METHOD
=============================================================================

If synthetic training isn't available, you can record samples manually:

1. Create directories:
   mkdir -p training_samples/positive
   mkdir -p training_samples/negative

2. Record 50-100 positive samples (you saying "Hey Prometheus"):
   
   for i in {1..50}; do
       echo "Recording sample $i - Say 'Hey Prometheus'"
       arecord -D plughw:3,0 -f S16_LE -r 16000 -d 2 training_samples/positive/sample_$i.wav
       sleep 1
   done

3. Record negative samples (similar phrases, NOT "Hey Prometheus"):
   - "Hey"
   - "Prometheus" 
   - "Hey there"
   - "Hello"
   etc.

4. Run training:
   python train_prometheus.py --train-only

5. Copy model to container:
   cp models/hey_prometheus.onnx /var/www/ollama_chatbot/wakeword/models/

6. Update docker-compose.yml:
   WAKE_WORD_MODEL=hey_prometheus

=============================================================================
""")


def use_pretrained_alternative():
    """
    Suggest using a pre-trained model as an alternative.
    """
    print("""
=============================================================================
🎯 ALTERNATIVE: Use Similar Pre-trained Model
=============================================================================

If training is too complex, you can use a similar-sounding pre-trained model:

| Pre-trained Model | Sounds Like        | Similarity |
|-------------------|--------------------|-----------| 
| hey_jarvis        | "Hey Jarvis"       | ⭐⭐⭐      |
| hey_mycroft       | "Hey Mycroft"      | ⭐⭐        |
| hey_rhasspy       | "Hey Rhasspy"      | ⭐          |

To use "hey_jarvis" instead:
1. Edit .env on the Pi:
   WAKE_WORD_MODEL=hey_jarvis

2. Restart the service:
   sudo docker-compose up -d wakeword

Then say "Hey Jarvis" instead of "Hey Prometheus".

=============================================================================
""")


def main():
    print("=" * 70)
    print("🎯 Hey Prometheus Wake Word Training")
    print("=" * 70)
    
    if not check_dependencies():
        manual_recording_instructions()
        use_pretrained_alternative()
        return
    
    print("\nChoose training method:")
    print("1. Synthetic (uses TTS to generate samples)")
    print("2. Manual (record your own voice)")
    print("3. Show instructions only")
    
    choice = input("\nEnter choice (1/2/3): ").strip()
    
    if choice == "1":
        if generate_synthetic_samples_with_piper():
            generate_negative_samples()
            train_model()
        else:
            manual_recording_instructions()
    elif choice == "2":
        manual_recording_instructions()
    else:
        manual_recording_instructions()
        use_pretrained_alternative()


if __name__ == "__main__":
    main()

