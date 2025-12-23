import config
import os
import time

try:
    from llama_cpp import Llama
    HAS_LLAMA = True
except ImportError:
    HAS_LLAMA = False
    print("Warning: 'llama-cpp-python' module not found. Chat features will be disabled.")

class ChatEngine:
    def __init__(self):
        self.enabled = False
        
        if not HAS_LLAMA:
            print("Chat Engine Disabled: Missing llama-cpp-python.")
            return

        if os.path.exists(config.LLM_MODEL_PATH):
            print(f"Loading Local LLM (LlamaCPP): {config.LLM_MODEL_FILENAME}...")
            try:
                # Initialize Llama model
                # n_gpu_layers=-1 to offload all to GPU if available, or set specific number
                # n_ctx should match model support (Phi-3 is 4096)
                self.llm = Llama(
                    model_path=config.LLM_MODEL_PATH,
                    n_ctx=config.LLM_CONTEXT_WINDOW,
                    n_gpu_layers=config.LLM_GPU_LAYERS,
                    verbose=False # Reduce noise
                )
                self.enabled = True
                print("LLM Loaded Successfully.")
            except Exception as e:
                print(f"Failed to load LLM: {e}")
                print("Try: pip install llama-cpp-python")
        else:
            print(f"LLM Model not found at {config.LLM_MODEL_PATH}. Chat features disabled.")

    def generate_reply(self, prompt, context_data=None):
        if not self.enabled:
            return "My conversational engine is offline. Please run reinstall.bat to fix it."
        
        # Build Context String from Memory
        memory_str = ""
        if context_data:
            memory_str = "Context from database:\n" + "\n".join([f"- {k}: {v}" for k,v in context_data.items()])
        
        # Llama 3 Prompt Template
        # <|start_header_id|>system<|end_header_id|>\n ... <|eot_id|><|start_header_id|>user<|end_header_id|>\n ... <|eot_id|><|start_header_id|>assistant<|end_header_id|>
        
        system_msg = (
            "You are Invenova, an AI inventory assistant. "
            "STRICT RULES:\n"
            "1. ONLY answer based on the 'Context from database' below.\n"
            "2. If the item is NOT in the Context, say 'I don't see that item in the inventory'.\n"
            "3. DO NOT invent items (like 'Teens', 'Kettles') or locations.\n"
            "4. Be concise."
        )
        
        full_prompt = (
            f"<|start_header_id|>system<|end_header_id|>\n\n{system_msg}\n{memory_str}<|eot_id|>"
            f"<|start_header_id|>user<|end_header_id|>\n\n{prompt}<|eot_id|>"
            f"<|start_header_id|>assistant<|end_header_id|>\n\n"
        )
        
        print(f"LLM Thinking...")
        start = time.time()
        
        try:
            output = self.llm(
                full_prompt, 
                max_tokens=200, 
                temperature=0.6,
                stop=["<|eot_id|>", "<|end_of_text|>"],
                echo=False
            )
            # LlamaCPP returns dict: {'choices': [{'text': '...', ...}], ...}
            response = output['choices'][0]['text'].strip()
            print(f"LLM Gen Time: {time.time() - start:.2f}s")
            return response
        except Exception as e:
            print(f"LLM Error: {e}")
            return "I encountered an error while thinking."

    def correct_query(self, user_text, candidates):
        """
        Uses LLM to correct ASR errors by selecting the best match from candidates.
        candidates: List of item names (strings).
        Returns: Corrected item name or None.
        """
        if not self.enabled or not candidates:
            return None

        # Format candidates list
        # "1. DC Motor\n2. AC Motor..."
        candidates_str = "\n".join([f"{i+1}. {c}" for i, c in enumerate(candidates)])
        
        system_msg = (
            "You are an ASR Correction Assistant. Your job is to match a noisy audio transcript to the correct item from a list.\n"
            "Rules:\n"
            "1. Output ONLY the exact Item Name from the list. No explanations.\n"
            "2. If the user input is a generic variation (e.g. 'Servo' vs 'Servo MG996R'), output the list item.\n"
            "3. If NO reasonable match exists, validly return 'None'.\n"
        )
        
        prompt = (
            f"<|start_header_id|>system<|end_header_id|>\n\n{system_msg}<|eot_id|>"
            f"<|start_header_id|>user<|end_header_id|>\n\n"
            f"Candidate List:\n{candidates_str}\n\n"
            f"User Audio Input: '{user_text}'\n"
            f"Which item did they mean?<|eot_id|>"
            f"<|start_header_id|>assistant<|end_header_id|>\n\n"
        )

        print(f"LLM Correcting '{user_text}' against {len(candidates)} candidates...")
        try:
            output = self.llm(
                prompt,
                max_tokens=50, 
                temperature=0.1, # Low temp for precision
                stop=["<|eot_id|>", "<|end_of_text|>", "\n"],
                echo=False
            )
            response = output['choices'][0]['text'].strip()
            cleanup_resp_original = response # Keep original for debug
            
            # Validation: Response must be REASONABLE (substring of candidate or vice versa)
            # Remove "1. " prfix if LLM hallucinated it
            clean_resp = response.strip('"').strip("'")
            
            # Remove conversational garbage
            garbage_prefixes = ["the user meant", "i think the user said", "correction:", "output:", "answer:"]
            for prefix in garbage_prefixes:
                if clean_resp.lower().startswith(prefix):
                    clean_resp = clean_resp[len(prefix):].strip().strip('"').strip("'")
            
            # Remove trailing periods
            if clean_resp.endswith("."): clean_resp = clean_resp[:-1]
            
            # Validation: Dual-Direction Check
            # 1. Candidate in Response (LLM said "I think it is DC Motor Plastic...")
            # 2. Response in Candidate (LLM said "DC Motor", Candidate is "DC Motor 100RPM")
            
            best_match = None
            # Sort candidates by length (descending) to match specific items first
            sorted_cands = sorted(candidates, key=len, reverse=True)
            
            # 1. Extract potential item from Quotes (Priority)
            # Response: 'The user meant "Servo Motor".' -> 'Servo Motor'
            # Also handle single quotes or just extracted name
            import re
            quoted = re.search(r'["\']([^"\']*)["\']', clean_resp)
            if quoted:
                 potential_quote = quoted.group(1).strip()
                 # Only use quote if it's not trivial
                 if len(potential_quote) > 3:
                     clean_resp = potential_quote
            
            clean_resp_lower = clean_resp.lower()
            
            # Debug Log
            print(f"DEBUG: LLM Parsed Response: '{clean_resp}' checking against {len(candidates)} candidates.")
            
            for cand in sorted_cands:
                c_low = cand.lower()
                
                # Check 0: Response STARTS with Candidate (Prefix Match in Response)
                # "Servo Motor as their input..." -> Match "Servo Motor"
                if clean_resp_lower.startswith(c_low):
                     best_match = cand
                     break
                     
                # Check 1: Candidate is mentioned in response
                if c_low in clean_resp_lower: 
                     best_match = cand
                     break
            
            
            print(f"DEBUG: LLM Parsed Response: '{clean_resp}' checking against {len(sorted_cands)} candidates.")
            # print(f"DEBUG: Candidates: {sorted_cands}") # Uncomment to see full list

            for cand in sorted_cands:
                c_low = cand.lower()
                
                # Check 1: Candidate is mentioned in response (Exact or contained)
                if c_low in clean_resp_lower: 
                     best_match = cand
                     break
                
                # Check 2: Response is a substring of candidate (Generalization)
                # Ensure response is substantial (len > 3)
                if len(clean_resp_lower) > 3 and clean_resp_lower in c_low:
                     # Generalization Strategy:
                     # If LLM said "DC Motor" and Candidate is "DC Motor 100RPM",
                     # Return "DC Motor" (Generic) so the system asks for clarification.
                     print(f"DEBUG: Generalization Detected. Returning Generic Term: '{clean_resp}'")
                     best_match = clean_resp 
                     break
                
                # Check 3: Candidate PREFIX match (First 2 words)
                # "Servo Motor" in "The user meant Servo Motor" -> Match "Servo Motor MG996R"
                c_parts = c_low.split()
                if len(c_parts) >= 2:
                    c_prefix = f"{c_parts[0]} {c_parts[1]}"
                    if len(c_prefix) > 4 and c_prefix in clean_resp_lower:
                        # Extract prefix as generic term if response is shorter than candidate
                        # e.g. Response="Servo Motor", Candidate="Servo Motor MG996R" -> return "Servo Motor"
                        best_match = clean_resp if len(clean_resp) < len(cand) else c_prefix
                        break

            if best_match:
                 print(f"LLM Correction: '{user_text}' -> '{best_match}'")
                 return best_match

            # --- Fallback: Token Overlap Match ---
            # If "Servo Motor" didn't match "Standard Servo" by substring, try token overlap.
            print("DEBUG: Substring match failed. Trying Token Overlap...")
            
            resp_tokens = set(clean_resp_lower.split())
            # Remove stopwords
            stopwords = {"the", "user", "meant", "item", "is", "a", "an", "of", "box"}
            resp_tokens = {t for t in resp_tokens if t not in stopwords and len(t) > 2}
            
            if not resp_tokens:
                 print(f"LLM failed to select valid candidate. Output: {cleanup_resp_original}")
                 return None

            best_cand = None
            max_overlap = 0
            
            for cand in candidates:
                c_tokens = set(cand.lower().split())
                overlap = len(resp_tokens.intersection(c_tokens))
                if overlap > max_overlap:
                    max_overlap = overlap
                    best_cand = cand
            
            if best_cand and max_overlap >= 1:
                # Construct Generic Term from Intersection
                # Intersect "servo motor" and "servo sm-s3317s" -> "servo"
                c_tokens = set(best_cand.lower().split())
                common = resp_tokens.intersection(c_tokens)
                
                # Sort by position in original string to maintain readability? 
                # Hard with set. Let's filter original response words.
                final_words = []
                for w in clean_resp.split():
                    w_clean = w.lower()
                    if w_clean in common:
                        final_words.append(w)
                
                generic_term = " ".join(final_words)
                if not generic_term: generic_term = best_cand # Fallback
                
                print(f"LLM Correction (Fuzzy Shortcut): '{user_text}' -> '{generic_term}' (Overlap: {max_overlap})")
                return generic_term
            
            # If invalid output, return None
            print(f"LLM failed to select valid candidate. Output: {cleanup_resp_original}")
            return None

        except Exception as e:
            print(f"LLM Correction Error: {e}")
            return None
