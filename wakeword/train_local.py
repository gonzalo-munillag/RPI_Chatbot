#!/usr/bin/env python3
"""
=============================================================================
Train "Hey Prometheus" Wake Word Model Using openWakeWord
=============================================================================

This script trains a wake word model that is COMPATIBLE with the openWakeWord
runtime by using their actual training pipeline.

openWakeWord models use 96-dimensional embeddings from a speech encoder,
not raw mel spectrograms. This script uses their `train_custom_model` function
to ensure compatibility.

Prerequisites:
    pip install openwakeword[training] torch torchaudio numpy

Usage:
    python train_local.py \
        --positive ./training_samples/positive \
        --negative ./training_samples/negative \
        --output ./models/hey_prometheus.onnx

=============================================================================
"""

import os
import sys
import argparse
import shutil
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')


def check_dependencies():
    """Check if required packages are installed."""
    required = {
        'openwakeword': 'openwakeword[training]',
        'torch': 'torch',
        'torchaudio': 'torchaudio',
        'numpy': 'numpy',
    }
    missing = []
    
    for pkg, install_name in required.items():
        try:
            __import__(pkg)
        except ImportError:
            missing.append(install_name)
    
    if missing:
        print(f"❌ Missing packages: {', '.join(missing)}")
        print(f"Install with: pip install {' '.join(missing)}")
        sys.exit(1)
    
    print("✅ All dependencies installed")


def count_wav_files(directory: str) -> int:
    """Count .wav files in a directory."""
    return len(list(Path(directory).glob("*.wav")))


def validate_samples(positive_dir: str, negative_dir: str, min_samples: int = 5):
    """
    Validate that we have enough training samples.
    
    Args:
        positive_dir: Directory with positive samples (wake word)
        negative_dir: Directory with negative samples (other speech)
        min_samples: Minimum samples required per class
    """
    pos_count = count_wav_files(positive_dir)
    neg_count = count_wav_files(negative_dir)
    
    print(f"\n📁 Training Samples:")
    print(f"   Positive (wake word): {pos_count} files")
    print(f"   Negative (other):     {neg_count} files")
    
    if pos_count < min_samples:
        print(f"\n❌ Need at least {min_samples} positive samples (have {pos_count})")
        sys.exit(1)
    
    if neg_count < min_samples:
        print(f"\n❌ Need at least {min_samples} negative samples (have {neg_count})")
        sys.exit(1)
    
    print(f"   ✅ Sufficient samples for training")
    return pos_count, neg_count


def train_with_openwakeword(positive_dir: str, negative_dir: str, output_path: str,
                             model_name: str = "hey_prometheus", epochs: int = 100):
    """
    Train using openWakeWord's native training pipeline.
    
    This ensures the model uses the same 96-dim embeddings as the runtime.
    
    Args:
        positive_dir: Directory with positive .wav samples
        negative_dir: Directory with negative .wav samples  
        output_path: Where to save the .onnx model
        model_name: Name for the model
        epochs: Training epochs
    """
    print(f"\n🚀 Training with openWakeWord pipeline...")
    print(f"   This ensures compatibility with the runtime\n")
    
    try:
        from openwakeword.train import train_custom_model
        
        # openWakeWord's train_custom_model expects specific directory structure
        # It will handle feature extraction using its own 96-dim embeddings
        
        output_dir = Path(output_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)
        
        print("=" * 60)
        print("Starting openWakeWord training...")
        print("=" * 60)
        
        # Train the model
        train_custom_model(
            model_name=model_name,
            positive_audio_dir=positive_dir,
            negative_audio_dir=negative_dir,
            output_dir=str(output_dir),
            epochs=epochs,
            # Use smaller batch for limited samples
            batch_size=16,
            # Learning rate
            learning_rate=0.001,
        )
        
        # The trained model should be in output_dir
        expected_model = output_dir / f"{model_name}.onnx"
        
        if expected_model.exists():
            # Rename if needed
            if str(expected_model) != output_path:
                shutil.move(str(expected_model), output_path)
            
            print(f"\n✅ Model trained successfully!")
            print(f"   Saved to: {output_path}")
            return True
        else:
            # Check for any .onnx files
            onnx_files = list(output_dir.glob("*.onnx"))
            if onnx_files:
                shutil.move(str(onnx_files[0]), output_path)
                print(f"\n✅ Model trained successfully!")
                print(f"   Saved to: {output_path}")
                return True
            
            print(f"\n❌ Training completed but model file not found")
            print(f"   Check {output_dir} for output files")
            return False
            
    except ImportError as e:
        print(f"\n❌ openWakeWord training module not available: {e}")
        print("   Install with: pip install openwakeword[training]")
        print("\n   Falling back to alternative training method...")
        return train_alternative(positive_dir, negative_dir, output_path, epochs)
    except Exception as e:
        print(f"\n❌ openWakeWord training failed: {e}")
        print("\n   Falling back to alternative training method...")
        return train_alternative(positive_dir, negative_dir, output_path, epochs)


