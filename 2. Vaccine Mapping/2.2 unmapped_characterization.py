import os
import re
import pandas as pd

# =============================================================================
# CONFIGURATION
# =============================================================================

FULLY_MAPPED_FILE = "vaers_fully_mapped.csv"
OUTPUT_UNMAPPED_FULL = "unmapped_symptoms_full_characterized.csv"
OUTPUT_UNMAPPED_SUMMARY = "unmapped_symptoms_category_summary.csv"
OUTPUT_TOP_UNMAPPED = "top_unmapped_symptoms.csv"

SYM_COL = "SYM"
MEDDRA_COL = "MedDRA_ID"
MATCH_COL = "Match_Type"

TOP_N = 100


# =============================================================================
# CATEGORY RULES
# =============================================================================
# These are designed for VAERS/MedDRA preferred-term style symptom strings.
# They are intentionally broad because the goal is reviewer-facing characterization,
# not definitive clinical classification.

CATEGORY_PATTERNS = {
    "Administrative / Product-use / Immunization error": [
        r"\bmedication error\b",
        r"\bproduct\b",
        r"\bdevice\b",
        r"\bwrong\b",
        r"\bincorrect\b",
        r"\binappropriate\b",
        r"\binterchange\b",
        r"\bextra dose\b",
        r"\bunderdose\b",
        r"\boverdose\b",
        r"\bexpired\b",
        r"\bstorage\b",
        r"\blot number\b",
        r"\bneedle issue\b",
        r"\bpreparation error\b",
        r"\badministration error\b",
        r"\broute of administration\b",
        r"\bsite of administration\b",
        r"\bcontraindicated\b",
        r"\boff label\b",
        r"\bno adverse event\b",
        r"\bno adverse effect\b",
    ],

    "Diagnostic test / Laboratory / Investigation term": [
        r"\btest\b",
        r"\bassay\b",
        r"\bscreening\b",
        r"\bculture\b",
        r"\bserology\b",
        r"\btitre\b",
        r"\btiter\b",
        r"\bantibody\b",
        r"\bantigen\b",
        r"\bpcr\b",
        r"\bscan\b",
        r"\bx[\-\s]?ray\b",
        r"\bradiograph\b",
        r"\bultrasound\b",
        r"\bmagnetic resonance\b",
        r"\bmri\b",
        r"\bcomputed tomography\b",
        r"\bct\b",
        r"\belectrocardiogram\b",
        r"\becg\b",
        r"\bekg\b",
        r"\belectroencephalogram\b",
        r"\beeg\b",
        r"\binvestigation\b",
        r"\bbiopsy\b",
        r"\bblood .* increased\b",
        r"\bblood .* decreased\b",
        r"\b.* increased\b",
        r"\b.* decreased\b",
        r"\b.* positive\b",
        r"\b.* negative\b",
        r"\b.* abnormal\b",
        r"\b.* normal\b",
    ],

    "Medical procedure / Health-care encounter": [
        r"\bsurgery\b",
        r"\bsurgical\b",
        r"\boperation\b",
        r"\bprocedure\b",
        r"\bhospitalisation\b",
        r"\bhospitalization\b",
        r"\bemergency care\b",
        r"\bemergency room\b",
        r"\bemergency department\b",
        r"\bintubation\b",
        r"\bcatheter\b",
        r"\bdrainage\b",
        r"\bexcision\b",
        r"\bectomy\b",
        r"\btherapy\b",
        r"\btreatment\b",
        r"\btransfusion\b",
        r"\bvaccination\b",
        r"\bimmunisation\b",
        r"\bimmunization\b",
    ],

    "Exposure / Transmission / Circumstance term": [
        r"\bexposure\b",
        r"\bcontact with\b",
        r"\baccidental exposure\b",
        r"\boccupational exposure\b",
        r"\bmaternal exposure\b",
        r"\bpaternal exposure\b",
        r"\btransmission\b",
        r"\binfection source\b",
        r"\bcontamination\b",
        r"\bneedle stick\b",
        r"\banimal bite\b",
        r"\bfamily history\b",
        r"\bmedical history\b",
        r"\bsocial circumstance\b",
        r"\bpregnancy\b",
        r"\bfoetal\b",
        r"\bfetal\b",
    ],

    "Temporal / Severity / Qualifier term": [
        r"\bonset\b",
        r"\bduration\b",
        r"\brecurrence\b",
        r"\bcondition aggravated\b",
        r"\bdisease progression\b",
        r"\bdisease recurrence\b",
        r"\btherapeutic response\b",
        r"\bacute\b",
        r"\bchronic\b",
        r"\bintermittent\b",
        r"\bpersistent\b",
        r"\btransient\b",
        r"\bmild\b",
        r"\bmoderate\b",
        r"\bsevere\b",
    ],

    "Anatomical location / Local qualifier only": [
        r"^left\b",
        r"^right\b",
        r"^bilateral\b",
        r"\binjection site$",
        r"\bvaccination site$",
        r"\bapplication site$",
        r"\badministration site$",
        r"\bupper limb\b",
        r"\blower limb\b",
        r"\barm\b",
        r"\bleg\b",
    ],
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def clean_symptom_text(text):
    """
    Normalize symptom text for pattern-based categorization.
    This does NOT alter the original term stored in output.
    """
    if pd.isna(text):
        return ""
    text = str(text).strip().lower()
    text = text.replace("-", " ")
    text = re.sub(r"\s+", " ", text)
    return text


def categorize_unmapped_term(term):
    """
    Assign an unmapped symptom term to a broad category.
    """
    t = clean_symptom_text(term)

    if t == "":
        return "Blank / Missing"

    for category, patterns in CATEGORY_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, t):
                return category

    # Very short fragments are usually not interpretable
    if len(t) <= 3:
        return "Ambiguous / Too short"

    # Default bucket: could be genuine clinical terms not currently covered by OAE extraction
    return "Unmapped clinical phenotype / Potential OAE gap"


