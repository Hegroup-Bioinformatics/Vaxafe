import os
import json
import pandas as pd
from dotenv import load_dotenv
from tqdm import tqdm

from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()

# --- CONFIGURATION ---
INPUT_FILE = "human_generic_vaccines.csv"
OUTPUT_FILE = "t_vaccine_import_ready.csv"

# The exact target columns for your mass import
TARGET_COLUMNS = [
    "c_vaccine_id", "c_vaccine_name", "c_type", "c_is_combination_vaccine", 
    "c_description", "c_adjuvant", "c_storage", "c_pathogen_id", "c_virulence", 
    "c_preparation", "c_brand_name", "c_full_text", "c_antigen", "c_curation_flag", 
    "c_vector", "c_proper_name", "c_manufacturer", "c_contraindication", "c_status", 
    "c_location_licensed", "c_host_species", "c_route", "c_vo_id", "c_usage_age", 
    "c_model_host", "c_preservative", "c_allergen", "c_preparation_vo_id", 
    "c_host_species2", "c_cvx_code", "c_cvx_desc"
]

# The strict list of permitted vaccine types
ALLOWED_TYPES = [
    "Live, attenuated vaccine", "Inactivated or \"killed\" vaccine", "Toxoid vaccine", 
    "Subunit vaccine", "Conjugate vaccine", "DNA vaccine", "Recombinant vector vaccine", 
    "Prime-boost vaccine with DNA vaccine priming", "Cocktail vaccine"
]

def main():
    print(f"--- Loading {INPUT_FILE} ---")
    try:
        df_input = pd.read_csv(INPUT_FILE)
    except Exception as e:
        print(f"Error loading file: {e}")
        return

    # Initialize the LLM
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

    # The AI Prompt to determine Type and Description
    prompt = ChatPromptTemplate.from_template("""
    You are a clinical data curator for the VIOLIN Vaccine Database.
    
    === VACCINE INFO ===
    Target Disease/Pathogen: "{disease_or_pathogen}"
    Generic Name: "{vaccine_name}"

    === TASK ===
    1. Identify the MOST PREVALENT historically licensed human vaccine type for this disease. 
       You MUST choose exactly one from this list: {allowed_types}. 
       If multiple major types exist (like COVID-19 having mRNA and vector), choose "Cocktail vaccine" or specify "Other: [Your Type]".
    2. Write a 1-2 sentence clinical description for this generic category.
       Example: "A generic representation of vaccines utilized to prevent COVID-19 infection in humans."

    === OUTPUT FORMAT ===
    Return a valid JSON object:
    {{
        "c_type": "The exact type string",
        "c_description": "The 1-2 sentence description"
    }}
    """)

    chain = prompt | llm
    import_rows = []

    print(f"\n--- Generating Import Data ({len(df_input)} items) ---")
    for index, row in tqdm(df_input.iterrows(), total=len(df_input)):
        vac_name = str(row['c_vaccine_name'])
        disease = str(row.get('original_disease', ''))
        pathogen = str(row.get('original_pathogen', ''))
        target_context = disease if disease and disease != 'nan' else pathogen

        try:
            # Get AI predictions
            res = chain.invoke({
                "disease_or_pathogen": target_context,
                "vaccine_name": vac_name,
                "allowed_types": ALLOWED_TYPES
            })
            
            content = res.content.replace("```json", "").replace("```", "").strip()
            data = json.loads(content)
            
            # Map the exact schema row
            db_row = {col: "" for col in TARGET_COLUMNS} # Fill all with blanks by default
            
            db_row["c_vaccine_id"] = f"GEN_{index + 1000}"  # Temporary unique ID for import
            db_row["c_vaccine_name"] = vac_name
            db_row["c_type"] = data.get("c_type", "Unknown")
            db_row["c_is_combination_vaccine"] = "No" 
            db_row["c_description"] = data.get("c_description", "")
            db_row["c_pathogen_id"] = row.get("c_pathogen_id_link", "")
            db_row["c_brand_name"] = "Generic"
            db_row["c_curation_flag"] = "0"  # 0 usually implies 'needs expert review'
            db_row["c_manufacturer"] = "Unknown"
            db_row["c_status"] = "Licensed"
            db_row["c_host_species"] = "Human"
            
            import_rows.append(db_row)
            
        except Exception as e:
            print(f"\nError processing {vac_name}: {e}")

    # Save the strictly formatted output
    if import_rows:
        df_import = pd.DataFrame(import_rows, columns=TARGET_COLUMNS)
        df_import.to_csv(OUTPUT_FILE, index=False)
        print(f"\n✅ Done! Saved {len(df_import)} import-ready rows to {OUTPUT_FILE}")
    else:
        print("\n⚠️ No rows generated.")

if __name__ == "__main__":
    main()