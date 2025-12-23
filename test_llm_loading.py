
import sys
import os

# Add current dir to path
sys.path.append(os.getcwd())

import config
from llm_engine import ChatEngine

def test_load():
    print(f"Testing LLM Load from: {config.LLM_MODEL_PATH}")
    if not os.path.exists(config.LLM_MODEL_PATH):
        print("Model file not found yet.")
        return False
    
    try:
        engine = ChatEngine()
        if engine.enabled:
            print("SUCCESS: Chat Engine Loaded Llama 3.2 1B!")
            # Quick Inference Test
            print("Running Inference Test: 'Hello'")
            reply = engine.generate_reply("Hello")
            print(f"Reply: {reply}")
            return True
        else:
            print("FAILED: Chat Engine disabled (ImportError?)")
            return False
    except Exception as e:
        print(f"FAILED with Error: {e}")
        return False

if __name__ == "__main__":
    test_load()
