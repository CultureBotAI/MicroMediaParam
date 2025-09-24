#!/usr/bin/env python3
"""
Apply OAK CHEBI annotation results to update composition_kg_mapping.tsv

This script processes JSON annotations from OAK annotate command and updates
the composition mapping file with new CHEBI mappings.
"""

import json
import pandas as pd
import logging
from pathlib import Path
from typing import Dict, List, Set, Optional
import argparse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_oak_annotations(annotations_file: Path, compounds_file: Path) -> Dict[str, str]:
    """Load OAK JSON annotations and extract compound -> CHEBI mappings.
    
    OAK annotate produces text annotations that find matches within compound strings.
    We need to map these back to the original compound names.
    """
    
    if not annotations_file.exists():
        logger.error(f"OAK annotations file not found: {annotations_file}")
        return {}
    
    if not compounds_file.exists():
        logger.error(f"Original compounds file not found: {compounds_file}")
        return {}
    
    logger.info(f"Loading OAK annotations from: {annotations_file}")
    
    # Load original compound list
    with open(compounds_file, 'r') as f:
        original_compounds = [line.strip() for line in f if line.strip()]
    
    logger.info(f"Loaded {len(original_compounds)} original compounds")
    
    compound_mappings = {}
    
    try:
        with open(annotations_file, 'r') as f:
            annotations = json.load(f)
        
        if not isinstance(annotations, list):
            logger.error("Expected OAK annotations to be a list of TextAnnotation objects")
            return {}
        
        logger.info(f"Processing {len(annotations)} text annotations...")
        
        # Group annotations by match_string to find best matches
        match_groups = {}
        for annotation in annotations:
            if isinstance(annotation, dict) and 'match_string' in annotation:
                match_str = annotation['match_string'].lower()
                if match_str not in match_groups:
                    match_groups[match_str] = []
                match_groups[match_str].append(annotation)
        
        logger.info(f"Found matches for {len(match_groups)} different strings")
        
        # For each original compound, try to find the best CHEBI mapping
        matches_found = 0
        
        for compound in original_compounds:
            compound_lower = compound.lower()
            best_chebi = None
            best_score = 0
            
            # Look for exact matches first
            if compound_lower in match_groups:
                # Take the first CHEBI match (they're sorted by relevance)
                for annotation in match_groups[compound_lower]:
                    if annotation.get('object_id', '').startswith('CHEBI:'):
                        best_chebi = annotation['object_id']
                        best_score = 100  # Perfect match
                        break
            
            # Look for partial matches within the compound string
            if not best_chebi:
                for match_str, match_annotations in match_groups.items():
                    if match_str in compound_lower and len(match_str) > 3:  # Avoid short spurious matches
                        match_score = len(match_str) / len(compound_lower) * 100
                        if match_score > best_score:
                            # Find the best CHEBI ID for this match
                            for annotation in match_annotations:
                                if annotation.get('object_id', '').startswith('CHEBI:'):
                                    best_chebi = annotation['object_id']
                                    best_score = match_score
                                    break
            
            if best_chebi:
                compound_mappings[compound] = best_chebi
                matches_found += 1
        
        logger.info(f"Mapped {matches_found} compounds to CHEBI IDs")
        
        # Show sample mappings
        if compound_mappings:
            logger.info("Sample OAK mappings:")
            for i, (compound, chebi_id) in enumerate(list(compound_mappings.items())[:10], 1):
                logger.info(f"  {i:2d}. {compound} -> {chebi_id}")
            
            if len(compound_mappings) > 10:
                logger.info(f"  ... and {len(compound_mappings) - 10} more mappings")
        else:
            logger.warning("No compound mappings could be extracted from OAK annotations")
        
        return compound_mappings
    
    except Exception as e:
        logger.error(f"Error loading OAK annotations: {e}")
        return {}

def apply_chebi_mappings(mapping_df: pd.DataFrame, chebi_mappings: Dict[str, str]) -> pd.DataFrame:
    """Apply CHEBI mappings to the composition mapping DataFrame."""
    
    logger.info("Applying CHEBI mappings to composition data...")
    
    # Create a copy to avoid modifying the original
    updated_df = mapping_df.copy()
    
    # Track statistics
    compounds_updated = 0
    rows_updated = 0
    mapping_conflicts = []
    
    for compound, chebi_id in chebi_mappings.items():
        # Find rows with this compound that are not already mapped to CHEBI
        compound_mask = (updated_df['original'] == compound) & \
                       (~updated_df['mapped'].str.startswith('CHEBI:', na=False))
        
        matching_rows = updated_df[compound_mask]
        
        if len(matching_rows) > 0:
            # Check for existing non-CHEBI mappings
            existing_mappings = matching_rows['mapped'].dropna()
            existing_mappings = existing_mappings[existing_mappings != '']
            
            if len(existing_mappings) > 0:
                # Log potential conflicts
                unique_existing = existing_mappings.unique()
                if len(unique_existing) > 0:
                    mapping_conflicts.append({
                        'compound': compound,
                        'new_chebi': chebi_id,
                        'existing': list(unique_existing),
                        'row_count': len(matching_rows)
                    })
            
            # Apply the CHEBI mapping
            updated_df.loc[compound_mask, 'mapped'] = chebi_id
            compounds_updated += 1
            rows_updated += len(matching_rows)
    
    logger.info(f"Applied CHEBI mappings:")
    logger.info(f"  Compounds updated: {compounds_updated}")
    logger.info(f"  Rows updated: {rows_updated}")
    
    if mapping_conflicts:
        logger.warning(f"Found {len(mapping_conflicts)} mapping conflicts:")
        for conflict in mapping_conflicts[:5]:  # Show first 5 conflicts
            logger.warning(f"  {conflict['compound']}: {conflict['existing']} -> {conflict['new_chebi']} ({conflict['row_count']} rows)")
        
        if len(mapping_conflicts) > 5:
            logger.warning(f"  ... and {len(mapping_conflicts) - 5} more conflicts")
    
    return updated_df

