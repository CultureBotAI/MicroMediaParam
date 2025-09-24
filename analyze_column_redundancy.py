#!/usr/bin/env python3
"""
Analyze the redundancy between mapped and base_chebi_id columns
and clarify their intended purposes.
"""

import pandas as pd
import argparse
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def analyze_column_redundancy(input_file):
    """Analyze redundancy between mapped and base_chebi_id columns."""
    
    logger.info(f"Loading file: {input_file}")
    df = pd.read_csv(input_file, sep='\t')
    
    logger.info(f"Dataset shape: {df.shape}")
    
    # Analyze the two columns
    total_rows = len(df)
    
    # 1. Check for missing values
    mapped_missing = df['mapped'].isna().sum()
    base_chebi_missing = df['base_chebi_id'].isna().sum()
    
    logger.info(f"\nMissing values analysis:")
    logger.info(f"  mapped column missing: {mapped_missing:,} ({mapped_missing/total_rows*100:.1f}%)")
    logger.info(f"  base_chebi_id missing: {base_chebi_missing:,} ({base_chebi_missing/total_rows*100:.1f}%)")
    
    # 2. Check for empty strings
    mapped_empty = (df['mapped'] == '').sum()
    base_chebi_empty = (df['base_chebi_id'] == '').sum()
    
    logger.info(f"  mapped column empty: {mapped_empty:,}")
    logger.info(f"  base_chebi_id empty: {base_chebi_empty:,}")
    
    # 3. Analyze content types
    logger.info(f"\nContent type analysis:")
    
    # Count different ID types in mapped column
    mapped_chebi = df['mapped'].str.startswith('CHEBI:', na=False).sum()
    mapped_pubchem = df['mapped'].str.startswith('PubChem:', na=False).sum()
    mapped_cas = df['mapped'].str.startswith('CAS-RN:', na=False).sum()
    mapped_solution = df['mapped'].str.startswith('solution:', na=False).sum()
    mapped_ingredient = df['mapped'].str.startswith('ingredient:', na=False).sum()
    mapped_other = len(df) - mapped_missing - mapped_empty - mapped_chebi - mapped_pubchem - mapped_cas - mapped_solution - mapped_ingredient
    
    logger.info(f"  mapped column content:")
    logger.info(f"    CHEBI: {mapped_chebi:,} ({mapped_chebi/total_rows*100:.1f}%)")
    logger.info(f"    PubChem: {mapped_pubchem:,} ({mapped_pubchem/total_rows*100:.1f}%)")
    logger.info(f"    CAS-RN: {mapped_cas:,} ({mapped_cas/total_rows*100:.1f}%)")
    logger.info(f"    solution: {mapped_solution:,} ({mapped_solution/total_rows*100:.1f}%)")
    logger.info(f"    ingredient: {mapped_ingredient:,} ({mapped_ingredient/total_rows*100:.1f}%)")
    logger.info(f"    other: {mapped_other:,}")
    
    # Count different ID types in base_chebi_id column
    base_chebi_chebi = df['base_chebi_id'].str.startswith('CHEBI:', na=False).sum()
    base_chebi_other = len(df) - base_chebi_missing - base_chebi_empty - base_chebi_chebi
    
    logger.info(f"  base_chebi_id column content:")
    logger.info(f"    CHEBI: {base_chebi_chebi:,} ({base_chebi_chebi/total_rows*100:.1f}%)")
    logger.info(f"    non-CHEBI: {base_chebi_other:,}")
    
    # 4. Check for redundancy/differences
    logger.info(f"\nRedundancy analysis:")
    
    # Cases where both columns have CHEBI IDs
    both_chebi = df[(df['mapped'].str.startswith('CHEBI:', na=False)) & 
                   (df['base_chebi_id'].str.startswith('CHEBI:', na=False))]
    
    logger.info(f"  Both columns have CHEBI: {len(both_chebi):,}")
    
    # Check if they match when both have CHEBI
    matching_chebi = (both_chebi['mapped'] == both_chebi['base_chebi_id']).sum()
    logger.info(f"  Matching CHEBI IDs: {matching_chebi:,} ({matching_chebi/len(both_chebi)*100:.1f}% of both-CHEBI cases)")
    
    if len(both_chebi) > matching_chebi:
        mismatched = both_chebi[both_chebi['mapped'] != both_chebi['base_chebi_id']]
        logger.info(f"  Mismatched CHEBI IDs: {len(mismatched)}")
        logger.info("  Examples of mismatched CHEBI IDs:")
        for _, row in mismatched.head(5).iterrows():
            logger.info(f"    {row['original']}: mapped='{row['mapped']}' vs base_chebi_id='{row['base_chebi_id']}'")
    
    # 5. Cases where mapped has non-CHEBI but base_chebi_id has CHEBI
    mapped_non_chebi_base_chebi = df[
        (~df['mapped'].str.startswith('CHEBI:', na=False)) & 
        (df['base_chebi_id'].str.startswith('CHEBI:', na=False)) &
        (df['mapped'].notna()) & (df['mapped'] != '')
    ]
    
    logger.info(f"  Cases where mapped=non-CHEBI but base_chebi_id=CHEBI: {len(mapped_non_chebi_base_chebi):,}")
    
    if len(mapped_non_chebi_base_chebi) > 0:
        logger.info("  Examples (mapped column had non-CHEBI, base_chebi_id has CHEBI):")
        for _, row in mapped_non_chebi_base_chebi.head(10).iterrows():
            logger.info(f"    {row['original']}: mapped='{row['mapped']}' → base_chebi_id='{row['base_chebi_id']}'")
    
    # 6. Recommendation
    logger.info(f"\nRecommendation:")
    logger.info(f"Based on the analysis:")
    logger.info(f"  - 'mapped' column: Should represent ORIGINAL mapping from various databases")
    logger.info(f"  - 'base_chebi_id' column: Should represent CHEBI mapping after hydration analysis")
    logger.info(f"  - They serve different purposes and should both be kept")
    logger.info(f"  - 'mapped' preserves original database diversity (CHEBI, PubChem, CAS-RN, etc.)")
    logger.info(f"  - 'base_chebi_id' provides unified CHEBI mapping for downstream analysis")
    
    return df

def main():
    parser = argparse.ArgumentParser(description="Analyze column redundancy")
    parser.add_argument("--input", required=True, help="Input TSV file")
    
    args = parser.parse_args()
    analyze_column_redundancy(args.input)

if __name__ == "__main__":
    main()