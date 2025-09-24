#!/usr/bin/env python3
"""
Fix two issues:
1. 'x H2O' should be interpreted as 1 water molecule, not variable x
2. Add missing ChEBI mappings for common compounds like MnSO4
"""

import pandas as pd
import argparse
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_x_hydration_and_missing_chebi(input_file, output_file):
    """Fix x hydration notation and add missing ChEBI mappings."""
    
    logger.info(f"Loading file: {input_file}")
    df = pd.read_csv(input_file, sep='\t')
    
    # Additional ChEBI mappings for compounds that are missing them
    additional_chebi_mappings = {
        'MnSO4': 'CHEBI:75211',           # Manganese(II) sulfate
        'FeSO4': 'CHEBI:75832',           # Iron(II) sulfate (check if already exists)
        'ZnSO4': 'CHEBI:35176',           # Zinc sulfate (check if already exists)
        'CuSO4': 'CHEBI:23414',           # Copper(II) sulfate (check if already exists)
        'AlCl3': 'CHEBI:30114',           # Aluminum chloride
        'BaCl2': 'CHEBI:88174',           # Barium chloride
        'CdCl2': 'CHEBI:47674',           # Cadmium chloride
        'PbCl2': 'CHEBI:37003',           # Lead(II) chloride
        'SnCl2': 'CHEBI:50341',           # Tin(II) chloride
        'Tris': 'CHEBI:9754',             # Tris buffer
        'HEPES': 'CHEBI:46756',           # HEPES buffer
        'MOPS': 'CHEBI:53580',            # MOPS buffer
    }
    
    # Count before changes
    x_hydrates_before = len(df[df['hydration_number'] == 'x'])
    missing_chebi_before = len(df[(df['base_chebi_id'].isna() | (df['base_chebi_id'] == '')) & 
                                  df['base_compound'].isin(additional_chebi_mappings.keys())])
    
    logger.info(f"Found {x_hydrates_before} compounds with 'x' hydration")
    logger.info(f"Found {missing_chebi_before} compounds missing ChEBI mappings")
    
    # Fix 1: Convert 'x H2O' to '1 H2O'
    x_fixes = 0
    for idx, row in df.iterrows():
        hydration_number = row.get('hydration_number', '')
        
        if hydration_number == 'x':
            # Convert x to 1
            df.at[idx, 'hydration_number'] = 1
            df.at[idx, 'water_molecules'] = 1
            
            # Update hydrate_formula
            base_compound = row.get('base_compound', '')
            if base_compound:
                df.at[idx, 'hydrate_formula'] = f"{base_compound}.1H2O"
            
            # Update molecular weights
            base_mw = row.get('base_molecular_weight', 100.0)
            water_mw = 18.015
            df.at[idx, 'water_molecular_weight'] = water_mw
            df.at[idx, 'hydrated_molecular_weight'] = base_mw + water_mw
            
            x_fixes += 1
            logger.info(f"  Fixed x hydration: {row['original']} -> 1 H2O")
    
    # Fix 2: Add missing ChEBI mappings
    chebi_added = 0
    for idx, row in df.iterrows():
        base_compound = row.get('base_compound', '')
        current_chebi = row.get('base_chebi_id', '')
        current_mapped = row.get('mapped', '')
        
        # Only add if compound is in our list and missing ChEBI mapping
        if (base_compound in additional_chebi_mappings and
            (pd.isna(current_chebi) or current_chebi == '') and
            pd.notna(current_mapped) and current_mapped != ''):
            
            new_chebi = additional_chebi_mappings[base_compound]
            df.at[idx, 'base_chebi_id'] = new_chebi
            
            # Update main mapped field if it doesn't have ChEBI
            if not current_mapped.startswith('CHEBI:'):
                df.at[idx, 'mapped'] = new_chebi
            
            chebi_added += 1
            logger.info(f"  Added ChEBI mapping: {base_compound} -> {new_chebi}")
    
    # Count after changes
    x_hydrates_after = len(df[df['hydration_number'] == 'x'])
    
    logger.info(f"Fixed {x_fixes} 'x' hydration cases")
    logger.info(f"Added {chebi_added} ChEBI mappings")
    logger.info(f"Remaining 'x' hydrations: {x_hydrates_after}")
    
    # Show examples of fixed cases
    if x_fixes > 0:
        fixed_cases = df[df['hydration_number'] == 1]
        logger.info(f"\nExamples of fixed hydration cases:")
        for _, row in fixed_cases.head(5).iterrows():
            if 'MnSO4' in str(row['original']) or 'x H2O' in str(row['original']):
                logger.info(f"  {row['original']}: {row['hydrate_formula']} (MW: {row['hydrated_molecular_weight']})")
    
    # Show examples of newly ChEBI-mapped compounds
    if chebi_added > 0:
        newly_mapped = df[df['base_compound'].isin(additional_chebi_mappings.keys()) & 
                         df['base_chebi_id'].notna()]
        logger.info(f"\nExamples of newly ChEBI-mapped compounds:")
        for _, row in newly_mapped.head(5).iterrows():
            if row['base_compound'] in additional_chebi_mappings:
                logger.info(f"  {row['base_compound']}: {row['base_chebi_id']}")
    
    # Calculate updated coverage
    total_compounds = len(df)
    chebi_mapped = df['base_chebi_id'].notna().sum()
    chebi_coverage = (chebi_mapped / total_compounds) * 100
    
    logger.info(f"\nUpdated ChEBI coverage: {chebi_mapped:,}/{total_compounds:,} ({chebi_coverage:.1f}%)")
    
    # Save the updated file
    df.to_csv(output_file, sep='\t', index=False)
    logger.info(f"Saved updated file: {output_file}")

def main():
    parser = argparse.ArgumentParser(description="Fix x hydration and missing ChEBI mappings")
    parser.add_argument("--input", required=True, help="Input TSV file")
    parser.add_argument("--output", required=True, help="Output TSV file")
    
    args = parser.parse_args()
    fix_x_hydration_and_missing_chebi(args.input, args.output)

if __name__ == "__main__":
    main()