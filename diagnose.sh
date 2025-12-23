#!/bin/bash

# Ensure script is run from its directory
cd "$(dirname "$0")"

echo "==================================================="
echo "  INVENOVA DIAGNOSTICS"
echo "==================================================="

# Check for .venv
if [ ! -d ".venv" ]; then
    echo "Error: .venv directory not found. Please run ./setup_pi_env.sh first."
    exit 1
fi

echo "Activating Environment..."
source .venv/bin/activate

echo "Running Diagnostic..."
python3 test_audio_diag.py

echo "==================================================="
echo "Diagnostic Complete."
