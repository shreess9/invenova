# Invenova: Voice-Activated Inventory Assistant

Invenova is an offline, privacy-first voice assistant designed for manufacturing and lab environments. Running entirely on a Raspberry Pi 4, it allows users to check stock levels, locate items, and query inventory specifications without needing an internet connection.

## Key Features
- **Offline Speech Recognition**: Uses Vosk API for accurate, low-latency command recognition.
- **Natural Language Processing**: Intelligent intent extraction to understand queries like "Where is the 12V motor?" or "Do we have any Arduino boards?"
- **Database Integration**: SQLite-backed inventory system with robust search capabilities.
- **Hardware Integration**: Physical buttons for "Push-to-Talk" and System Power, plus Status LED feedback.
- **Voice Response**: Text-to-Speech feedback via Piper/eSpeak.

## Getting Started

### Prerequisites
- Raspberry Pi 4 (4GB+ recommended)
- USB Microphone
- Speaker (3.5mm or USB)
- Push Buttons (GPIO 23 for Power, GPIO 24 for Interact)
- LED (GPIO 27)

### Installation
1.  Clone the repository:
    ```bash
    git clone https://github.com/shreess9/invenova.git
    cd invenova
    ```
2.  Run the automated setup script:
    ```bash
    ./fix_deps.sh
    ```
    This installs Python dependencies, Vosk models, and system libraries.

3.  (Optional) Install Auto-Start Service:
    ```bash
    sudo ./install_service.sh
    ```
    This ensures the assistant starts automatically when the Pi boots.

### Usage
- **Start**: Press the **Green Button (GPIO 23)** (or flip the switch) to launch the system. The Status LED will light up.
- **Talk**: Press the **Red Button (GPIO 24)** once to start listening.
- **Speak**: Say your command, e.g., *"How many DC Motors do we have?"*
- **Stop**: Press the Red Button again to finish speaking (or wait for silence).
- **Listen**: The assistant will speak the answer.

## Monitoring
To view live logs while running as a service:
```bash
journalctl -u invenova -f
```

## File Structure
- `pi_launcher.py`: Hardware watchdog. Monitors the Power Switch and launches the main app.
- `mini_assistant.py`: Main application logic.
- `asr_engine.py`: Speech recognition core (Vosk).
- `tts_engine.py`: Text-to-Speech core.
- `config.py`: Configuration settings (Pins, paths, models).
