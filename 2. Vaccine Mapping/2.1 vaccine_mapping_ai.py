import os
import json
import re
import pandas as pd
from dotenv import load_dotenv
from tqdm import tqdm
from rapidfuzz import process, fuzz

from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()

# --- CONFIGURATION ---
SOURCE_FILE = "unique_vaccines.xlsx"
SOURCE_NAME_COL = "VAX_NAME"
SOURCE_MANU_COL = "VAX_MANU"

TARGET_DB_FILE = "t_vaccine.csv"
OUTPUT_FILE = "unique_vaccines_mapped_final.xlsx"

TEST_LIMIT = 50

DB_COLS = {
    "name": "c_vaccine_name",
    "brand": "c_brand_name",
    "mfr": "c_manufacturer",
    "desc": "c_description",
    "id": "c_vaccine_id"
}

STOP_WORDS = {"no", "brand", "name", "unknown", "product", "nos", "usp", "vax", "vaccine", "manufacturer"}

VAX_ACRONYMS = {
    r'\bdtap\b': 'diphtheria tetanus pertussis',
    r'\btdap\b': 'tetanus diphtheria pertussis',
    r'\bdt\b': 'diphtheria tetanus',
    r'\btd\b': 'tetanus diphtheria',
    r'\bipv\b': 'polio poliovirus',
    r'\bopv\b': 'polio poliovirus',
    r'\bhib\b': 'haemophilus influenzae',
    r'\bhepb\b': 'hepatitis b',
    r'\bhepa\b': 'hepatitis a',
    r'\bmmr\b': 'measles mumps rubella',
    r'\bbcg\b': 'tuberculosis mycobacterium',
    r'\bhpv\b': 'papillomavirus'
}

def clean_company_name(name):
    if not isinstance(name, str): return ""
    name = str(name).lower()
    name = re.sub(r"\b(inc|corp|ltd|llc|gmbh|co|company|corporation|limited|laboratories|labs)\b", "", name)
    name = re.sub(r"[^a-z0-9\s]", " ", name)
    return name.strip()

def load_data():
    print("--- Loading Files ---")
    df_source = pd.read_excel(SOURCE_FILE)
    
    if SOURCE_MANU_COL not in df_source.columns:
        df_source[SOURCE_MANU_COL] = ""
    df_source[SOURCE_MANU_COL] = df_source[SOURCE_MANU_COL].fillna("").astype(str)
    
    try:
        df_db = pd.read_csv(TARGET_DB_FILE, encoding='utf-8')
    except UnicodeDecodeError:
        df_db = pd.read_csv(TARGET_DB_FILE, encoding='latin1')
        
    for col in DB_COLS.values():
        if col in df_db.columns:
            df_db[col] = df_db[col].fillna("").astype(str)
            
    return df_source, df_db

KNOWN_ALIASES = {
    "wyeth": "pfizer",
    "lederle": "pfizer",
    "aventis": "sanofi",
    "pasteur merieux": "sanofi",
    "connaught": "sanofi",
    "smithkline": "glaxosmithkline",
    "glaxo": "glaxosmithkline",
    "gsk": "glaxosmithkline",
    "north american vaccines": "baxter",
    "bioport": "emergent",
    "chiron": "novartis",
    "medimmune": "astrazeneca",
    "crucell": "janssen",
    "berna": "crucell", 
    "organon": "merck",
    "powderject": "novartis",
    "janssen": "johnson & johnson"
}

def build_manufacturer_map(source_manus, db_manus):
    print("\n--- Auto-Mapping Manufacturers (Hybrid) ---")
    unique_db_manus = list(set(db_manus))
    clean_db_manus = [clean_company_name(m) for m in unique_db_manus]
    
    mapping = {}
    
    for raw_manu in tqdm(source_manus, desc="Linking Companies"):
        raw_manu_str = str(raw_manu).strip().lower()
        
        if not raw_manu or raw_manu_str in ["unknown", "unknown manufacturer", "nan", "none", ""]:
            mapping[raw_manu] = "Unknown" 
            continue

        clean_source = clean_company_name(raw_manu)
        
        alias_found = False
        for alias, owner in KNOWN_ALIASES.items():
            if alias.lower() in clean_source:
                match = process.extractOne(owner.lower(), clean_db_manus, scorer=fuzz.token_sort_ratio, score_cutoff=60)
                if match:
                    _, _, index = match
                    mapping[raw_manu] = unique_db_manus[index]
                else:
                    mapping[raw_manu] = owner.title() 
                alias_found = True
                break
        
        if alias_found: continue

        match = process.extractOne(clean_source, clean_db_manus, scorer=fuzz.token_sort_ratio, score_cutoff=75)
        
        if match:
            _, _, index = match
            mapping[raw_manu] = unique_db_manus[index]
        else:
            mapping[raw_manu] = raw_manu 

    return mapping

