import os
import ctypes
import config
import dll_fix # Ensure DLLs are loaded

from faster_whisper import WhisperModel
import time


class VoiceListener:
    def __init__(self, dynamic_vocab=None):
        if config.PI_MODE:
            print(f"ASR Mode: LITE (CPU, Model: {config.WHISPER_MODEL_SIZE})")
            self.model = WhisperModel(config.WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
        else:
            try:
                # print("DEBUG: Attempting to load Whisper on CUDA...")
                self.model = WhisperModel(config.WHISPER_MODEL_SIZE, device="cuda", compute_type="float16")
                print("ASR Model (CUDA) loaded.")
            except Exception as e:
                print(f"WARNING: CUDA initialization failed ({e}). Falling back to CPU...")
                # print("DEBUG: Attempting to load Whisper on CPU...")
                self.model = WhisperModel(config.WHISPER_MODEL_SIZE, device="cpu", compute_type="int8")
                print("ASR Model (CPU) loaded.")
        
        # Base technical vocabulary - ENHANCED for NUMBERS
        self.base_vocab = [
            "BLDC", "DC Motor", "BO Motor", "RPM", "10 RPM", "100 RPM", "1000 RPM", "KV", "Lipo", "mAh", 
            "GPS", "GSM", "SMA", "HDMI", "VGA", "USB", "LAN", "BNC", "SD Card", "OLED", "LCD", "LED", 
            "RFID", "PIR", "LDR", "DHT", "MQ", "TSOP", "RTC", "CNC", "BMS", "PCB", "SMPS", "UPS", "MCB", 
            "ECG", "Servo", "Stepper", "L298N", "L293D", "ULN2003", "LM358", "LM317", "HC05", "HCSR04", 
            "ESP8266", "ESP32", "STM32", "MSP430", "PIC", "ATmega", "Raspberry Pi", "Arduino", 
            "Multimeter", "Oscilloscope", "Tektronix", "Keysight", "Agilent", 
            "Weller", "Soldering", "Relay", "Switch", "Mosfet", "Transistor", "Resistor", "Capacitor", 
            "Diode", "Fuse", "Battery", "Charger", "Adapter", "Cable", "Wire", "Shield", "Module"
        ]
        
        # Add dynamic vocab from DB if provided
        if dynamic_vocab:
            # Merge and deduplicate
            # Limit global prompt size roughly (Whisper limit ~224 tokens, text length varies)
            # We prioritize Dynamic (DB) vocab by putting it FIRST? Or appending?
            # Appending is safer.
            print(f"Priming ASR with {len(dynamic_vocab)} unique words from Database.")
            self.final_vocab_list = list(set(self.base_vocab + dynamic_vocab))
        else:
            self.final_vocab_list = self.base_vocab
            
        # Create prompt string
        self.vocab_prompt = f"{', '.join(self.final_vocab_list)}."
        print(f"ASR Prompt: {self.vocab_prompt[:100]}...") # Debug print


    def transcribe(self, audio_path):
        """
        Transcribes the given audio file path.
        Returns the text string.
        """
        if not os.path.exists(audio_path):
            print(f"Audio file not found: {audio_path}")
            return ""

        segments, info = self.model.transcribe(
            audio_path, 
            beam_size=config.BEAM_SIZE,
            language="en", 
            initial_prompt=self.vocab_prompt,
            condition_on_previous_text=False # Better for short commands
        )
        
        full_text = ""
        for segment in segments:
            full_text += segment.text + " "
            
        return full_text.strip()

# Note: We need a way to RECORD audio.
# The user pipeline says: Voice Input -> ASR
# I'll add a simple recorder using pyaudio here or in a separate util.
# Putting it here for cohesion.

# --- Audio Recorder (SoundDevice Version) ---
import sounddevice as sd
import soundfile as sf
import numpy as np

# Context Manager for ALSA Suppression (Module Level)
from contextlib import contextmanager

@contextmanager
def no_alsa_err():
    """
    Suppress C-level ALSA/PortAudio errors by redirecting stderr to /dev/null.
    Works on Linux/Pi to hide 'paInvalidSampleRate', etc.
    """
    if os.name == 'nt':
        yield
        return
    
    try:
        # Open /dev/null
        devnull = os.open(os.devnull, os.O_WRONLY)
        
        # Save original fds
        try:
            saved_stderr = os.dup(2)
        except Exception:
            # If stderr is not valid (e.g. some IDEs), just yield
            yield
            return

        # Flush Python streams
        sys.stderr.flush()
        
        # Redirect stderr to devnull
        os.dup2(devnull, 2)
        
        try:
            yield
        finally:
            # Restore stderr
            os.dup2(saved_stderr, 2)
            os.close(saved_stderr)
            os.close(devnull)
    except Exception:
        # Fallback if anything fails
        yield

class AudioRecorder:
    def __init__(self):
        self.sample_rate = config.SAMPLE_RATE
        self.channels = 1
        self.device_index = config.AUDIO_CARD_INDEX # Explicit Device from Config

    def record(self, output_filename, duration=None, silence_threshold=0.01, silence_duration=1.5):
        """
        Records audio to a WAV file.
        If duration is None, records until silence is detected (VAD-like).
        """
        print(f"Recording... (Device Index: {self.device_index})")
        
        recorded_frames = []
        
        def callback(indata, frames, time, status):
            if status:
                print(status, file=sys.stderr)
            recorded_frames.append(indata.copy())

        # Wrap stream in ALSA suppression
        with no_alsa_err():
            # Auto-Negotiate Sample Rate for Raspberry Pi USB Mics
            supported_rates = [self.sample_rate, 48000, 44100, 16000]
            stream = None
            
            for rate in supported_rates:
                try:
                    # Try to open stream with this rate
                    stream = sd.InputStream(samplerate=rate, 
                                        device=self.device_index,
                                        channels=self.channels, 
                                        callback=callback)
                    stream.start() # Explicit start to trigger error if invalid
                    print(f"DEBUG: Recording started at {rate}Hz")
                    break
                except Exception as e:
                    if stream: stream.close()
                    stream = None
                    # print(f"DEBUG: Rate {rate}Hz failed: {e}")
                    continue
            
            if not stream:
                print(f"Error: Could not open audio device (Index {self.device_index}) with any common sample rate.")
                return False

            try:
                # Keep stream open and monitor
                if duration:
                    sd.sleep(int(duration * 1000))
                else:
                    # Simple Energy-based VAD
                    print("Listening for speech...")
                    max_silence_blocks = int(silence_duration * (self.sample_rate / 1024))
                    silent_blocks = 0
                    has_started = False
                    
                    while True:
                        if not recorded_frames:
                            sd.sleep(100)
                            continue
                            
                        last_chunk = recorded_frames[-1]
                        if len(last_chunk) > 0:
                            amplitude = np.linalg.norm(last_chunk) / len(last_chunk)
                        else:
                            amplitude = 0
                        
                        if amplitude > silence_threshold:
                            has_started = True
                            silent_blocks = 0
                        elif has_started:
                            silent_blocks += 1
                            
                        if has_started and silent_blocks > 20: 
                            print("Silence detected. Stopping.")
                            break
                            
                        sd.sleep(100)
                        
                        if len(recorded_frames) * 1024 / self.sample_rate > 15: # 15s Max
                            break
                            
            except Exception as e:
                print(f"Recording Logic Error: {e}")
            finally:
                if stream:
                    stream.stop()
                    stream.close()

        # Save to file
        if not recorded_frames:
            return False
            
        audio_data = np.concatenate(recorded_frames, axis=0)
        sf.write(output_filename, audio_data, self.sample_rate)
        return output_filename


