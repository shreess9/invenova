# Project Context: Forge-Integrated (Raspberry Pi 4 Port)

**Current Status**: 
This project is a fork of "Invenova Voice Assistant" optimized for **Raspberry Pi 4 (Linux/ARM)**. 
We are currently in **Simulation Mode** on Windows.

## Immediate Goals
1. **Model Swap**: 
   - Replace `XTTS` (too heavy) with `Piper TTS` (Windows binary for simulation, ARM binary for Pi).
   - Downgrade `faster-whisper` model from `medium.en` to `tiny.en` or `base.en`.
   
2. **Environment Setup**:
   - Create a new Virtual Environment (`venv`).
   - Install "Lite" dependencies (see `requirements_pi.txt` - to be created).

3. **Verify Simulation**:
   - Run `mini_assistant.py`.
   - Ensure latency is low (<1s response) and memory usage is low.

## Key Files
- `mini_assistant.py`: Main entry point.
- `deploy_integrated.bat`: Script that created this folder.
- `dll_fix.py`: Crucial for Windows simulation (CUDA loading).

## Next Step for AI
- Create `requirements_pi.txt` with `piper-tts`, `faster-whisper`, `numpy`, `sounddevice`.
- Modify `config.py` to add a `PI_MODE` flag.
- Implement `PiperSpeaker` class in `tts_engine.py`.
