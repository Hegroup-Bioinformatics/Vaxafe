import pandas as pd

# --- CONFIGURATION ---
VACCINES_FILE = "vaers_with_violin_ids_1.csv"
OUTPUT_FILE = "unique_flu_vaccines_to_categorize.csv"

def isolate_flu_vaccines():
    print("Loading mapped vaccines (this might take a moment)...")
    # Using low_memory=False prevents warnings on large VAERS files
    df = pd.read_csv(VACCINES_FILE, low_memory=False)
    
    # 1. Filter for Flu Vaccines
    # We look for VAX_TYPE starting with 'FLU' OR 'INFLUENZA' in the mapped VIOLIN name
    is_flu_type = df['VAX_TYPE'].astype(str).str.upper().str.startswith('FLU')
    is_flu_name = df['violin_name'].astype(str).str.upper().str.contains('INFLUENZA')
    
    df_flu = df[is_flu_type | is_flu_name].copy()
    
    print(f"\n✅ Found {len(df_flu):,} total Influenza vaccine records.")
    
    # 2. Group them to find the unique combinations
    flu_summary = df_flu.groupby(
        ['VAX_TYPE', 'VAX_NAME', 'violin_name', 'violin_id']
    ).size().reset_index(name='Occurrence_Count')
    
    # Sort by the most commonly reported vaccines
    flu_summary = flu_summary.sort_values(by='Occurrence_Count', ascending=False)
    
    # 3. Save the list so we can categorize it
    flu_summary.to_csv(OUTPUT_FILE, index=False)
    
    print(f"✅ Extracted {len(flu_summary):,} unique flu vaccine combinations.")
    print(f"✅ Saved summary to: {OUTPUT_FILE}\n")
    
    # 4. Show a quick preview of what we are dealing with
    print("=== TOP 10 MOST COMMON FLU VACCINES IN YOUR DATA ===")
    # We just print a few columns to keep the console clean
    print(flu_summary[['VAX_TYPE', 'VAX_NAME', 'Occurrence_Count']].head(10).to_string(index=False))

if __name__ == "__main__":
    isolate_flu_vaccines()