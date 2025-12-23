import os

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "inventory.db")
CSV_PATH = os.path.join(BASE_DIR, "inventory.csv")

# PI_MODE: Set to True to force Lite models (Piper TTS, Tiny Whisper, etc.)
# If on Linux (Pi), default to True.
PI_MODE = True if os.name == 'posix' else True # Force True for Simulation on Windows

# ASR Settings
# On Pi/Simulation, use tiny/base for speed.
# ASR Settings
# On Pi/Simulation, use tiny/base for speed. small for accuracy.
WHISPER_MODEL_SIZE = "small.en" if PI_MODE else "medium.en" 
BEAM_SIZE = 5

# NLP Settings
NLP_MODEL_NAME = "all-MiniLM-L6-v2"
# Intent detection threshold
INTENT_THRESHOLD = 0.30

# TTS Settings
# Options: "fast" (pyttsx3 - Robotic but Instant), "high_quality" (XTTS - Natural but Slow)
# Options: "fast" (pyttsx3), "high_quality" (XTTS), "piper" (Pi Optimum)
TTS_ENGINE = "piper" if PI_MODE else "high_quality"
# XTTS v2 model name in Coqui TTS
# Piper Settings
PIPER_BINARY = os.path.join(BASE_DIR, "piper", "piper", "piper.exe" if os.name == 'nt' else "piper")
PIPER_MODEL = os.path.join(BASE_DIR, "piper", "en_US-amy-medium.onnx")

TTS_MODEL_NAME = "tts_models/multilingual/multi-dataset/xtts_v2"
SPEAKER_IDX = "Ana Florence" # Default English female speaker
LANGUAGE_IDX = "en"

# Audio Settings
SAMPLE_RATE = 16000
# LLM Settings
# Llama-3.2-1B-Instruct (High Perf, Low RAM) for Pi 4
LLM_MODEL_FILENAME = "Llama-3.2-1B-Instruct-Q4_K_M.gguf" if PI_MODE else "Phi-3-mini-4k-instruct-q4.gguf"
LLM_MODEL_PATH = os.path.join(BASE_DIR, "models", LLM_MODEL_FILENAME)
# Pi 4 (4GB/8GB) safe context. 2048 is plenty for inventory.
LLM_CONTEXT_WINDOW = 2048
# On Pi (CPU), GPU layers should be 0.
LLM_GPU_LAYERS = 0 if PI_MODE else 50
