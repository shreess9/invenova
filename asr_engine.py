import os
import json
import time
import sys
import wave
import re
import config
import sounddevice as sd
import numpy as np

try:
    import RPi.GPIO as GPIO
except ImportError:
    GPIO = None

# Suppress ALSA/Vosk logs
os.environ['VOSK_LOG_LEVEL'] = '-1' # Silences Info

try:
    from vosk import Model, KaldiRecognizer, SetLogLevel
    SetLogLevel(-1)
except ImportError:
    print("Vosk not installed. Run: pip install vosk")

try:
    from num2words import num2words
except ImportError:
    print("Num2Words not installed. Run: pip install num2words")
    # Fallback to avoid crash, but nums will be limited
    def num2words(num, lang='en'): return str(num)

# Context Manager to suppress C-level Stderr (Vosk/ALSA logs)
class ignore_stderr(object):
    def __init__(self):
        self.null_fds = [os.open(os.devnull, os.O_RDWR) for x in range(2)]
        self.save_fds = [os.dup(2)]

    def __enter__(self):
        os.dup2(self.null_fds[1], 2)

    def __exit__(self, *_):
        os.dup2(self.save_fds[0], 2)
        os.close(self.null_fds[1])
        os.close(self.save_fds[0])

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
        
        # Initialize container outside to prevent NameError if loop fails
        audio_data = []

        # Try 3 times to get a lock on the microphone
        for attempt in range(1, 4):
            try:
                # 1. Negotiate Sample Rate (Per Attempt)
                final_rate = samplerate
                rates_to_try = [16000, 48000, 44100, 32000, 8000]
                found_rate = False
                
                # Check what works
                for r in rates_to_try:
                    try:
                         # Just query, don't open yet
                        sd.check_input_settings(device=None, channels=1, dtype=resolution, samplerate=r)
                        final_rate = r
                        found_rate = True
                        break
                    except:
                        continue
                
                if not found_rate:
                     try:
                         dev = sd.query_devices(kind='input')
                         final_rate = int(dev['default_samplerate'])
                     except:
                         pass

                print(f"DEBUG: Recording started at {final_rate}Hz (Attempt {attempt})")
                
                # Reset data for this attempt
                audio_data = []
                
                # Define Callback Closure
                def callback(indata, frames, time, status):
                    if status: pass
                    audio_data.append(indata.copy())

                # Open Stream at NEGOTIATED rate
                # We put this in a nested try/except to catch stream errors specifically
                try:
                    with sd.InputStream(samplerate=final_rate, channels=channels, dtype=resolution, callback=callback):
                        if duration:
                            print(f"Recording for {duration} seconds...")
                            sd.sleep(int(duration * 1000))
                        else:
                            print("Recording... Press ENTER (or Button) to stop.")
                            start_time = time.time()
                            min_duration = 0.5 
                            
                            while True:
                                sd.sleep(50)
                                elapsed = time.time() - start_time
                                should_stop = False
                                
                                # GPIO Button Stop
                                if config.GPIO_INTERACT_PIN and GPIO.input(config.GPIO_INTERACT_PIN) == GPIO.LOW:
                                    # Ignore initial bounce/hold
                                    if elapsed < min_duration:
                                        pass 
                                    else:
                                        should_stop = True
                                
                                # Keyboard Stop (Disabled in Service Mode)
                                if sys.stdin.isatty():
                                    if os.name == 'nt':
                                        import msvcrt
                                        if msvcrt.kbhit():
                                            if msvcrt.getch() == b'\r': should_stop = True
                                    else:
                                        import select
                                        if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
                                            sys.stdin.readline()
                                            should_stop = True
                                if should_stop:
                                    print("Stop signal received.")
                                    break
                    
                    # If we exit 'with', stream is closed.
                    if len(audio_data) > 0:
                        break # Success
                        
                except Exception as stream_err:
                     print(f"Stream Error (Attempt {attempt}): {stream_err}")
                     raise stream_err # Re-raise to trigger retry logic

            except Exception as e:
                print(f"Microphone init failed (Attempt {attempt}/3): {e}")
                time.sleep(0.5)
        
        # Save File Post-Recording
        if not audio_data:
            print("Error: No audio data captured after retries.")
            return None
            
        audio_concatenated = np.concatenate(audio_data, axis=0)
        
        # Save as WAV for Vosk Processing
        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(2) # 16-bit
            wf.setframerate(final_rate) # Use ACTUAL rate
            wf.writeframes(audio_concatenated.tobytes())
            
        return filename


try:
    import speech_recognition as sr
    HAS_ONLINE = True
except ImportError:
    HAS_ONLINE = False
    print("Warning: SpeechRecognition not installed. Online ASR disabled.")

