#!/usr/bin/env python3
"""
Fix remaining issues:
1. Strange symbols in hydrate_formula column
2. Missing base_chebi_id for compounds already mapped to CHEBI
"""

import pandas as pd
import re
import argparse
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_remaining_issues(input_file, output_file):
    """Fix hydrate symbols and populate base_chebi_id."""
    
    logger.info(f"Loading file: {input_file}")
    df = pd.read_csv(input_file, sep='\t')
    
    # Fix 1: Clean up ALL hydrate formula columns with strange symbols
    formula_fixes = 0
    hydrate_columns = ['hydrate_formula', 'base_formula']
    
    for col in hydrate_columns:
        if col in df.columns:
            for idx, row in df.iterrows():
                value = row.get(col, '')
                if pd.notna(value) and value:
                    original_value = str(value)
                    # Replace ALL possible strange symbols with proper dot
                    # Including the specific problematic character ¬
                    cleaned_value = original_value
                    for bad_char in ['¬∑', '¬', '∑', '•', '․', '‧', '⋅', '*', '..', '. ']:
                        cleaned_value = cleaned_value.replace(bad_char, '·')
                    
                    # Also ensure proper spacing around the dot
                    cleaned_value = re.sub(r'\s*·\s*', '·', cleaned_value)
                    
                    if cleaned_value != original_value:
                        df.at[idx, col] = cleaned_value
                        formula_fixes += 1
    
    # Fix 2: Populate base_chebi_id for compounds mapped to CHEBI
    chebi_fixes = 0
    for idx, row in df.iterrows():
        mapped_value = row.get('mapped', '')
        base_chebi_id = row.get('base_chebi_id', '')
        
        # If compound is mapped to CHEBI but base_chebi_id is empty
        if (pd.notna(mapped_value) and str(mapped_value).startswith('CHEBI:') and
            (pd.isna(base_chebi_id) or base_chebi_id == '')):
            
            # Copy the CHEBI ID to base_chebi_id
            df.at[idx, 'base_chebi_id'] = mapped_value
            chebi_fixes += 1
    
    # Fix 3: Clean up base_formula to ensure it doesn't have hydrate info
    base_formula_fixes = 0
    for idx, row in df.iterrows():
        base_compound = row.get('base_compound', '')
        base_formula = row.get('base_formula', '')
        hydration_num = row.get('hydration_number', 0)
        
        # If base_formula contains hydrate info, clean it
        if pd.notna(base_formula) and base_formula:
            if 'hydrate' in str(base_formula).lower() or 'H2O' in str(base_formula):
                # Use base_compound as the clean formula
                if pd.notna(base_compound) and base_compound:
                    df.at[idx, 'base_formula'] = base_compound
                    base_formula_fixes += 1
                    
                    # Regenerate hydrate_formula with proper symbol
                    if pd.notna(hydration_num) and hydration_num not in [0, '0']:
                        df.at[idx, 'hydrate_formula'] = f"{base_compound}·{hydration_num}H2O"
    
    # Save the file
    df.to_csv(output_file, sep='\t', index=False)
    
    logger.info(f"Fixed {formula_fixes} formulas with strange symbols")
    logger.info(f"Fixed {chebi_fixes} missing base_chebi_id entries")
    logger.info(f"Fixed {base_formula_fixes} base formulas with hydrate info")
    
    # Show examples
    if chebi_fixes > 0:
        logger.info("\nExamples of CHEBI fixes:")
        chebi_examples = df[(df['mapped'].str.startswith('CHEBI:', na=False)) & 
                           (df['base_chebi_id'].str.startswith('CHEBI:', na=False))]
        for _, row in chebi_examples.head(5).iterrows():
            logger.info(f"  {row['original']} → mapped: {row['mapped']}, base_chebi_id: {row['base_chebi_id']}")
    
    # Show hydrate formula examples
    hydrate_examples = df[df['hydrate_formula'].str.contains('·', na=False)]
    if len(hydrate_examples) > 0:
        logger.info("\nExamples of fixed hydrate formulas:")
        for _, row in hydrate_examples.head(5).iterrows():
            logger.info(f"  {row['original']} → {row['hydrate_formula']}")
    
    # Statistics
    total_chebi_mapped = len(df[df['mapped'].str.startswith('CHEBI:', na=False)])
    total_with_base_chebi = len(df[df['base_chebi_id'].str.startswith('CHEBI:', na=False)])
    logger.info(f"\nCHEBI mapping statistics:")
    logger.info(f"  Total CHEBI mapped: {total_chebi_mapped}")
    logger.info(f"  With base_chebi_id: {total_with_base_chebi}")

def main():
    parser = argparse.ArgumentParser(description="Fix remaining mapping issues")
    parser.add_argument("--input", required=True, help="Input TSV file")
    parser.add_argument("--output", required=True, help="Output TSV file")
    
    args = parser.parse_args()
    fix_remaining_issues(args.input, args.output)

if __name__ == "__main__":
    main()