import sqlite3
import pandas as pd
import os
import config
from datetime import datetime

def get_db_connection():
    conn = sqlite3.connect(config.DB_PATH)
    return conn

def init_db(csv_path=None, csv_columns=None):
    """
    Initialize the database.
    If DB doesn't exist, create it and populate from CSV.
    """
    target_csv = csv_path if csv_path else config.CSV_PATH
    
    db_exists = os.path.exists(config.DB_PATH)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Always create table if not exists
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventory (
            item_name TEXT PRIMARY KEY,
            quantity INTEGER,
            location TEXT,
            last_updated TEXT
        )
    ''')

    # Memory Table for Context
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_memory (
            key_name TEXT PRIMARY KEY,
            value_content TEXT,
            timestamp TEXT
        )
    ''')
    
    # If DB was just created or table empty, try to load from CSV
    cursor.execute('SELECT count(*) FROM inventory')
    count = cursor.fetchone()[0]
    
    if count == 0 and os.path.exists(target_csv):
        print(f"Loading data from {target_csv}...")
        try:
            df = pd.read_csv(target_csv)
            
            # Map columns if provided
            # Expected DB columns: item_name, quantity, location, last_updated
            # CSV columns: defined in csv_columns
            
            for index, row in df.iterrows():
                # Extract values based on mapping or default
                if csv_columns:
                    item = row.get(csv_columns.get('item', 'item_name'))
                    qty = row.get(csv_columns.get('quantity', 'quantity'), 0)
                    loc = row.get(csv_columns.get('location', 'location'), 'Unknown')
                else:
                    item = row.get('item_name')
                    qty = row.get('quantity', 0)
                    loc = row.get('location', 'Unknown')
                
                # Cleanup
                if pd.isna(qty): qty = 0
                else: 
                    # Handle "10" or integers
                    try:
                        qty = int(qty)
                    except:
                        qty = 0
                        
                if pd.isna(loc): loc = "Unknown"
                if pd.isna(item): continue

                timestamp = datetime.now().strftime("%Y-%m-%d")

                cursor.execute('''
                    INSERT OR REPLACE INTO inventory (item_name, quantity, location, last_updated)
                    VALUES (?, ?, ?, ?)
                ''', (str(item), qty, str(loc), timestamp))
            print("Data loaded successfully.")
        except Exception as e:
            print(f"Error loading CSV: {e}")
            
    conn.commit()
    conn.close()

