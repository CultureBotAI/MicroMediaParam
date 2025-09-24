#!/usr/bin/env python3
"""
Remove '_composition' suffix from medium_id values.
"""

import pandas as pd
import argparse
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_medium_ids(input_file, output_file):
    """Remove '_composition' suffix from medium_id values."""
    
    logger.info(f"Loading file: {input_file}")
    df = pd.read_csv(input_file, sep='\t')
    
    logger.info(f"Original dataset shape: {df.shape}")
    
    # Check current medium_id values
    if 'medium_id' in df.columns:
        sample_ids = df['medium_id'].head(10).tolist()
        logger.info(f"Sample medium_id values before: {sample_ids}")
        
        # Count how many have '_composition' suffix
        composition_count = df['medium_id'].str.endswith('_composition').sum()
        logger.info(f"Found {composition_count} medium_id values with '_composition' suffix")
        
        # Remove '_composition' suffix
        df['medium_id'] = df['medium_id'].str.replace('_composition$', '', regex=True)
        
        # Check results
        sample_ids_after = df['medium_id'].head(10).tolist()
        logger.info(f"Sample medium_id values after: {sample_ids_after}")
        
        # Verify no '_composition' suffixes remain
        remaining_composition = df['medium_id'].str.endswith('_composition').sum()
        logger.info(f"Remaining '_composition' suffixes: {remaining_composition}")
        
        if remaining_composition == 0:
            logger.info("✓ Successfully removed all '_composition' suffixes")
        else:
            logger.warning(f"⚠ {remaining_composition} '_composition' suffixes still remain")
        
        # Show unique medium types
        unique_ids = df['medium_id'].unique()
        logger.info(f"Total unique medium IDs: {len(unique_ids)}")
        
        # Show examples by source type
        source_examples = {}
        for idx, row in df.iterrows():
            medium_id = row['medium_id']
            if medium_id.startswith('dsmz_'):
                source_examples['DSMZ'] = medium_id
            elif medium_id.startswith('ccap_'):
                source_examples['CCAP'] = medium_id
            elif medium_id.startswith('atcc_'):
                source_examples['ATCC'] = medium_id
            elif medium_id.startswith('cyanosite_'):
                source_examples['CyanoSite'] = medium_id
            
            if len(source_examples) >= 4:  # Stop after we have examples from different sources
                break
        
        logger.info("Examples of cleaned medium IDs by source:")
        for source, example in source_examples.items():
            logger.info(f"  {source}: {example}")
    else:
        logger.error("medium_id column not found!")
        return df
    
    # Save the corrected dataset
    df.to_csv(output_file, sep='\t', index=False)
    logger.info(f"✓ Saved corrected dataset to: {output_file}")
    
    return df

def main():
    parser = argparse.ArgumentParser(description="Fix medium_id values")
    parser.add_argument("--input", required=True, help="Input TSV file")
    parser.add_argument("--output", required=True, help="Output TSV file")
    
    args = parser.parse_args()
    fix_medium_ids(args.input, args.output)

if __name__ == "__main__":
    main()