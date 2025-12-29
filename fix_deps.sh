#!/bin/bash
# One-click fix for missing RPi.GPIO
cd "$(dirname "$0")"

if [ -d ".venv" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
    
    echo "Installing dependencies (Vosk, SoundDevice, RPi.GPIO)..."
    pip install vosk sounddevice numpy RPi.GPIO
    
    echo "Done! You can now run the launcher."
else
    echo "Error: Virtual environment not found. Run ./setup_pi_env.sh first."
fi
