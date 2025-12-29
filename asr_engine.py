import os
import json
import time
import sys
import wave
import config
import sounddevice as sd
import numpy as np

# Suppress ALSA/Vosk logs
os.environ['VOSK_LOG_LEVEL'] = '-1'

try:
    from vosk import Model, KaldiRecognizer, SetLogLevel
    SetLogLevel(-1)
except ImportError:
    print("Vosk not installed. Run: pip install vosk")

class VoiceListener:
    def __init__(self):
        pass

    def record(self, filename="input.wav", duration=None, samplerate=16000):
        """
        Records audio from the microphone.
        Auto-negotiates sample rate if 16k fails.
        """
        channels = 1
        resolution = 'int16'
        
        # 1. Negotiate Sample Rate
        final_rate = samplerate
        try:
            # Try 16k first
            sd.check_input_settings(device=None, channels=1, dtype=resolution, samplerate=16000)
            final_rate = 16000
        except Exception:
            # Fallback to device default
            try:
                dev_info = sd.query_devices(kind='input')
                final_rate = int(dev_info['default_samplerate'])
                print(f"DEBUG: 16k failed. Fallback to native rate: {final_rate}Hz")
            except:
                final_rate = 44100 # Last resort

        print(f"DEBUG: Recording started at {final_rate}Hz")
        
        audio_data = []
        
        # Callback for stream
        def callback(indata, frames, time, status):
            if status:
                pass # Ignore ALSA underflows
            audio_data.append(indata.copy())

        try:
            # Open Stream at NEGOTIATED rate
            with sd.InputStream(samplerate=final_rate, channels=channels, dtype=resolution, callback=callback):
                if duration:
                    # Timer Mode
                    print(f"Recording for {duration} seconds...")
                    sd.sleep(int(duration * 1000))
                else:
                    # Manual Control: GPIO / Keyboard Stop
                    print("Recording... Press ENTER (or Button) to stop.")
                    
                    # Wait Loop
                    while True:
                        sd.sleep(50) # Small sleep
                        should_stop = False
                        
                        # 1. Keyboard Check
                        if os.name == 'nt':
                            import msvcrt
                            if msvcrt.kbhit():
                                if msvcrt.getch() == b'\r': should_stop = True
                        else:
                            import select
                            if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
                                sys.stdin.readline()
                                should_stop = True
                                
                        # 2. GPIO Check
                        try:
                            import RPi.GPIO as GPIO
                            if GPIO.getmode() is not None:
                                # If Button Pressed (LOW)
                                if GPIO.input(config.GPIO_INTERACT_PIN) == GPIO.LOW:
                                    print("Button Stop Signal Received.")
                                    should_stop = True
                        except:
                            pass
                            
                        if should_stop:
                            print("Stop signal received.")
                            break

            # Save File POst-Recording
            if not audio_data:
                return None
                
            audio_concatenated = np.concatenate(audio_data, axis=0)
            
            # Save as WAV for Vosk Processing
            with wave.open(filename, 'wb') as wf:
                wf.setnchannels(channels)
                wf.setsampwidth(2) # 16-bit
                wf.setframerate(final_rate) # Use ACTUAL rate
                wf.writeframes(audio_concatenated.tobytes())
                
            return filename
            
        except Exception as e:
            print(f"Recording Error: {e}")
            return None


class ASREngine:
    def __init__(self, model_path="model", db_manager=None):
        self.model_path = model_path
        self.grammar = None
        
        print("Loading Vosk Model...")
        if not os.path.exists(model_path):
            print(f"FATAL: Vosk model not found at '{model_path}'. Run download_vosk.py")
            self.model = None
        else:
            self.model = Model(model_path)
            print("Vosk Model Loaded.")

        # Build Grammar if DB provided
        if db_manager:
            self.build_grammar(db_manager)

    def build_grammar(self, db_manager):
        """
        Constructs a JSON list of valid words/phrases from Inventory DB.
        This restricts Vosk to ONLY listen for these things.
        """
        print("Building Dynamic Grammar from Inventory...")
        try:
            # 1. Base Commands
            commands = [
                "check stock", "where is", "update stock", "add", "remove", 
                "record", "stop", "cancel", "confirm", "yes", "no", 
                "quantity", "inventory", "search", "find", "show me"
            ]
            
            # 2. Numbers (0-100)
            numbers = [str(i) for i in range(100)] 
            
            # 3. Inventory Items
            items = db_manager.get_all_item_names() # Returns list of strings
            
            # Extract unique words to keep grammar flexible ("Servo Motor" -> "servo", "motor")
            # OR keep full phrases if we want strict phrase matching. 
            # Vosk works best with a list of words or short phrases.
            
            unique_words = set()
            
            # Add base commands
            for c in commands:
                unique_words.update(c.split())
                
            # Add numbers
            unique_words.update(numbers)
            
            # Add item tokens
            for item in items:
                # Clean: "L293D (Motor Driver)" -> "l293d", "motor", "driver"
                # Remove special chars
                clean = item.lower().replace("(", "").replace(")", "").replace("-", " ")
                parts = clean.split()
                unique_words.update(parts)
                
            # Convert to list
            grammar_list = list(unique_words)
            # Add [UNK] for unknown? Vosk usually prefers just the list.
            
            # Format: '["word1", "word2", "[unk]"]'
            self.grammar = json.dumps(grammar_list)
            print(f"Grammar Constructed. {len(grammar_list)} unique words allowed.")
            
        except Exception as e:
            print(f"Grammar Build Failed: {e}")
            self.grammar = None

    def update_grammar(self, extra_words):
        """
        Extends the current grammar with a list of additional words.
        Useful for adding common English fillers.
        """
        if not self.grammar: return
        
        try:
            current_list = json.loads(self.grammar)
            unique_set = set(current_list)
            
            # Add new words
            initial_count = len(unique_set)
            unique_set.update([w.lower() for w in extra_words])
            
            if len(unique_set) > initial_count:
                print(f"Extending Grammar: Added {len(unique_set) - initial_count} common words.")
                self.grammar = json.dumps(list(unique_set))
        except Exception as e:
            print(f"Grammar Update Failed: {e}")

    def transcribe(self, audio_file):
        """
        Transcribes the audio file using Vosk.
        """
        if not self.model: 
            return ""
            
        try:
            wf = wave.open(audio_file, "rb")
        except FileNotFoundError:
            return ""
            
        if wf.getnchannels() != 1 or wf.getsampwidth() != 2 or wf.getcomptype() != "NONE":
            # Vosk requires Mono PCM 16-bit
            # Our recorder produces exactly this, so usually fine.
            pass

        # Create Recognizer
        # If we have a grammar, use it!
        if self.grammar:
            rec = KaldiRecognizer(self.model, wf.getframerate(), self.grammar)
        else:
            rec = KaldiRecognizer(self.model, wf.getframerate())

        rec.SetWords(True)

        # Process Audio
        while True:
            data = wf.readframes(4000)
            if len(data) == 0:
                break
            rec.AcceptWaveform(data)

        # Get Result
        res = json.loads(rec.FinalResult())
        text = res.get('text', '')
        
        return text
