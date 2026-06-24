import pandas as pd

# --- CONFIGURATION ---
INPUT_FILE = 'flu_parsed_significant_signals2.csv'
OUTPUT_FILE = 'final_ontology_summary.csv'

# 1. Map VAERS trade names to the Professor's 3 Ontology Categories
def map_to_professor_categories(vax_name):
    name = str(vax_name).upper()
    
    if 'UNKNOWN' in name or 'FOREIGN' in name or 'NO BRAND' in name:
        return 'DROP'
    if 'FLUBLOK' in name:
        return 'Protein (Recombinant)'
    if 'FLUMIST' in name or '(FLUENZ)' in name or 'MEDIMMUNE' in name or '(FLUENZ TETRA)' in name:
        return 'Live Attenuated'
    if 'FLU' in name or 'H1N1' in name: 
        return 'Inactivated'
        
    return 'DROP'

def generate_report():
    print(f"Loading {INPUT_FILE}...")
    df = pd.read_csv(INPUT_FILE)
    
    # Apply the ontology mapping
    df['Ontology_Category'] = df['VAX_NAME'].apply(map_to_professor_categories)
    df = df[df['Ontology_Category'] != 'DROP'].copy()
    
    # Clean numeric columns
    df['Case_Count'] = pd.to_numeric(df['Case_Count'], errors='coerce')
    df['PRR'] = pd.to_numeric(df['PRR'], errors='coerce')
    df['Chi_Squared'] = pd.to_numeric(df['Chi_Squared'], errors='coerce')
    
    # --- ADD THE TOTAL CASES MATH ---
    df['Cell_A'] = pd.to_numeric(df['Cell_A'], errors='coerce')
    df['Cell_C'] = pd.to_numeric(df['Cell_C'], errors='coerce')
    df['Total_Cases'] = df['Cell_A'] + df['Cell_C']
    
    # --- FIND GBS SIGNALS ---
    gbs_mask = df['Adverse_Event'].str.contains('Guillain', case=False, na=False)
    df_gbs = df[gbs_mask].copy()
    
    # Keep individual vaccines, just sort them
    df_gbs = df_gbs.sort_values(['Ontology_Category', 'PRR'], ascending=[True, False])
    df_gbs['Report_Group'] = 'Targeted Focus: GBS'
    
    # --- FIND TOP OTHER SIGNALS ---
    df_others = df[~gbs_mask].copy()
    
    # Sort by PRR and grab the top 3 highest signals for each category
    top_others = df_others.sort_values(['Ontology_Category', 'PRR'], ascending=[True, False])
    top_others = top_others.groupby('Ontology_Category').head(3).copy()
    top_others['Report_Group'] = 'Top Category Signals'
    
    # Combine the GBS findings with the Top Other findings
    final_report = pd.concat([df_gbs, top_others])
    
    # --- FORMAT EXACTLY AS REQUESTED ---
    columns_to_keep = [
        'Ontology_Category', 'Report_Group', 'Adverse_Event', 
        'VAX_NAME', 'Case_Count', 'Total_Cases', 'PRR', 'Chi_Squared'
    ]
    final_report = final_report[columns_to_keep]
    
    # Save for Excel formatting
    final_report.to_csv(OUTPUT_FILE, index=False)
    
    print("\n=== SCRIPT COMPLETE ===")
    print(f"Saved to: {OUTPUT_FILE}")
    print("\nPreview of the first few rows:")
    print(final_report.head(3).to_string(index=False))

if __name__ == "__main__":
    generate_report()