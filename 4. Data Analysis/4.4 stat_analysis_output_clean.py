import pandas as pd
import re

# --- CONFIGURATION ---
INPUT_FILE = 'flu_stat_analysis_OUTPUT2.html'
OUTPUT_FILE = 'flu_parsed_significant_signals2.csv'

def parse_html_results():
    print(f"Loading raw HTML results from {INPUT_FILE}...")
    
    with open(INPUT_FILE, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    blocks = content.split("Below are the results of statistically significant AEs associated with:")
    
    data_rows = []
    
    print("Parsing blocks and cleaning HTML...")
    for block in blocks[1:]: 
        vax_name = block.split("<br/>")[0].strip()
        clean_text = re.sub(r'<[^>]+>', '\n', block)
        lines = clean_text.split('\n')
        
        for line in lines:
            line = line.strip()
            
            # CHANGED: We now need to check for at least 14 underscores
            if line.count('_') >= 14 and not line.startswith('AE _'):
                
                # CHANGED: Split from the right 14 times to account for the 4 new cells
                parts = line.rsplit('_', 14)
                
                row = [vax_name] + parts
                data_rows.append(row)

    # CHANGED: Added the 4 new cell columns to our dataframe structure
    columns = [
        'VAX_NAME', 'Adverse_Event', 'Case_Count', 'PRR', 'Percentage', 
        'Chi_Squared', 'Significance_1', 'Female_Count', 'Male_Count', 
        'Female_Total', 'Male_Total', 'Cell_A', 'Cell_B', 'Cell_C', 'Cell_D', 'Significance_2'
    ]
    df = pd.DataFrame(data_rows, columns=columns)
    
    # Filter for ONLY statistically significant signals
    df_significant = df[df['Significance_1'].str.upper() == 'YES'].copy()
    
    # Clean up numbers (convert string to floats/ints for Pandas)
    numeric_columns = ['Case_Count', 'PRR', 'Chi_Squared', 'Cell_A', 'Cell_B', 'Cell_C', 'Cell_D']
    for col in numeric_columns:
        df_significant[col] = pd.to_numeric(df_significant[col], errors='coerce')
    
    # Sort by the highest PRR signal per vaccine
    df_significant = df_significant.sort_values(by=['VAX_NAME', 'PRR'], ascending=[True, False])
    
    # Save the final file
    df_significant.to_csv(OUTPUT_FILE, index=False)
    
    print("\n=== PARSING COMPLETE ===")
    print(f"Total Rows Extracted: {len(df):,}")
    print(f"Significant 'YES' Signals Kept: {len(df_significant):,}")
    print(f"Saved clean file to: {OUTPUT_FILE}")

if __name__ == "__main__":
    parse_html_results()