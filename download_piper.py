import os
import requests
import zipfile
import io

PIPER_URL_WIN = "https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_windows_amd64.zip"
VOICE_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/amy/medium/en_US-amy-medium.onnx"
VOICE_CONFIG_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/amy/medium/en_US-amy-medium.onnx.json"

def download_file(url, target_path):
    print(f"Downloading {url}...")
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        with open(target_path, 'wb') as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)
        print(f"Saved to {target_path}")
    else:
        print(f"Failed to download {url}")

def setup_piper():
    if not os.path.exists("piper"):
        os.makedirs("piper")
    
    # Check for executable
    if not os.path.exists("piper/piper/piper.exe"):
        print("Downloading Piper binary...")
        r = requests.get(PIPER_URL_WIN)
        if r.status_code == 200:
            z = zipfile.ZipFile(io.BytesIO(r.content))
            z.extractall("piper")
            print("Extracted Piper.")
        else:
            print("Error downloading Piper binary.")
            return

    # Check for Voice Model
    if not os.path.exists("piper/en_US-amy-medium.onnx"):
        print("Downloading Voice Model (Amy)...")
        download_file(VOICE_URL, "piper/en_US-amy-medium.onnx")
        download_file(VOICE_CONFIG_URL, "piper/en_US-amy-medium.onnx.json")

if __name__ == "__main__":
    setup_piper()