def normalize_vax_text(text):
    text = str(text).lower()
    text = re.sub(r'covid[\s\-]?19', 'covid 19', text)
    return text

def get_candidates(row, manu_mapping, df_db):
    raw_name = str(row[SOURCE_NAME_COL])
    raw_manu = str(row[SOURCE_MANU_COL])
    mapped_manu = manu_mapping.get(raw_manu, "")
    
    # --- 1. Extract Brand from Parentheses ---
    extracted_brand = ""
    brand_match = re.search(r'\((.*?)\)', raw_name)
    if brand_match:
        b_text = brand_match.group(1).lower().strip()
        if not any(x in b_text for x in ["no brand", "unknown", "foreign", "nos"]):
            extracted_brand = b_text

    # --- 2. Expand Acronyms for Search ---
    search_text = normalize_vax_text(f"{raw_name} {mapped_manu if mapped_manu else ''}")
    for acr, exp in VAX_ACRONYMS.items():
        if re.search(acr, search_text):
            search_text += f" {exp}"

    tokens = re.findall(r'\w+', search_text)
    tokens = [t for t in tokens if t not in STOP_WORDS and len(t) >= 2]
    
    if not tokens: return "No usable keywords."

    scores = [0] * len(df_db)
    db_mfrs = df_db[DB_COLS["mfr"]].tolist()
    db_brands = df_db[DB_COLS["brand"]].tolist()
    
    db_identities_raw = (df_db[DB_COLS["name"]] + " " + df_db[DB_COLS["brand"]]).tolist()
    db_identities = [normalize_vax_text(name) for name in db_identities_raw]
    
    for i in range(len(df_db)):
        score = 0
        row_mfr = str(db_mfrs[i])
        row_brand = str(db_brands[i])
        row_name = str(df_db.loc[i, DB_COLS["name"]]).lower()
        
        token_score = 0
        for token in tokens:
            if token in db_identities[i]:
                token_score += 10
            elif token in str(df_db.loc[i, DB_COLS["desc"]]).lower():
                token_score += 1
                
        score += token_score
        
        # --- 3. Give Massive Boost to Extracted Brand ---
        if extracted_brand and (extracted_brand in row_brand.lower() or extracted_brand in row_name):
            score += 50 

        # Manufacturer Match
        if mapped_manu and mapped_manu.lower() != "unknown":
            if mapped_manu.lower() == row_mfr.lower():
                score += 25
            elif mapped_manu.lower() in row_mfr.lower():
                score += 15
                
        # Generic Boost
        if row_mfr.lower() == "unknown" and row_brand.lower() == "generic":
            if mapped_manu.lower() == "unknown" and token_score > 0:
                score += 50  
            elif token_score > 0:
                score += 15  

        scores[i] = score

    df_db["_score"] = scores
    candidates = df_db[df_db["_score"] > 0].sort_values(by="_score", ascending=False).head(10)
    
    if candidates.empty: return "No matching candidates found in DB."
    
    blocks = []
    for _, r in candidates.iterrows():
        blocks.append(
            f"ID: {r[DB_COLS['id']]}\n"
            f"Name: {r[DB_COLS['name']]}\n"
            f"Brand: {r[DB_COLS['brand']]}\n"
            f"Mfr: {r[DB_COLS['mfr']]}\n"
            f"Desc: {r[DB_COLS['desc']][:300]}...\n"
        )
    return "\n".join(blocks)

