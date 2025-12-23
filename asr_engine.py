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

import pyaudio
import wave

class AudioRecorder:
    def __init__(self):
        self.chunk = 1024
        self.format = pyaudio.paInt16
        self.channels = 1
        self.rate = config.SAMPLE_RATE
        self.p = pyaudio.PyAudio()

    def record(self, output_filename, duration=None):
        """
        Records audio until ENTER is pressed (if duration is None)
        or for fixed duration.
        """
        if os.name == 'nt':
            import msvcrt
            
            # Flush existing keypresses
            while msvcrt.kbhit():
                msvcrt.getch()

        stream = self.p.open(format=self.format,
                        channels=self.channels,
                        rate=self.rate,
                        input=True,
                        frames_per_buffer=self.chunk)
        frames = []

        print("Recording... Press ENTER to stop.")

        if os.name == 'nt':
            start_time = time.time()
            try:
                while True:
                    data = stream.read(self.chunk)
                    frames.append(data)
                    
                    # Check Duration
                    if duration and (time.time() - start_time > duration):
                        break
                        
                    # Check Keypress (Enter to stop)
                    if not duration and msvcrt.kbhit():
                        ch = msvcrt.getch()
                        if ch == b'\r':
                            break
            except KeyboardInterrupt:
                pass
        else:
            # Linux: Use Non-Blocking Input via Select or separate check
            # Since stream.read is blocking, we need to check input before reading loop or use threading.
            # Simpler approach: Check input non-blockingly using select on stdin.
            import sys, select
            
            start_time = time.time()
            try:
                while True:
                    # Capture Audio
                    data = stream.read(self.chunk, exception_on_overflow=False)
                    frames.append(data)
                    
                    if duration and (time.time() - start_time > duration):
                        break
                        
                    if not duration:
                        # Check for Enter key (Non-blocking)
                        if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
                            line = sys.stdin.readline()
                            break
            except KeyboardInterrupt:
                pass

        print("Finished recording.")

        stream.stop_stream()
        stream.close()
        # Don't terminate p here, keep it alive for reuse

        wf = wave.open(output_filename, 'wb')
        wf.setnchannels(self.channels)
        wf.setsampwidth(self.p.get_sample_size(self.format))
        wf.setframerate(self.rate)
        wf.writeframes(b''.join(frames))
        wf.close()
        return output_filename

    def __del__(self):
        self.p.terminate()
