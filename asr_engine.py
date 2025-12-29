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
        
        # Explicit Fallback List (Most common hardware rates)
        # 16k is preferred for Vosk, but many cheap mics only support 44.1/48k
        rates_to_try = [16000, 48000, 44100, 32000, 8000]
        
        found_rate = False
        for r in rates_to_try:
            try:
                sd.check_input_settings(device=None, channels=1, dtype=resolution, samplerate=r)
                final_rate = r
                found_rate = True
                print(f"DEBUG: Microphone accepted {r}Hz")
                break
            except Exception:
                continue
        
        if not found_rate:
             # Last resort: Query Default
             try:
                 dev = sd.query_devices(kind='input')
                 final_rate = int(dev['default_samplerate'])
                 print(f"DEBUG: Fallback to device default: {final_rate}Hz")
             except:
                 print("ERROR: Could not negotiate sample rate.")
                 return None

        print(f"DEBUG: Recording started at {final_rate}Hz")
        
        audio_data = []

        # ... (Callback unchanged)

    # -------------------------------------------------------------

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
            
            # 3. Inventory Items with Unit Expansion
            # "4v" -> "4", "v", "volt", "volts"
            items = db_manager.get_all_item_names() # Returns list of strings
            
            unique_words = set()
            
            # Unit Mappings
            unit_map = {
                "v": ["volt", "volts"],
                "a": ["amp", "amps", "amperes"],
                "ah": ["amp hour", "amp hours"],
                "mah": ["milliamp", "milliamps"],
                "w": ["watt", "watts"],
                "kw": ["kilowatt", "kilowatts"],
                "ohm": ["ohms", "resistance"],
                "k": ["kilo", "thousand"],
                "uf": ["microfarad"],
                "nf": ["nanofarad"],
                "pf": ["picofarad"],
                "hz": ["hertz"],
                "mhz": ["megahertz"],
                "ghz": ["gigahertz"],
                "mm": ["millimeter", "millimeters"],
                "cm": ["centimeter", "centimeters"],
                "m": ["meter", "meters"],
                "rpm": ["rotation", "speed", "rounds"],
                "dc": ["direct current"],
                "ac": ["alternating current"]
            }

            # Add base commands
            for c in commands:
                unique_words.update(c.split())
                
            # Add numbers
            unique_words.update(numbers)
            
            # Add item tokens
            for item in items:
                # Clean: "L293D (Motor Driver)" -> "l293d", "motor", "driver"
                # Remove special chars
                clean = item.lower().replace("(", " ").replace(")", " ").replace("-", " ").replace("/", " ")
                parts = clean.split()
                
                for p in parts:
                    unique_words.add(p)
                    
                    # Check for units (e.g., "12v" -> "12" + "v" -> "volt")
                    # Naive split: if ends with unit
                    for unit, expansions in unit_map.items():
                        if p.endswith(unit) and len(p) > len(unit) and p[:-len(unit)].isdigit():
                             # Case "12v"
                             num = p[:-len(unit)]
                             unique_words.add(num)
                             unique_words.add(unit)
                             unique_words.update(expansions)
                        elif p == unit:
                             unique_words.update(expansions)
            
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
