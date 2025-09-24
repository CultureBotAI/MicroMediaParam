#!/usr/bin/env python3
"""
Clean up the final dataset:
1. Rename hydration_number to water_molecules
2. Remove the duplicate water_molecules column
3. Replace 'already_mapped' with 'anhydrous' in hydration_state
4. Fix any extra tab issues
"""

import pandas as pd
import argparse
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def clean_final_dataset(input_file, output_file):
    """Clean up the final dataset with the requested changes."""
    
    logger.info(f"Loading file: {input_file}")
    df = pd.read_csv(input_file, sep='\t')
    
    logger.info(f"Original dataset shape: {df.shape}")
    logger.info(f"Original columns: {list(df.columns)}")
    
    # 1. Rename hydration_number to water_molecules
    if 'hydration_number' in df.columns:
        df = df.rename(columns={'hydration_number': 'water_molecules'})
        logger.info("✓ Renamed 'hydration_number' to 'water_molecules'")
    
    # 2. Remove duplicate water_molecules column if it exists
    # Check if there are duplicate column names
    columns = list(df.columns)
    if columns.count('water_molecules') > 1:
        logger.info(f"Found {columns.count('water_molecules')} 'water_molecules' columns")
        
        # Find indices of water_molecules columns
        water_mol_indices = [i for i, col in enumerate(columns) if col == 'water_molecules']
        
        # Keep the first one (the renamed hydration_number), remove others
        columns_to_keep = []
        for i, col in enumerate(columns):
            if col == 'water_molecules':
                if i == water_mol_indices[0]:
                    columns_to_keep.append(col)  # Keep first occurrence
                # Skip other occurrences
            else:
                columns_to_keep.append(col)
        
        # Reorder dataframe to keep only desired columns
        df = df[columns_to_keep]
        logger.info(f"✓ Removed duplicate 'water_molecules' columns, kept one")
    
    # 3. Replace 'already_mapped' with 'anhydrous' in hydration_state column
    if 'hydration_state' in df.columns:
        before_count = (df['hydration_state'] == 'already_mapped').sum()
        df.loc[df['hydration_state'] == 'already_mapped', 'hydration_state'] = 'anhydrous'
        after_count = (df['hydration_state'] == 'anhydrous').sum()
        logger.info(f"✓ Replaced 'already_mapped' with 'anhydrous': {before_count} cases")
    
    # 4. Check for and fix any data quality issues
    logger.info("Checking for data quality issues...")
    
    # Check for rows with unexpected number of columns
    expected_cols = len(df.columns)
    
    # Reset index to ensure clean data
    df = df.reset_index(drop=True)
    
    # Check for any NaN values that might indicate tab issues
    total_cells = df.shape[0] * df.shape[1]
    nan_cells = df.isnull().sum().sum()
    if nan_cells > 0:
        logger.info(f"Found {nan_cells} NaN cells out of {total_cells} total cells ({nan_cells/total_cells*100:.2f}%)")
    
    # Clean up hydration_state values
    if 'hydration_state' in df.columns:
        unique_states = df['hydration_state'].value_counts()
        logger.info(f"Hydration states after cleanup:")
        for state, count in unique_states.items():
            logger.info(f"  {state}: {count:,}")
    
    # Ensure water_molecules column has consistent data types
    if 'water_molecules' in df.columns:
        # Convert 'x' to string, numbers to int where possible
        def clean_water_molecules(val):
            if pd.isna(val) or val == '':
                return 0
            if val == 'x':
                return 'x'
            try:
                return int(float(val))
            except:
                return val
        
        df['water_molecules'] = df['water_molecules'].apply(clean_water_molecules)
        logger.info("✓ Cleaned water_molecules column")
    
    # Show final column structure
    logger.info(f"\nFinal dataset structure:")
    logger.info(f"  Shape: {df.shape}")
    logger.info(f"  Columns ({len(df.columns)}): {list(df.columns)}")
    
    # Show examples of key columns
    key_columns = ['medium_id', 'original', 'base_compound', 'water_molecules', 'hydrate_formula', 
                   'base_chebi_id', 'base_chebi_label', 'hydration_state']
    available_key_cols = [col for col in key_columns if col in df.columns]
    
    if available_key_cols:
        logger.info(f"\nExample rows (first 5):")
        example_df = df[available_key_cols].head(5)
        for idx, row in example_df.iterrows():
            logger.info(f"  Row {idx+1}: {dict(row)}")
    
    # Save the cleaned dataset
    df.to_csv(output_file, sep='\t', index=False)
    logger.info(f"\n✓ Saved cleaned dataset to: {output_file}")
    
    # Verify no extra tabs by checking if file reads correctly
    verify_df = pd.read_csv(output_file, sep='\t')
    if verify_df.shape == df.shape:
        logger.info("✓ File verification passed - no extra tab issues")
    else:
        logger.warning(f"⚠ File verification failed - shape mismatch: {verify_df.shape} vs {df.shape}")
    
    return df

def main():
    parser = argparse.ArgumentParser(description="Clean up final dataset")
    parser.add_argument("--input", required=True, help="Input TSV file")
    parser.add_argument("--output", required=True, help="Output TSV file")
    
    args = parser.parse_args()
    clean_final_dataset(args.input, args.output)

if __name__ == "__main__":
    main()