def analyze_mapping_improvement(original_df: pd.DataFrame, updated_df: pd.DataFrame) -> None:
    """Analyze the improvement in mapping coverage."""
    
    logger.info("Analyzing mapping coverage improvement...")
    
    # Count CHEBI mappings before and after
    original_chebi = (original_df['mapped'].str.startswith('CHEBI:', na=False)).sum()
    updated_chebi = (updated_df['mapped'].str.startswith('CHEBI:', na=False)).sum()
    
    # Count unmapped before and after
    original_unmapped = (original_df['mapped'].isna() | (original_df['mapped'] == '')).sum()
    updated_unmapped = (updated_df['mapped'].isna() | (updated_df['mapped'] == '')).sum()
    
    total_rows = len(original_df)
    
    logger.info("Coverage improvement:")
    logger.info(f"  CHEBI mappings: {original_chebi} -> {updated_chebi} (+{updated_chebi - original_chebi})")
    logger.info(f"  CHEBI coverage: {original_chebi/total_rows*100:.2f}% -> {updated_chebi/total_rows*100:.2f}% (+{(updated_chebi - original_chebi)/total_rows*100:.2f}%)")
    logger.info(f"  Unmapped entries: {original_unmapped} -> {updated_unmapped} ({updated_unmapped - original_unmapped})")
    logger.info(f"  Unmapped rate: {original_unmapped/total_rows*100:.2f}% -> {updated_unmapped/total_rows*100:.2f}% ({(updated_unmapped - original_unmapped)/total_rows*100:.2f}%)")

def main():
    """Main function."""
    
    parser = argparse.ArgumentParser(
        description="Apply OAK CHEBI annotations to composition mapping"
    )
    parser.add_argument(
        '--mapping-file',
        type=Path,
        default=Path('composition_kg_mapping.tsv'),
        help='Input composition mapping file (default: composition_kg_mapping.tsv)'
    )
    parser.add_argument(
        '--annotations-file',
        type=Path,
        default=Path('data/oak_chebi_annotations.json'),
        help='OAK annotations JSON file (default: data/oak_chebi_annotations.json)'
    )
    parser.add_argument(
        '--compounds-file',
        type=Path,
        default=Path('compounds_for_chebi_mapping.txt'),
        help='Original compounds file (default: compounds_for_chebi_mapping.txt)'
    )
    parser.add_argument(
        '--output-file',
        type=Path,
        default=Path('composition_kg_mapping_updated.tsv'),
        help='Output updated mapping file (default: composition_kg_mapping_updated.tsv)'
    )
    parser.add_argument(
        '--backup',
        action='store_true',
        help='Create backup of original mapping file'
    )
    
    args = parser.parse_args()
    
    print("🔄 Applying OAK CHEBI Annotations to Composition Mapping")
    print("=" * 55)
    
    # Check input files
    if not args.mapping_file.exists():
        logger.error(f"Mapping file not found: {args.mapping_file}")
        return
    
    if not args.annotations_file.exists():
        logger.error(f"Annotations file not found: {args.annotations_file}")
        logger.info("Run 'make oak-chebi-annotate' first to generate annotations")
        return
    
    # Load original mapping
    logger.info(f"Loading composition mapping from: {args.mapping_file}")
    original_df = pd.read_csv(args.mapping_file, sep='\t')
    logger.info(f"Loaded {len(original_df):,} mapping entries")
    
    # Create backup if requested
    if args.backup:
        backup_file = args.mapping_file.with_suffix('.tsv.backup')
        original_df.to_csv(backup_file, sep='\t', index=False)
        logger.info(f"Created backup: {backup_file}")
    
    # Load OAK annotations
    chebi_mappings = load_oak_annotations(args.annotations_file, args.compounds_file)
    
    if not chebi_mappings:
        logger.warning("No CHEBI mappings found in annotations file")
        return
    
    # Apply mappings
    updated_df = apply_chebi_mappings(original_df, chebi_mappings)
    
    # Analyze improvement
    analyze_mapping_improvement(original_df, updated_df)
    
    # Save updated mapping
    logger.info(f"Saving updated mapping to: {args.output_file}")
    updated_df.to_csv(args.output_file, sep='\t', index=False)
    
    logger.info("✅ OAK CHEBI mapping application completed!")
    
    print(f"\n🚀 Next steps:")
    print(f"  1. Review the updated mapping file: {args.output_file}")
    print(f"  2. Replace original if satisfied:")
    print(f"     mv {args.output_file} {args.mapping_file}")
    print(f"  3. Continue with downstream analysis:")
    print(f"     make compute-properties")

if __name__ == "__main__":
    main()