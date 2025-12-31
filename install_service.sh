#!/bin/bash

# Auto-Startup Installer for Invenova
# Creates a systemd service to run pi_launcher.py on boot.

SERVICE_NAME="invenova"
USER="pi"
APP_DIR="/home/pi/invenova"
VENV_PYTHON="$APP_DIR/.venv/bin/python"
LAUNCHER="$APP_DIR/pi_launcher.py"

echo "========================================="
echo "   Invenova Auto-Startup Installer"
echo "========================================="

# 1. Verify Paths
if [ ! -f "$LAUNCHER" ]; then
    echo "Error: pi_launcher.py not found at $LAUNCHER"
    exit 1
fi

if [ ! -f "$VENV_PYTHON" ]; then
    echo "Error: Virtual environment python not found at $VENV_PYTHON"
    echo "Please run ./setup_pi_env.sh first."
    exit 1
fi

echo "Creating systemd service file..."

# 2. Create Service File Content
# We use tee to write to the protected directory with sudo
sudo tee /etc/systemd/system/${SERVICE_NAME}.service > /dev/null <<EOF
[Unit]
Description=Invenova Voice Assistant Launcher
After=network.target sound.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$APP_DIR
ExecStart=$VENV_PYTHON $LAUNCHER
Environment="PYTHONUNBUFFERED=1"
Environment="VOSK_LOG_LEVEL=-1"

# Restart automatically if it crashes
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

echo "Service file created at /etc/systemd/system/${SERVICE_NAME}.service"

# 3. Reload and Enable
echo "Reloading systemd daemon..."
sudo systemctl daemon-reload

echo "Enabling service to start on boot..."
sudo systemctl enable ${SERVICE_NAME}.service

echo "Starting service now..."
sudo systemctl start ${SERVICE_NAME}.service

echo "========================================="
echo "   Success! Invenova is now installed."
echo "========================================="
echo "To check status: sudo systemctl status $SERVICE_NAME"
echo "To stop:         sudo systemctl stop $SERVICE_NAME"
echo "To view logs:    journalctl -u $SERVICE_NAME -f"
