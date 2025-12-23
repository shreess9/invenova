import os
import sys
# Fix DLLs immediately
import dll_fix 
import time
import argparse
import site
import warnings

import re
from difflib import SequenceMatcher

try:
    import winsound
    import msvcrt # Windows Console I/O
except ImportError:
    winsound = None
    msvcrt = None
    # Linux Input Handling
    import sys, tty, termios
    def getch_unix():
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch.encode('utf-8')

# Suppress HuggingFace/FutureWarnings
warnings.filterwarnings("ignore", category=FutureWarning)
# Specific suppression for the pytree warning if generic isn't enough, but generic should work if placed early.
warnings.filterwarnings("ignore", module="transformers")

# Local Modules
import config
import db_manager
from nlp_engine import IntentParser
from asr_engine import VoiceListener
from tts_engine import Speaker
from llm_engine import ChatEngine

# Helper to extract specs (RPM, Voltage, etc.) from a list of names
def extract_specs(names):
    # Regex for distinct specifications (Voltage, Ampere, Wattage, RPM, Dimensions)
    # Handles: "12V", "7 AH", "1.3 AH", "1point3 AH", "1000 RPM"
    # Note: \s* allows for optional space between number and unit
    # (?:[.,]|\s*point\s*)? allows for decimals like 1.5, 1,5, or 1 point 5
    spec_pattern = r'\b(\d+(?:[.,]|\s*point\s*)?\d*)\s*(RPM|KV|V|W|A|AH|mAh|mm|cm|M|KG|G|OHM|OHMS)\b'
    
    specs = set()
    for name in names:
        if not name: continue
        # Normalize simple variations
        normalized = name.replace("-", " ").replace("_", " ").upper()
        
        matches = re.findall(spec_pattern, normalized, re.IGNORECASE)
        for val, unit in matches:
            # Clean up value (remove 'point' -> '.')
            clean_val = val.lower().replace("point", ".").replace(",", ".").replace(" ", "")
            # Return "7 AH", "1.3 AH"
            specs.add(f"{clean_val} {unit.upper()}")
            
    return sorted(list(specs))



def play_emergency_sound():
    if winsound:
        try:
            # Beep pattern: High Low High Low
            for _ in range(3):
                winsound.Beep(2500, 300) 
                winsound.Beep(2000, 300)
        except:
            pass
    else:
        # Linux simple beep (or silence)
        print("\a") # ASCII Bell

# Unit Pronunciation Mapping (Dynamic)
UNIT_PRONUNCIATIONS = {
    "V": "Volt",
    "KV": "Kilo Volt",
    "W": "Watt",
    "KW": "Kilo Watt",
    "RPM": "R P M",
    "A": "Ampere",
    "MA": "Milli Amp",
    "MAH": "Milli Amp Hour",
    "MM": "Millimeter",
    "CM": "Centimeter",
    "M": "Meter",
    "KG": "Kilogram",
    "G": "Gram",
    "AH": "Ampere Hour",
    "OHM": "Ohm",
    "OHMS": "Ohms"
}

PHONETIC_LETTERS = {
    'A': 'Ehh', 'B': 'Bee', 'C': 'See', 'D': 'Dee', 'E': 'Ee', 'F': 'Eff',
    'G': 'Gee', 'H': 'Aitch', 'I': 'Eye', 'J': 'Jay', 'K': 'Kay', 'L': 'Ell',
    'M': 'Emm', 'N': 'Enn', 'O': 'Oh', 'P': 'Pee', 'Q': 'Kyoo', 'R': 'Arr',
    'S': 'Ess', 'T': 'Tee', 'U': 'Yoo', 'V': 'Vee', 'W': 'Double U', 'X': 'Ex',
    'Y': 'Why', 'Z': 'Zee'
}

FORCE_SPELL_ACRONYMS = {
    "IR", "DHT", "PIR", "LCD", "LED", "XLR", "PCB", "IC", "USB", "SSD", "HDD", "PWM", "CNC", "DIY"
}

def expand_units_for_tts(text):
    """
    Expands "1000 KV" -> "1000 Kilo Volt" based on UNIT_PRONUNCIATIONS.
    Uses regex to safely identify number+unit pairs.
    """
    def replace_unit(match):
        val = match.group(1)
        unit = match.group(2).upper()
        # Check specific mapping
        if unit in UNIT_PRONUNCIATIONS:
            return f"{val} {UNIT_PRONUNCIATIONS[unit]}"
        return match.group(0) # Return original if not in map
    
    # Regex for "123 UNIT" or "12.5 UNIT" or "1point3 UNIT" (Space optional e.g. 12V)
    # Matches integer or float or point: \d+(?:[.,]|\s*point\s*)?\d*
    return re.sub(r'\b(\d+(?:[.,]|\s*point\s*)?\d*)\s*([A-Za-z]+)\b', replace_unit, text, flags=re.IGNORECASE)