def load_fully_mapped_file():
    """
    Load the merged symptom-level dataset.
    """
    print(f"Loading {FULLY_MAPPED_FILE}...")

    try:
        df = pd.read_csv(FULLY_MAPPED_FILE, encoding="utf-8")
    except UnicodeDecodeError:
        df = pd.read_csv(FULLY_MAPPED_FILE, encoding="latin1")

    required_cols = [SYM_COL, MEDDRA_COL, MATCH_COL]
    missing = [c for c in required_cols if c not in df.columns]

    if missing:
        raise ValueError(f"Missing required columns in {FULLY_MAPPED_FILE}: {missing}")

    print(f"Loaded {len(df):,} symptom occurrences.")
    return df


def identify_unmapped_occurrences(df):
    """
    Identify unmapped rows.

    A row is considered unmapped if:
    - MedDRA_ID is missing, OR
    - Match_Type is 'Unmapped'
    """
    print("\nIdentifying unmapped symptom occurrences...")

    match_type = df[MATCH_COL].fillna("").astype(str).str.strip().str.lower()

    unmapped_mask = (
        df[MEDDRA_COL].isna()
        | match_type.eq("unmapped")
        | match_type.eq("")
    )

    df_unmapped_occ = df.loc[unmapped_mask].copy()
    df_mapped_occ = df.loc[~unmapped_mask].copy()

    total_occ = len(df)
    mapped_occ = len(df_mapped_occ)
    unmapped_occ = len(df_unmapped_occ)

    print(f"Total symptom occurrences:    {total_occ:,}")
    print(f"Mapped occurrences:           {mapped_occ:,} ({mapped_occ / total_occ * 100:.2f}%)")
    print(f"Unmapped occurrences:         {unmapped_occ:,} ({unmapped_occ / total_occ * 100:.2f}%)")

    total_unique = df[SYM_COL].dropna().nunique()
    mapped_unique = df_mapped_occ[SYM_COL].dropna().nunique()
    unmapped_unique = df_unmapped_occ[SYM_COL].dropna().nunique()

    print(f"\nTotal unique symptom strings: {total_unique:,}")
    print(f"Mapped unique strings:        {mapped_unique:,} ({mapped_unique / total_unique * 100:.2f}%)")
    print(f"Unmapped unique strings:      {unmapped_unique:,} ({unmapped_unique / total_unique * 100:.2f}%)")

    return df_unmapped_occ, df_mapped_occ


def build_unmapped_term_table(df_unmapped_occ):
    """
    Collapse unmapped occurrences into one row per unique symptom string.
    """
    print("\nBuilding unique unmapped term table...")

    unmapped_terms = (
        df_unmapped_occ
        .groupby(SYM_COL, dropna=False)
        .agg(
            occurrence_count=(SYM_COL, "size"),
            unique_vaers_cases=("VAERS_ID", "nunique")
        )
        .reset_index()
        .rename(columns={SYM_COL: "symptom_text"})
    )

    unmapped_terms["category"] = unmapped_terms["symptom_text"].apply(categorize_unmapped_term)

    unmapped_terms = unmapped_terms.sort_values(
        by="occurrence_count",
        ascending=False
    ).reset_index(drop=True)

    print(f"Unique unmapped terms: {len(unmapped_terms):,}")

    return unmapped_terms


def summarize_categories(unmapped_terms):
    """
    Summarize unmapped terms by broad category.
    """
    summary = (
        unmapped_terms
        .groupby("category")
        .agg(
            unique_terms=("symptom_text", "count"),
            total_occurrences=("occurrence_count", "sum"),
            total_vaers_cases=("unique_vaers_cases", "sum")
        )
        .reset_index()
    )

    total_unique = summary["unique_terms"].sum()
    total_occ = summary["total_occurrences"].sum()

    summary["pct_unique_terms"] = (summary["unique_terms"] / total_unique * 100).round(2)
    summary["pct_occurrences"] = (summary["total_occurrences"] / total_occ * 100).round(2)

    summary = summary.sort_values(
        by="total_occurrences",
        ascending=False
    ).reset_index(drop=True)

    return summary


