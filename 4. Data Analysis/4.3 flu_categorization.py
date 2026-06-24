import pandas as pd

# --- CONFIGURATION ---
VACCINES_FILE = "vaers_with_violin_ids_1.csv"
OUTPUT_FILE = "vaers_flu_categorized.csv"

def categorize_flu(row):
    name = str(row['VAX_NAME']).upper()
    vax_type = str(row['VAX_TYPE']).upper()
    violin_name = str(row['violin_name']).upper()
    
    # 1. Catch and drop the bacterial 'Hib' trap
    if 'HIB' in name or 'HIB' in vax_type or 'HAEMOPHILUS' in violin_name:
        return 'DROP - Bacterial'
        
    # 2. Recombinant (Protein)
    if '(FLUBLOK)' in name:
        return 'Recombinant (RIV)'
        
    # 3. Live Attenuated (Fixed the FLUENZ trap by adding parentheses!)
    if '(FLUMIST)' in name or '(FLUENZ)' in name or vax_type == 'FLUN' or vax_type == 'FLUN3' or vax_type == 'FLUN4':
        return 'Live Attenuated (LAIV)'
        
    # 4. Cell-Cultured
    if '(FLUCELVAX)' in name or '(OPTAFLU)' in name or vax_type == 'FLUC3' or vax_type == 'FLUC4':
        return 'Cell-Cultured Inactivated (ccIIV)'
        
    # 5. Adjuvanted
    if '(FLUAD)' in name or vax_type == 'FLUA3' or vax_type == 'FLUA4':
        return 'Adjuvanted Inactivated (aIIV)'
        
    # 6. High-Dose
    if 'HIGH-DOSE' in name or vax_type == 'FLUHD':
        return 'High-Dose Inactivated (HD-IIV)'
        
    # 7. Standard Inactivated 
    # Must be placed LAST so it catches the remaining generic flu shots
    if 'FLU' in name or 'FLU' in vax_type or 'H1N1' in name or 'H5N1' in name:
        return 'Standard Inactivated (IIV)'
        
    return 'DROP - Non-Flu'

def build_flu_dataset():
    print("Loading mapped vaccines...")
    df = pd.read_csv(VACCINES_FILE, low_memory=False)
    
    print("Categorizing vaccines based on Ontology parent classes...")
    df['Flu_Category'] = df.apply(categorize_flu, axis=1)
    
    # Filter out the non-flu and bacterial records
    df_flu_only = df[~df['Flu_Category'].str.contains('DROP')].copy()
    
    print(f"\n✅ Total Viral Flu Vaccines retained: {len(df_flu_only):,}")
    
    # Show the breakdown of our new categories
    breakdown = df_flu_only['Flu_Category'].value_counts()
    print("\n=== FLU VACCINE ONTOLOGY CATEGORIES ===")
    for category, count in breakdown.items():
        print(f"{category}: {count:,}")
        
    # Save the new flu-only dataset
    df_flu_only.to_csv(OUTPUT_FILE, index=False)
    print(f"\nSaved categorized flu dataset to {OUTPUT_FILE}")

if __name__ == "__main__":
    build_flu_dataset()