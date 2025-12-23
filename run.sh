#!/bin/bash

# Ensure script is run from its directory
cd "$(dirname "$0")"

echo "==================================================="
echo "  INVENOVA PI 4 - LAUNCHER"
echo "==================================================="

if [ ! -d ".venv" ]; then
    echo "[ERROR] Virtual Environment not found. Please run ./setup_pi_env.sh first."
    exit 1
fi

echo "Activating Environment..."
source .venv/bin/activate

echo "Starting Assistant (Lite Mode)..."
python3 -u mini_assistant.py
