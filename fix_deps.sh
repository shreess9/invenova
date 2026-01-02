#!/bin/bash

# Ensure script is run from its directory
cd "$(dirname "$0")"

echo "==================================================="
echo "  Fix Dependencies / Setup Invenova (Pi 4)"
echo "==================================================="

# Check for .venv
if [ ! -d ".venv" ]; then
    echo "[INFO] Creating Virtual Environment..."
    python3 -m venv .venv
fi

echo "[INFO] Activating Environment..."
source .venv/bin/activate

echo "[INFO] Installing System Build Dependencies (if needed)..."
# Just a soft check or reminder. We assume basic system dep are there. 
# But SpeechRecognition might fails without flac
# sudo apt-get install -y flac python3-pyaudio portaudio19-dev libatlas-base-dev

echo "[INFO] Installing Python Dependencies..."
pip install --upgrade pip
pip install -r requirements_pi.txt

echo "[INFO] Checking for SpeechRecognition..."
pip install SpeechRecognition

echo "==================================================="
echo "  Setup Complete. Run ./run.sh to start."
echo "==================================================="
