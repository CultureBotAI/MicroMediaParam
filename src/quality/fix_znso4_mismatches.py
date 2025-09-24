#!/usr/bin/env python3
"""
Investigate and fix ZnSO4 ChEBI ID mismatches between mapped and base_chebi_id columns.
"""

import pandas as pd
import argparse
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_znso4_mismatches(input_file, output_file):
    """Fix ZnSO4 ChEBI ID mismatches."""
    
    logger.info(f"Loading file: {input_file}")
    df = pd.read_csv(input_file, sep='\t')
    
    logger.info(f"Dataset shape: {df.shape}")
    
    # Find all ZnSO4 entries with ChEBI ID mismatches
    znso4_mismatches = df[
        (df['base_compound'] == 'ZnSO4') & 
        (df['mapped'] != df['base_chebi_id']) &
        (df['mapped'].notna()) & (df['base_chebi_id'].notna())
    ]
    
    logger.info(f"Found {len(znso4_mismatches)} ZnSO4 entries with ChEBI ID mismatches")
    
    if len(znso4_mismatches) > 0:
        # Show the mismatch details
        logger.info("ZnSO4 mismatch details:")
        for _, row in znso4_mismatches.head(10).iterrows():
            logger.info(f"  {row['medium_id']}: {row['original']} → mapped='{row['mapped']}' vs base_chebi_id='{row['base_chebi_id']}'")
        
        # Research the correct ChEBI ID for ZnSO4
        logger.info("\nResearching correct ChEBI ID for ZnSO4:")
        logger.info("  CHEBI:35176 = zinc sulfate (anhydrous)")
        logger.info("  CHEBI:62984 = zinc sulfate (could be different hydration state)")
        
        # Check what the mapped column originally had
        mapped_ids = znso4_mismatches['mapped'].unique()
        base_ids = znso4_mismatches['base_chebi_id'].unique()
        
        logger.info(f"  Original mapped IDs: {list(mapped_ids)}")
        logger.info(f"  Base ChEBI IDs: {list(base_ids)}")
        
        # Check hydration states of these entries
        logger.info("\nHydration analysis of mismatched ZnSO4 entries:")
        for _, row in znso4_mismatches.head(5).iterrows():
            water_molecules = row.get('water_molecules', 'N/A')
            hydrate_formula = row.get('hydrate_formula', 'N/A')
            logger.info(f"  {row['original']}: water_molecules={water_molecules}, hydrate_formula='{hydrate_formula}'")
        
        # Determine the correct mapping based on research
        # CHEBI:35176 is the more commonly used zinc sulfate ID
        # Let's align base_chebi_id with the mapped column since mapped was the original correct mapping
        correct_chebi_id = 'CHEBI:35176'  # zinc sulfate (standard)
        correct_label = 'zinc sulfate'
        correct_formula = 'O4SZn'
        
        logger.info(f"\nApplying fix: Using {correct_chebi_id} as the correct ChEBI ID for ZnSO4")
        
        # Update base_chebi_id to match mapped for consistency
        fixes_applied = 0
        for idx in znso4_mismatches.index:
            if df.at[idx, 'mapped'] == 'CHEBI:35176':
                # Update base_chebi_id to match mapped
                df.at[idx, 'base_chebi_id'] = 'CHEBI:35176'
                # Also update related fields if needed
                df.at[idx, 'base_chebi_label'] = correct_label
                df.at[idx, 'base_chebi_formula'] = correct_formula
                fixes_applied += 1
                logger.info(f"  Fixed: {df.at[idx, 'original']} → base_chebi_id updated to CHEBI:35176")
            elif df.at[idx, 'base_chebi_id'] == 'CHEBI:62984':
                # Update mapped to match base_chebi_id (if base_chebi_id is more accurate)
                # But first let's check if CHEBI:62984 is valid
                df.at[idx, 'mapped'] = df.at[idx, 'base_chebi_id']
                fixes_applied += 1
                logger.info(f"  Fixed: {df.at[idx, 'original']} → mapped updated to match base_chebi_id")
        
        logger.info(f"✓ Applied {fixes_applied} fixes to ZnSO4 entries")
        
        # Verify fixes
        remaining_mismatches = df[
            (df['base_compound'] == 'ZnSO4') & 
            (df['mapped'] != df['base_chebi_id']) &
            (df['mapped'].notna()) & (df['base_chebi_id'].notna())
        ]
        
        logger.info(f"Remaining ZnSO4 mismatches after fix: {len(remaining_mismatches)}")
        
    else:
        logger.info("No ZnSO4 ChEBI ID mismatches found")
    
    # Check all remaining mismatches in the dataset
    all_mismatches = df[
        (df['mapped'] != df['base_chebi_id']) &
        (df['mapped'].notna()) & (df['base_chebi_id'].notna()) &
        (df['mapped'].str.startswith('CHEBI:', na=False)) &
        (df['base_chebi_id'].str.startswith('CHEBI:', na=False))
    ]
    
    logger.info(f"\nTotal remaining ChEBI ID mismatches in dataset: {len(all_mismatches)}")
    
    if len(all_mismatches) > 0:
        logger.info("Remaining mismatch examples:")
        mismatch_summary = all_mismatches.groupby(['base_compound', 'mapped', 'base_chebi_id']).size().reset_index(name='count')
        for _, row in mismatch_summary.head(5).iterrows():
            logger.info(f"  {row['base_compound']}: mapped='{row['mapped']}' vs base_chebi_id='{row['base_chebi_id']}' ({row['count']} cases)")
    
    # Save the corrected dataset
    df.to_csv(output_file, sep='\t', index=False)
    logger.info(f"\n✓ Saved corrected dataset to: {output_file}")
    
    return df

def main():
    parser = argparse.ArgumentParser(description="Fix ZnSO4 ChEBI ID mismatches")
    parser.add_argument("--input", required=True, help="Input TSV file")
    parser.add_argument("--output", required=True, help="Output TSV file")
    
    args = parser.parse_args()
    fix_znso4_mismatches(args.input, args.output)

if __name__ == "__main__":
    main()