class ASREngine:
    def __init__(self, model_path="model", db_manager=None):
        self.model_path = model_path
        self.grammar = None
        self.recognizer = None
        
        if config.USE_ONLINE_ASR and HAS_ONLINE:
             self.recognizer = sr.Recognizer()
             print("Online ASR (Google Speech) Enabled.")
        
        print("Loading Vosk Model (Offline Backup)...")
        if not os.path.exists(model_path):
            print(f"FATAL: Vosk model not found at '{model_path}'. Run download_vosk.py")
            self.model = None
        else:
            self.model = Model(model_path)
            print("Vosk Model Loaded.")

        # Build Grammar if DB provided
        if db_manager:
            self.build_grammar(db_manager)

    def transcribe_online(self, wav_file):
        """
        Attempts to transcribe using Google Speech Recognition.
        Returns: text (str) or None (if failed/no internet)
        """
        if not self.recognizer: return None
        
        try:
            with sr.AudioFile(wav_file) as source:
                audio = self.recognizer.record(source)
            
            # Recognize
            start_rec = time.time()
            text = self.recognizer.recognize_google(audio)
            print(f"Online ASR Result ({time.time()-start_rec:.2f}s): '{text}'")
            return text
        except sr.UnknownValueError:
            print("Online ASR: Could not understand audio (Silence/Unclear).")
            return None # Return None to allow Vosk to try? Or "" to stop? User said "Only if internet isn't working".
            # If Google can't hear it, Vosk might just guess. But let's try Vosk as a "Second Opinion".
            # return None 
            return "" # Safe choice: If online fails to understand, it's likely noise.
        except sr.RequestError as e:
            print(f"Online ASR Connection Error: {e}")
            return None # Fallback to Offline
        except Exception as e:
            print(f"Online ASR Unexpected Error: {e}")
            return None

    def transcribe(self, wav_file):
        """
        Transcribes the given WAV file.
        Strategy:
        1. Try Online (if enabled)
        2. If fails, use Vosk (Offline)
        """
        start_t = time.time()
        
        # 1. Online Attempt
        if config.USE_ONLINE_ASR and self.recognizer:
            text = self.transcribe_online(wav_file)
            if text is not None:
                 # Success!
                 return text.lower()
            print("Fallback to Vosk Offline...")
        
        # 2. Vosk Offline
        if not self.model: return ""
        
        wf = wave.open(wav_file, "rb")

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
            
            # 2. Number Words (Vosk Small model doesn't know digits '1', '2'...)
            # We map 0-100 to words.
            digit_map = {
                "0": "zero", "1": "one", "2": "two", "3": "three", "4": "four", "5": "five",
                "6": "six", "7": "seven", "8": "eight", "9": "nine", "10": "ten",
                "11": "eleven", "12": "twelve", "13": "thirteen", "14": "fourteen", "15": "fifteen",
                "16": "sixteen", "17": "seventeen", "18": "eighteen", "19": "nineteen", "20": "twenty",
                "30": "thirty", "40": "forty", "50": "fifty", "60": "sixty", "70": "seventy", "80": "eighty", "90": "ninety",
                "100": "hundred", "1000": "thousand"
            }
            # Add simple range 0-9 as strings just in case, but rely on words
            # Actually, let's just add the words.
            numbers = list(digit_map.values())
            
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
                    # 1. Advanced Tokenization: Split "sim800l" -> "sim 800 l"
                    # Vosk often knows "sim" and "800" but not "sim800l"
                    sub_tokens = re.split(r'(\d+)', p)
                    for t in sub_tokens:
                        if not t.strip(): continue
                        
                        # Add literal token (e.g. "sim", "800")
                        unique_words.add(t)
                        
                        # 2. Number Expansion (Critical for "12000" -> "twelve thousand")
                        # If it's a digit string, we MUST tell Vosk how to say it.
                        if t.isdigit():
                             try:
                                 # Convert "12000" -> "twelve thousand"
                                 word_form = num2words(int(t), lang='en')
                                 unique_words.update(word_form.replace("-", " ").split())
                                 
                                 # Convert "12000" -> "one two zero zero zero" (Digit-wise)
                                 # Useful for model numbers "800" -> "eight zero zero"
                                 digits_as_words = [num2words(int(ch)) for ch in t]
                                 unique_words.update(digits_as_words)
                             except:
                                 pass
                    
                    # 3. Check for units (e.g., "12v" -> "12" + "v" -> "volt")
                    # Naive split: if ends with unit
                    for unit, expansions in unit_map.items():
                        if p.endswith(unit) and len(p) > len(unit) and p[:-len(unit)].isdigit():
                             # Case "12v"
                             num = p[:-len(unit)]
                             unique_words.add(num)
                             # Expand Number
                             try:
                                 word_form = num2words(int(num), lang='en')
                                 unique_words.update(word_form.replace("-", " ").split())
                             except: pass
                                 
                             # Add Unit
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
        # Silence Stderr to hide "Missing in vocabulary" warnings
        with ignore_stderr():
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
