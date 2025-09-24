#!/usr/bin/env python3
"""
Add missing ChEBI mappings for compounds that have CAS-RN or PubChem IDs
but are missing ChEBI mappings.
"""

import pandas as pd
import argparse
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_missing_chebi_mappings(input_file, output_file):
    """Add missing ChEBI mappings for compounds with other database IDs."""
    
    logger.info(f"Loading file: {input_file}")
    df = pd.read_csv(input_file, sep='\t')
    
    # Define missing ChEBI mappings for compounds with external IDs
    missing_chebi_mappings = {
        'KH2PO4': 'CHEBI:63036',           # Potassium dihydrogen phosphate
        'NaNO3': 'CHEBI:63005',            # Sodium nitrate
        'Na2CO3': 'CHEBI:29377',           # Sodium carbonate (already exists but check)
        'NH4H2PO4': 'CHEBI:62982',         # Ammonium dihydrogen phosphate
        'NH4NO3': 'CHEBI:63038',           # Ammonium nitrate
        'K2CrO4': 'CHEBI:75249',           # Potassium chromate
        'L-Cysteine HCl': 'CHEBI:91247',   # L-Cysteine hydrochloride
        'Glacial acetic acid': 'CHEBI:15366',  # Acetic acid
        'Glutathione': 'CHEBI:16856',      # Glutathione
        # Additional common compounds
        'Acetic acid': 'CHEBI:15366',      # Acetic acid (alternative name)
        'Sodium acetate': 'CHEBI:17713',   # Sodium acetate
        'Potassium acetate': 'CHEBI:32047', # Potassium acetate
        'Ammonium acetate': 'CHEBI:62947', # Ammonium acetate
    }
    
    # Count before
    before_chebi = df['base_chebi_id'].notna().sum()
    logger.info(f"ChEBI mappings before: {before_chebi}")
    
    added_mappings = 0
    updated_compounds = []
    
    # Apply mappings based on base_compound
    for idx, row in df.iterrows():
        base_compound = row.get('base_compound', '')
        current_chebi = row.get('base_chebi_id', '')
        current_mapped = row.get('mapped', '')
        
        # Only add if no ChEBI mapping exists but other mapping exists
        if (pd.notna(base_compound) and base_compound in missing_chebi_mappings and
            (pd.isna(current_chebi) or current_chebi == '') and
            (pd.notna(current_mapped) and current_mapped != '')):
            
            new_chebi = missing_chebi_mappings[base_compound]
            df.at[idx, 'base_chebi_id'] = new_chebi
            
            # Also update the main mapped field if it doesn't already have ChEBI
            if not current_mapped.startswith('CHEBI:'):
                df.at[idx, 'mapped'] = new_chebi
            
            added_mappings += 1
            updated_compounds.append(f"{base_compound} -> {new_chebi}")
            logger.info(f"  Added ChEBI mapping: {base_compound} -> {new_chebi}")
    
    # Count after
    after_chebi = df['base_chebi_id'].notna().sum()
    logger.info(f"ChEBI mappings after: {after_chebi}")
    logger.info(f"Added {added_mappings} new ChEBI mappings")
    
    # Show what was updated
    if updated_compounds:
        logger.info("\nUpdated compounds:")
        for compound in updated_compounds:
            logger.info(f"  {compound}")
    
    # Calculate new coverage
    total_compounds = len(df)
    chebi_coverage = (after_chebi / total_compounds) * 100
    total_mapped = df['mapped'].notna().sum()
    total_coverage = (total_mapped / total_compounds) * 100
    
    logger.info(f"\nCoverage Summary:")
    logger.info(f"  Total compounds: {total_compounds:,}")
    logger.info(f"  ChEBI mapped: {after_chebi:,} ({chebi_coverage:.1f}%)")
    logger.info(f"  Total mapped: {total_mapped:,} ({total_coverage:.1f}%)")
    
    # Save the updated file
    df.to_csv(output_file, sep='\t', index=False)
    logger.info(f"Saved updated file: {output_file}")
    
    # Show examples of newly mapped compounds
    newly_mapped = df[df['base_compound'].isin(missing_chebi_mappings.keys()) & 
                     df['base_chebi_id'].notna()]
    if len(newly_mapped) > 0:
        logger.info(f"\nExamples of newly ChEBI-mapped compounds:")
        for _, row in newly_mapped.head(10).iterrows():
            logger.info(f"  {row['base_compound']}: {row['base_chebi_id']} (was {row['mapped']})")

def main():
    parser = argparse.ArgumentParser(description="Add missing ChEBI mappings")
    parser.add_argument("--input", required=True, help="Input TSV file")
    parser.add_argument("--output", required=True, help="Output TSV file")
    
    args = parser.parse_args()
    add_missing_chebi_mappings(args.input, args.output)

if __name__ == "__main__":
    main()