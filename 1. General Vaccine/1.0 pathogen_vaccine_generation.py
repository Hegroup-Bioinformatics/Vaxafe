import os
import json
import pandas as pd
from dotenv import load_dotenv
from tqdm import tqdm

from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()

# --- CONFIGURATION ---
INPUT_FILE = "t_pathogen.csv"
OUTPUT_FILE = "human_generic_vaccines.csv"

# Limit for testing so you don't burn tokens on the whole file at once
# TEST_LIMIT = 20 

def main():
    print(f"--- Loading {INPUT_FILE} ---")
    try:
        # Sometimes these DB exports are tab-separated. If so, add sep='\t'
        df_pathogen = pd.read_csv(INPUT_FILE)
    except Exception as e:
        print(f"Error loading file: {e}")
        return

    # 1. Initialize the LLM (Using your existing Azure setup)
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

    # 2. The Clinical Curator Prompt
    prompt = ChatPromptTemplate.from_template("""
    You are a senior biomedical ontology curator for the VIOLIN Vaccine Database.
    Your task is to determine whether the input refers to a true human infectious disease caused by a pathogen, and if so, generate a standardized disease name and a generic vaccine label.
    You must be conservative. If uncertain, classify as NOT human infectious.

    === INPUT RECORD ===

    Pathogen Name: “{pathogen}”
    Disease Name: “{disease}”
    Host Range Context: “{host}”

    === CLASSIFICATION RULES ===

    Step 1 — Determine Category

    The entry MUST be classified into ONE of the following:

    A. Human infectious pathogen (virus, bacterium, parasite, fungus that infects humans)
    B. Animal-only infectious pathogen (no human infection)
    C. Plant pathogen
    D. Gene / protein / toxin / antigen
    E. Vaccine product / drug / experimental platform
    F. Non-infectious disease (autoimmune, cancer, metabolic, genetic, cardiovascular, etc.)
    G. Lab strain / accession number / subtype only
    H. General term / vague term
    I. Invalid / placeholder / non-biomedical

    Only Category A qualifies as “is_human = true”.

    ⸻

    Step 2 — Human Infectious Criteria

    Mark as human ONLY IF:

    • It is a recognized human pathogen
    • It causes a human infectious disease
    • A human vaccine would biologically make clinical sense

    Mark as NOT human if:

    • It is exclusively animal (e.g., swine, bovine, avian, equine)
    • It is a gene, protein, toxin, peptide, or antigen
    • It is a vaccine candidate or product code
    • It is a lab strain (e.g., PAO1, NTUH K-2044)
    • It is autoimmune, cancer, metabolic, addiction, thrombosis, etc.
    • It is a general term like “Parasites” or “Infectious disease”
    • It is clearly a test/placeholder entry

    When in doubt → return false.

    ⸻

    Step 3 — Standard Disease Name (ONLY if human infectious)

    If Category A:

    • Convert pathogen name to standard clinical disease name
    • Use the commonly accepted human disease terminology
    • Normalize capitalization
    • Avoid repeating “virus infection” unless necessary

    Examples:
        •	SARS-CoV-2 → COVID-19
        •	Respiratory syncytial virus → Respiratory syncytial virus infection
        •	Treponema pallidum → Syphilis
        •	Plasmodium falciparum → Malaria
        •	Mycobacterium tuberculosis → Tuberculosis

    ⸻

    Step 4 — Vaccine String

    If human infectious:

    generic_vaccine_name = “licensed [standard_disease] human vaccine”

    If not human infectious:

    standard_disease = null
    generic_vaccine_name = null

    ⸻

    === OUTPUT FORMAT ===

    Return ONLY valid JSON (no markdown, no commentary):

    {{
    “category”: “A-I”,
    “is_human”: true or false,
    “standard_disease”: “Standardized disease name” or null,
    “generic_vaccine_name”: “licensed [disease] human vaccine” or null,
    “rationale”: “One concise sentence explaining the classification.”
    }}
    """)

    chain = prompt | llm
    
    # if TEST_LIMIT:
    #     print(f"--- Limiting to first {TEST_LIMIT} rows for testing ---")
    #     df_pathogen = df_pathogen.head(TEST_LIMIT)

    results = []
    
    print(f"\n--- Starting AI Pathogen Triage ({len(df_pathogen)} items) ---")
    for index, row in tqdm(df_pathogen.iterrows(), total=len(df_pathogen)):
        pathogen = str(row.get('c_pathogen_name', '')).strip()
        disease = str(row.get('c_disease_name', '')).strip()
        host = str(row.get('c_host_range', '')).strip()
        path_id = row.get('c_pathogen_id')

        # Skip rows that are completely blank
        if pd.isna(pathogen) and pd.isna(disease) or (pathogen == 'nan' and disease == 'nan'):
            continue

        try:
            # Ask the AI to evaluate the pathogen
            res = chain.invoke({
                "pathogen": pathogen,
                "disease": disease,
                "host": host
            })
            
            # Parse JSON safely
            content = res.content.replace("```json", "").replace("```", "").strip()
            data = json.loads(content)
            
            # Keep the data ONLY if the AI decided it was a human pathogen
            if data.get("is_human"):
                results.append({
                    "c_pathogen_id_link": path_id,
                    "c_vaccine_name": data.get("generic_vaccine_name"),
                    "c_brand_name": "Generic",
                    "c_manufacturer": "Unknown",
                    "original_pathogen": pathogen,
                    "original_disease": disease,
                    "ai_rationale": data.get("rationale")
                })
                
        except Exception as e:
            print(f"\nError on pathogen ID {path_id}: {e}")

    # 3. Save Results
    if results:
        df_results = pd.DataFrame(results)
        df_results.to_csv(OUTPUT_FILE, index=False)
        print(f"\n✅ Done! Successfully generated {len(df_results)} human generic vaccines. Saved to {OUTPUT_FILE}")
    else:
        print("\n⚠️ No human pathogens were identified in this batch.")

if __name__ == "__main__":
    main()