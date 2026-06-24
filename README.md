# Vaxafe: An Ontology-Driven Semantic Integration Platform for Precision Vaccine Safety Surveillance

Vaxafe is a web-accessible platform that maps VAERS (Vaccine Adverse Event Reporting System) reports to the Vaccine Ontology (VO) and the Ontology of Adverse Events (OAE), enabling ontology-backed pharmacovigilance signal detection.

**Live Platform:** [https://violinet.org/vaxafe/](https://violinet.org/vaxafe/)

**Paper:** Yeh FY, Zheng J, He YO. Vaxafe: An Ontology-Driven Semantic Integration Platform for Precision Vaccine Safety Surveillance. *AMIA 2026 Annual Symposium* (submitted).

---

## Overview

Post-marketing vaccine safety monitoring relies on spontaneous reporting systems where semantic heterogeneity and unstructured clinical text can obscure safety signals. Vaxafe addresses this by:

1. **Generic Fallback Generation** — Creating parent-level vaccine entries for ambiguous reports lacking specific product information
2. **Vaccine Formulation Mapping** — Mapping heterogeneous VAERS vaccine records to VIOLIN database entries and VO using heuristic scoring and LLM-assisted curation
3. **Adverse Event Mapping** — Mapping VAERS symptom strings to OAE using a three-pass pipeline with guarded fuzzy matching
4. **Statistical Signal Detection** — Computing disproportionality metrics (PRR, Chi-square, EBGM) for vaccine–adverse event pairs

The system processed 2.28 million VAERS records, recovered 30.9% of ambiguous reports via generic fallback routing, and achieved 71.32% semantic coverage across symptom occurrences.

---

## Repository Structure

```
Vaxafe/
├── 1. General Vaccine/          # Phase I: Generic fallback entry generation
│   ├── 1.0 pathogen_vaccine_generation.py   # LLM classification of pathogens
│   ├── 1.2 t_vaccine_fill.py               # LLM assignment of vaccine type/description
│   ├── 1.3 sql_generation.py               # SQL generation for VIOLIN database import
│   └── t_pathogen.csv                       # Input: VIOLIN pathogen table export
│
├── 2. Vaccine Mapping/          # Phase II: VAERS vaccine → VIOLIN/VO mapping
│   ├── 2.1 vaccine_mapping_ai.py           # Heuristic scoring + LLM curator mapping
│   ├── 2.2 unmapped_characterization.py    # Characterization of unmapped terms
│   ├── 2.3 vaccine_mapping_merge.py        # Merge mapped IDs back onto VAERS dataset
│   ├── t_vaccine.csv                        # Input: VIOLIN vaccine table export
│   ├── unique_vaccines.xlsx                 # Input: unique VAERS vaccine name/manufacturer pairs
│   ├── unique_vaccines_mapped_final.xlsx    # Output: mapping results
│   └── vaers_fully_mapped.csv               # Output: VAERS records with VIOLIN IDs
│
├── 3. Adverse Event Mapping/    # Phase III: VAERS symptoms → OAE mapping
│   ├── 3.1 ae_meddra_mapping.py            # Three-pass mapping (exact, word-swap, guarded fuzzy)
│   ├── 3.2 ae_merge.py                     # Merge mapped OAE IDs onto full VAERS symptom file
│   ├── ad.csv                               # Input: OAE adverse event concepts from Ontobee
│   ├── unique_symptoms.xlsx                 # Input: unique VAERS symptom strings
│   └── vaers_data_sym_202602161641.csv      # Input: raw VAERS symptom file
│
├── 4. Data Analysis/            # Use case: GBS signal detection in influenza vaccines
│   ├── 4.1 flu_use_case.py                 # Extract influenza vaccine subset
│   ├── 4.2 isolate_flu.py                  # Isolate flu-specific VAERS records
│   ├── 4.3 flu_categorization.py           # VO-based formulation categorization
│   ├── 4.4 stat_analysis_output_clean.py   # Disproportionality analysis pipeline
│   ├── 4.5 gbs_stats.py                    # GBS-specific statistical analysis
│   ├── 4.6 nervous_system_ae_stats.py      # Broad neurological signal detection
│   └── [output files]                       # Analysis results and intermediate files
│
└── README.md
```

---

## Pipeline Execution Order

### Phase I: Generic Fallback Entry Generation

```bash
cd "1. General Vaccine"
python "1.0 pathogen_vaccine_generation.py"   # Classify pathogens → retain human-infectious
python "1.2 t_vaccine_fill.py"               # Assign vaccine type + description
python "1.3 sql_generation.py"               # Generate SQL for VIOLIN database import
```

### Phase II: Vaccine Formulation Mapping

```bash
cd "2. Vaccine Mapping"
python "2.1 vaccine_mapping_ai.py"           # Map VAERS vaccines → VIOLIN entries
python "2.3 vaccine_mapping_merge.py"        # Merge mappings onto full VAERS dataset
python "2.2 unmapped_characterization.py"    # Characterize unmapped terms (optional)
```

### Phase III: Adverse Event Mapping

```bash
cd "3. Adverse Event Mapping"
python "3.1 ae_meddra_mapping.py"            # Three-pass OAE mapping
python "3.2 ae_merge.py"                     # Merge onto full VAERS symptom file
```

### Phase IV: Data Analysis (Use Case)

```bash
cd "4. Data Analysis"
python "4.1 flu_use_case.py"
python "4.2 isolate_flu.py"
python "4.3 flu_categorization.py"
python "4.4 stat_analysis_output_clean.py"
python "4.5 gbs_stats.py"
python "4.6 nervous_system_ae_stats.py"
```

---

## Requirements

### Dependencies

```
pandas
rapidfuzz
langchain-openai
python-dotenv
openpyxl
tqdm
```

### Environment Variables

Create a `.env` file with your Azure OpenAI credentials (This is following the UMich api format):

```env
DEPLOYMENT=<your-deployment-name>
API_VERSION=2025-04-01-preview
API_KEY=<your-api-key>
ENDPOINT=<your-azure-endpoint>
ORGANIZATION=<your-organization>
```

### Data Files

Large data files (`.csv`, `.xlsx`) are not included in this repository due to size constraints. Required input data:

| File | Source | Description |
|------|--------|-------------|
| `t_pathogen.csv` | VIOLIN database export | Pathogen table with pathogen name, disease, host range |
| `t_vaccine.csv` | VIOLIN database export | Vaccine table with name, brand, manufacturer, description |
| `vaers_data_sym_202602161641.csv` | VAERS download | Raw VAERS symptom data (processed as of June 28, 2024) |
| `ad.csv` | SPARQL extraction from Ontobee | OAE adverse event concepts with labels, synonyms, MedDRA IDs |
| `unique_vaccines.xlsx` | Extracted from VAERS | Unique vaccine name/manufacturer pairs |
| `unique_symptoms.xlsx` | Extracted from VAERS | Unique symptom strings |

---

## Key Methods

### LLM Configuration

- **Model:** GPT-4.1 via Azure OpenAI
- **API Version:** `2025-04-01-preview`
- **Temperature:** 0 (deterministic output)
- **Usage:** Pathogen classification, vaccine type assignment, vaccine formulation mapping

### Adverse Event Mapping Pipeline

- **Pass 1:** Exact match against OAE labels and synonyms
- **Pass 2:** Token-sort matching for word-order variants (e.g., `"pain injection site"` ↔ `"injection site pain"`)
- **Pass 3:** Guarded fuzzy matching with clinical conflict matrix to prevent unsafe matches (e.g., blocking `"increased"` ↔ `"decreased"`)

### Statistical Signal Detection

- Proportional Reporting Ratio (PRR)
- Chi-square statistic (with Yates' continuity correction)
- Empirical Bayes Geometric Mean (EBGM)
- Signal thresholds: N ≥ 3, frequency > 0.2%, PRR > 2.0, χ² > 4.0, EBGM > 2.0

---

## Citation

If you use Vaxafe or this codebase in your research, please cite:

```
To be updated
```

---

## Contact

- **Feng-Yu (Leo) Yeh** — leofye@umich.edu
- **Yongqun Oliver He** (Corresponding Author) — yongqunh@umich.edu
- University of Michigan Medical School, Ann Arbor, MI, USA