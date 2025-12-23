
import os
import sys
import sounddevice as sd
import soundfile as sf
import subprocess

try:
    import config
    KEYWORD = config.AUDIO_OUTPUT_KEYWORD
except:
    KEYWORD = "Headphones"

def test_audio():
    print("=== Audio Diagnostic ===")
    
    # 1. List Devices
    print(f"\n1. Listing Audio Devices (Looking for '{KEYWORD}'):")
    try:
        devices = sd.query_devices()
        print(devices)
        
        target_indices = []
        for i, dev in enumerate(devices):
            if dev['max_output_channels'] > 0:
                if KEYWORD.lower() in dev['name'].lower():
                    print(f"   [MATCH FOUND] Index {i}: {dev['name']}")
                    target_indices.append(i)
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
    
    # 5. Advanced: Try to force Headphone Jack via amixer (Legacy Pi)
    print("\n5. Attempting to force Headphone Jack (3.5mm) via amixer...")
    try:
        # numid=3 1 -> Analog (Jack), 2 -> HDMI
        subprocess.run(["amixer", "cset", "numid=3", "1"], capture_output=True)
        print("   Executed 'amixer cset numid=3 1' (Force Analog).")
    except:
        print("   amixer command failed (might be using PulseAudio/Pipewire).")

    # 6. Brute Force 'aplay' on all cards
    print("\n6. Brute Force Playback on Hardware Cards:")
    try:
        # List cards
        list_out = subprocess.run(["aplay", "-l"], capture_output=True, text=True).stdout
        print(list_out)
        
        # Extract card numbers: "card 0:", "card 1:"
        import re
        cards = re.findall(r'card (\d+):', list_out)
        unique_cards = sorted(list(set(cards)))
        
        for card in unique_cards:
            device_str = f"plughw:{card},0"
            print(f"\n   >>> Testing Device: {device_str} <<<")
            print("   (Listen for sound now...)")
            try:
                subprocess.run(["aplay", "-D", device_str, filename], capture_output=True)
            except:
                pass
    except Exception as e:
        print(f"Error listing cards: {e}")

if __name__ == "__main__":
    test_audio()
