import config
import os
import torch
import subprocess
import soundfile as sf
import sounddevice as sd

class Speaker:
    def __init__(self):
        self.engine_type = config.TTS_ENGINE
        print(f"Loading TTS Engine: {self.engine_type}...")
        
        if self.engine_type == "fast":
            try:
                import pyttsx3
                self.engine = pyttsx3.init()
                # Configure pyttsx3
                voices = self.engine.getProperty('voices')
                if len(voices) > 1:
                    self.engine.setProperty('voice', voices[1].id)
            except Exception as e:
                print(f"Fast TTS Init Failed: {e}. Switching to Silent Mode.")
                self.engine = None

        elif self.engine_type == "piper":
            print(f"Initializing Piper TTS (Binary: {config.PIPER_BINARY})...")
            if not os.path.exists(config.PIPER_BINARY):
                print("ERROR: Piper binary not found! Please run setup_pi_env.bat")
                self.engine_type = "fast" # Fallback
            else:
                self.piper_path = config.PIPER_BINARY
                self.piper_model = config.PIPER_MODEL

        else:
            # XTTS (High Quality)
            from TTS.api import TTS
            device = "cuda" if torch.cuda.is_available() else "cpu"
            self.tts = TTS(model_name=config.TTS_MODEL_NAME).to(device)

        # Detect Audio Device Once at Startup
        self.target_device_id = None
        if hasattr(config, 'AUDIO_OUTPUT_KEYWORD') and config.AUDIO_OUTPUT_KEYWORD:
             try:
                 print(f"Searching for Audio Output: {config.AUDIO_OUTPUT_KEYWORD}...")
                 devices = sd.query_devices()
                 for i, dev in enumerate(devices):
                     if dev['max_output_channels'] > 0:
                         if config.AUDIO_OUTPUT_KEYWORD.lower() in dev['name'].lower():
                             self.target_device_id = i
                             print(f"TTS Audio Output Set: {dev['name']} (Index {i})")
                             break
             except Exception as e:
                 print(f"Audio Device Detection Failed: {e}")

        print("TTS Engine Ready.")

    def speak(self, text, output_file="response.wav"):
        """
        Generates speech.
        """
        if not text:
            return
            
        if self.engine_type == "fast":
            if self.engine:
                try:
                    self.engine.say(text)
                    self.engine.runAndWait()
                except Exception as e:
                    print(f"pyttsx3 Error: {e}")
        
        elif self.engine_type == "piper":
            try:
                # OPTIMIZED: Streaming Playback (Pipe -> Play)
                # Command: echo text | piper --output_raw | aplay -r 22050 -f S16_LE -t raw -
                
                # Command construction
                piper_cmd = [
                    self.piper_path,
                    "--model", self.piper_model,
                    "--output_raw" 
                ]
                
                # Check OS for Player
                if os.name == 'nt':
                    # Windows: We still need a temporary file or complex streaming not easily done with std libs.
                    # Fallback to file mode on Windows for safety.
                    self.speak_to_file(text, output_file)
                    return
                else:
                    # Linux/Pi: Use aplay for instant streaming
                    # Piper outputs 22050Hz (default for Amy) or 16000Hz depending on model.
                    # Amy is usually 22050Hz.
                    # Adjust format: S16_LE is standard.
                    
                    player_cmd = ["aplay", "-r", "22050", "-f", "S16_LE", "-t", "raw", "-"]
                    
                    if hasattr(config, 'AUDIO_CARD_INDEX') and config.AUDIO_CARD_INDEX is not None:
                         # Use specific card
                         player_cmd = ["aplay", "-D", f"plughw:{config.AUDIO_CARD_INDEX},0", "-r", "22050", "-f", "S16_LE", "-t", "raw", "-"]
                    
                    # Create Pipeline
                    # echo "text" -> p1 (piper) -> p2 (aplay)
                    
                    p1 = subprocess.Popen(piper_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    p2 = subprocess.Popen(player_cmd, stdin=p1.stdout, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                    
                    # Close p1 output in parent so it can flow to p2
                    p1.stdout.close()
                    
                    # Write text to p1
                    p1.communicate(input=text.encode('utf-8'))
                    p2.wait() # Wait for playback to finish
                    
            except Exception as e:
                print(f"Piper Streaming Error: {e}. Fallback to file.")
                self.speak_to_file(text, output_file)

    def speak_to_file(self, text, output_file):
        # Legacy File-Based Logic (Original Code)
        try:
             cmd = [
                self.piper_path,
                "--model", self.piper_model,
                "--output_file", output_file
             ]
             process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
             stdout, stderr = process.communicate(input=text.encode('utf-8'))
             if process.returncode == 0:
                 self.play_audio(output_file)
             else:
                 print(f"Piper Error: {stderr.decode()}")
        except Exception as e:
            print(f"TTS File Error: {e}")

        else:
            # XTTS
            try:
                self.tts.tts_to_file(
                    text=text, 
                    file_path=output_file,
                    speaker=config.SPEAKER_IDX,
                    language=config.LANGUAGE_IDX
                )
                self.play_audio(output_file)
            except Exception as e:
                print(f"XTTS Error: {e}")

    def play_audio(self, file_path):
        try:
            # Cross-platform storage playback using sounddevice (PortAudio)
            # Uses cached target_device_id from __init__
            data, fs = sf.read(file_path)
            sd.play(data, fs, device=self.target_device_id)
            sd.wait()
            
        except Exception as e:
            # print(f"DEBUG: SoundDevice Playback failed: {e}")
            # Fallback for Windows
            if os.name == 'nt':
                try:
                    import winsound
                    winsound.PlaySound(file_path, winsound.SND_FILENAME)
                except ImportError:
                    pass
            # Fallback for Linux (Raspberry Pi)
            else:
                try:
                    # Try specifying card if configured
                    cmd = ["aplay", file_path]
                    
                    if hasattr(config, 'AUDIO_CARD_INDEX') and config.AUDIO_CARD_INDEX is not None:
                        # Explicit Card Override (e.g. 2 -> plughw:2,0)
                        card_dev = f"plughw:{config.AUDIO_CARD_INDEX},0"
                        cmd = ["aplay", "-D", card_dev, file_path]
                        # print(f"DEBUG: aplay using {card_dev}")
                    
                    subprocess.run(cmd, check=False)
                except Exception as ex:
                    print(f"Playback error (aplay): {ex}")
