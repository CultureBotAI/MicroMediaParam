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
    
    # 1. First, handle duplicate columns by renaming them
    columns = list(df.columns)
    
    # Find hydration_number column and water_molecules columns
    hydration_number_idx = None
    water_molecules_indices = []
    
    for i, col in enumerate(columns):
        if col == 'hydration_number':
            hydration_number_idx = i
        elif col == 'water_molecules':
            water_molecules_indices.append(i)
    
    # Create new column names to avoid duplicates temporarily
    new_columns = columns.copy()
    if hydration_number_idx is not None:
        new_columns[hydration_number_idx] = 'new_water_molecules'
        logger.info("✓ Marked 'hydration_number' for renaming to 'new_water_molecules'")
    
    # Rename duplicate water_molecules columns
    for i, idx in enumerate(water_molecules_indices):
        new_columns[idx] = f'old_water_molecules_{i}'
        logger.info(f"✓ Marked 'water_molecules' column {i} for removal")
    
    # Apply new column names
    df.columns = new_columns
    
    # 2. Now rename new_water_molecules to water_molecules and drop old ones
    if 'new_water_molecules' in df.columns:
        df = df.rename(columns={'new_water_molecules': 'water_molecules'})
        logger.info("✓ Renamed to final 'water_molecules' column")
    
    # Drop old water_molecules columns
    cols_to_drop = [col for col in df.columns if col.startswith('old_water_molecules_')]
    if cols_to_drop:
        df = df.drop(columns=cols_to_drop)
        logger.info(f"✓ Removed {len(cols_to_drop)} duplicate water_molecules columns")
    
    # Also remove hydration_number_extracted if it exists (seems redundant)
    if 'hydration_number_extracted' in df.columns:
        df = df.drop(columns=['hydration_number_extracted'])
        logger.info("✓ Removed redundant 'hydration_number_extracted' column")
    
    # 3. Replace 'already_mapped' with 'anhydrous' in hydration_state column
    if 'hydration_state' in df.columns:
        before_count = (df['hydration_state'] == 'already_mapped').sum()
        df.loc[df['hydration_state'] == 'already_mapped', 'hydration_state'] = 'anhydrous'
        after_count = (df['hydration_state'] == 'anhydrous').sum()
        logger.info(f"✓ Replaced 'already_mapped' with 'anhydrous': {before_count} cases")
    
    # 4. Clean up water_molecules column data
    if 'water_molecules' in df.columns:
        # Handle the water_molecules column more carefully
        def clean_water_molecules(val):
            if pd.isna(val):
                return 0
            if isinstance(val, str):
                if val == '' or val.lower() == 'nan':
                    return 0
                if val == 'x':
                    return 'x'
                try:
                    return int(float(val))
                except:
                    return val
            try:
                return int(val)
            except:
                return val
        
        df['water_molecules'] = df['water_molecules'].apply(clean_water_molecules)
        logger.info("✓ Cleaned water_molecules column")
    
    # 5. Check for and report data quality
    logger.info("Checking for data quality issues...")
    
    # Check for any NaN values
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
    
    # Show final column structure
    logger.info(f"\nFinal dataset structure:")
    logger.info(f"  Shape: {df.shape}")
    logger.info(f"  Columns ({len(df.columns)}): {list(df.columns)}")
    
    # Show examples of hydrated compounds
    if 'water_molecules' in df.columns and 'original' in df.columns:
        hydrated_examples = df[df['water_molecules'].astype(str) != '0'].head(5)
        logger.info(f"\nExamples of hydrated compounds:")
        for idx, row in hydrated_examples.iterrows():
            logger.info(f"  {row['original']}: {row['water_molecules']} water molecules")
    
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