def main():
    try:
        llm = AzureChatOpenAI(
            deployment_name=os.getenv("DEPLOYMENT"),
            api_version=os.getenv("API_VERSION"),
            api_key=os.getenv("API_KEY"),
            azure_endpoint=os.getenv("ENDPOINT"),
            openai_organization=os.getenv("ORGANIZATION"),
            temperature=0
        )
    except Exception as e:
        print(f"Error initializing LLM: {e}")
        return

    df_source, df_db = load_data()
    
    source_manus = df_source[SOURCE_MANU_COL].unique().tolist()
    db_manus = df_db[DB_COLS["mfr"]].unique().tolist()
    manu_map = build_manufacturer_map(source_manus, db_manus)
    
    unique_pairs = df_source[[SOURCE_NAME_COL, SOURCE_MANU_COL]].drop_duplicates()
    # if TEST_LIMIT:
    #     print(f"--- Limiting to first {TEST_LIMIT} rows for testing ---")
    #     unique_pairs = unique_pairs.head(TEST_LIMIT)

    prompt = ChatPromptTemplate.from_template("""
    You are a strict data curator for the VIOLIN Vaccine Database mapping VAERS data. 
    Your ultimate goal is to match a Source Record to exactly one Candidate ID. You MUST NOT return null if any reasonable generic fallback is available.

    === SOURCE RECORD ===
    Name: "{raw_name}"
    Manufacturer: "{raw_manu}" (Mapped Context: "{mapped_manu}")
    NOTE: All source records are HUMAN vaccines.

    === CANDIDATES ===
    {candidates}

    === MATCHING LOGIC ===
    1. THE "NO ANIMALS" RULE (CRITICAL):
    - The source data is exclusively human. You MUST NEVER map to a veterinary/animal vaccine (e.g., canine, feline, bovine, poultry, avian, USDA licensed).
    - If a candidate contains animal terms, IGNORE IT completely. 

    2. EXACT MATCH & KNOWN TRADE NAMES (PRIORITY):
    - Attempt to find the specific human vaccine where the target disease and manufacturer match.
    - TRADE NAME RULE: If the source record does not list a brand, but you know the candidate's brand is the official trade name for that manufacturer's vaccine (e.g., Pfizer/BioNTech's COVID-19 vaccine is "Comirnaty", Sanofi's DTaP is "Daptacel"), you MUST treat it as an exact match. Do NOT fall back to generic.
    
    3. UNKNOWN MANUFACTURER RULE:
    - If the Source Manufacturer or Mapped Context is "Unknown", you MUST map the record to the Generic human candidate (Mfr: "Unknown", Brand: "Generic"). 

    4. GENERIC FALLBACK:
    - If the Source Manufacturer is known (e.g., Pfizer) but the only manufacturer matches in the candidates are for ANIMALS, reject them and map to the Generic human candidate.
    - If you CANNOT find an exact manufacturer match or a known trade name match for humans, map it to the Generic human candidate.

    5. COMBINATION VACCINE FALLBACK:
    - If the Source indicates multiple components (e.g., "DTAP", "DT + IPV", "MMR") but there is NO generic candidate that contains all components, map it to a generic candidate that covers AT LEAST ONE of the primary components (e.g., map a DTaP vaccine to a generic Diphtheria vaccine). DO NOT return null.

    === OUTPUT FORMAT ===
    Return a single JSON object (no markdown, no code blocks):
    {{
        "matched_id": "ID here" or null,
        "matched_name": "Exact Name from Candidate" or null,
        "is_generic_fallback": true or false,
        "rationale": "One sentence explaining the match, the fallback, or why null was returned."
    }}
    """)

    chain = prompt | llm
    results = []

    print(f"\n--- Starting AI Mapping ({len(unique_pairs)} items) ---")
    
    for _, row in tqdm(unique_pairs.iterrows(), total=len(unique_pairs)):
        cand_str = get_candidates(row, manu_map, df_db)
        mapped_manu_val = manu_map.get(str(row[SOURCE_MANU_COL]), "Unknown")

        if cand_str.startswith("No"):
            results.append({
                "original_name": row[SOURCE_NAME_COL],
                "violin_id": None,
                "rationale": "No relevant candidates found in DB."
            })
            continue
            
        try:
            res = chain.invoke({
                "raw_name": row[SOURCE_NAME_COL],
                "raw_manu": str(row[SOURCE_MANU_COL]),
                "mapped_manu": mapped_manu_val,
                "candidates": cand_str
            })
            
            content = res.content.replace("```json", "").replace("```", "").strip()
            data = json.loads(content)
            
            results.append({
                "original_name": row[SOURCE_NAME_COL],
                "original_manu": row[SOURCE_MANU_COL],
                "mapped_manu": mapped_manu_val,
                "violin_id": data.get("matched_id"),
                "violin_name": data.get("matched_name"),
                "used_fallback": data.get("is_generic_fallback"),
                "rationale": data.get("rationale")
            })
            
        except Exception as e:
            results.append({
                "original_name": row[SOURCE_NAME_COL], 
                "violin_id": "ERROR", 
                "rationale": str(e)
            })

    df_results = pd.DataFrame(results)
    df_results.to_excel(OUTPUT_FILE, index=False)
    print(f"✅ Done! Saved {len(df_results)} rows to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()