def clean_item_name_for_tts(text):
    """
    Cleans item definitions from DB for natural reading.
    "Wheel 13point5 cm Dia" -> "Wheel 13.5 Centimeter Diameter"
    "PUD81I" -> "P U D 8 1 I" (Spells out complex codes)
    """
    if not text: return ""
    
    # 0. "cross" -> "x" (Fix DB artifact: Procrossimity -> Proximity)
    text = re.sub(r'cross', 'x', text, flags=re.IGNORECASE)

    # 1. "13point5" -> "13.5" (Standardize for regexes)
    text = re.sub(r'(\d+)\s*point\s*(\d+)', r'\1.\2', text, flags=re.IGNORECASE)
    
    # 2. "Dia" -> "Diameter"
    text = re.sub(r'\bDia\b', 'Diameter', text, flags=re.IGNORECASE)
    
    # "NI" -> "National Instruments"
    text = re.sub(r'\bNI\b', 'National Instruments', text, flags=re.IGNORECASE)

    # "Li-ion" -> "Lithium Ion" (Handle before dash replacement)
    text = re.sub(r'\bLi-ion\b', 'Lithium Ion', text, flags=re.IGNORECASE)
    # "Li" -> "Lithium"
    text = re.sub(r'\bLi\b', 'Lithium', text, flags=re.IGNORECASE)
    
    # "dash" -> " to " (Case Insensitive)
    text = re.sub(r'dash', ' to ', text, flags=re.IGNORECASE)
    # "-" -> " to "
    text = text.replace("-", " to ").replace("_", " ")

    # 3. Handle Model Codes (Mixed Alpha/Numeric)
    # Examples: "PUD81I" (Space out), "25W" (Keep as unit)
    words = text.split()
    cleaned_words = []
    
    for w in words:
        # Check if mixed (digits and letters)
        if re.search(r'\d', w) and re.search(r'[a-zA-Z]', w):
             # Check if it is a Unit (Number + UnitSuffix) e.g. "25W", "13.5cm"
             match_unit = re.match(r'^(\d+(?:\.\d+)?)([a-zA-Z]+)$', w)
             is_unit = False
             if match_unit:
                 val, suffix = match_unit.groups()
                 if suffix.upper() in UNIT_PRONUNCIATIONS:
                     is_unit = True
                     # Expand joined unit "25W" -> "25 Watt"
                     w = f"{val} {UNIT_PRONUNCIATIONS[suffix.upper()]}"
             
             if not is_unit:
                 # It is a model code like PUD81I. Use phonetic spelling for letters, keep numbers natural.
                 # "A2210" -> "A" "2210" -> "A Two Thousand Two Hundred Ten"
                 # "PUD81I" -> "P U D 81 I" -> "Pee Yoo Dee Eighty One Eye"
                 
                 # Split into blocks of Digits vs Letters
                 chunks = re.findall(r'(\d+|[a-zA-Z]+)', w)
                 final_parts = []
                 for chunk in chunks:
                     if chunk.isdigit():
                         final_parts.append(chunk) # Keep number intact for natural reading
                     else:
                         # Spell out letters
                         for c in chunk:
                             if c.upper() in PHONETIC_LETTERS:
                                 final_parts.append(PHONETIC_LETTERS[c.upper()])
                             else:
                                 final_parts.append(c)
                 
                 w = " ".join(final_parts)
        
        cleaned_words.append(w)
        
    text = " ".join(cleaned_words)
    
    # 4. Expand Units
    text = expand_units_for_tts(text)
    
    return text

# Helper to Clean Text for TTS (Fix pronunciation)
def clean_for_tts(text):
    if not text: return ""
    
    # 0. Location Expansion Rules
    
    # Rule 1: Shooter Racks (Starts with S: SD5, SH1, etc)
    # Example: "SD5 #3" -> "Shooter Rack Ess Dee 5, Box 3"
    match = re.search(r'\b(S[A-Z]*\d+)\s*#(\d+)\b', text)
    if match:
        code, box = match.groups()
        # Phonetic expansion using global map
        chars = []
        for c in code:
            if c.upper() in PHONETIC_LETTERS:
                chars.append(PHONETIC_LETTERS[c.upper()])
            else:
                chars.append(c)
        
        spaced_code = " ".join(chars)
        return text.replace(match.group(0), f"Shooter Rack {spaced_code}, Box {box}")

    # Example: "SI4" -> "Shooter Rack Ess Eye 4"
    match = re.search(r'\b(S[A-Z]*\d+)\b', text)
    if match:
        code = match.group(1)
        chars = []
        for c in code:
            if c.upper() in PHONETIC_LETTERS:
                chars.append(PHONETIC_LETTERS[c.upper()])
            else:
                chars.append(c)
            
        spaced_code = " ".join(chars)
        return text.replace(match.group(0), f"Shooter Rack {spaced_code}")

    # Rule 2: Red Cubicles (A-G prefix)
    # Example: "A5 #3" -> "Red Cubicle A, Cabinet 5, Box 3"
    match = re.search(r'\b([A-G])(\d+)\s*#(\d+)\b', text)
    if match:
        letter, cabinet, box = match.groups()
        return text.replace(match.group(0), f"Red Cubicle {letter}, Cabinet {cabinet}, Box {box}")
        
    # Example: "A8" -> "Red Cubicle A, Cabinet 8"
    match = re.search(r'\b([A-G])(\d+)\b', text)
    if match:
        letter, cabinet = match.groups()
        return text.replace(match.group(0), f"Red Cubicle {letter}, Cabinet {cabinet}")
    
    # 1. Handle "A5", "D8" -> "A 5", "D 8"
    # This prevents "D8" being read as "dit" or "A5" as "a five" (article)
    text = re.sub(r'([A-Za-z])(\d+)', r'\1 \2', text)
    
    # 2. Handle "#" -> "number"
    text = text.replace("#", " number ")
    
    # 3. Handle specific mispronunciations if needed
    # Force "A" to be "Ay" if it's a single letter location? 
    # Usually "A 5" is fine, but let's see. 
    
    return text

# ------------------ DLL Fix for Windows ------------------
def add_nvidia_paths():
    try:
        # Check standard site-packages locations
        site_packages = site.getsitepackages()
        for sp in site_packages:
            # Look for nvidia/cudnn/bin and nvidia/cublas/bin
            nvidia_path = os.path.join(sp, "nvidia")
            if os.path.isdir(nvidia_path):
                for component in ["cudnn", "cublas", "cudart"]:
                   bin_path = os.path.join(nvidia_path, component, "bin") # usually 'bin' on windows
                   if os.path.isdir(bin_path):
                       os.environ["PATH"] = bin_path + os.pathsep + os.environ["PATH"]
                       try:
                           if hasattr(os, 'add_dll_directory'):
                               os.add_dll_directory(bin_path)
                       except:
                           pass
    except Exception as e:
        print(f"Warning: Could not auto-add nvidia paths: {e}")

if os.name == 'nt':
    add_nvidia_paths()
# ---------------------------------------------------------

import config
from asr_engine import VoiceListener, AudioRecorder
from nlp_engine import IntentParser
from tts_engine import Speaker
import db_manager

