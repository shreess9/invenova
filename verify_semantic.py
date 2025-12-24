from nlp_engine import IntentParser
from mini_assistant import semantic_search_inventory
import db_manager
import config

# Mock setup
print("Init DB...")
db_manager.init_db()
print("Loading NLP...")
nlp = IntentParser()

print("Building Index...")
items = db_manager.get_all_item_names()
embs = nlp.encode_text(items)
# Manually set the global in mini_assistant because we imported it
import mini_assistant
mini_assistant.SEMANTIC_INDEX = (items, embs)

queries = ["Servo Motor", "I want to solder something", "10 RPM"]

print("\n--- Semantic Search Tests ---")
for q in queries:
    print(f"\nQuery: '{q}'")
    # Test with default threshold 0.45
    results = semantic_search_inventory(q, nlp, threshold=0.35) # Lower threshold to test
    if not results:
        print("No matches.")
    else:
        for name, score in results:
            print(f"  {score:.4f} | {name}")
