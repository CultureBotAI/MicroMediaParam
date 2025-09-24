#!/usr/bin/env python3
"""
Fix remaining hydrate parsing issues:
1. Strange symbols in hydrate formulas
2. False negatives where already-mapped compounds are treated as unmapped
"""

import pandas as pd
import re
import argparse
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_hydrate_issues(input_file, output_file):
    """Fix hydrate formula symbols and false negative mappings."""
    
    logger.info(f"Loading file: {input_file}")
    df = pd.read_csv(input_file, sep='\t')
    
    # Fix 1: Clean up hydrate formulas with strange symbols
    formula_fixes = 0
    for idx, row in df.iterrows():
        hydrate_formula = row.get('hydrate_formula', '')
        if pd.notna(hydrate_formula) and hydrate_formula:
            # Replace strange symbols with proper dot
            original_formula = hydrate_formula
            # Replace various symbols with proper middle dot
            cleaned_formula = re.sub(r'[¬∑•․‧⋅*]', '·', hydrate_formula)
            
            if cleaned_formula != original_formula:
                df.at[idx, 'hydrate_formula'] = cleaned_formula
                formula_fixes += 1
    
    # Fix 2: Handle already-mapped compounds that should not be in unmapped category
    mapping_fixes = 0
    for idx, row in df.iterrows():
        mapped_value = row.get('mapped', '')
        hydration_state = row.get('hydration_state', '')
        original = row['original']
        
        # If compound is already mapped to ChEBI/PubChem/CAS but marked as unmapped
        if (pd.notna(mapped_value) and mapped_value and 
            str(mapped_value).startswith(('CHEBI:', 'PubChem:', 'CAS-RN:')) and
            hydration_state in ['hydrated', 'anhydrous']):
            
            # This should be marked as already_mapped, not unmapped
            df.at[idx, 'hydration_state'] = 'already_mapped'
            df.at[idx, 'base_compound_for_mapping'] = original
            df.at[idx, 'hydration_number_extracted'] = ''
            mapping_fixes += 1
    
    # Fix 3: Ensure proper base compounds for already-mapped items
    base_compound_fixes = 0
    for idx, row in df.iterrows():
        original = row['original']
        base_compound = row.get('base_compound', '')
        hydration_state = row.get('hydration_state', '')
        
        # If it's already mapped but base_compound still has hydrate info
        if (hydration_state == 'already_mapped' and 
            pd.notna(base_compound) and 
            ('hydrate' in str(base_compound).lower() or 
             re.search(r'\d+\s*H2O', str(base_compound)))):
            
            # Parse to get clean base compound
            base_clean, hydration_num = parse_hydrate_simple(original)
            if base_clean != original:
                df.at[idx, 'base_compound'] = base_clean
                df.at[idx, 'base_formula'] = base_clean
                if hydration_num and hydration_num != 0:
                    df.at[idx, 'hydration_number'] = hydration_num
                    df.at[idx, 'hydrate_formula'] = f"{base_clean}·{hydration_num}H2O"
                base_compound_fixes += 1
    
    # Save the file
    df.to_csv(output_file, sep='\t', index=False)
    
    logger.info(f"Fixed {formula_fixes} hydrate formulas with strange symbols")
    logger.info(f"Fixed {mapping_fixes} false negative mappings")
    logger.info(f"Fixed {base_compound_fixes} base compounds for mapped items")
    
    # Show examples of fixes
    if formula_fixes > 0:
        logger.info("\nExamples of formula fixes:")
        strange_formulas = df[df['hydrate_formula'].str.contains('·', na=False)]
        for _, row in strange_formulas.head(5).iterrows():
            logger.info(f"  {row['original']} → {row['hydrate_formula']}")
    
    # Show mapping statistics
    already_mapped = len(df[df['hydration_state'] == 'already_mapped'])
    hydrated = len(df[df['hydration_state'] == 'hydrated'])
    anhydrous = len(df[df['hydration_state'] == 'anhydrous'])
    total = len(df)
    
    logger.info(f"\nMapping state statistics:")
    logger.info(f"  Already mapped: {already_mapped} ({already_mapped/total*100:.1f}%)")
    logger.info(f"  Hydrated (unmapped): {hydrated} ({hydrated/total*100:.1f}%)")
    logger.info(f"  Anhydrous (unmapped): {anhydrous} ({anhydrous/total*100:.1f}%)")

def parse_hydrate_simple(compound_name):
    """Simple hydrate parser for cleaning base compounds."""
    if pd.isna(compound_name):
        return compound_name, 0
    
    compound_name = str(compound_name).strip()
    
    # Simple patterns
    patterns = [
        (r'^(.+?)\s+(\d+)\s*[-]?\s*hydrate$', lambda m: (m.group(1).strip(), int(m.group(2)))),
        (r'^(.+?)\s+(\d+)\s*H2O$', lambda m: (m.group(1).strip(), int(m.group(2)))),
        (r'^(.+?)\s+x\s+H2O$', lambda m: (m.group(1).strip(), 'x')),
    ]
    
    for pattern, extractor in patterns:
        match = re.match(pattern, compound_name, re.IGNORECASE)
        if match:
            return extractor(match)
    
    return compound_name, 0

def main():
    parser = argparse.ArgumentParser(description="Fix hydrate issues")
    parser.add_argument("--input", required=True, help="Input TSV file")
    parser.add_argument("--output", required=True, help="Output TSV file")
    
    args = parser.parse_args()
    fix_hydrate_issues(args.input, args.output)

if __name__ == "__main__":
    main()