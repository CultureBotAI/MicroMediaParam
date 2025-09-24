#!/usr/bin/env python3
"""
Fix the persistent strange symbols in hydrate formulas and add water molecules column.
"""

import pandas as pd
import re
import argparse
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_symbols_and_add_water_column(input_file, output_file):
    """Fix symbols and add water molecules column."""
    
    logger.info(f"Loading file: {input_file}")
    df = pd.read_csv(input_file, sep='\t')
    
    # Add water_molecules column if it doesn't exist
    if 'water_molecules' not in df.columns:
        df['water_molecules'] = ''
    
    # Fix symbols and populate water molecules
    symbol_fixes = 0
    water_fixes = 0
    
    for idx, row in df.iterrows():
        # Fix 1: Clean hydrate_formula column specifically
        hydrate_formula = row.get('hydrate_formula', '')
        if pd.notna(hydrate_formula) and hydrate_formula:
            original = str(hydrate_formula)
            
            # Replace the specific problematic characters
            fixed = original
            # Target the exact sequence ¬∑ 
            fixed = fixed.replace('¬∑', '·')
            fixed = fixed.replace('¬', '·')
            fixed = fixed.replace('∑', '')
            
            # Also handle other possible symbols
            for bad_symbol in ['•', '․', '‧', '⋅', '*']:
                fixed = fixed.replace(bad_symbol, '·')
            
            # Clean up multiple dots or spaces
            fixed = re.sub(r'·+', '·', fixed)
            fixed = re.sub(r'\s*·\s*', '·', fixed)
            
            if fixed != original:
                df.at[idx, 'hydrate_formula'] = fixed
                symbol_fixes += 1
        
        # Fix 2: Add water molecules count
        hydration_number = row.get('hydration_number', '')
        if pd.notna(hydration_number) and hydration_number not in ['', 0, '0']:
            # Convert to string for consistency
            water_count = str(hydration_number)
            df.at[idx, 'water_molecules'] = water_count
            water_fixes += 1
        else:
            df.at[idx, 'water_molecules'] = '0'
    
    # Additional pass to ensure all hydrate formulas are clean
    for idx, row in df.iterrows():
        base_compound = row.get('base_compound', '')
        water_molecules = row.get('water_molecules', '0')
        
        # Regenerate hydrate_formula if it still has issues
        if (pd.notna(base_compound) and base_compound and 
            water_molecules not in ['0', '', '0.0']):
            
            clean_formula = f"{base_compound}·{water_molecules}H2O"
            df.at[idx, 'hydrate_formula'] = clean_formula
    
    # Save the file
    df.to_csv(output_file, sep='\t', index=False)
    
    logger.info(f"Fixed {symbol_fixes} hydrate formulas with strange symbols")
    logger.info(f"Added water molecule counts for {water_fixes} compounds")
    
    # Show examples of fixes
    logger.info("\nExamples of fixed hydrate formulas:")
    hydrated = df[df['water_molecules'] != '0']
    for _, row in hydrated.head(10).iterrows():
        orig = row['original']
        formula = row.get('hydrate_formula', '')
        water = row.get('water_molecules', '')
        logger.info(f"  {orig} → {formula} (water molecules: {water})")
    
    # Check for remaining problematic symbols
    problematic = df[df['hydrate_formula'].str.contains('[¬∑•․‧⋅]', na=False, regex=True)]
    if len(problematic) > 0:
        logger.warning(f"Still found {len(problematic)} formulas with problematic symbols:")
        for _, row in problematic.head(5).iterrows():
            logger.warning(f"  {row['original']}: {row['hydrate_formula']}")
    else:
        logger.info("✅ No more problematic symbols found!")
    
    # Statistics
    total_hydrated = len(df[df['water_molecules'] != '0'])
    total_compounds = len(df)
    logger.info(f"\nWater molecule statistics:")
    logger.info(f"  Hydrated compounds: {total_hydrated}/{total_compounds} ({total_hydrated/total_compounds*100:.1f}%)")

def main():
    parser = argparse.ArgumentParser(description="Fix symbols and add water column")
    parser.add_argument("--input", required=True, help="Input TSV file")
    parser.add_argument("--output", required=True, help="Output TSV file")
    
    args = parser.parse_args()
    fix_symbols_and_add_water_column(args.input, args.output)

if __name__ == "__main__":
    main()