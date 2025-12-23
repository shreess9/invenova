#!/bin/bash

# Ensure script is run from its directory
cd "$(dirname "$0")"

echo "==================================================="
echo "  Setup Invenova (Pi 4 Linux)"
echo "==================================================="

# Check for .venv
if [ ! -d ".venv" ]; then
    echo "[INFO] Creating Virtual Environment..."
    // Ensure python3-venv is installed on the system first
    python3 -m venv .venv
fi

echo "[INFO] Activating Environment..."
source .venv/bin/activate

echo "[INFO] Installing Dependencies..."
# Ensure system deps: libasound2-dev portaudio19-dev
echo "NOTE: If installation fails, run: sudo apt-get install python3-dev libasound2-dev portaudio19-dev"
pip install -r requirements_pi.txt

echo ""
echo "[INFO] Download Piper TTS (Linux ARM64)..."
python3 download_piper.py

echo ""
echo "[INFO] Download Lite LLM (TinyLlama)..."
python3 download_llm_lite.py

echo ""
echo "Setup Complete."
echo "Run ./run.sh to start."
