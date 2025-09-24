#!/usr/bin/env python3
"""
Force fix the persistent sigma symbols in hydrate formulas.
Target the exact problematic character sequence.
"""

import pandas as pd
import re
import argparse
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def force_fix_sigma_symbols(input_file, output_file):
    """Force fix sigma symbols with direct string replacement."""
    
    logger.info(f"Loading file: {input_file}")
    df = pd.read_csv(input_file, sep='\t')
    
    # Show problematic cases before fixing
    problematic_before = df[df['hydrate_formula'].str.contains('¬|∑', na=False, regex=True)]
    logger.info(f"Found {len(problematic_before)} cases with problematic symbols before fixing")
    
    if len(problematic_before) > 0:
        logger.info("Problematic cases:")
        for _, row in problematic_before.head(10).iterrows():
            logger.info(f"  {row['original']}: '{row['hydrate_formula']}'")
    
    # Force fix all hydrate_formula entries
    fixes = 0
    for idx, row in df.iterrows():
        hydrate_formula = row.get('hydrate_formula', '')
        if pd.notna(hydrate_formula) and hydrate_formula:
            original = str(hydrate_formula)
            
            # Force replace the exact problematic characters
            fixed = original
            
            # Replace specific character combinations
            fixed = fixed.replace('¬∑', '·')
            fixed = fixed.replace('¬', '·')
            fixed = fixed.replace('∑', '')
            
            # Also handle any other variations
            fixed = fixed.replace('•', '·')
            fixed = fixed.replace('․', '·')
            fixed = fixed.replace('‧', '·')
            fixed = fixed.replace('⋅', '·')
            fixed = fixed.replace('*', '·')
            
            # Clean up any double dots
            fixed = re.sub(r'·+', '·', fixed)
            
            if fixed != original:
                df.at[idx, 'hydrate_formula'] = fixed
                fixes += 1
                logger.info(f"  Fixed: '{original}' → '{fixed}'")
    
    # Alternative approach: Regenerate all hydrate formulas from scratch
    regenerated = 0
    for idx, row in df.iterrows():
        base_compound = row.get('base_compound', '')
        hydration_number = row.get('hydration_number', '')
        
        if (pd.notna(base_compound) and base_compound and 
            pd.notna(hydration_number) and hydration_number not in ['', 0, '0']):
            
            # Generate clean formula
            clean_formula = f"{base_compound}·{hydration_number}H2O"
            
            # Update if different
            current_formula = row.get('hydrate_formula', '')
            if current_formula != clean_formula:
                df.at[idx, 'hydrate_formula'] = clean_formula
                regenerated += 1
    
    # Save the file
    df.to_csv(output_file, sep='\t', index=False)
    
    logger.info(f"Applied {fixes} direct symbol fixes")
    logger.info(f"Regenerated {regenerated} hydrate formulas")
    
    # Check for remaining problems
    problematic_after = df[df['hydrate_formula'].str.contains('¬|∑', na=False, regex=True)]
    logger.info(f"Remaining problematic cases: {len(problematic_after)}")
    
    if len(problematic_after) > 0:
        logger.warning("Still problematic:")
        for _, row in problematic_after.iterrows():
            logger.warning(f"  {row['original']}: '{row['hydrate_formula']}'")
    else:
        logger.info("✅ All sigma symbols successfully removed!")
    
    # Show some examples of clean formulas
    clean_hydrates = df[(df['hydrate_formula'].str.contains('·', na=False)) & 
                       (~df['hydrate_formula'].str.contains('¬|∑', na=False, regex=True))]
    logger.info(f"\nExamples of clean hydrate formulas ({len(clean_hydrates)} total):")
    for _, row in clean_hydrates.head(10).iterrows():
        logger.info(f"  {row['original']}: {row['hydrate_formula']}")

def main():
    parser = argparse.ArgumentParser(description="Force fix sigma symbols")
    parser.add_argument("--input", required=True, help="Input TSV file")
    parser.add_argument("--output", required=True, help="Output TSV file")
    
    args = parser.parse_args()
    force_fix_sigma_symbols(args.input, args.output)

if __name__ == "__main__":
    main()