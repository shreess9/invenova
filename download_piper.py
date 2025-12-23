import os
import requests
import zipfile
import tarfile
import io
import platform

PIPER_URL_WIN = "https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_windows_amd64.zip"
# Pi 4 is aarch64
PIPER_URL_LINUX_ARM64 = "https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_aarch64.tar.gz"

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
    
    # Check for executable (OS Dependent)
    system = platform.system()
    machine = platform.machine()
    
    exe_name = "piper.exe" if system == "Windows" else "piper"
    exe_path = f"piper/piper/{exe_name}" if system == "Windows" else "piper/piper/piper" 
    # Note: Structure might differ slightly between zip and tar.gz, checking extraction...
    # Windows zip extracts to 'piper/', linux tar might also. 
    # Let's verify commonly.
    
    if not os.path.exists(exe_path):
        print(f"Downloading Piper binary for {system} ({machine})...")
        
        url = ""
        is_zip = False
        
        if system == "Windows":
            url = PIPER_URL_WIN
            is_zip = True
        elif system == "Linux" and ("aarch64" in machine or "arm64" in machine):
            url = PIPER_URL_LINUX_ARM64
            is_zip = False # tar.gz
        else:
            print(f"WARNING: No automatic download for {system} {machine}. Please download Piper manually.")
            return

        print(f"Fetching from: {url}")
        r = requests.get(url)
        if r.status_code == 200:
            if is_zip:
                z = zipfile.ZipFile(io.BytesIO(r.content))
                z.extractall("piper")
            else:
                # tar.gz
                z = tarfile.open(fileobj=io.BytesIO(r.content), mode="r:gz")
                z.extractall("piper")
            
            print("Extracted Piper.")
            
            # Additional Linux setup: make executable chmod +x
            if system == "Linux":
                full_exe = os.path.join(os.getcwd(), "piper", "piper", "piper")
                if os.path.exists(full_exe):
                    os.chmod(full_exe, 0o755)
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
