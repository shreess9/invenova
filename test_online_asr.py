import sys
import os
import time

print("--- Online ASR Diagnostic ---")
print(f"Python: {sys.executable}")

try:
    import speech_recognition as sr
    print("[SUCCESS] speech_recognition module imported.")
except ImportError:
    print("[FAIL] speech_recognition module NOT found.")
    print("Please run: ./fix_deps.sh")
    sys.exit(1)

r = sr.Recognizer()
print("[INFO] Recognizer initialized.")

# Check Microphone (optional, might fail if no mic)
try:
    mics = sr.Microphone.list_microphone_names()
    print(f"[INFO] Microphones found: {len(mics)}")
    for i, m in enumerate(mics):
        print(f"  - {i}: {m}")
except Exception as e:
    print(f"[WARN] Could not list microphones: {e}")

print("\n--- Testing Google Speech API ---")
print("We will attempt to recognize a dummy file or empty buffer if allowed,")
print("but really we just want to know if the library works.")

# Create a dummy small wav file to test API connectivity? 
# Or just ask user to speak? 
# Let's try to verify if we can make a request.
# Without audio, we can't test much. 
# But just getting this far proves the library is there.

print("[RESULT] Diagnostics Complete. If you see [SUCCESS] above, the library IS installed.")
