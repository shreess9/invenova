
import os
import sys
import sounddevice as sd
import soundfile as sf
import subprocess

def test_audio():
    print("=== Audio Diagnostic ===")
    
    # 1. List Devices
    print("\n1. Listing Audio Devices:")
    try:
        print(sd.query_devices())
    except Exception as e:
        print(f"Error querying devices: {e}")

    # 2. Generate a Test Tone (Sine Wave)
    import numpy as np
    fs = 44100
    duration = 1.0  # seconds
    f = 440.0  # Hz
    t = np.linspace(0, duration, int(duration * fs), False)
    tone = 0.5 * np.sin(2 * np.pi * f * t)
    
    filename = "test_tone.wav"
    sf.write(filename, tone, fs)
    print(f"\n2. Generated {filename}")

    # 3. Try Playback with sounddevice
    print(f"\n3. Playing with sounddevice (PortAudio)...")
    try:
        data, fs = sf.read(filename)
        sd.play(data, fs)
        sd.wait()
        print("   Finished. Did you hear it?")
    except Exception as e:
        print(f"   Sounddevice Error: {e}")

    # 4. Try Playback with aplay
    print(f"\n4. Playing with 'aplay' (ALSA CLI)...")
    if os.name == 'posix':
        try:
            result = subprocess.run(["aplay", filename], capture_output=True, text=True)
            if result.returncode == 0:
                print("   aplay executed successfully. Did you hear it?")
            else:
                print(f"   aplay failed: {result.stderr}")
        except FileNotFoundError:
            print("   aplay not found.")
    else:
        print("   Skipped (Not Linux)")

    print("\nIf you heard 'aplay' but not 'sounddevice', we might need to select a specific device index.")
    
if __name__ == "__main__":
    test_audio()
