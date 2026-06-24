import pandas as pd
import re
from rapidfuzz import process, fuzz

# --- CONFIGURATION ---
VAERS_SYMPTOMS_FILE = "unique_symptoms.xlsx"
OAE_MASTER_FILE = "ad.csv"
OUTPUT_FILE = "mapped_symptoms_v4_safe.csv"
FUZZY_THRESHOLD = 88  # Bumped up slightly for tighter safety

# Critical clinical modifiers that should NEVER be fuzzy-matched against each other
CONFLICT_GROUPS = [
    {"increased", "high", "elevated", "prolonged"},
    {"decreased", "low", "reduced", "shortened"},
    {"normal"}, {"abnormal"},
    {"positive"}, {"negative"},
    {"acute"}, {"chronic"},
    {"macule", "papule", "vesicle", "pustule"}, # Stop rash mix-ups
    {"scab", "scar"}, # Stop wound-healing mix-ups
    {"induration", "indentation"}, # Stop textural mix-ups
    {"injection", "incision"}, # Stop site mix-ups
    {"joint"} # Stop skin vs joint mix-ups (if one has 'joint' and the other doesn't, it blocks)
]

def clean_text(text):
    if pd.isna(text) or not str(text).strip(): return None
    clean = str(text).lower().strip()
    clean = clean.replace("-", " ")
    return re.sub(r'\s+ae$', '', clean)

def clean_meddra(meddra_id):
    if pd.isna(meddra_id): return None
    return str(meddra_id).replace("MedDRA:", "").replace("MEDDRA:", "").strip()

def has_clinical_conflict(vaers_str, oae_str):
    """Blocks matches if they mix up opposite medical terms (e.g., prolonged vs shortened)."""
    vaers_words = set(vaers_str.split())
    oae_words = set(oae_str.split())
    
    for group in CONFLICT_GROUPS:
        # Does the VAERS string have a word from this group?
        vaers_has_group = bool(vaers_words.intersection(group))
        # Does the OAE string have a word from this group?
        oae_has_group = bool(oae_words.intersection(group))
        
        # If one string has a specific modifier (like 'prolonged') but the other DOES NOT, 
        # or it has a conflicting one (like 'shortened'), block the match.
        if vaers_has_group != oae_has_group:
            return True # Conflict found! Block the match.
            
    return False # Safe to match

def process_and_merge():
    print("Loading datasets...")
    df_vaers = pd.read_excel(VAERS_SYMPTOMS_FILE)
    df_oae_raw = pd.read_csv(OAE_MASTER_FILE)

    df_vaers['match_key'] = df_vaers['SYM'].apply(clean_text)

    records = []
    for _, row in df_oae_raw.iterrows():
        med_id = clean_meddra(row.get('MedDRA_ID'))
        ont_id = row.get('x')
        
        lbl = clean_text(row.get('label'))
        if lbl: records.append({'match_key': lbl, 'ontology_id': ont_id, 'MedDRA_ID': med_id})
            
        syn = clean_text(row.get('synonym'))
        if syn: records.append({'match_key': syn, 'ontology_id': ont_id, 'MedDRA_ID': med_id})

    df_dict_grouped = pd.DataFrame(records).groupby('match_key', as_index=False).agg({
        'ontology_id': 'first',
        'MedDRA_ID': lambda x: ' | '.join(sorted(set(x.dropna().astype(str))))
    })

    # --- PASS 1: Exact Match ---
    print("Pass 1: Exact matching...")
    df_merged = pd.merge(df_vaers, df_dict_grouped, on='match_key', how='left')
    df_merged['Match_Type'] = df_merged['MedDRA_ID'].apply(lambda x: 'Exact' if pd.notna(x) else None)

    # --- PASS 2 & 3 Setup ---
    unmapped_mask = df_merged['MedDRA_ID'].isna()
    unmapped_symptoms = df_merged.loc[unmapped_mask, 'match_key'].dropna().unique()
    oae_choices = df_dict_grouped['match_key'].tolist()
    
    print(f"Pass 2 & 3: Processing {len(unmapped_symptoms)} unmapped symptoms...")
    
    word_swap_count = 0
    fuzzy_count = 0

    for idx, row in df_merged[unmapped_mask].iterrows():
        sym = row['match_key']
        if not sym: continue
            
        # Extract the best match using token_sort_ratio
        best_match = process.extractOne(sym, oae_choices, scorer=fuzz.token_sort_ratio)
        
        if best_match:
            match_str, score, _ = best_match
            
            # PASS 2: Word-Order Swap (100% same words, different order)
            if score == 100:
                match_type = f"Word-Swap ({match_str})"
                success = True
                word_swap_count += 1
                
            # PASS 3: Guarded Fuzzy Match (>= Threshold AND No Clinical Conflict)
            elif score >= FUZZY_THRESHOLD and not has_clinical_conflict(sym, match_str):
                match_type = f"Fuzzy ({match_str})"
                success = True
                fuzzy_count += 1
            else:
                success = False

            # If successful, apply to dataframe
            if success:
                oae_row = df_dict_grouped[df_dict_grouped['match_key'] == match_str].iloc[0]
                df_merged.at[idx, 'ontology_id'] = oae_row['ontology_id']
                df_merged.at[idx, 'MedDRA_ID'] = oae_row['MedDRA_ID']
                df_merged.at[idx, 'Match_Type'] = match_type

    # Clean up and show stats
    df_merged['Match_Type'] = df_merged['Match_Type'].fillna('Unmapped')
    df_merged = df_merged.drop(columns=['match_key'])
    
    matched_count = df_merged['MedDRA_ID'].notna().sum()
    total_count = len(df_merged)
    
    print(f"\n✅ Done! Mapped {matched_count} out of {total_count} symptoms ({(matched_count / total_count) * 100:.1f}%).")
    print(f"   - Exact Matches: {matched_count - word_swap_count - fuzzy_count}")
    print(f"   - Word-Swap Matches: {word_swap_count}")
    print(f"   - Fuzzy Matches: {fuzzy_count}")
    
    df_merged.to_csv(OUTPUT_FILE, index=False)
    print(f"Saved results to {OUTPUT_FILE}")

if __name__ == "__main__":
    process_and_merge()