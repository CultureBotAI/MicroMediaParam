#!/usr/bin/env python3
"""
Merge additional ingredient mappings into compound lookup table.

Takes the output from map_unmapped_ingredients.py and merges it into
the existing compound_name_lookup.tsv to create an extended version.

Usage:
    python -m src.mapping.merge_additional_mappings \
        --lookup-table pipeline_output/merge_mappings/compound_name_lookup.tsv \
        --additional pipeline_output/merge_mappings/additional_ingredient_mappings.tsv \
        --output pipeline_output/merge_mappings/compound_name_lookup_extended.tsv
"""

import argparse
import logging
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from src.mapping.compound_normalizer import get_excluded_cas_mappings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class MergeStats:
    """Statistics from merge operation."""
    original_count: int = 0
    additional_count: int = 0
    additional_mapped: int = 0
    new_added: int = 0
    duplicates_skipped: int = 0
    blocklisted_removed: int = 0
    final_count: int = 0


def merge_mappings(
    lookup_table: Path,
    additional_mappings: Path,
    output: Path
) -> MergeStats:
    """
    Merge additional mappings into existing lookup table.

    Preserves all original mappings and adds new ones.
    Skips duplicates (same original_name already in lookup table).

    Args:
        lookup_table: Existing compound_name_lookup.tsv
        additional_mappings: New mappings from map_unmapped_ingredients
        output: Output path for extended lookup table

    Returns:
        MergeStats with merge results
    """
    stats = MergeStats()

    # Load existing lookup table
    logger.info(f"Loading existing lookup table from {lookup_table}")
    if lookup_table.exists():
        lookup_df = pd.read_csv(lookup_table, sep='\t')
        stats.original_count = len(lookup_df)
    else:
        logger.warning(f"Lookup table not found: {lookup_table}, creating new")
        lookup_df = pd.DataFrame(columns=[
            'original_name', 'mapped_id', 'chebi_label', 'chebi_formula'
        ])

    logger.info(f"Loaded {stats.original_count} existing mappings")

    # Get set of existing names for deduplication
    existing_names = set(lookup_df['original_name'].str.lower().dropna())

    # Load additional mappings
    logger.info(f"Loading additional mappings from {additional_mappings}")
    additional_df = pd.read_csv(additional_mappings, sep='\t')
    stats.additional_count = len(additional_df)

    # Count how many have mappings
    mapped_mask = additional_df['mapped_id'].notna() & (additional_df['mapped_id'] != '')
    stats.additional_mapped = mapped_mask.sum()

    logger.info(f"Found {stats.additional_mapped} mapped entries in additional file")

    # Get blocklist of incorrect CAS mappings
    excluded_cas = get_excluded_cas_mappings()
    logger.info(f"Loaded {len(excluded_cas)} excluded CAS mappings to filter")

    # Prepare new rows
    new_rows = []

    for _, row in additional_df.iterrows():
        original_name = str(row.get('original_name', '')) if pd.notna(row.get('original_name')) else ''
        mapped_id = str(row.get('mapped_id', '')) if pd.notna(row.get('mapped_id')) else ''

        # Skip empty names or unmapped entries
        if not original_name or not mapped_id:
            continue

        # Skip blocklisted CAS mappings (known incorrect mappings from upstream KG)
        if mapped_id in excluded_cas:
            stats.blocklisted_removed += 1
            logger.info(f"Blocked incorrect mapping: '{original_name}' → '{mapped_id}'")
            continue

        # Skip duplicates
        if original_name.lower() in existing_names:
            stats.duplicates_skipped += 1
            continue

        # Get label and formula from additional mappings
        # Use mapped_label for label, formula for formula
        label = str(row.get('mapped_label', '')) if pd.notna(row.get('mapped_label')) else ''
        formula = str(row.get('formula', '')) if pd.notna(row.get('formula')) else ''

        new_rows.append({
            'original_name': original_name,
            'mapped_id': mapped_id,
            'chebi_label': label,  # Using same column name for compatibility
            'chebi_formula': formula
        })

        existing_names.add(original_name.lower())
        stats.new_added += 1

    logger.info(f"Adding {stats.new_added} new mappings, skipped {stats.duplicates_skipped} duplicates")

    # Combine dataframes
    if new_rows:
        new_df = pd.DataFrame(new_rows)
        merged_df = pd.concat([lookup_df, new_df], ignore_index=True)
    else:
        merged_df = lookup_df

    # Sort by original name (case-insensitive)
    merged_df = merged_df.sort_values(
        by='original_name',
        key=lambda x: x.str.lower()
    )

    stats.final_count = len(merged_df)

    # Save output
    output.parent.mkdir(parents=True, exist_ok=True)
    merged_df.to_csv(output, sep='\t', index=False)

    logger.info(f"Saved merged lookup table to {output}")

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Merge additional ingredient mappings into compound lookup table"
    )
    parser.add_argument(
        "--lookup-table",
        type=Path,
        required=True,
        help="Existing compound_name_lookup.tsv"
    )
    parser.add_argument(
        "--additional",
        type=Path,
        required=True,
        help="Additional mappings from map_unmapped_ingredients"
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output path for extended lookup table"
    )

    args = parser.parse_args()

    stats = merge_mappings(
        args.lookup_table,
        args.additional,
        args.output
    )

    # Print summary
    print("\n" + "=" * 60)
    print("MERGE MAPPINGS COMPLETE")
    print("=" * 60)
    print(f"Original mappings:     {stats.original_count}")
    print(f"Additional file:       {stats.additional_count}")
    print(f"  - With mappings:     {stats.additional_mapped}")
    print()
    print("Merge results:")
    print(f"  New added:           {stats.new_added}")
    print(f"  Duplicates skipped:  {stats.duplicates_skipped}")
    print(f"  Blocklisted removed: {stats.blocklisted_removed}")
    print()
    print(f"Final mappings:        {stats.final_count}")
    print(f"Net gain:              +{stats.final_count - stats.original_count}")
    print()
    print(f"Output:                {args.output}")
    print("=" * 60)


if __name__ == "__main__":
    main()
