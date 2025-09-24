#!/usr/bin/env python3
"""
Find cases where the original compound name doesn't match the ChEBI label.
This helps identify potential mapping errors or name inconsistencies.
"""

import pandas as pd
import argparse
import logging
import re
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def normalize_name(name):
    """Normalize compound names for comparison."""
    if not name or pd.isna(name):
        return ''
    
    # Convert to lowercase
    name = str(name).lower().strip()
    
    # Remove common variations
    name = re.sub(r'\s+', ' ', name)  # Multiple spaces to single
    name = re.sub(r'[()[\]]', '', name)  # Remove brackets
    name = re.sub(r'[-_]', ' ', name)   # Hyphens/underscores to spaces
    name = re.sub(r'\s*\d+\s*hydrate.*', '', name)  # Remove hydration info
    name = re.sub(r'\s*x\s*h2o.*', '', name)  # Remove x H2O
    name = re.sub(r'\s*\d+\s*h2o.*', '', name)  # Remove specific hydration
    name = re.sub(r'\s*monohydrate.*', '', name)  # Remove monohydrate
    name = re.sub(r'\s*dihydrate.*', '', name)  # Remove dihydrate
    name = re.sub(r'\s*heptahydrate.*', '', name)  # Remove heptahydrate
    name = re.sub(r'\s*hexahydrate.*', '', name)  # Remove hexahydrate
    name = re.sub(r'\s*pentahydrate.*', '', name)  # Remove pentahydrate
    name = re.sub(r'\s*tetrahydrate.*', '', name)  # Remove tetrahydrate
    name = re.sub(r'\s*trihydrate.*', '', name)  # Remove trihydrate
    
    # Chemical name normalizations
    name = name.replace('l cysteine', 'cysteine')
    name = name.replace('l ', '')  # Remove L- prefix
    name = name.replace('d ', '')  # Remove D- prefix
    name = name.replace('dl ', '')  # Remove DL- prefix
    name = name.replace('alpha ', '')  # Remove alpha prefix
    name = name.replace('beta ', '')  # Remove beta prefix
    name = name.replace('gamma ', '')  # Remove gamma prefix
    name = name.replace(' acid', '')  # Remove acid suffix for comparison
    name = name.replace('ic acid', 'ic')  # Nicotinic acid -> nicotinic
    name = name.replace('benzoic', 'aminobenzoic')  # p-aminobenzoic
    name = name.replace('lipoic', 'alpha lipoic')  # alpha-lipoic
    
    # Salt name normalizations
    name = name.replace('hcl', 'hydrochloride')
    name = name.replace(' cl', ' chloride')
    name = name.replace(' so4', ' sulfate')
    name = name.replace(' no3', ' nitrate')
    name = name.replace(' co3', ' carbonate')
    name = name.replace(' po4', ' phosphate')
    name = name.replace('h2po4', 'dihydrogen phosphate')
    name = name.replace('hpo4', 'hydrogen phosphate')
    name = name.replace('hco3', 'hydrogencarbonate')
    name = name.replace('moo4', 'molybdate')
    name = name.replace('seo3', 'selenite')
    name = name.replace('wo4', 'tungstate')
    
    # Ion charge normalizations
    name = re.sub(r'\s*\(\d+[\+\-]\)\s*', ' ', name)  # Remove (2+) etc
    name = re.sub(r'\s*\d+[\+\-]\s*', ' ', name)  # Remove 2+ etc
    
    # Final cleanup
    name = re.sub(r'\s+', ' ', name).strip()
    
    return name

def calculate_similarity(name1, name2):
    """Calculate simple similarity between two normalized names."""
    if not name1 or not name2:
        return 0.0
    
    # Simple word overlap
    words1 = set(name1.split())
    words2 = set(name2.split())
    
    if not words1 or not words2:
        return 0.0
    
    intersection = words1.intersection(words2)
    union = words1.union(words2)
    
    return len(intersection) / len(union) if union else 0.0