def rarity_distribution(unmapped_terms):
    """
    Quantify how rare the unmapped strings are.
    """
    print("\nRarity distribution among unmapped unique strings:")

    total_unique = len(unmapped_terms)
    total_occ = unmapped_terms["occurrence_count"].sum()

    bins = {
        "appeared exactly 1 time": unmapped_terms["occurrence_count"].eq(1),
        "appeared ≤5 times": unmapped_terms["occurrence_count"].le(5),
        "appeared ≤10 times": unmapped_terms["occurrence_count"].le(10),
        "appeared ≤50 times": unmapped_terms["occurrence_count"].le(50),
    }

    for label, mask in bins.items():
        n_terms = mask.sum()
        n_occ = unmapped_terms.loc[mask, "occurrence_count"].sum()
        print(
            f"  Terms that {label}: "
            f"{n_terms:,}/{total_unique:,} unique terms "
            f"({n_terms / total_unique * 100:.2f}%), "
            f"{n_occ:,}/{total_occ:,} occurrences "
            f"({n_occ / total_occ * 100:.2f}%)"
        )


def print_top_examples(unmapped_terms, n=10):
    """
    Print top examples from each category for manual inspection.
    """
    print("\nTop examples by category:")

    categories = (
        unmapped_terms
        .groupby("category")["occurrence_count"]
        .sum()
        .sort_values(ascending=False)
        .index
        .tolist()
    )

    for cat in categories:
        subset = (
            unmapped_terms[unmapped_terms["category"] == cat]
            .sort_values("occurrence_count", ascending=False)
            .head(n)
        )

        print("\n" + "-" * 80)
        print(cat)
        print("-" * 80)

        for _, row in subset.iterrows():
            print(
                f"{int(row['occurrence_count']):>8,} occurrences | "
                f"{int(row['unique_vaers_cases']):>8,} cases | "
                f"{row['symptom_text']}"
            )


def print_paper_ready_text(df, df_unmapped_occ, unmapped_terms, summary):
    """
    Print concise statistics that can be dropped into the paper.
    """
    total_occ = len(df)
    unmapped_occ = len(df_unmapped_occ)

    total_unique = df[SYM_COL].dropna().nunique()
    unmapped_unique = len(unmapped_terms)

    rare_1 = unmapped_terms[unmapped_terms["occurrence_count"].eq(1)]
    rare_5 = unmapped_terms[unmapped_terms["occurrence_count"].le(5)]

    print("\n" + "=" * 100)
    print("PAPER-READY STATISTICS")
    print("=" * 100)

    print(
        f"Unmapped symptoms represented {unmapped_unique:,} of {total_unique:,} unique "
        f"symptom strings ({unmapped_unique / total_unique * 100:.2f}%) and "
        f"{unmapped_occ:,} of {total_occ:,} total symptom occurrences "
        f"({unmapped_occ / total_occ * 100:.2f}%)."
    )

    print(
        f"Among unmapped unique strings, {len(rare_1):,} "
        f"({len(rare_1) / unmapped_unique * 100:.2f}%) appeared only once, and "
        f"{len(rare_5):,} ({len(rare_5) / unmapped_unique * 100:.2f}%) appeared five "
        f"or fewer times."
    )

    print("\nCategory summary:")
    for _, row in summary.iterrows():
        print(
            f"- {row['category']}: {int(row['unique_terms']):,} unique terms "
            f"({row['pct_unique_terms']:.2f}%), "
            f"{int(row['total_occurrences']):,} occurrences "
            f"({row['pct_occurrences']:.2f}%)."
        )

    # Optional concise sentence template
    print("\nSuggested manuscript sentence:")
    print(
        "Preliminary characterization of unmapped symptom strings showed that many "
        "represented low-frequency terms, administrative/product-use concepts, diagnostic "
        "test or procedure terms, exposure/circumstance descriptors, or MedDRA concepts not "
        "yet represented in the extracted OAE dictionary, rather than common high-volume "
        "clinical phenotypes."
    )


# =============================================================================
# MAIN
# =============================================================================

def main():
    df = load_fully_mapped_file()

    df_unmapped_occ, df_mapped_occ = identify_unmapped_occurrences(df)

    unmapped_terms = build_unmapped_term_table(df_unmapped_occ)

    summary = summarize_categories(unmapped_terms)

    print("\nUnmapped category summary:")
    print(summary.to_string(index=False))

    rarity_distribution(unmapped_terms)

    print_top_examples(unmapped_terms, n=10)

    print_paper_ready_text(df, df_unmapped_occ, unmapped_terms, summary)

    # Save outputs
    unmapped_terms.to_csv(OUTPUT_UNMAPPED_FULL, index=False)
    summary.to_csv(OUTPUT_UNMAPPED_SUMMARY, index=False)
    unmapped_terms.head(TOP_N).to_csv(OUTPUT_TOP_UNMAPPED, index=False)

    print("\nSaved outputs:")
    print(f"  Full characterized unmapped terms: {OUTPUT_UNMAPPED_FULL}")
    print(f"  Category summary:                 {OUTPUT_UNMAPPED_SUMMARY}")
    print(f"  Top {TOP_N} unmapped symptoms:     {OUTPUT_TOP_UNMAPPED}")


if __name__ == "__main__":
    main()