def execute_query(sql_query, params=()):
    """
    Executes a SQL query.
    Returns result for SELECT, or commits for INSERT/UPDATE.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute(sql_query, params)
        
        if sql_query.strip().upper().startswith("SELECT"):
            result = cursor.fetchall()
            return result
        else:
            conn.commit()
            return cursor.rowcount
            
    except Exception as e:
        print(f"Database error: {e}")
        return None
    finally:
        conn.close()

def get_stock(item_name):
    res = execute_query("SELECT quantity, location FROM inventory WHERE item_name LIKE ?", (f"%{item_name}%",))
    if res:
        return res[0] # (quantity, location)
    return None

def search_items(keyword):
    """
    Returns a list of tuples: (item_name, quantity, location)
    for all items matching the keyword.
    """
    import re
    raw_words = keyword.split()
    if not raw_words: return []
    
    # Tokenize: Split alphanumerics (RMCS1106 -> RMCS, 1106)
    words = []
    for w in raw_words:
        if re.match(r'^\d+\.\d+$', w):
            words.append(w)
        else:
            parts = re.split(r'(\d+)', w)
            for p in parts:
                if p: words.append(p)
    
    # Build query: WHERE ... AND (item_name LIKE %13.5% OR item_name LIKE %13point5%) ...
    conditions = []
    params = []
    
    for token in words:
        # Check for decimal: 13.5 -> search also for 13point5
        if re.match(r'^\d+\.\d+$', token):
            token_var = token.replace(".", "point")
            conditions.append("(item_name LIKE ? OR item_name LIKE ?)")
            params.append(f"%{token}%")
            params.append(f"%{token_var}%")
        
        # Check for 'x' -> 'cross' (e.g. proximity -> procrossimity, flex -> flecross)
        elif 'x' in token:
            token_cross = token.replace("x", "cross")
            conditions.append("(item_name LIKE ? OR item_name LIKE ?)")
            params.append(f"%{token}%")
            params.append(f"%{token_cross}%")
            
        else:
            conditions.append("item_name LIKE ?")
            params.append(f"%{token}%")
    
    query = f"SELECT item_name, quantity, location FROM inventory WHERE {' AND '.join(conditions)}"
    
    # Identify pure integers from input to enforce strict matching
    strict_ints = set()
    for w in raw_words:
        if w.isdigit():
            strict_ints.add(int(w))
            
    print(f"DEBUG: STRICT INTS: {strict_ints}")

    res = execute_query(query, tuple(params))
    if not res: return []
    
    # Python-side filtering: Ensure 100 doesn't match 1000 (Integer Check)
    final_res = []
    for r in res:
        item_name = r[0]
        # Extract all integers from item name
        # "1000 RPM" -> {1000}
        # "RMCS1106" -> {1106}
        item_ints = set()
        for num_str in re.findall(r'\d+', item_name):
            item_ints.add(int(num_str))
        
        match = True
        for query_int in strict_ints:
            if query_int not in item_ints:
                print(f"DEBUG: Integer Mismatch: {query_int} not in {item_ints} for '{item_name}'")
                match = False
                break
        
        if match:
             final_res.append(r)
            
    return final_res

def search_items_ranked(keyword):
    """
    Search with scoring based on token overlap.
    Returns matching items sorted by relevance (score).
    "Green Motor Driver" -> matches "Motor Driver" (Score 2) over "Green LED" (Score 1).
    """
    import re
    raw_words = keyword.split()
    if not raw_words: return []
    
    # Tokenize: Split alphanumerics (RMCS1106 -> RMCS, 1106)
    words = []
    for w in raw_words:
        if re.match(r'^\d+\.\d+$', w):
            words.append(w)
        else:
            parts = re.split(r'(\d+)', w)
            for p in parts:
                if p: words.append(p)
    
    # 1. Build Score Query
    # Score = sum of matches for each token
    score_cases = []
    params = []
    
    for token in words:
        # Handle variations like "13.5" vs "13point5" and "x" vs "cross"
        token_var = None
        if re.match(r'^\d+\.\d+$', token):
            token_var = token.replace(".", "point")
        elif 'x' in token:
            token_var = token.replace("x", "cross")
            
        if token_var:
            # Match either token or variation
            score_cases.append(f"(CASE WHEN item_name LIKE ? OR item_name LIKE ? THEN 1 ELSE 0 END)")
            params.append(f"%{token}%")
            params.append(f"%{token_var}%")
        else:
            score_cases.append(f"(CASE WHEN item_name LIKE ? THEN 1 ELSE 0 END)")
            params.append(f"%{token}%")
            
    score_clause = " + ".join(score_cases)
    
    # Subquery to calculate score, then filter and sort
    query = f"""
        SELECT item_name, quantity, location, score FROM (
            SELECT item_name, quantity, location, ({score_clause}) as score 
            FROM inventory
        ) WHERE score > 0 ORDER BY score DESC
    """
    
    res = execute_query(query, tuple(params))
    
    # Minimum score filter
    MIN_SCORE = 2 if len(words) >= 2 else 1
    filtered = []
    if res:
        for r in res:
            if r[3] >= MIN_SCORE:
                filtered.append(r)

    # Strict integer filtering
    strict_ints = {int(w) for w in raw_words if w.isdigit()}
    if strict_ints:
        final = []
        for r in filtered:
            item_ints = {int(num) for num in re.findall(r'\d+', r[0])}
            if strict_ints.issubset(item_ints):
                final.append(r)
        filtered = final

    filtered.sort(key=lambda x: x[3], reverse=True)
    return filtered

def update_stock(item_name, quantity_change):
    # check if exists
    current = get_stock(item_name)
    timestamp = datetime.now().strftime("%Y-%m-%d")
    
    if current:
        new_qty = current[0] + quantity_change
        if new_qty < 0: new_qty = 0
        execute_query("UPDATE inventory SET quantity = ?, last_updated = ? WHERE item_name LIKE ?", (new_qty, timestamp, f"%{item_name}%"))
        return (item_name, new_qty)
    else:
        # If adding positive amount to non-existent item, create it?
        if quantity_change > 0:
            execute_query("INSERT INTO inventory (item_name, quantity, location, last_updated) VALUES (?, ?, ?, ?)", 
                          (item_name, quantity_change, "Unknown Location", timestamp))
            return (item_name, quantity_change)
        
        return f"Item {item_name} not found to remove from."

if __name__ == "__main__":
    init_db()
    print("Database initialized.")
def get_unique_vocabulary():
    """
    Extracts unique significant phrases (Brands, Item Types) from the inventory 
    for ASR priming. Prioritizes sequences like "Track Wheel" over "Track", "Wheel".
    """
    import re
    conn = sqlite3.connect(config.DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT item_name FROM inventory")
    items = cursor.fetchall()
    conn.close()
    
    vocab_phrases = set()
    
    # Regex to catch "Spec-like" words (containing digits, e.g. 12V, 7x2, 100RPM, 5.5)
    spec_pattern = r'\b\w*\d+\w*\b'
    
    # Connector stopwords that break phrases
    stopwords = {"for", "with", "and", "in", "at", "on", "to", "by", "from", "of", "unit", "units", "pcs", "set", "kit", "cm", "mm", "v", "w", "kv", "rpm"}
    
    for item in items:
        name = item[0]
        # 1. Remove words with digits (Specs)
        clean_name = re.sub(spec_pattern, ' ', name)
        
        # 2. Remove special chars (keep spaces)
        clean_name = re.sub(r'[^a-zA-Z\s]', ' ', clean_name)
        
        # 3. Build phrase chunks
        tokens = clean_name.split()
        current_chunk = []
        
        for t in tokens:
            t_lower = t.lower()
            if t_lower in stopwords or len(t) < 2:
                # Break phrase
                if current_chunk:
                    phrase = " ".join(current_chunk)
                    if len(phrase) > 2: vocab_phrases.add(phrase)
                    current_chunk = []
            else:
                current_chunk.append(t)
        
        # Add last chunk
        if current_chunk:
            phrase = " ".join(current_chunk)
            if len(phrase) > 2: vocab_phrases.add(phrase)
            
    # Return as list, sorted
    return sorted(list(vocab_phrases))

def get_all_item_names():
    """
    Returns a list of all item names for Semantic Indexing.
    """
    conn = sqlite3.connect(config.DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT item_name FROM inventory")
    items = cursor.fetchall()
    conn.close()
    return [i[0] for i in items]

def save_memory(key, value):
    """
    Saves a key-value pair to user_memory.
    """
    conn = sqlite3.connect(config.DB_PATH)
    cursor = conn.cursor()
    ts = datetime.now().isoformat()
    try:
        cursor.execute('''
            INSERT INTO user_memory (key_name, value_content, timestamp)
            VALUES (?, ?, ?)
            ON CONFLICT(key_name) DO UPDATE SET
            value_content=excluded.value_content,
            timestamp=excluded.timestamp
        ''', (key, value, ts))
        conn.commit()
    except Exception as e:
        print(f"Error saving memory: {e}")
    finally:
        conn.close()

def get_memory(key):
    """
    Retrieves a value from user_memory. Returns None if not found.
    """
    conn = sqlite3.connect(config.DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT value_content FROM user_memory WHERE key_name = ?", (key,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else None

def get_all_memories():
    """
    Returns dict of all memories for context injection.
    """
    conn = sqlite3.connect(config.DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT key_name, value_content FROM user_memory")
    rows = cursor.fetchall()
    conn.close()
    return {r[0]: r[1] for r in rows}

