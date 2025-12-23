from sentence_transformers import SentenceTransformer, util
import config
import re

class IntentParser:
    def __init__(self):
        print(f"Loading NLP model: {config.NLP_MODEL_NAME}...")
        self.model = SentenceTransformer(config.NLP_MODEL_NAME)
        
        # Define Anchor Sentences for Intents
        self.intents = {
            "check_stock": [
                "Check stock of soldering irons",
                "How many multimeters do we have",
                "What is the quantity of wire spools",
                "Do we have any resistors in stock",
                "List inventory of item",
                "Is the 3.5mm jack available",
                "Is item available",
                "Do we have 13.5 cm wheel",
                "Do we have item",
                "Are all the items",
                "Are all the motor drivers",
                "Are there any connectors",
                "Matrix",
                "Display",
                "Soldering Iron",
                "Motor Driver",
                "Sensor", 
                "How much units are there",
                "How many items",
                "What is the count",
                "Count of item",
                "Stock level"
            ],
            "update_stock_add": [
                "Add 5 multimeters to inventory",
                "Restock 10 soldering irons",
                "Increase stock of wires by 2",
                "Received 5 new oscilloscopes",
                "Add item",
                "Put 5 items",
                "Placed 2 units",
                "Deposited 10 units"
            ],
            "update_stock_remove": [
                "Remove 2 soldering irons",
                "Take out 5 resistors",
                "Decrease stock of multimeter by 1",
                "Used 3 wire spools",
                "Remove item",
                "I have taken 3 units",
                "Took 2 items",
                "Picked up 5 sensors",
                "Grabbed 1 motor",
                "Withdrew 3 units",
                "Reduce 2 units",
                "Reduce stock of battery"
            ],
            "check_location": [
                "Where is the multimeter kept",
                "Where can I find soldering irons",
                "Location of resistor pack",
                "Which crawler has the wire spool",
                "Find item",
                "Here is the item", 
                "Where's the item",
                "Where is the adapter",
                "Where is the converter",
                "Where is the device",
                "Where is the 10mm screw",
                "Location of 12V motor",
                "Find 13.5 cm wheel",
                "Find 13.5 cm wheel",
                "Where are the 100RPM motors"
            ],
            "emergency": [
                 "Help me", "Emergency", "Fire alarm", "Danger", "Alert security", "Call for help", "Critical situation", "Accident"
            ],
            "save_info": [
                 "My name is", "Save this information", "Remember that", "Note that", "Keep in mind", "My phone number is", "Store this"
            ]
        }
        
        # Pre-compute embeddings for anchors
        self.intent_embeddings = {}
        for intent, phrases in self.intents.items():
            self.intent_embeddings[intent] = self.model.encode(phrases)
            
        print("NLP model loaded.")

    def encode_text(self, text):
        """
        Generates vector embedding for text.
        Returns numpy array.
        """
        # compute_embeddings for list or string
        return self.model.encode(text)

    def detect_intent(self, text):
        """
        Returns (intent_name, confidence_score)
        """
        if not text:
            return None, 0.0

        text_emb = self.model.encode(text)
        
        best_intent = None
        best_score = -1.0
        
        for intent, anchor_embs in self.intent_embeddings.items():
            # semantic search against all anchors for this intent
            scores = util.cos_sim(text_emb, anchor_embs)[0]
            max_score = float(scores.max())
            
            if max_score > best_score:
                best_score = max_score
                best_intent = intent
                
        if best_score < config.INTENT_THRESHOLD:
            return "unknown", best_score
            
        return best_intent, best_score

    def extract_entities(self, text):
        """
        Extracts 'item_name' and 'quantity' from text.
        Intelligent extraction:
        - Avoids confusing specs (e.g. "100 RPM", "13.5 cm") with quantity.
        """
        text = text.lower()
        
        # Unit Normalization (Input -> DB format)
        # "centimeter" -> "cm", "volt" -> "v"
        unit_map = {
            "centimeter": "cm", "centimeters": "cm",
            "millimeter": "mm", "millimeters": "mm",
            "meter": "m", "meters": "m",
            "kilovolt": "kv", "kilovolts": "kv",
            "volt": "v", "volts": "v",
            "watt": "w", "watts": "w",
            "kilowatt": "kw", "kilowatts": "kw",
            "ampere": "a", "amperes": "a", "amp": "a", "amps": "a",
            "diameter": "dia", "diameters": "dia",
            "national instruments": "ni", "nat inst": "ni"
        }
        for full, short in unit_map.items():
            text = re.sub(rf'\b{full}\b', short, text)
        
        # Normalization
        text = text.replace(" to ", "dash").replace("-", "dash")
        
        # Convert number words to digits
        word_to_num = {
            "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
            "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10"
        }
        words = []
        for w in text.split():
            words.append(word_to_num.get(w, w))
            
        quantity = 1
        qty_index = -1
        
        # Units that indicate a number is a spec, not a quantity
        units = {'v', 'kv', 'w', 'kw', 'rpm', 'a', 'mah', 'mm', 'cm', 'm', 'kg', 'g', 'dia', 'volt', 'watt', 'amp', 'ohm', 'volts', 'watts', 'amps', 'cross', 'x', 'by', 'ah', 'ohms'}
        
        # 1. Identify Quantity
        for i, w in enumerate(words):
            # Clean punctuation for number check: "5," -> "5"
            w_clean = w.strip(".,?!")
            
            # Is it a simple integer? "13.5" is not digit. "100" is.
            if w_clean.isdigit():
                # Check unit lookahead
                is_spec = False
                if i + 1 < len(words):
                    next_word = words[i+1].lower().strip(".,?!")
                    if next_word in units:
                        is_spec = True
                
                if not is_spec:
                    quantity = int(w_clean)
                    qty_index = i
                    break # Assume first valid non-spec number is quantity
        
        # 2. Extract Item Name
        # Stopwords to remove from item name
        stopwords = {
            "s", "so", "well", "now", "then", "okay", "ok",
            "please", "give", "find", "search", "show", "tell", "where", "what", "how", "needed", "need", "want", "looking", "look", "get", "got", "have", "has", "had", "stored", "kept", "located", "check", "stock", "quantity", "many", "mucch", "much", "available", "left", "inventory", "count",
            "taken", "took", "picked", "grabbed", "put", "placed", "deposited", "withdrew", "reduce", "unit", "units", "piece", "pieces", "for", "from", "with", "by", "per", "of",
            "is", "it", "its", "am", "are", "was", "were", "be", "been", "being", "this", "that", "there", "here", "the", "a", "an",
            "what", "all", "available", "list",
            "type", "types", "kind", "kinds", "sort", "sorts",
            "item", "items", "thing", "things", "stuff", "object", "objects",
            "here",
            "cable", "converter", "adapter", "connector", "wire", "connection", "cord"
        }
        
        clean_words = []
        for i, w in enumerate(words):
            if i == qty_index:
                continue # Skip the extracted quantity number
            
            # Keep dots for "13.5"
            w_check = w.lower().strip("?!,") # Keep dots inside? "13.5" -> "13.5". "end." -> "end"
            if w_check.endswith("."): w_check = w_check[:-1]
            
            if w_check not in stopwords and len(w_check) > 0:
                 clean_words.append(w_check)
                 
        item_name = " ".join(clean_words)
        
        # Heuristics
        if item_name.endswith("ies"): item_name = item_name[:-3] + "y"
        elif item_name.endswith("s") and not item_name.endswith("ss"): item_name = item_name[:-1]
        
        return {
            "item_name": item_name,
            "quantity": quantity
        }