# ------------------ SEARCH HELPERS --------------------
def clean_entity_name(item_name):
    """
    Removes linguistic artifacts that NLP might capture as part of the item name.
    e.g. "I need AC-DC" -> "i acdashdc" (extracted) -> "acdashdc" (cleaned).
    e.g. "Find me a servo" -> "find me a servo" -> "servo"
    """
    if not item_name: return item_name
    
    clean = item_name.lower().strip()
    
    colors = ["red", "blue", "green", "black", "white", "yellow", "orange", "purple", "brown", "grey", "gray"]
    
    # Common prefixes to strip (Longer first)
    prefixes = [
        "i need a ", "i need ", "i want ", "i would like ", "please find ", "find ", "where is ", 
        "look for ", "search for ", "check for ", "give me ", "get me ", "show me ",
        "do you have ", "is there ", "are there ",
        "i meant ", "meant ", "actually ", "no ", "sorry ", "correction "
    ]
    
    start_len = len(clean)
    
    # Prefix Cleanup
    for p in prefixes:
        if clean.startswith(p):
            clean = clean[len(p):].strip()
            
    # Leading Stopword Cleanup (if entity is "the servo", remove "the")
    stopwords = ["the ", "a ", "an ", "some ", "my ", "i ", "they ", "we "]
    for s in stopwords:
        if clean.startswith(s):
             # Ensure we don't stripping "i" from "iphone" (check space)
             clean = clean[len(s):].strip()
    
    # --- ALIAS MAPPING ---
    # Explicit synonyms for robust search
    # Map LOWERCASE phrase -> DB Term
    SEARCH_ALIASES = {
        # --- POWER & BATTERIES ---
        "universal power supply": "ups",
        "uninterruptible power supply": "ups",
        "backup power": "ups",
        "battery backup": "ups",
        "lipo": "lithium polymer",
        "li po": "lithium polymer",
        "lithium polymer": "lipo", # Or reverse depending on DB. DB has "Lipo" or "Lead Acid"
        "adapter": "adaptor", # Spell fix
        "smps": "switched mode power supply",
        "power supply": "variable power supply", # Default to bench supply if vague? Or list all.
        
        # --- BOARDS & CONTROLLERS ---
        "rpi": "raspberry pi",
        "pi": "raspberry pi",
        "raspi": "raspberry pi",
        "arduino": "development board arduino", # Triggers wider search
        "esp8266": "development board esp8266",
        "esp32": "development board esp 32",
        "nucleo": "stm32",
        "flight controller": "drone flight controller",
        "kk board": "drone flight controller kk board",
        
        # --- COMPONENTS ---
        "led": "led",
        "resistor": "resistors microssed", # DB has "Resistors Microssed"
        "capacitor": "capacitor",
        "pot": "potentiometer",
        "variable resistor": "potentiometer",
        "stepper": "stepper motor",
        "servo": "servo motor",
        "bldc": "bldc motor",
        "motor driver": "motor driver module",
        "relay": "relay module",
        "display": "lcd display",
        "screen": "lcd display",
        "oled": "oled display",
        
        # --- TOOLS ---
        "soldering iron": "soldering station", # Prefer station or iron? DB has both. "Soldering Iron" finds specific.
        "solder ion": "soldering iron",     # Correc AS
        "solder gun": "soldering iron",
        "multimeter": "multimeter", # DB has "Multimeter UT33D", etc.
        "dmm": "multimeter",
        "cro": "oscilloscope",
        "dso": "oscilloscope",
        "scope": "oscilloscope",
        "function generator": "waveform generator",
        "glue gun": "glue gun 60w",
        "hot glue": "glue sticks",
        
        # --- CABLES & CONN ---
        "usb cable": "arduino cable usb",
        "jumper": "jumper wires",
        "connector": "connector",
        "header": "berg pins",
        
        # --- SENSORS ---
        "distance sensor": "ultrasonic sensor",
        "sonar": "ultrasonic sensor",
        "line sensor": "ir sensor module",
        "ir sensor": "ir sensor module",
        "pir": "sensor pir",
        "motion sensor": "sensor pir",
        "gas sensor": "sensor mq", # Triggers MQ list
        "smoke sensor": "sensor mq 2",
        "temp sensor": "temperature sensor",
        "humidity sensor": "dht sensor",
        "dht": "dht sensor",
        "imu": "sensor imu",
        "gyro": "sensor gyroscopic",
        "magnetometer": "sensor imu",
        "accel": "accelerometer sensor",
        
        # --- BRAND SPECIFIC ---
        "ni": "national instruments",
        "myrio": "ni myrio",
        "roborio": "robo rio",
        "keysight": "keysight",
        "tektronix": "tektronicross", # DB spelling fix "Tektronicross"
        "tektronics": "tektronicross"
    }
    
    if clean in SEARCH_ALIASES:
        return SEARCH_ALIASES[clean]

    return clean

def filter_by_critical_tokens(results, query):
    """
    Enforces that keywords present in BOTH the query and the top result
    must be present in all other results.
    Ex: Query "Plastic Gearbox". Top Result "DC Motor Plastic Gear...".
    Critical: "Plastic", "Gear".
    Item "Metal Gearbox" (Missing Plastic): Dropped.
    """
    if not results: return []
    
    # 1. Identify Critical Tokens from Top Result
    top_item = results[0][0].lower()
    query_tokens = query.lower().split()
    
    critical_tokens = []
    # Stopwords to ignore
    stopwords = {"s", "parts", "part", "item", "items", "the", "a", "an", "of", "in", "is", "are", "do", "you", "have", "looking", "for", "please", "show", "me", "where", "stock", "check", "find", "search", "list", "all"}
    
    for token in query_tokens:
        clean_token = token.strip(".,?!")
        if clean_token in stopwords: continue
        
        # If token from query is found in the top result, it is critical
        if clean_token in top_item:
            critical_tokens.append(clean_token)
            
    if not critical_tokens:
        return results
    
    # 2. Filter Results
    filtered = []
    for r in results:
        name = r[0].lower()
        if all(token in name for token in critical_tokens):
            filtered.append(r)
            
    return filtered

def filter_by_strict_numbers(results, query):
    """
    Enforces EXACT number matching.
    Query: "10 RPM" -> Must contain integer "10".
    Result "100 RPM" -> Contains "100" (Not "10") -> REJECT.
    Result "10 RPM" -> Contains "10" -> ACCEPT.
    """
    if not results: return []
    
    # Extract standalone digits from query
    import re
    # Look for digits bounded by non-digits
    q_nums = set(re.findall(r'\b\d+\b', query))
    
    if not q_nums: 
        return results

    # print(f"DEBUG: Strict Num Check: Need {q_nums}")
    
    filtered = []
    for r in results:
        # Extract standalone digits from item name
        r_text = r[0]
        # normalize "1.5" -> "1" "5" is fine for now, but usually looking for integers
        r_nums = set(re.findall(r'\b\d+\b', r_text))
        
        # Check subset: Query numbers must be in Result numbers
        if q_nums.issubset(r_nums):
            filtered.append(r)
            
    return filtered

# Semantic Search Global Index
SEMANTIC_INDEX = None # (item_names_list, embeddings_tensor)

