#!/usr/bin/env python3
"""Create a non-redundant version of unified compound mappings."""

import pandas as pd
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def create_nonredundant_mappings(input_file, output_file):
    """Create non-redundant compound mappings by keeping unique compounds."""
    
    logging.info(f"Loading unified mappings from {input_file}")
    df = pd.read_csv(input_file, sep='\t', dtype=str)
    
    # Report initial statistics
    logging.info(f"Total rows: {len(df)}")
    logging.info(f"Total unique compounds: {df['original'].nunique()}")
    
    # Select columns relevant for compound mapping (exclude medium-specific info)
    mapping_columns = [
        'original', 'mapped', 'normalized_compound', 'hydration_number',
        'chebi_match', 'chebi_id', 'chebi_original_name', 
        'similarity_score', 'match_confidence', 'matching_method',
        'mapping_status', 'mapping_quality'
    ]
    
    # Keep only mapping columns that exist
    available_columns = [col for col in mapping_columns if col in df.columns]
    df_mapping = df[available_columns].copy()
    
    # Remove duplicates based on 'original' compound name
    # Keep the first occurrence which typically has the best mapping
    df_nonredundant = df_mapping.drop_duplicates(subset=['original'], keep='first')
    
    # Sort by mapping quality (best first) and compound name
    quality_order = {'excellent': 0, 'very_good': 1, 'good': 2, 'none': 3}
    df_nonredundant['quality_rank'] = df_nonredundant['mapping_quality'].map(quality_order).fillna(4)
    df_nonredundant = df_nonredundant.sort_values(['quality_rank', 'original'])
    df_nonredundant = df_nonredundant.drop('quality_rank', axis=1)
    
    # Report statistics
    logging.info(f"\nNon-redundant mapping statistics:")
    logging.info(f"Total unique compounds: {len(df_nonredundant)}")
    
    # Count mapping quality
    quality_counts = df_nonredundant['mapping_quality'].value_counts()
    logging.info(f"\nMapping quality distribution:")
    for quality, count in quality_counts.items():
        percentage = (count / len(df_nonredundant)) * 100
        logging.info(f"  {quality}: {count} ({percentage:.1f}%)")
    
    # Count mapping status
    status_counts = df_nonredundant['mapping_status'].value_counts()
    logging.info(f"\nMapping status distribution:")
    for status, count in status_counts.items():
        percentage = (count / len(df_nonredundant)) * 100
        logging.info(f"  {status}: {count} ({percentage:.1f}%)")
    
    # Check ChEBI coverage
    has_kg_mapping = df_nonredundant['mapped'].notna() & (df_nonredundant['mapped'] != '')
    has_chebi_match = df_nonredundant['chebi_id'].notna() & (df_nonredundant['chebi_id'] != '')
    has_any_mapping = has_kg_mapping | has_chebi_match
    
    logging.info(f"\nMapping coverage:")
    logging.info(f"  Compounds with KG mapping: {has_kg_mapping.sum()} ({(has_kg_mapping.sum() / len(df_nonredundant)) * 100:.1f}%)")
    logging.info(f"  Compounds with ChEBI match: {has_chebi_match.sum()} ({(has_chebi_match.sum() / len(df_nonredundant)) * 100:.1f}%)")
    logging.info(f"  Compounds with any mapping: {has_any_mapping.sum()} ({(has_any_mapping.sum() / len(df_nonredundant)) * 100:.1f}%)")
    
    # Save non-redundant mappings
    logging.info(f"\nSaving non-redundant mappings to {output_file}")
    df_nonredundant.to_csv(output_file, sep='\t', index=False)
    
    # Show some examples
    logging.info(f"\nExample mappings:")
    examples = df_nonredundant.head(10)
    for _, row in examples.iterrows():
        kg_id = row.get('mapped', 'None')
        chebi_id = row.get('chebi_id', 'None')
        quality = row.get('mapping_quality', 'none')
        logging.info(f"  {row['original']} -> KG: {kg_id}, ChEBI: {chebi_id} [{quality}]")
    
    return df_nonredundant

if __name__ == "__main__":
    input_file = "pipeline_output/merge_mappings/unified_compound_mappings.tsv"
    output_file = "pipeline_output/merge_mappings/nonredundant_compound_mappings.tsv"
    
    create_nonredundant_mappings(input_file, output_file)