import pandas as pd

# --- CONFIGURATION ---
VAERS_FILE = "vaers_data_vax.csv" # Change this to your actual VAERS raw data file
MAPPED_FILE = "unique_vaccines_mapped_final.xlsx"
OUTPUT_FILE = "vaers_with_violin_ids_2.csv"

def merge_vaers_data():
    print("Loading datasets...")
    # Load the original VAERS dataset
    # (Using latin1 encoding just in case, as VAERS data often has weird characters)
    try:
        df_vaers = pd.read_csv(VAERS_FILE, encoding='utf-8')
    except UnicodeDecodeError:
        df_vaers = pd.read_csv(VAERS_FILE, encoding='latin1')
        
    # Load your AI-mapped results
    df_mapped = pd.read_excel(MAPPED_FILE)

    print(f"Original VAERS rows: {len(df_vaers)}")
    print(f"Mapped unique pairs: {len(df_mapped)}")

    # 1. Clean the join columns to ensure a perfect match
    # We must handle NaNs exactly the same way we did in the extraction script
    df_vaers['VAX_NAME'] = df_vaers['VAX_NAME'].fillna("").astype(str)
    df_vaers['VAX_MANU'] = df_vaers['VAX_MANU'].fillna("").astype(str)
    
    df_mapped['original_name'] = df_mapped['original_name'].fillna("").astype(str)
    df_mapped['original_manu'] = df_mapped['original_manu'].fillna("").astype(str)

    # 2. Perform the Left Join
    # This keeps all original VAERS rows and attaches the VIOLIN data where it matches
    print("Merging data...")
    df_final = df_vaers.merge(
        df_mapped[['original_name', 'original_manu', 'violin_id', 'violin_name']], 
        how='left', 
        left_on=['VAX_NAME', 'VAX_MANU'], 
        right_on=['original_name', 'original_manu']
    )

    # 3. Clean up the dataframe (drop the redundant matching columns)
    df_final = df_final.drop(columns=['original_name', 'original_manu'])

    # Fix violin_id type (remove .0 but preserve NaN)
    df_final['violin_id'] = df_final['violin_id'].astype('Int64')

    # 4. Save the result
    df_final.to_csv(OUTPUT_FILE, index=False)
    print(f"✅ Success! Saved updated VAERS data to {OUTPUT_FILE}")

if __name__ == "__main__":
    merge_vaers_data()