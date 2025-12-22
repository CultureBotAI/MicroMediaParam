#!/usr/bin/env python3
"""
Create simplified mapping files with just chemical name, formula, and identifiers.

This script extracts key columns from the full compound mapping files to create
lightweight, non-redundant reference files suitable for external use.

The output contains unique chemicals only (duplicates removed), with one entry
per unique chemical name.

Output columns:
- Strict version: original, mapped, chebi_label, chebi_formula
- Hydrate version: + hydrated_chebi_id, hydrated_chebi_label
"""

import argparse
import pandas as pd
from pathlib import Path


def create_simplified_strict(input_file: Path, output_file: Path) -> None:
    """Create simplified version of strict mapping file with unique chemicals only."""
    print(f"Reading {input_file}...")
    df = pd.read_csv(input_file, sep='\t', dtype=str, na_values=[''], keep_default_na=False)

    original_count = len(df)
    print(f"  Total rows: {original_count:,}")

    # Select key columns
    columns = ['original', 'mapped', 'chebi_label', 'chebi_formula']
    simplified = df[columns].copy()

    # Remove duplicates - keep first occurrence of each unique chemical
    simplified = simplified.drop_duplicates(subset='original', keep='first')
    unique_count = len(simplified)
    print(f"  Unique chemicals: {unique_count:,} (removed {original_count - unique_count:,} duplicates)")

    # Sort by mapped ID for better organization
    simplified = simplified.sort_values('mapped')

    # Save output
    output_file.parent.mkdir(parents=True, exist_ok=True)
    simplified.to_csv(output_file, sep='\t', index=False)

    print(f"Saved {len(simplified):,} unique chemicals to {output_file}")
    print(f"  Columns: {', '.join(columns)}")

    # Summary stats
    total = len(simplified)
    with_chebi = (simplified['mapped'].str.startswith('CHEBI:', na=False)).sum()
    with_foodon = (simplified['mapped'].str.startswith('FOODON:', na=False)).sum()
    with_formula = (simplified['chebi_formula'] != '').sum()

    print(f"\nSummary:")
    print(f"  Unique chemicals: {total:,}")
    print(f"  ChEBI IDs: {with_chebi:,} ({100*with_chebi/total:.1f}%)")
    print(f"  FOODON IDs: {with_foodon:,} ({100*with_foodon/total:.1f}%)")
    print(f"  With formula: {with_formula:,} ({100*with_formula/total:.1f}%)")


def create_simplified_hydrate(input_file: Path, output_file: Path) -> None:
    """Create simplified version of hydrate mapping file with unique chemicals only."""
    print(f"Reading {input_file}...")
    df = pd.read_csv(input_file, sep='\t', dtype=str, na_values=[''], keep_default_na=False)

    original_count = len(df)
    print(f"  Total rows: {original_count:,}")

    # Select key columns including hydrate-specific ones
    columns = [
        'original', 'mapped', 'chebi_label', 'chebi_formula',
        'hydrated_chebi_id', 'hydrated_chebi_label'
    ]
    simplified = df[columns].copy()

    # Remove duplicates - keep first occurrence of each unique chemical
    simplified = simplified.drop_duplicates(subset='original', keep='first')
    unique_count = len(simplified)
    print(f"  Unique chemicals: {unique_count:,} (removed {original_count - unique_count:,} duplicates)")

    # Sort by mapped ID for better organization
    simplified = simplified.sort_values('mapped')

    # Save output
    output_file.parent.mkdir(parents=True, exist_ok=True)
    simplified.to_csv(output_file, sep='\t', index=False)

    print(f"Saved {len(simplified):,} unique chemicals to {output_file}")
    print(f"  Columns: {', '.join(columns)}")

    # Summary stats
    total = len(simplified)
    with_chebi = (simplified['mapped'].str.startswith('CHEBI:', na=False)).sum()
    with_foodon = (simplified['mapped'].str.startswith('FOODON:', na=False)).sum()
    with_formula = (simplified['chebi_formula'] != '').sum()
    with_hydrate = (simplified['hydrated_chebi_id'] != '').sum()

    print(f"\nSummary:")
    print(f"  Unique chemicals: {total:,}")
    print(f"  ChEBI IDs: {with_chebi:,} ({100*with_chebi/total:.1f}%)")
    print(f"  FOODON IDs: {with_foodon:,} ({100*with_foodon/total:.1f}%)")
    print(f"  With formula: {with_formula:,} ({100*with_formula/total:.1f}%)")
    print(f"  With hydrate form: {with_hydrate:,} ({100*with_hydrate/total:.1f}%)")


def main():
    parser = argparse.ArgumentParser(
        description="Create simplified mapping files with chemical name, formula, and identifiers"
    )
    parser.add_argument(
        '--strict-input',
        type=Path,
        default=Path('pipeline_output/merge_mappings/compound_mappings_strict_final.tsv'),
        help='Input strict mapping file'
    )
    parser.add_argument(
        '--strict-output',
        type=Path,
        default=Path('pipeline_output/merge_mappings/compound_mappings_simplified.tsv'),
        help='Output simplified strict mapping file'
    )
    parser.add_argument(
        '--hydrate-input',
        type=Path,
        default=Path('pipeline_output/merge_mappings/compound_mappings_strict_final_hydrate.tsv'),
        help='Input hydrate mapping file'
    )
    parser.add_argument(
        '--hydrate-output',
        type=Path,
        default=Path('pipeline_output/merge_mappings/compound_mappings_simplified_hydrate.tsv'),
        help='Output simplified hydrate mapping file'
    )

    args = parser.parse_args()

    print("=" * 70)
    print("Creating Simplified Mapping Files")
    print("=" * 70)
    print()

    # Create strict version
    print("--- STRICT VERSION ---")
    create_simplified_strict(args.strict_input, args.strict_output)
    print()

    # Create hydrate version
    print("--- HYDRATE VERSION ---")
    create_simplified_hydrate(args.hydrate_input, args.hydrate_output)
    print()

    print("=" * 70)
    print("✓ Simplified mapping files created successfully")
    print("=" * 70)


if __name__ == '__main__':
    main()
