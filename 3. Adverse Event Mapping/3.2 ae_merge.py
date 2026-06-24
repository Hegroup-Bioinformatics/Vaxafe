import pandas as pd

# --- CONFIGURATION ---
ORIGINAL_VAERS_FILE = "vaers_data_sym_202602161641.csv" # Update to your actual file name/extension
MAPPED_SYMPTOMS_FILE = "mapped_symptoms_v4_safe.csv"
OUTPUT_FILE = "vaers_fully_mapped.csv"

def merge_vaers_data():
    print("Loading datasets...")
    # Load the original VAERS file containing the patient IDs
    df_vaers_main = pd.read_csv(ORIGINAL_VAERS_FILE) # Use read_excel if it's an xlsx
    
    # Load your newly mapped unique symptoms dictionary
    df_mapped = pd.read_csv(MAPPED_SYMPTOMS_FILE)
    
    print(f"Original VAERS rows: {len(df_vaers_main)}")
    print(f"Unique mapped symptoms: {len(df_mapped)}")

    # Perform the Left Join on the 'SYM' column
    print("\nMerging data...")
    df_final = pd.merge(
        df_vaers_main,
        df_mapped[['SYM', 'ontology_id', 'MedDRA_ID', 'Match_Type']], 
        on='SYM', 
        how='left'
    )

    # Sanity check: The number of rows in df_final should exactly match df_vaers_main
    if len(df_final) == len(df_vaers_main):
        print("✅ Merge successful! Row counts match perfectly.")
    else:
        print("⚠️ Warning: Row counts changed. Check for exact duplicates in your mapped file's SYM column.")

    # Show a quick preview of the merged data
    print("\nPreview of merged data:")
    print(df_final[['VAERS_ID', 'SYM', 'MedDRA_ID', 'Match_Type']].head())

    # Save to CSV
    df_final.to_csv(OUTPUT_FILE, index=False)
    print(f"\nSaved final merged dataset to {OUTPUT_FILE}")

if __name__ == "__main__":
    merge_vaers_data()