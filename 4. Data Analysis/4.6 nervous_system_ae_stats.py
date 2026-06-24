import pandas as pd

# --- CONFIGURATION ---
INPUT_FILE = 'flu_parsed_significant_signals2.csv' # Make sure to use the file WITH the Cell columns!

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

# 1. Add the abnormal tests explicitly to our positive list
NEURO_KEYWORDS = [
    'guillain', 'palsy', 'seizure', 'syncope', 'neuropath', 
    'hallucination', 'encephalitis', 'encephalopathy', 'myelitis', 
    'ataxia', 'tremor', 'paralysis', 'paresis', 'dizziness', 
    'headache', 'somnolence', 'neuralgia', 'convulsion', 'lethargy', 
    'narcolepsy', r'\btic\b', r'\btics\b', 'cognitive', 'delirium', 
    'amnesia', 'dyskinesia', 'hypoesthesia',
    'electroencephalogram abnormal', 'magnetic resonance imaging brain abnormal'
]

# 2. Use word boundaries so we ONLY drop the exact word "normal" 
EXCLUDE_KEYWORDS = [
    r'\bnormal\b', 'uncomplicated', 'negative'
]

def find_validated_neuro_clusters():
    print(f"Loading {INPUT_FILE}...\n")
    df = pd.read_csv(INPUT_FILE)
    
    # Apply Categories
    df['Ontology_Category'] = df['VAX_NAME'].apply(map_to_professor_categories)
    df = df[df['Ontology_Category'] != 'DROP']
    
    # Convert string numbers to floats
    df['Case_Count'] = pd.to_numeric(df['Case_Count'], errors='coerce')
    df['PRR'] = pd.to_numeric(df['PRR'], errors='coerce')
    df['Chi_Squared'] = pd.to_numeric(df['Chi_Squared'], errors='coerce')
    
    # --- NEW: CALCULATE TOTAL CASES BEFORE GROUPING ---
    df['Cell_A'] = pd.to_numeric(df['Cell_A'], errors='coerce')
    df['Cell_C'] = pd.to_numeric(df['Cell_C'], errors='coerce')
    df['Total_Cases'] = df['Cell_A'] + df['Cell_C']
    
    # APPLY YOUR VALIDATION CRITERIA (Cases >= 10, PRR >= 2, Chi-Squared >= 4)
    df_valid = df[
        (df['Case_Count'] >= 10) & 
        (df['PRR'] >= 2.0) & 
        (df['Chi_Squared'] >= 4.0)
    ].copy()
    
    # Filter FOR Neurological terms
    pattern = '|'.join(NEURO_KEYWORDS)
    neuro_mask = df_valid['Adverse_Event'].str.contains(pattern, case=False, na=False)
    df_neuro = df_valid[neuro_mask].copy()
    
    # Filter OUT the hospital tests and normal results
    exclude_pattern = '|'.join(EXCLUDE_KEYWORDS)
    exclude_mask = df_neuro['Adverse_Event'].str.contains(exclude_pattern, case=False, na=False)
    df_neuro = df_neuro[~exclude_mask]
    
    # Group by Category and AE to remove duplicates
    grouped = df_neuro.groupby(['Ontology_Category', 'Adverse_Event']).agg({
        'PRR': 'max',
        'Case_Count': 'sum',
        'Total_Cases': 'sum', # --- NEW: AGGREGATE THE TOTAL CASES ---
        'Chi_Squared': 'max'
    }).reset_index()
    
    # Sort by PRR (highest to lowest)
    grouped = grouped.sort_values(by=['Ontology_Category', 'PRR'], ascending=[True, False])
    
    print("=== TOP 15 VALIDATED NEUROLOGICAL SIGNALS BY CATEGORY ===")
    print("(Filtered: Cases >= 10, PRR >= 2, Chi-Square >= 4)\n")
    
    for category in grouped['Ontology_Category'].unique():
        all = grouped[grouped['Ontology_Category'] == category]
        
        print(f">> {category.upper()} (Total Validated Neuro AEs: {len(grouped[grouped['Ontology_Category'] == category])})")
        
        for index, row in all.iterrows():
            # --- NEW: PRINT THE TOTAL CASES ---
            print(f"   - {row['Adverse_Event']} (Cases: {int(row['Case_Count'])} / Total: {int(row['Total_Cases'])}, PRR: {row['PRR']:.2f}), Chi-Squared: {row['Chi_Squared']:.2f}")
        print()

if __name__ == "__main__":
    find_validated_neuro_clusters()