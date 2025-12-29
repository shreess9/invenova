import os
import zipfile
import urllib.request
import shutil

MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
MODEL_ZIP = "vosk-model-small-en-us-0.15.zip"
MODEL_DIR = "model" # Vosk expects a folder simply named 'model' or we point to it

def download_and_extract():
    if os.path.exists(MODEL_DIR):
        print(f"Vosk model already exists in '{MODEL_DIR}'. Skipping.")
        return

    print(f"Downloading Vosk model from {MODEL_URL}...")
    try:
        urllib.request.urlretrieve(MODEL_URL, MODEL_ZIP)
        print("Download complete. Extracting...")
        
        with zipfile.ZipFile(MODEL_ZIP, 'r') as zip_ref:
            zip_ref.extractall(".")
            
        # Rename extracted folder to 'model'
        extracted_name = "vosk-model-small-en-us-0.15"
        if os.path.exists(extracted_name):
            os.rename(extracted_name, MODEL_DIR)
            print(f"Model extracted and renamed to '{MODEL_DIR}'.")
        
        # Cleanup
        os.remove(MODEL_ZIP)
        print("Setup complete.")
        
    except Exception as e:
        print(f"Failed to download/extract model: {e}")

if __name__ == "__main__":
    download_and_extract()