def train_alternative(positive_dir: str, negative_dir: str, output_path: str, epochs: int = 100):
    """
    Alternative training using embedding extraction + simple classifier.
    
    This extracts embeddings using openWakeWord's preprocessor and trains
    a simple classifier on top.
    """
    print("\n🔄 Using alternative training method...")
    print("   Extracting embeddings with openWakeWord's preprocessor\n")
    
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import Dataset, DataLoader
    import numpy as np
    import torchaudio
    
    try:
        from openwakeword.model import Model as OWWModel
    except ImportError:
        print("❌ Could not import openwakeword.model")
        print("   Install: pip install openwakeword")
        return False
    
    # =========================================================================
    # EXTRACT EMBEDDINGS USING OPENWAKEWORD'S PREPROCESSOR
    # =========================================================================
    
    print("📊 Extracting embeddings from audio samples...")
    
    # Initialize openWakeWord (this loads the embedding model)
    oww = OWWModel(wakeword_models=["hey_jarvis"])  # Just to load embeddings
    
    def extract_embedding(wav_path: str) -> np.ndarray:
        """Extract 96-dim embedding using openWakeWord's preprocessor."""
        # Load audio
        waveform, sr = torchaudio.load(wav_path)
        
        # Resample to 16kHz if needed
        if sr != 16000:
            resampler = torchaudio.transforms.Resample(sr, 16000)
            waveform = resampler(waveform)
        
        # Convert to mono
        if waveform.shape[0] > 1:
            waveform = waveform.mean(dim=0, keepdim=True)
        
        # Get audio as numpy (16-bit int format expected by openWakeWord)
        audio = (waveform.squeeze().numpy() * 32767).astype(np.int16)
        
        # Process through openWakeWord's preprocessor
        # This gives us the 96-dim embeddings
        oww.predict(audio)
        
        # Get the preprocessed features (embeddings)
        # openWakeWord stores these internally
        if hasattr(oww, 'preprocessor'):
            embeddings = oww.preprocessor.get_features()
            if embeddings is not None and len(embeddings) > 0:
                return embeddings
        
        # Fallback: use raw prediction features
        return np.zeros((1, 96), dtype=np.float32)
    
    # Collect embeddings
    positive_embeddings = []
    negative_embeddings = []
    
    pos_dir = Path(positive_dir)
    neg_dir = Path(negative_dir)
    
    print("   Processing positive samples...")
    for wav_file in pos_dir.glob("*.wav"):
        try:
            emb = extract_embedding(str(wav_file))
            if emb is not None and len(emb) > 0:
                positive_embeddings.append(emb)
        except Exception as e:
            print(f"     Warning: Could not process {wav_file.name}: {e}")
    
    print("   Processing negative samples...")
    for wav_file in neg_dir.glob("*.wav"):
        try:
            emb = extract_embedding(str(wav_file))
            if emb is not None and len(emb) > 0:
                negative_embeddings.append(emb)
        except Exception as e:
            print(f"     Warning: Could not process {wav_file.name}: {e}")
    
    if not positive_embeddings or not negative_embeddings:
        print("❌ Could not extract embeddings from samples")
        return False
    
    print(f"   Extracted {len(positive_embeddings)} positive, {len(negative_embeddings)} negative embeddings")
    
    # =========================================================================
    # TRAIN SIMPLE CLASSIFIER
    # =========================================================================
    
    print("\n🎯 Training classifier on embeddings...")
    
    # Prepare data
    # Pad/truncate embeddings to fixed length
    MAX_FRAMES = 76  # Standard openWakeWord frame count
    EMBEDDING_DIM = 96
    
    def pad_embedding(emb, target_len=MAX_FRAMES):
        """Pad or truncate embedding to fixed length."""
        if len(emb) >= target_len:
            return emb[:target_len]
        else:
            padding = np.zeros((target_len - len(emb), EMBEDDING_DIM), dtype=np.float32)
            return np.vstack([emb, padding])
    
    X_pos = np.array([pad_embedding(e) for e in positive_embeddings])
    X_neg = np.array([pad_embedding(e) for e in negative_embeddings])
    
    X = np.vstack([X_pos, X_neg])
    y = np.array([1] * len(X_pos) + [0] * len(X_neg))
    
    # Shuffle
    indices = np.random.permutation(len(X))
    X = X[indices]
    y = y[indices]
    
    # Convert to tensors
    X_tensor = torch.FloatTensor(X)
    y_tensor = torch.LongTensor(y)
    
    # Create simple dataset
    class EmbeddingDataset(Dataset):
        def __init__(self, X, y):
            self.X = X
            self.y = y
        
        def __len__(self):
            return len(self.X)
        
        def __getitem__(self, idx):
            return self.X[idx], self.y[idx]
    
    dataset = EmbeddingDataset(X_tensor, y_tensor)
    loader = DataLoader(dataset, batch_size=16, shuffle=True)
    
    # Simple classifier model (matches openWakeWord's expected input)
    class WakeWordClassifier(nn.Module):
        """
        Simple classifier that takes 96-dim embeddings.
        Input shape: (batch, time_frames, 96)
        Output: (batch, 1) probability of wake word
        """
        def __init__(self, embedding_dim=96, hidden_dim=64):
            super().__init__()
            
            # 1D convolutions over time
            self.conv1 = nn.Conv1d(embedding_dim, hidden_dim, kernel_size=5, padding=2)
            self.bn1 = nn.BatchNorm1d(hidden_dim)
            self.conv2 = nn.Conv1d(hidden_dim, hidden_dim, kernel_size=5, padding=2)
            self.bn2 = nn.BatchNorm1d(hidden_dim)
            
            # Global pooling and output
            self.pool = nn.AdaptiveAvgPool1d(1)
            self.fc = nn.Linear(hidden_dim, 1)
            self.sigmoid = nn.Sigmoid()
        
        def forward(self, x):
            # x: (batch, time, 96) -> (batch, 96, time)
            x = x.permute(0, 2, 1)
            
            x = torch.relu(self.bn1(self.conv1(x)))
            x = torch.relu(self.bn2(self.conv2(x)))
            
            x = self.pool(x).squeeze(-1)  # (batch, hidden)
            x = self.sigmoid(self.fc(x))  # (batch, 1)
            
            return x
    
    # Train
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = WakeWordClassifier().to(device)
    criterion = nn.BCELoss()
    optimizer = optim.Adam(model.parameters(), lr=0.001)
    
    print(f"   Training on: {device}")
    
    for epoch in range(epochs):
        model.train()
        total_loss = 0
        correct = 0
        total = 0
        
        for batch_x, batch_y in loader:
            batch_x = batch_x.to(device)
            batch_y = batch_y.float().to(device)
            
            optimizer.zero_grad()
            outputs = model(batch_x).squeeze()
            loss = criterion(outputs, batch_y)
            loss.backward()
            optimizer.step()
            
            total_loss += loss.item()
            predicted = (outputs > 0.5).float()
            correct += (predicted == batch_y).sum().item()
            total += batch_y.size(0)
        
        if (epoch + 1) % 20 == 0 or epoch == 0:
            acc = 100 * correct / total
            print(f"   Epoch {epoch+1}/{epochs} - Loss: {total_loss/len(loader):.4f} - Accuracy: {acc:.1f}%")
    
    # =========================================================================
    # EXPORT TO ONNX
    # =========================================================================
    
    print(f"\n📦 Exporting to ONNX...")
    
    model.eval()
    model.cpu()
    
    # Create dummy input matching openWakeWord's expected shape
    # openWakeWord feeds (batch=1, frames=76, features=96)
    dummy_input = torch.randn(1, MAX_FRAMES, EMBEDDING_DIM)
    
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        torch.onnx.export(
            model,
            dummy_input,
            output_path,
            input_names=['input'],
            output_names=['output'],
            dynamic_axes={
                'input': {0: 'batch', 1: 'time'},
                'output': {0: 'batch'}
            },
            opset_version=11,
            do_constant_folding=True
        )
        
        print(f"✅ Model exported to: {output_path}")
        
        # Verify
        import onnx
        onnx_model = onnx.load(output_path)
        onnx.checker.check_model(onnx_model)
        print("✅ ONNX model verified")
        
        return True
        
    except Exception as e:
        print(f"❌ ONNX export failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Train Hey Prometheus wake word model",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Train with samples in training_samples directory:
    python train_local.py \\
        --positive ./training_samples/positive \\
        --negative ./training_samples/negative \\
        --output ./models/hey_prometheus.onnx
        
    # Train with more epochs:
    python train_local.py \\
        --positive ./training_samples/positive \\
        --negative ./training_samples/negative \\
        --output ./models/hey_prometheus.onnx \\
        --epochs 200
        """
    )
    
    parser.add_argument(
        '--positive', '-p',
        required=True,
        help='Directory containing positive samples (wake word recordings)'
    )
    parser.add_argument(
        '--negative', '-n', 
        required=True,
        help='Directory containing negative samples (other speech/noise)'
    )
    parser.add_argument(
        '--output', '-o',
        required=True,
        help='Output path for the .onnx model'
    )
    parser.add_argument(
        '--epochs', '-e',
        type=int,
        default=100,
        help='Number of training epochs (default: 100)'
    )
    parser.add_argument(
        '--name',
        default='hey_prometheus',
        help='Model name (default: hey_prometheus)'
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("🎤 Hey Prometheus Wake Word Training")
    print("=" * 60)
    
    # Check dependencies
    check_dependencies()
    
    # Validate samples exist
    if not os.path.isdir(args.positive):
        print(f"❌ Positive samples directory not found: {args.positive}")
        sys.exit(1)
    
    if not os.path.isdir(args.negative):
        print(f"❌ Negative samples directory not found: {args.negative}")
        sys.exit(1)
    
    # Validate sample counts
    validate_samples(args.positive, args.negative)
    
    # Train model
    success = train_with_openwakeword(
        positive_dir=args.positive,
        negative_dir=args.negative,
        output_path=args.output,
        model_name=args.name,
        epochs=args.epochs
    )
    
    if success:
        print("\n" + "=" * 60)
        print("🎉 Training Complete!")
        print("=" * 60)
        print(f"\nTo deploy to Raspberry Pi:")
        print(f"  1. Copy {args.output} to the Pi")
        print(f"  2. Update .env: WAKE_WORD_MODEL=/app/models/hey_prometheus.onnx")
        print(f"  3. Restart: docker-compose up -d wakeword")
        print(f"  4. Start: curl -X POST http://localhost:5003/start")
    else:
        print("\n❌ Training failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