def semantic_search_inventory(query, nlp, threshold=0.45):
    """
    Uses Vector Search to find items semantically similar to query.
    Ex: "Servo Motor" -> "MG996R TowerPro"
    """
    global SEMANTIC_INDEX
    if not SEMANTIC_INDEX: return []
    
    import torch
    from sentence_transformers import util
    
    item_names, item_embs = SEMANTIC_INDEX
    # Encode user query
    query_emb = nlp.encode_text(query)
    
    # Cosine Similarity
    scores = util.cos_sim(query_emb, item_embs)[0]
    
    results = []
    # Get top 5 matches
    # scores is a tensor. We use torch.topk
    k = min(5, len(item_names))
    if k == 0: return []
    
    top_results = torch.topk(scores, k=k)
    
    for score, idx in zip(top_results.values, top_results.indices):
        if score.item() < threshold: continue
        name = item_names[idx.item()]
        # Return matched name and score
        results.append((name, score.item()))
        
    return results

# ------------------ CSV CONFIG ------------------------
CSV_PATH = "inventory.csv"

CSV_COLUMNS = {
    "item": "Name of the Equipment",          # must EXACTLY match CSV header
    "location": "Location",
    "quantity": "Available Quantity"
}


# ------------------ MAIN APP --------------------------
def main():
    print("Initializing AI Voice Assistant...")

    # 1️⃣ Initialize Database (CSV → SQLite)
    try:
        db_manager.init_db(
            csv_path=CSV_PATH,
            csv_columns=CSV_COLUMNS
        )
    except Exception as e:
        print(f"Database initialization failed: {e}")
        return

    # 2️⃣ Load Models
    try:
        print("Loading ASR...")
        # Fetch vocabulary for ASR Priming
        print("Fetching Dynamic Vocabulary for ASR...")
        db_vocab = db_manager.get_unique_vocabulary()
        asr = VoiceListener(dynamic_vocab=db_vocab)

        print("Loading NLP...")
        nlp = IntentParser()
        
        # Init Semantic Index
        print("Constructing Semantic Index...")
        all_items = db_manager.get_all_item_names()
        if all_items:
            print(f"Indexing {len(all_items)} items...")
            item_embs = nlp.encode_text(all_items)
            global SEMANTIC_INDEX
            SEMANTIC_INDEX = (all_items, item_embs)
            print("Semantic Index Ready.")
        else:
            print("Warning: Inventory empty. Semantic Index skipped.")
        
        print("Loading Chat Engine...")
        chat_ai = ChatEngine()

        print("Loading TTS...")
        tts = Speaker()

        recorder = AudioRecorder()

    except Exception as e:
        print(f"CRITICAL ERROR loading models: {e}")
        import traceback
        traceback.print_exc()
        return

    print("\n" + "=" * 45)
    print("  SYSTEM READY — VOICE INVENTORY ONLINE  ")
    print("=" * 45)

    # ------------------ MAIN LOOP ----------------------
    context = {}
    while True:
        try:
            print("\nPress ENTER to start listening (Ctrl+C to exit)...")
            # Robust Wait for Enter (Bypasses input() EOFError)
            # Robust Wait for Enter (Bypasses input() EOFError)
            while True:
                if msvcrt:
                    key = msvcrt.getch()
                    if key == b'\r': # Enter
                        break
                    if key == b'\x03': # Ctrl+C
                        raise KeyboardInterrupt
                else:
                    # Linux fallback
                    key = getch_unix()
                    if key == b'\r' or key == b'\n':
                        break
                    if key == b'\x03':
                        raise KeyboardInterrupt

            # 🎤 Record Audio
            # print("Listening...") # Handled by recorder now
            try:
                # duration=None enables Press-to-Stop
                audio_file = recorder.record("input.wav", duration=None)
            except KeyboardInterrupt:
                break

            # 🧠 Transcribe
            print("Transcribing...")
            t0 = time.time()
            text = asr.transcribe(audio_file)
            print(f"User Said: {text} | ASR Time: {time.time()-t0:.2f}s")

            if not text.strip():
                tts.speak("I didn't hear anything. Please try again.")
                continue

            # ------------------ ACTIONS ------------------
            intent = None # Reset intent for this turn
            
            # Context Handling (Refinement)
            # If we were waiting for a spec (e.g. "which RPM?"), try to combine it
            if context.get("awaiting_spec"):
                # Clean input improvements
                # Clean input improvements
                # 1. Use the shared NLP cleaner first to strip "i meant", "actually", etc.
                cleaned_name = clean_entity_name(text)
                
                # 2. "Thousand" -> "1000"
                text_clean = cleaned_name.lower().replace("thousand", "1000").replace("hundred", "00")
                # 3. ASR Fixes: "RQM" -> "RPM"
                text_clean = text_clean.replace("rqm", "rpm")
                
                # 4. Clean conversational filler (Legacy list plus extra safety)
                # We want to remove "isn't there a", "i want", etc but KEEP "12000" and "RPM"
                # Using a local stopword set for refinement context
                fillers = {
                    "isnt", "isn't", "there", "a", "an", "the", "do", "you", "have", "available", 
                    "check", "stock", "of", "where", "is", "one", "which", "want", "looking", "for", 
                    "please", "show", "me", "i", "can", "find", "search", "they", "we"
                }
                
                # Remove punctuation
                text_clean_clean = re.sub(r'[^\w\s]', '', text_clean)
                words = text_clean_clean.split()
                filtered = [w for w in words if w not in fillers]
                
                filtered = [w for w in words if w not in fillers]
                
                clean_input = " ".join(filtered)
                
                # Normalize Plurals for Refinement (volts -> volt)
                clean_input = clean_input.replace("volts", "volt").replace("amps", "amp").replace("metres", "meter").replace("meters", "meter")
                
                print(f"DEBUG: Context active. Combining '{context['parent_item']}' + '{clean_input}'")
                refined_item = f"{context['parent_item']} {clean_input}"
                
                # New Refinement Logic: Filter existing Context Parent Results instead of Global Search
                # 1. Fetch ALL items matching parent context ("Servo")
                parent_results = db_manager.search_items(context['parent_item'])
                if not parent_results:
                     parent_results = db_manager.search_items_ranked(context['parent_item'])
                
                # 2. Filter these results using the NEW tokens ("24", "volt")
                # Using looser comparisons (Python-side) than SQL strictness
                refined_results = []
                
                # Prepare refinement tokens
                ref_tokens = set(clean_input.lower().split())
                # filter garbage
                # Allow "9", "5", "1" (Digits) OR words longer than 1 char (exclude "a", "i")
                ref_tokens = {t for t in ref_tokens if (len(t) > 1 or t.isdigit()) and t not in fillers}
                
                print(f"DEBUG: Refining {len(parent_results)} parent items with tokens: {ref_tokens}")
                
                # Safeguard: If no tokens left (e.g. input was just "the"), fail refinement
                if not ref_tokens:
                     refined_results = []
                     # This will trigger the "Refinement failed" block below

                for r in parent_results:
                     r_name = r[0].lower()
                     r_name_clean = re.sub(r'[^\w\s]', '', r_name) # "24v" -> "24v"
                     
                     # Check if ALL meaningful refinement tokens are represented in the item
                     match_all = True
                     for rt in ref_tokens:
                         # 1. Direct check
                         if rt in r_name_clean: continue
                         
                         # 2. Number check ("24" matches "24v")
                         if rt.isdigit():
                             # Check if this digit sequence exists in r_name
                             if rt in r_name: continue
                         
                         # 3. Unit check ("volt" matches "v", "rpm" matches "r p m")
                         # (Basic heuristics)
                         # 3. Unit check ("volt" matches "v", "rpm" matches "r p m")
                         # (Basic heuristics)
                         if rt == "volt" and re.search(r'\b\d*v\b', r_name_clean): continue
                         if rt == "rpm" and ("rpm" in r_name_clean or "r p m" in r_name_clean): continue
                         # "amps"/"ampere" match "a" or "amp"
                         if rt in ["ampere", "amp", "amps"] and ("amp" in r_name_clean or re.search(r'\b\d*a\b', r_name_clean)): continue
                         
                         print(f"DEBUG: Token '{rt}' missing in '{r_name_clean}'")
                         match_all = False
                         break
                    
                     if match_all:
                         refined_results.append(r)

                if refined_results:
                    # VALIDATION: Verify that new input tokens actually exist in the found items.
                    # Prevents "Garbage" inputs (e.g. "Save") from being ignored by fuzzy search 
                    # from returning the original parent list.
                    
                    is_valid_refinement = True
                    input_tokens = set(clean_input.lower().split())

                    # FIX: Check only UNIQUE tokens if possible, to prevent loops
                    parent_tokens = set(context.get('parent_item', '').lower().split())
                    unique_tokens = input_tokens - parent_tokens
                    tokens_to_check = unique_tokens if unique_tokens else input_tokens
                    
                    if tokens_to_check:
                        matches_input = False
                        for r in refined_results:
                            r_name = r[0].lower()
                            # Check if at least one new token appears in this result
                            # (Simple substring check for robustness)
                            if any(token in r_name for token in tokens_to_check):
                                matches_input = True
                                break
                        
                        if not matches_input:
                            print(f"DEBUG: Refinement Rejected. Tokens {tokens_to_check} not found in search results.")
                            is_valid_refinement = False
                            refined_results = [] # Treat as failed to trigger fall-through

                    if is_valid_refinement:
                        print(f"DEBUG: Refinement successful. Found {len(refined_results)}")
                        intent = context["intent"] # Preserve original intent (check_stock/location)
                        item = refined_item
                        # Restore quantity if present (for update commands)
                        qty = context.get("quantity", 1)
                        entities = {"item_name": item, "quantity": qty}
                        score = 1.0
                        context = {} # Clear context (Success!)
                        
                        # IMPORTANT: We already have the correct results. Do NOT re-search.
                        results = refined_results
                        skip_primary_search = True
                else:
                    print(f"DEBUG: Refinement failed. Persisting context for next turn.")
                    # context = {} # DO NOT CLEAR CONTEXT! 
                    # If refinement fails ("9-1"), keep "Adapter" so "9V" works next.
                    pass
                    # Fall through to normal NLP

            # Normal Intent Detection (if not handled by context)
            if not intent: # If we didn't force it via context
                print("Analyzing intent...")
                t0 = time.time()
                intent, score = nlp.detect_intent(text)
                entities = nlp.extract_entities(text)
                
                # CLEAN ENTITY NAME (Fix: "I need AC..." -> "i ac..." -> "ac...")
                if entities.get("item_name"):
                    entities["item_name"] = clean_entity_name(entities["item_name"])
                    
                print(f"NLP Time: {time.time()-t0:.2f}s")
                
                # Context Injection: If no item mentioned, but context exists, use it
                if not entities.get("item_name") and context.get("parent_item"):
                     print(f"DEBUG: Injecting Context Item: {context['parent_item']}")
                     entities["item_name"] = context["parent_item"]
                
                # Threshold for Low Confidence (Hallucination Prevention)
                # "It is open up" -> Check Stock (0.37) -> REJECT
                if score < 0.55 and intent != "exit": 
                    intent = "unknown"

            print(f"Intent: {intent} | Score: {score:.2f}")
            print(f"Entities: {entities}")

            if intent == "unknown":
                # Heuristic: If we extracted an item name, try searching.
                # If matches found, assume User meant to find the item.
                if entities and entities.get("item_name"):
                     item_check = entities["item_name"]
                     # Quick search to see if it exists
                     matches = db_manager.search_items(item_check)
                     if matches:
                          print(f"DEBUG: Unknown intent but item '{item_check}' found. Defaulting to check_location.")
                          intent = "check_location"
                     else:
                          # Try ranked fallback
                          matches_ranked = db_manager.search_items_ranked(item_check)
                          if matches_ranked:
                               # Filter by Score
                               if len(matches_ranked[0]) >= 4:
                                   max_score = matches_ranked[0][3]
                                   matches_ranked = [r for r in matches_ranked if r[3] >= max_score * 0.85]
                                   
                                   # Critical Token Filter
                                   matches_ranked = filter_by_critical_tokens(matches_ranked, item_check)
                                   matches_ranked = filter_by_strict_numbers(matches_ranked, item_check)
                                   
                                   # STRICT CHECK: Match Ratio > 0.6 (Heuristic Safe-guard)
                                   # Prevents "Warm Water" (2) -> "Water" (1) -> 0.5 Accept
                               # RELAXED: If User Input shares the same FIRST WORD as Candidate (e.g. "Servo Motor" -> "Servo MG996R"), treat as valid prefix match.
                               is_prefix = False
                               if matches_ranked:
                                   cand_start = matches_ranked[0][0].lower().split()[0]
                                   input_start = item_check.lower().split()[0]
                                   is_prefix = (cand_start == input_start) or any(cand[0].lower().startswith(item_check.lower()) for cand in matches_ranked)
                                   
                                   # Super Relaxed for "Servo Motor" (0.39)
                                   # If the user input is substantial (> 4 chars) and matches start, trust it.
                                   if is_prefix:
                                        ratio_threshold = 0.3 
                                   else:
                                        ratio_threshold = 0.6
                                   
                                   # Calculate fuzzy ratio
                                   top_cand = matches_ranked[0][0]
                                   ratio = SequenceMatcher(None, item_check.lower(), top_cand.lower()).ratio()
                                   
                                   if ratio > ratio_threshold: 
                                        print(f"DEBUG: Heuristic Ranked Match Accepted (Ratio {ratio:.2f} > {ratio_threshold})")
                                        print(f"DEBUG: Unknown intent but ranked item '{top_cand}' found. Defaulting to check_location.")
                                        intent = "check_location"
                                        print("DEBUG: Intent forced to check_location by Heuristic Match")
                                   else:
                                        print(f"DEBUG: Heuristic Ranked Match Rejected (Ratio {ratio:.2f} < {ratio_threshold})")
                                # We do NOT want to auto-select the top result if it's just a guess.
                                # Falling through to LLM Correction below.
                                   intent = "check_location"
            
            # Skip primary search if we already have results from Refinement
            skip_primary_search = False
            results = [] 
            
            # --- LLM ASR CORRECTION STEP ---
            # If still unknown, and we have an item entity but fuzzy search failed (or NLP failed to get entity),
            # Let's try to get candidates and ask LLM.
            if intent == "unknown":
                 query_for_correction = entities.get("item_name") if entities.get("item_name") else text
                 
                 # LOG QUERY
                 print(f"DEBUG: Generating Candidates for Query: '{query_for_correction}'")
                 
                 # Get broad candidates (lower threshold implicitly by taking all > 0 score)
                 # We need names only
                 candidates = []
                 seen = set() # Initialize here so it exists for both blocks
                 raw_candidates = db_manager.search_items_ranked(query_for_correction)
                 
                 # FALLBACK: If Entity produced no candidates, try Raw Text
                 if not raw_candidates and query_for_correction != text:
                      print(f"DEBUG: No candidates for entity '{query_for_correction}'. Trying raw text '{text}'")
                      query_for_correction = text
                      raw_candidates = db_manager.search_items_ranked(query_for_correction)

                 if raw_candidates:
                      # Take top 10 unique names
                      for rc in raw_candidates:
                           if rc[0] not in seen:
                                candidates.append(rc[0])
                                seen.add(rc[0])
                           if len(candidates) >= 5: break # Keep text candidates limited
                 
                 # ALWAY Mix in Semantic Candidates (Critical for "Sevr" -> "Servo", "Wire" -> "Cable")
                 # This bridges the gap between slang and database names
                 if SEMANTIC_INDEX:
                      # Use lenient threshold to catch "Sevr"
                      sem_cands = semantic_search_inventory(query_for_correction, nlp, threshold=0.35) 
                      for sc in sem_cands:
                           if sc[0] not in seen:
                                candidates.append(sc[0])
                                seen.add(sc[0])
                
                 if candidates:
                      corrected_item = chat_ai.correct_query(text, candidates)
                      if corrected_item:
                           print(f"DEBUG: LLM Corrected Intent to check_location for '{corrected_item}'")
                           intent = "check_location"
                           entities = {"item_name": corrected_item, "quantity": 1}
            
            # If still unknown -> STOP (Do not fall through to faulty Chat LLM)
            if intent == "unknown":
                 response_text = "I didn't catch that. Please mention an item name."
                 # intent = "chat" # DISABLE CHAT to prevent hallucinations on 1.1B model

            # Only process if intent is NOT unknown
            
            if intent == "emergency":
                print("!!! EMERGENCY ALERT !!!")
                play_emergency_sound() # Beep
                response_text = "Emergency Alert Activated! Alerting Authorities."
                # Here you would trigger external APIs
            
            elif intent == "save_info":
                # Save to Memory
                # Determine key (timestamp for now)
                key = f"note_{int(time.time())}"
                db_manager.save_memory(key, text)
                response_text = "I have saved that to your memory."

            elif intent == "chat":
                # Generate conversational response
                memories = db_manager.get_all_memories()
                reply = chat_ai.generate_reply(text, memories)
                response_text = reply

            elif intent == "check_stock":
                item = entities.get("item_name")
                if not item:
                    response_text = "Which item should I check?"
                else:
                    # Use search_items to get ALL matches
                    results = db_manager.search_items(item)
                    
                    # Fallback: Ranked Search (Relaxed Match)
                    if not results:
                        fallback_res = db_manager.search_items_ranked(item)
                        if fallback_res:
                            # Filter results: Drop items with significantly lower relevance
                            # fallback_res is sorted by score DESC. Max score is first.
                            if len(fallback_res[0]) >= 4: # Ensure score exists
                                max_score = fallback_res[0][3]
                                # Keep items with score >= 85% of max matches
                                cutoff = max_score * 0.85
                                results = [r for r in fallback_res if r[3] >= cutoff]
                                
                                # Critical Token Filter (Enforce 'Plastic' if in top result)
                                results = filter_by_critical_tokens(results, item)
                                results = filter_by_strict_numbers(results, item)

                            else:
                                results = fallback_res
                            
                            # Fuzzy Sort: Prioritize items closest to "DHD Sensor" (e.g. DHT Sensor)
                            try:
                                import difflib
                                results.sort(key=lambda x: difflib.SequenceMatcher(None, item.lower(), x[0].lower()).ratio(), reverse=True)
                            except ImportError:
                                pass
                            except ImportError:
                                pass
                    
                    # Fallback: Semantic Search (Vectors)
                    if not results and SEMANTIC_INDEX:
                         semantic_matches = semantic_search_inventory(item, nlp)
                         if semantic_matches:
                              # Fetch full details for matched names
                              results = []
                              seen = set()
                              for name, score in semantic_matches:
                                   if name in seen: continue
                                   seen.add(name)
                                   # Get strict details
                                   details = db_manager.search_items(name)
                                   results.extend(details)

                    # Filter Zero Quantity Items (User Request: Do not read 0 qty)
                    # Keep backup to distinguish "Not Found" vs "Out of Stock"
                    found_matches = results
                    results = [r for r in results if r[1] > 0]

                    if not results:
                        if found_matches:
                            response_text = f"I found matches for {clean_item_name_for_tts(item)}, but they are currently out of stock."
                        else:
                            response_text = f"I could not find anything matching {item}."
                    
                    # Check for "force list" intent (Strict)
                    # User wants to bypass summary only if explicitly requested
                    triggers = ["list all", "list everything", "show all", "show me all", "give me all", "tell me all"]
                    force_list = any(t in text.lower() for t in triggers)
                    
                    # Smart Summary for many results (unless forced)
                    if len(results) > 20 and not force_list:
                        response_text = f"I found {len(results)} matches. That's too many to list. Please be more specific."
                        context = {
                            "parent_item": item,
                            "intent": "check_stock",
                            "awaiting_spec": True
                        }
                    elif len(results) > 5 and not force_list:
                        # Hybrid Variation Collection: Specs OR Names
                        variations = set()
                        for r in results:
                            # Extract distinctive specs (e.g. 12V, 7AH)
                            specs = extract_specs([r[0]])
                            if specs:
                                variations.update(specs)
                            else:
                                # Fallback to cleaned name if no specs found
                                variations.add(clean_item_name_for_tts(r[0]))
                        
                        sorted_vars = sorted(list(variations))[:20]
                        example_specs = ", ".join(sorted_vars)
                        
                        response_text = f"I found {len(results)} matches. "
                        response_text += f"Variations include {example_specs}. Which one do you want?"
                        
                        # Set Context to wait for refinement
                        context = {
                            "parent_item": item,
                            "intent": "check_stock",
                            "awaiting_spec": True
                        }
                    
                    elif len(results) == 1:
                        # Single match behavior
                        name, qty, loc = results[0][:3]
                        # Clean location for TTS
                        spoken_loc = clean_for_tts(loc)
                        
                        prefix = "There is" if qty == 1 else "There are"
                        suffix = "" if qty == 1 else "s"
                        
                        response_text = f"{prefix} {qty} {clean_item_name_for_tts(name)}{suffix} stored in {spoken_loc}."
                        # Save Context for Follow-up
                        context = {"parent_item": name, "intent": "check_stock"}
                    else:
                        # Multiple matches behavior
                        # User requested FULL list of all matches
                        # Group items by Location
                        # loc -> list of (name, qty)
                        loc_groups = {}
                        for r in results:
                             # r = (name, quantity, location)
                             loc = r[2]
                             # Clean name for TTS
                             spoken_name = clean_item_name_for_tts(r[0])
                             qty = r[1]
                             if loc not in loc_groups: 
                                 loc_groups[loc] = []
                             loc_groups[loc].append((spoken_name, qty))

                        response_text = f"I found {len(results)} matches. "
                        details = []
                        for loc, items in loc_groups.items():
                            cleaned_loc = clean_for_tts(loc)
                            # items is list of (name, qty)
                            # Construct "N units of Name"
                            parts = []
                            for name, qty in items:
                                unit_str = "unit" if qty == 1 else "units"
                                parts.append(f"{qty} {unit_str} of {name}")
                            
                            # "1 unit of A, 3 units of B are all located at Loc"
                            if len(parts) > 1:
                                item_list = ", ".join(parts[:-1]) + " and " + parts[-1]
                                details.append(f"{item_list} are all located at {cleaned_loc}")
                            else:
                                # Single item in this location
                                # "5 units of X is located at Y"
                                details.append(f"{parts[0]} is located at {cleaned_loc}")
                        
                        response_text += ". ".join(details)
                        # Interaction complete for this group
                        context = {}

            elif intent in ["update_stock_add", "update_stock_remove"]:
                item = entities.get("item_name")
                qty = entities.get("quantity", 0)
                is_add = (intent == "update_stock_add")
                action_word = "add to" if is_add else "remove from"

                if not item:
                    response_text = "What item would you like to check?"
                    context = {"intent": "check_stock", "quantity": 1}
                else:
                    # 1. Search for Item (if not already found via Refinement)
                    if not skip_primary_search:
                         results = db_manager.search_items(item)
                    
                    if not results and not skip_primary_search:
                        # Fallback 1: Ranked Search (Phonetic)
                        fallback_res = db_manager.search_items_ranked(item)
                        if fallback_res:
                             if len(fallback_res[0]) >= 4:
                                 max_score = fallback_res[0][3]
                                 cutoff = max_score * 0.85
                                 results = [r for r in fallback_res if r[3] >= cutoff]
                                 results = filter_by_critical_tokens(results, item)
                                 results = filter_by_strict_numbers(results, item)
                             else:
                                 results = fallback_res

                    # Fallback: Semantic Search
                    if not results and SEMANTIC_INDEX:
                         semantic_matches = semantic_search_inventory(item, nlp)
                         if semantic_matches:
                              results = []
                              seen = set()
                              for name, score in semantic_matches:
                                   if name in seen: continue
                                   seen.add(name)
                                   results.extend(db_manager.search_items(name))
                    
                    # FILTER LOGIC FOR REMOVE INTENT
                    # If removing stock, we cannot remove from 0-qty items.
                    # Hide them from disambiguation to reduce noise.
                    if not is_add:
                        found_matches = results
                        results = [r for r in results if r[1] > 0]
                        
                        if not results and found_matches:
                             response_text = f"I found items matching {clean_item_name_for_tts(item)}, but they all have 0 stock, so I can't remove anything."
                             # Stop here
                             print(f"Assistant: {response_text}")
                             tts.speak(response_text)
                             continue # Skip to next loop iteration (break out of intent)

                    if not results:
                        response_text = f"I couldn't find {clean_item_name_for_tts(item)} in the inventory."
                    
                    elif len(results) == 1:
                        # Single match -> Execute Update
                        exact_name = results[0][0]
                        change = qty if is_add else -qty
                        res = db_manager.update_stock(exact_name, change)
                        
                        if isinstance(res, tuple):
                             # Success (name, new_qty)
                             name, new_qty = res
                             cleaned_name = clean_item_name_for_tts(name)
                             response_text = f"Updated {cleaned_name}. New quantity is {new_qty}."
                        else:
                             # Error string
                             response_text = res
                        
                    else:
                        # Multiple matches -> Disambiguate
                        if len(results) > 20:
                             response_text = f"I found {len(results)} matches for {clean_item_name_for_tts(item)}. Please be more specific."
                             context = {"parent_item": item, "intent": intent, "quantity": qty, "awaiting_spec": True}
                        else:
                             # List variations
                             variations = set()
                             for r in results:
                                 variations.add(clean_item_name_for_tts(r[0]))
                             
                             sorted_vars = sorted(list(variations))[:20]
                             example_specs = ", ".join(sorted_vars)
                             
                             response_text = f"I found {len(results)} matches. Variations include {example_specs}. Which one did you mean?"
                             context = {
                                 "parent_item": item,
                                 "intent": intent,
                                 "quantity": qty,
                                 "awaiting_spec": True
                             }

            elif intent == "check_location":
                item = entities.get("item_name")
                if not item:
                    response_text = "Which item are you looking for?"
                else:
                    # Use search_items to get ALL matches
                    if not skip_primary_search:
                         results = db_manager.search_items(item)
                    
                    # Fallback: Ranked Search (Relaxed Match)
                    # "Green Motor Driver" -> Matches "Motor Driver" (Score 2)
                    if not results and not skip_primary_search:
                        fallback_res = db_manager.search_items_ranked(item)
                        if fallback_res:
                            # Filter results: Drop items with significantly lower relevance
                            if len(fallback_res[0]) >= 4:
                                max_score = fallback_res[0][3]
                                cutoff = max_score * 0.85
                                results = [r for r in fallback_res if r[3] >= cutoff]
                                
                                # Critical Token Filter
                                results = filter_by_critical_tokens(results, item)
                                results = filter_by_strict_numbers(results, item)
                            else:
                                results = fallback_res
                            
                            # Fuzzy Sort: Prioritize closest string matches (DHD -> DHT)
                            try:
                                import difflib
                                results.sort(key=lambda x: difflib.SequenceMatcher(None, item.lower(), x[0].lower()).ratio(), reverse=True)
                            except ImportError:
                                pass
                            except ImportError:
                                pass
                    
                    # Fallback: Semantic Search
                    if not results and SEMANTIC_INDEX:
                         semantic_matches = semantic_search_inventory(item, nlp)
                         if semantic_matches:
                              results = []
                              seen = set()
                              for name, score in semantic_matches:
                                   if name in seen: continue
                                   seen.add(name)
                                   results.extend(db_manager.search_items(name))

                    # Filter Zero Quantity Items
                    found_matches = results
                    results = [r for r in results if r[1] > 0]

                    if not results:
                        if found_matches:
                            response_text = f"I found matches for {clean_item_name_for_tts(item)}, but they are out of stock."
                        else:
                            response_text = f"I don't know where {item} is stored."
                    
                    # Check for "force list" intent (Strict)
                    # User wants to bypass summary only if explicitly requested
                    triggers = ["list all", "list everything", "show all", "show me all", "give me all", "tell me all"]
                    force_list = any(t in text.lower() for t in triggers)

                    # Smart Summary for many results (unless forced)
                    if len(results) > 20 and not force_list:
                        response_text = f"I found {len(results)} matches. That's too many to list. Please be more specific."
                        context = {
                            "parent_item": item,
                            "intent": "check_location",
                            "awaiting_spec": True
                        }
                    elif len(results) > 5 and not force_list:
                        # Hybrid Variation Collection: Specs OR Names
                        # Use concise specs to avoid listing full long names
                        variations = set()
                        # Extract Specs
                        found_specs = extract_specs([r[0] for r in results])
                        
                        # If specs found, use them. Else fall back to names
                        if found_specs:
                             # Clean up specs for TTS (e.g. "12V" -> "12 Volt")
                             # Already handled by regex cleaning or just raw
                             variations = set(found_specs)
                        else:
                             for r in results:
                                  variations.add(clean_item_name_for_tts(r[0]))
                        
                        # Sort and limit
                        # Sort by length first to put short specs at start
                        sorted_vars = sorted(list(variations), key=len)[:15]
                        example_specs = ", ".join(sorted_vars)
                        
                        response_text = f"I found {len(results)} matches. "
                        response_text += f"Variations include {example_specs}. Which one are you looking for?"
                        
                        context = {
                            "parent_item": item,
                            "intent": "check_location",
                            "awaiting_spec": True
                        }

                    elif len(results) == 1:
                        stock = results[0]
                        spoken_name = clean_item_name_for_tts(stock[0])
                        spoken_loc = clean_for_tts(stock[2])
                        qty = stock[1]
                        unit_str = "unit" if qty == 1 else "units"
                        response_text = f"{qty} {unit_str} of {spoken_name} is located at {spoken_loc}."
                        # Save Context for Follow-up
                        context = {"parent_item": stock[0], "intent": "check_location"}
                    else:
                        # Group items by Location
                        # loc -> [item names]
                        # Group items by Location
                        # loc -> list of (name, qty)
                        loc_groups = {}
                        for r in results:
                             # r = (name, quantity, location)
                             loc = r[2]
                             spoken_name = clean_item_name_for_tts(r[0])
                             qty = r[1]
                             if loc not in loc_groups: 
                                 loc_groups[loc] = []
                             loc_groups[loc].append((spoken_name, qty))
                        
                        response_text = f"I found {len(results)} matches. "
                        details = []
                        for loc, items in loc_groups.items():
                            cleaned_loc = clean_for_tts(loc)
                            
                            # Construct "N units of Name"
                            parts = []
                            for name, qty in items:
                                unit_str = "unit" if qty == 1 else "units"
                                parts.append(f"{qty} {unit_str} of {name}")
                            
                            if len(parts) > 1:
                                item_list = ", ".join(parts[:-1]) + " and " + parts[-1]
                                details.append(f"{item_list} are all located at {cleaned_loc}")
                            else:
                                details.append(f"{parts[0]} is located at {cleaned_loc}")
                        
                        response_text += ". ".join(details)

            else:
                response_text = "I'm not sure I understood. Please repeat."


            # if intent == "unknown":
            #    tts.speak("I'm not sure I understood. Please repeat.")
            #    continue

            # 🔊 Speak Response
            print(f"Assistant: {response_text}")
            t0 = time.time()
            tts.speak(response_text)
            print(f"TTS Time: {time.time()-t0:.2f}s")

        except KeyboardInterrupt:
            print("\nExiting assistant. Goodbye!")
            break

        except Exception as e:
            print(f"Runtime error: {e}")
            import traceback
            traceback.print_exc()


# ------------------ ENTRY POINT -----------------------
if __name__ == "__main__":
    main()