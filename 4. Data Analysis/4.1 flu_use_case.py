import pandas as pd

# --- CONFIGURATION ---
VACCINES_FILE = "vaers_with_violin_ids_1.csv"
SYMPTOMS_FILE = "vaers_fully_mapped_symptoms.csv"

def analyze_clinical_findings():
    print("Loading datasets...")
    # We only need specific columns to save memory
    df_vax = pd.read_csv(VACCINES_FILE, usecols=['VAERS_ID', 'VAX_NAME'])
    df_sym = pd.read_csv(SYMPTOMS_FILE, usecols=['VAERS_ID', 'SYM', 'Match_Type'])
    
    print("Merging records on VAERS_ID...")
    # Inner join means we only keep rows where we have BOTH the vaccine and the symptom
    df_merged = pd.merge(df_sym, df_vax, on='VAERS_ID', how='inner')
    
    # 1. Isolate the two vaccines using a case-insensitive search
    flumist_mask = df_merged['VAX_NAME'].astype(str).str.contains('FLUMIST', case=False)
    afluria_mask = df_merged['VAX_NAME'].astype(str).str.contains('AFLURIA', case=False)
    
    df_flumist = df_merged[flumist_mask]
    df_afluria = df_merged[afluria_mask]
    
    print(f"\n✅ Found {len(df_flumist):,} total symptom occurrences for Flumist.")
    print(f"✅ Found {len(df_afluria):,} total symptom occurrences for Afluria.")
    
    # 2. Get Top 15 Symptoms for each
    top_n = 15
    flumist_top = df_flumist['SYM'].value_counts().head(top_n)
    afluria_top = df_afluria['SYM'].value_counts().head(top_n)
    
    print("\n=== TOP 15 ADVERSE EVENTS: FLUMIST ===")
    print(flumist_top.to_string())
    
    print("\n=== TOP 15 ADVERSE EVENTS: AFLURIA ===")
    print(afluria_top.to_string())
    
    # 3. Analyze Overlaps and Unique Symptoms
    # We will compare the Top 50 symptoms of each to find meaningful clinical differences
    compare_depth = 50
    flumist_set = set(df_flumist['SYM'].value_counts().head(compare_depth).index)
    afluria_set = set(df_afluria['SYM'].value_counts().head(compare_depth).index)
    
    overlap = flumist_set.intersection(afluria_set)
    flumist_unique = flumist_set - afluria_set
    afluria_unique = afluria_set - flumist_set
    
    print(f"\n=== CLINICAL COMPARISON (Based on Top {compare_depth} Symptoms) ===")
    print(f"Shared Symptoms ({len(overlap)}):")
    # Print the first 10 shared symptoms as an example
    print(", ".join(list(overlap)[:10]) + "...")
    
    print(f"\nUnique to Flumist's Top {compare_depth}:")
    print(", ".join(list(flumist_unique)))
    
    print(f"\nUnique to Afluria's Top {compare_depth}:")
    print(", ".join(list(afluria_unique)))

if __name__ == "__main__":
    analyze_clinical_findings()