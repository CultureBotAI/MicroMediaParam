#!/usr/bin/env python3
"""Create a final non-redundant version of compound mappings with high-quality matches only."""

import pandas as pd
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def create_final_nonredundant_mappings(input_file, output_file):
    """Create final non-redundant compound mappings with only high-quality matches."""
    
    logging.info(f"Loading unified mappings from {input_file}")
    df = pd.read_csv(input_file, sep='\t', dtype=str)
    
    # Report initial statistics
    logging.info(f"Total rows: {len(df)}")
    logging.info(f"Total unique compounds: {df['original'].nunique()}")
    
    # Filter out unmapped entries and low/medium confidence matches
    logging.info("\nFiltering criteria:")
    logging.info("- Removing unmapped entries (mapping_status == 'unmapped')")
    logging.info("- Removing low confidence matches (match_confidence == 'low')")
    logging.info("- Removing medium confidence matches (match_confidence == 'medium')")
    
    # Apply filters
    df_filtered = df[
        (df['mapping_status'] != 'unmapped') &
        (df['match_confidence'] != 'low') &
        (df['match_confidence'] != 'medium')
    ].copy()
    
    logging.info(f"\nRows after filtering: {len(df_filtered)} (removed {len(df) - len(df_filtered)} rows)")
    
    # Check for problematic normalizations
    problematic_mappings = df_filtered[
        df_filtered['original'].str.contains('NH4', na=False) & 
        df_filtered['chebi_original_name'].str.contains('potassium', na=False)
    ]
    
    if len(problematic_mappings) > 0:
        logging.warning(f"\nFound {len(problematic_mappings)} problematic NH4 -> potassium mappings:")
        for _, row in problematic_mappings.head().iterrows():
            logging.warning(f"  {row['original']} -> {row['chebi_original_name']} (ChEBI:{row['chebi_id']})")
        
        # Remove these problematic mappings
        df_filtered = df_filtered[~(
            df_filtered['original'].str.contains('NH4', na=False) & 
            df_filtered['chebi_original_name'].str.contains('potassium', na=False)
        )]
        logging.info(f"Removed {len(problematic_mappings)} problematic mappings")
    
    # Select columns relevant for compound mapping
    mapping_columns = [
        'original', 'mapped', 'normalized_compound', 'hydration_number',
        'chebi_match', 'chebi_id', 'chebi_original_name', 
        'similarity_score', 'match_confidence', 'matching_method',
        'mapping_status', 'mapping_quality'
    ]
    
    # Keep only mapping columns that exist
    available_columns = [col for col in mapping_columns if col in df_filtered.columns]
    df_mapping = df_filtered[available_columns].copy()
    
    # Remove duplicates based on 'original' compound name
    # For compounds with multiple high-confidence mappings, prefer:
    # 1. exact_normalized over fuzzy methods
    # 2. higher similarity scores
    # 3. mapping_quality: excellent > very_good > good
    
    # Sort to ensure best mapping is kept when dropping duplicates
    quality_order = {'excellent': 0, 'very_good': 1, 'good': 2}
    method_order = {'exact_normalized': 0, 'exact_label': 1, 'fuzzy_normalized': 2, 'fuzzy_label': 3}
    
    df_mapping['quality_rank'] = df_mapping['mapping_quality'].map(quality_order).fillna(3)
    df_mapping['method_rank'] = df_mapping['matching_method'].map(method_order).fillna(4)
    df_mapping['similarity_score_num'] = pd.to_numeric(df_mapping['similarity_score'], errors='coerce').fillna(0)
    
    # Sort by quality, method, and similarity score (best first)
    df_mapping = df_mapping.sort_values(
        ['original', 'quality_rank', 'method_rank', 'similarity_score_num'],
        ascending=[True, True, True, False]
    )
    
    # Remove duplicates, keeping the best mapping for each compound
    df_nonredundant = df_mapping.drop_duplicates(subset=['original'], keep='first')
    
    # Remove temporary ranking columns
    df_nonredundant = df_nonredundant.drop(['quality_rank', 'method_rank', 'similarity_score_num'], axis=1)
    
    # Sort by compound name for readability
    df_nonredundant = df_nonredundant.sort_values('original')
    
    # Report statistics
    logging.info(f"\nFinal non-redundant mapping statistics:")
    logging.info(f"Total unique compounds: {len(df_nonredundant)}")
    
    # Count mapping quality
    quality_counts = df_nonredundant['mapping_quality'].value_counts()
    logging.info(f"\nMapping quality distribution:")
    for quality, count in quality_counts.items():
        percentage = (count / len(df_nonredundant)) * 100
        logging.info(f"  {quality}: {count} ({percentage:.1f}%)")
    
    # Count matching methods
    method_counts = df_nonredundant['matching_method'].value_counts()
    logging.info(f"\nMatching method distribution:")
    for method, count in method_counts.items():
        percentage = (count / len(df_nonredundant)) * 100
        logging.info(f"  {method}: {count} ({percentage:.1f}%)")
    
    # Count confidence levels
    confidence_counts = df_nonredundant['match_confidence'].value_counts()
    logging.info(f"\nConfidence level distribution:")
    for conf, count in confidence_counts.items():
        percentage = (count / len(df_nonredundant)) * 100
        logging.info(f"  {conf}: {count} ({percentage:.1f}%)")
    
    # Save final non-redundant mappings
    logging.info(f"\nSaving final non-redundant mappings to {output_file}")
    df_nonredundant.to_csv(output_file, sep='\t', index=False)
    
    # Show some examples
    logging.info(f"\nExample high-quality mappings:")
    examples = df_nonredundant[df_nonredundant['mapping_quality'] == 'excellent'].head(10)
    for _, row in examples.iterrows():
        kg_id = row.get('mapped', 'None')
        chebi_id = row.get('chebi_id', 'None')
        chebi_name = row.get('chebi_original_name', 'None')
        method = row.get('matching_method', 'none')
        logging.info(f"  {row['original']} -> ChEBI:{chebi_id} ({chebi_name}) [{method}]")
    
    # Check for remaining NH4 compounds
    nh4_compounds = df_nonredundant[df_nonredundant['original'].str.contains('NH4', na=False)]
    logging.info(f"\nNH4 compounds in final mapping: {len(nh4_compounds)}")
    if len(nh4_compounds) > 0:
        logging.info("Examples:")
        for _, row in nh4_compounds.head(5).iterrows():
            chebi_name = row.get('chebi_original_name', 'No ChEBI name')
            chebi_id = row.get('chebi_id', 'No ChEBI')
            logging.info(f"  {row['original']} -> {chebi_name} (ChEBI:{chebi_id})")
    
    return df_nonredundant

if __name__ == "__main__":
    input_file = "pipeline_output/merge_mappings/unified_compound_mappings.tsv"
    output_file = "pipeline_output/merge_mappings/final_nonredundant_compound_mappings.tsv"
    
    create_final_nonredundant_mappings(input_file, output_file)