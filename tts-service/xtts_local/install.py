#!/usr/bin/env python3
"""
XTTS v2 Local Installation Script
Встановлює Coqui TTS з підтримкою XTTS v2
"""

import subprocess
import sys

def run_cmd(cmd):
    print(f"\n>>> {cmd}")
    result = subprocess.run(cmd, shell=True)
    return result.returncode == 0

print("=" * 60)
print("XTTS v2 (Coqui TTS) - Installation")
print("=" * 60)

# Перевірка Python версії
print(f"\nPython version: {sys.version}")
if sys.version_info < (3, 9):
    print("ERROR: Python 3.9+ required!")
    sys.exit(1)

print("\n[1/3] Installing PyTorch...")
# PyTorch CPU version (для GPU потрібна інша команда)
if not run_cmd("pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu"):
    print("WARNING: PyTorch installation may have issues")

print("\n[2/3] Installing Coqui TTS...")
if not run_cmd("pip install TTS"):
    print("ERROR: Failed to install TTS")
    sys.exit(1)

print("\n[3/3] Verifying installation...")
try:
    from TTS.api import TTS
    print("OK: TTS imported successfully")

    # Список доступних моделей
    print("\nAvailable XTTS models:")
    for model in TTS().list_models():
        if "xtts" in model.lower():
            print(f"  - {model}")

except ImportError as e:
    print(f"ERROR: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("Installation complete!")
print("=" * 60)
print("\nNext step: Run test_xtts.py to test the model")
