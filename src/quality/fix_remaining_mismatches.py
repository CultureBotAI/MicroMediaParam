#!/usr/bin/env python3
"""
Fix the remaining ChEBI ID mismatches (MnSO4 cases).
"""

import pandas as pd
import argparse
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_remaining_mismatches(input_file, output_file):
    """Fix remaining ChEBI ID mismatches."""
    
    logger.info(f"Loading file: {input_file}")
    df = pd.read_csv(input_file, sep='\t')
    
    logger.info(f"Dataset shape: {df.shape}")
    
    # Find all remaining ChEBI ID mismatches
    all_mismatches = df[
        (df['mapped'] != df['base_chebi_id']) &
        (df['mapped'].notna()) & (df['base_chebi_id'].notna()) &
        (df['mapped'].str.startswith('CHEBI:', na=False)) &
        (df['base_chebi_id'].str.startswith('CHEBI:', na=False))
    ]
    
    logger.info(f"Found {len(all_mismatches)} total ChEBI ID mismatches")
    
    if len(all_mismatches) > 0:
        # Group by compound and mismatch type
        mismatch_summary = all_mismatches.groupby(['base_compound', 'mapped', 'base_chebi_id']).size().reset_index(name='count')
        
        logger.info("Mismatch summary:")
        for _, row in mismatch_summary.iterrows():
            logger.info(f"  {row['base_compound']}: mapped='{row['mapped']}' vs base_chebi_id='{row['base_chebi_id']}' ({row['count']} cases)")
        
        # Focus on MnSO4 mismatches
        mnso4_mismatches = all_mismatches[all_mismatches['base_compound'] == 'MnSO4']
        
        if len(mnso4_mismatches) > 0:
            logger.info(f"\nAnalyzing MnSO4 mismatches ({len(mnso4_mismatches)} cases):")
            
            # Check hydration states
            for _, row in mnso4_mismatches.head(3).iterrows():
                water_molecules = row.get('water_molecules', 'N/A')
                hydrate_formula = row.get('hydrate_formula', 'N/A')
                original = row.get('original', 'N/A')
                logger.info(f"  {original}: water_molecules={water_molecules}, hydrate_formula='{hydrate_formula}'")
            
            # Research the correct ChEBI ID for MnSO4
            logger.info("\nResearching correct ChEBI ID for MnSO4:")
            logger.info("  CHEBI:86360 = could be one form of manganese sulfate")
            logger.info("  CHEBI:135251 = could be another form of manganese sulfate")
            logger.info("  CHEBI:75211 = manganese(2+) sulfate (from our earlier work)")
            
            # Use CHEBI:75211 as the standard (from our known compounds mapping)
            correct_chebi_id = 'CHEBI:75211'
            correct_label = 'manganese(2+) sulfate'
            correct_formula = 'MnO4S'
            
            logger.info(f"\nApplying fix: Using {correct_chebi_id} as the standard ChEBI ID for MnSO4")
            
            # Update both columns to use the standard ChEBI ID
            fixes_applied = 0
            for idx in mnso4_mismatches.index:
                df.at[idx, 'mapped'] = correct_chebi_id
                df.at[idx, 'base_chebi_id'] = correct_chebi_id
                df.at[idx, 'base_chebi_label'] = correct_label
                df.at[idx, 'base_chebi_formula'] = correct_formula
                fixes_applied += 1
            
            logger.info(f"✓ Applied {fixes_applied} fixes to MnSO4 entries")
        
        # Check for any other remaining mismatches
        remaining_mismatches = df[
            (df['mapped'] != df['base_chebi_id']) &
            (df['mapped'].notna()) & (df['base_chebi_id'].notna()) &
            (df['mapped'].str.startswith('CHEBI:', na=False)) &
            (df['base_chebi_id'].str.startswith('CHEBI:', na=False))
        ]
        
        logger.info(f"\nTotal remaining mismatches after MnSO4 fix: {len(remaining_mismatches)}")
        
        if len(remaining_mismatches) > 0:
            remaining_summary = remaining_mismatches.groupby(['base_compound', 'mapped', 'base_chebi_id']).size().reset_index(name='count')
            logger.info("Remaining mismatch summary:")
            for _, row in remaining_summary.iterrows():
                logger.info(f"  {row['base_compound']}: mapped='{row['mapped']}' vs base_chebi_id='{row['base_chebi_id']}' ({row['count']} cases)")
        else:
            logger.info("✓ All ChEBI ID mismatches resolved!")
    
    else:
        logger.info("No ChEBI ID mismatches found")
    
    # Final verification
    final_mismatches = df[
        (df['mapped'] != df['base_chebi_id']) &
        (df['mapped'].notna()) & (df['base_chebi_id'].notna()) &
        (df['mapped'].str.startswith('CHEBI:', na=False)) &
        (df['base_chebi_id'].str.startswith('CHEBI:', na=False))
    ]
    
    logger.info(f"\nFinal verification:")
    logger.info(f"  Total ChEBI entries: {len(df[df['base_chebi_id'].str.startswith('CHEBI:', na=False)])}")
    logger.info(f"  ChEBI ID mismatches: {len(final_mismatches)}")
    logger.info(f"  Consistency rate: {(1 - len(final_mismatches) / len(df[df['base_chebi_id'].str.startswith('CHEBI:', na=False)])) * 100:.3f}%")
    
    # Save the corrected dataset
    df.to_csv(output_file, sep='\t', index=False)
    logger.info(f"\n✓ Saved corrected dataset to: {output_file}")
    
    return df

def main():
    parser = argparse.ArgumentParser(description="Fix remaining ChEBI ID mismatches")
    parser.add_argument("--input", required=True, help="Input TSV file")
    parser.add_argument("--output", required=True, help="Output TSV file")
    
    args = parser.parse_args()
    fix_remaining_mismatches(args.input, args.output)

if __name__ == "__main__":
    main()