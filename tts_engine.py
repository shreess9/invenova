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
                # Piper expects input via stdin
                # Command: echo "text" | piper.exe --model model.onnx --output_file output.wav
                
                cmd = [
                    self.piper_path,
                    "--model", self.piper_model,
                    "--output_file", output_file
                ]
                
                # Run subprocess
                process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
                stdout, stderr = process.communicate(input=text.encode('utf-8'))
                
                if process.returncode != 0:
                     print(f"Piper Error: {stderr.decode()}")
                else:
                     self.play_audio(output_file)

            except Exception as e:
                print(f"Piper Execution Fail: {e}")

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
        import winsound
        try:
            winsound.PlaySound(file_path, winsound.SND_FILENAME)
        except Exception as e:
            print(f"Playback error: {e}")
