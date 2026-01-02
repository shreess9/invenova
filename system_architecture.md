# System Architecture

The Invenova system follows a modular, layer-based architecture designed for offline efficiency on embedded hardware.

## 1. Hardware Layer
- **Input**: Microphone (Audio), GPIO Buttons (Control).
- **Output**: Speaker (Audio), LED (Visual Feedback).
- **Processing**: Raspberry Pi 4 (SoC).

## 2. Interface Layer (`pi_launcher.py`)
- Acts as the **System Watchdog**.
- Monitors the **Power Switch (GPIO 23)**.
- Launches the `mini_assistant.py` process when the switch is ON.
- Kills the process when the switch is OFF (Deadman/Safety feature).
- Manages the top-level **GPIO Cleanup** to prevent resource conflicts.

## 3. Application Layer (`mini_assistant.py`)
- The central brain of the assistant.
- **Event Loop**: Waits for Wake Events (GPIO 24 Press).
- **Orchestrator**: Calls ASR, NLP, DB, and TTS modules in sequence.
- **Normalization**: Converts spoken numbers (e.g., "twelve thousand") into digits ("12000") for accurate database matching.

## 4. Core Services (Engines)
- **ASR Engine (`asr_engine.py`)**:
    - Wraps the **Vosk API**.
    - Handles Microphone Audio Stream via `sounddevice`.
    - Features: Dynamic Grammar construction (learns inventory item names), Noise Suppression, and "Hold-to-Record" logic.
- **NLP Engine**:
    - Performs Intent Classification (e.g., `check_stock`, `check_location`).
    - Extract Entities (Item Name, Quantity, Value).
- **Database Manager**:
    - Executes SQL queries against `inventory.db`.
    - Returns structured results (Stock counts, Shelf locations).
- **TTS Engine**:
    - Converts text responses into audio.
    - Uses **Piper** (Neural) or **eSpeak** (Formant) for generation.
    - Streams audio specifically to the configured output device.

## Data Flow
`User Speech` -> `Microphone` -> `ASR (Text)` -> `NLP (Intent)` -> `DB (Query)` -> `TTS (Speech)` -> `Speaker`