def find_label_mismatches(input_file, output_file):
    """Find cases where original names don't match ChEBI labels."""
    
    logger.info(f"Loading file: {input_file}")
    df = pd.read_csv(input_file, sep='\t')
    
    # Only look at entries with ChEBI labels
    chebi_entries = df[df['base_chebi_label'].notna() & (df['base_chebi_label'] != '')].copy()
    logger.info(f"Found {len(chebi_entries)} entries with ChEBI labels")
    
    # Normalize names for comparison
    chebi_entries['original_normalized'] = chebi_entries['original'].apply(normalize_name)
    chebi_entries['label_normalized'] = chebi_entries['base_chebi_label'].apply(normalize_name)
    
    # Calculate similarity scores
    chebi_entries['similarity'] = chebi_entries.apply(
        lambda row: calculate_similarity(row['original_normalized'], row['label_normalized']), 
        axis=1
    )
    
    # Find mismatches (low similarity)
    threshold = 0.3  # Adjust this threshold as needed
    mismatches = chebi_entries[chebi_entries['similarity'] < threshold].copy()
    
    # Sort by similarity (worst first)
    mismatches = mismatches.sort_values('similarity')
    
    logger.info(f"Found {len(mismatches)} potential mismatches (similarity < {threshold})")
    
    # Prepare output data
    output_data = mismatches[['medium_id', 'original', 'base_compound', 'base_chebi_id', 'base_chebi_label', 
                             'original_normalized', 'label_normalized', 'similarity']].copy()
    
    # Save to file
    output_data.to_csv(output_file, sep='\t', index=False)
    logger.info(f"Saved mismatches to: {output_file}")
    
    # Show statistics
    total_with_labels = len(chebi_entries)
    mismatch_count = len(mismatches)
    mismatch_percent = (mismatch_count / total_with_labels) * 100
    
    logger.info(f"\nMismatch Analysis:")
    logger.info(f"  Total entries with ChEBI labels: {total_with_labels:,}")
    logger.info(f"  Potential mismatches: {mismatch_count:,} ({mismatch_percent:.1f}%)")
    logger.info(f"  Good matches: {total_with_labels - mismatch_count:,} ({100-mismatch_percent:.1f}%)")
    
    # Show examples of mismatches
    logger.info(f"\nWorst mismatches (similarity < 0.1):")
    worst_mismatches = mismatches[mismatches['similarity'] < 0.1]
    for _, row in worst_mismatches.head(10).iterrows():
        logger.info(f"  '{row['original']}' -> '{row['base_chebi_label']}' (similarity: {row['similarity']:.3f})")
    
    # Show examples of borderline cases
    logger.info(f"\nBorderline cases (0.1 <= similarity < {threshold}):")
    borderline = mismatches[(mismatches['similarity'] >= 0.1) & (mismatches['similarity'] < threshold)]
    for _, row in borderline.head(10).iterrows():
        logger.info(f"  '{row['original']}' -> '{row['base_chebi_label']}' (similarity: {row['similarity']:.3f})")
    
    # Analyze by compound type
    logger.info(f"\nMismatch patterns:")
    
    # Hydration-related mismatches
    hydration_mismatches = mismatches[mismatches['original'].str.contains('hydrate|H2O|h2o', case=False, na=False)]
    logger.info(f"  Hydration-related: {len(hydration_mismatches)} cases")
    
    # Salt form mismatches
    salt_mismatches = mismatches[mismatches['original'].str.contains('HCl|hydrochloride', case=False, na=False)]
    logger.info(f"  Salt form mismatches: {len(salt_mismatches)} cases")
    
    # Isomer mismatches (L-, D-, etc.)
    isomer_mismatches = mismatches[mismatches['original'].str.contains(r'\b[LD]-|\bDL-', case=False, na=False)]
    logger.info(f"  Isomer-related: {len(isomer_mismatches)} cases")
    
    return len(mismatches), total_with_labels

def main():
    parser = argparse.ArgumentParser(description="Find mismatches between original names and ChEBI labels")
    parser.add_argument("--input", required=True, help="Input TSV file")
    parser.add_argument("--output", required=True, help="Output TSV file for mismatches")
    
    args = parser.parse_args()
    find_label_mismatches(args.input, args.output)

if __name__ == "__main__":
    main()