import os
import requests
import sys

# Llama 3.2 1B Instruct (SOTA for Edge) from Bartowski (Reliable quantizer)
MODEL_URL = "https://huggingface.co/bartowski/Llama-3.2-1B-Instruct-GGUF/resolve/main/Llama-3.2-1B-Instruct-Q4_K_M.gguf"
MODEL_FILENAME = "Llama-3.2-1B-Instruct-Q4_K_M.gguf"
MODELS_DIR = "models"

def download_file(url, target_path):
    print(f"Downloading {url}...")
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        total_size = int(response.headers.get('content-length', 0))
        done = 0
        with open(target_path, 'wb') as f:
            for chunk in response.iter_content(1024*1024): # 1MB chunks
                if chunk:
                    f.write(chunk)
                    done += len(chunk)
                    if total_size > 0:
                        sys.stdout.write(f"\rProgress: {int(done/total_size*100)}%")
                        sys.stdout.flush()
        print(f"\nSaved to {target_path}")
    else:
        print(f"Failed to download {url}")

def setup_llm():
    if not os.path.exists(MODELS_DIR):
        os.makedirs(MODELS_DIR)
    
    target_path = os.path.join(MODELS_DIR, MODEL_FILENAME)
    
    if not os.path.exists(target_path):
        print(f"Downloading TinyLlama (Lite LLM for Pi)...")
        download_file(MODEL_URL, target_path)
    else:
        print("Lite LLM already exists.")

if __name__ == "__main__":
    setup_llm()
