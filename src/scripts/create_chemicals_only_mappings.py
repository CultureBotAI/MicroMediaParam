#!/usr/bin/env python3
"""
Create chemicals-only mapping files excluding complex ingredients, media, and solutions.

This script filters the simplified mapping files to include only pure chemicals
(both mapped and unmapped), excluding:
- FOODON: biological/complex ingredients (yeast extract, peptone, etc.)
- medium: media formulations and broths
- ingredient: unmapped complex ingredients and solutions

Included chemical types:
- CHEBI: mapped chemicals with ChEBI IDs
- CAS-RN: unmapped chemicals with CAS registry numbers
- PubChem/PUBCHEM.COMPOUND: unmapped chemicals with PubChem IDs
- KEGG: chemicals with KEGG IDs
- UBERON: anatomical entities

Output columns:
- Strict version: original, mapped, chebi_label, chebi_formula
- Hydrate version: + hydrated_chebi_id, hydrated_chebi_label
"""

import argparse
import pandas as pd
from pathlib import Path


def is_chemical(mapped_id: str) -> bool:
    """Check if mapped ID represents a pure chemical (not complex ingredient/media)."""
    if pd.isna(mapped_id) or mapped_id == '':
        return False

    # Include pure chemicals
    chemical_prefixes = ['CHEBI:', 'CAS-RN:', 'PubChem:', 'PUBCHEM.COMPOUND:', 'KEGG:', 'UBERON:']
    if any(mapped_id.startswith(prefix) for prefix in chemical_prefixes):
        return True

    # Exclude complex ingredients, media, solutions
    exclude_prefixes = ['FOODON:', 'medium:', 'ingredient:']
    if any(mapped_id.startswith(prefix) for prefix in exclude_prefixes):
        return False

    # Exclude other weird entries
    return False


def create_chemicals_only_strict(input_file: Path, output_file: Path) -> None:
    """Create chemicals-only version of strict mapping file."""
    print(f"Reading {input_file}...")
    df = pd.read_csv(input_file, sep='\t', dtype=str, na_values=[''], keep_default_na=False)

    original_count = len(df)
    print(f"  Total chemicals in simplified file: {original_count:,}")

    # Filter to only pure chemicals
    df['is_chemical'] = df['mapped'].apply(is_chemical)
    chemicals = df[df['is_chemical']].copy()
    chemicals = chemicals.drop(columns=['is_chemical'])

    chemical_count = len(chemicals)
    excluded_count = original_count - chemical_count

    print(f"  Pure chemicals only: {chemical_count:,}")
    print(f"  Excluded (complex/media): {excluded_count:,}")

    # Save output
    output_file.parent.mkdir(parents=True, exist_ok=True)
    chemicals.to_csv(output_file, sep='\t', index=False)

    print(f"Saved {len(chemicals):,} pure chemicals to {output_file}")

    # Summary stats
    total = len(chemicals)
    with_chebi = (chemicals['mapped'].str.startswith('CHEBI:', na=False)).sum()
    with_cas = (chemicals['mapped'].str.startswith('CAS-RN:', na=False)).sum()
    with_pubchem = (chemicals['mapped'].str.startswith('PubChem:', na=False) |
                     chemicals['mapped'].str.startswith('PUBCHEM.COMPOUND:', na=False)).sum()
    with_formula = (chemicals['chebi_formula'] != '').sum()

    print(f"\nSummary:")
    print(f"  Pure chemicals: {total:,}")
    print(f"  ChEBI IDs: {with_chebi:,} ({100*with_chebi/total:.1f}%)")
    print(f"  CAS-RN: {with_cas:,} ({100*with_cas/total:.1f}%)")
    print(f"  PubChem: {with_pubchem:,} ({100*with_pubchem/total:.1f}%)")
    print(f"  With formula: {with_formula:,} ({100*with_formula/total:.1f}%)")


def create_chemicals_only_hydrate(input_file: Path, output_file: Path) -> None:
    """Create chemicals-only version of hydrate mapping file."""
    print(f"Reading {input_file}...")
    df = pd.read_csv(input_file, sep='\t', dtype=str, na_values=[''], keep_default_na=False)

    original_count = len(df)
    print(f"  Total chemicals in simplified file: {original_count:,}")

    # Filter to only pure chemicals
    df['is_chemical'] = df['mapped'].apply(is_chemical)
    chemicals = df[df['is_chemical']].copy()
    chemicals = chemicals.drop(columns=['is_chemical'])

    chemical_count = len(chemicals)
    excluded_count = original_count - chemical_count

    print(f"  Pure chemicals only: {chemical_count:,}")
    print(f"  Excluded (complex/media): {excluded_count:,}")

    # Save output
    output_file.parent.mkdir(parents=True, exist_ok=True)
    chemicals.to_csv(output_file, sep='\t', index=False)

    print(f"Saved {len(chemicals):,} pure chemicals to {output_file}")

    # Summary stats
    total = len(chemicals)
    with_chebi = (chemicals['mapped'].str.startswith('CHEBI:', na=False)).sum()
    with_cas = (chemicals['mapped'].str.startswith('CAS-RN:', na=False)).sum()
    with_pubchem = (chemicals['mapped'].str.startswith('PubChem:', na=False) |
                     chemicals['mapped'].str.startswith('PUBCHEM.COMPOUND:', na=False)).sum()
    with_formula = (chemicals['chebi_formula'] != '').sum()
    with_hydrate = (chemicals['hydrated_chebi_id'] != '').sum()

    print(f"\nSummary:")
    print(f"  Pure chemicals: {total:,}")
    print(f"  ChEBI IDs: {with_chebi:,} ({100*with_chebi/total:.1f}%)")
    print(f"  CAS-RN: {with_cas:,} ({100*with_cas/total:.1f}%)")
    print(f"  PubChem: {with_pubchem:,} ({100*with_pubchem/total:.1f}%)")
    print(f"  With formula: {with_formula:,} ({100*with_formula/total:.1f}%)")
    print(f"  With hydrate form: {with_hydrate:,} ({100*with_hydrate/total:.1f}%)")


def main():
    parser = argparse.ArgumentParser(
        description="Create chemicals-only mapping files (excludes complex ingredients, media, solutions)"
    )
    parser.add_argument(
        '--strict-input',
        type=Path,
        default=Path('pipeline_output/merge_mappings/compound_mappings_simplified.tsv'),
        help='Input simplified strict mapping file'
    )
    parser.add_argument(
        '--strict-output',
        type=Path,
        default=Path('pipeline_output/merge_mappings/compound_mappings_chemicals_only.tsv'),
        help='Output chemicals-only strict mapping file'
    )
    parser.add_argument(
        '--hydrate-input',
        type=Path,
        default=Path('pipeline_output/merge_mappings/compound_mappings_simplified_hydrate.tsv'),
        help='Input simplified hydrate mapping file'
    )
    parser.add_argument(
        '--hydrate-output',
        type=Path,
        default=Path('pipeline_output/merge_mappings/compound_mappings_chemicals_only_hydrate.tsv'),
        help='Output chemicals-only hydrate mapping file'
    )

    args = parser.parse_args()

    print("=" * 70)
    print("Creating Chemicals-Only Mapping Files")
    print("(Excluding: FOODON, medium, ingredient codes)")
    print("=" * 70)
    print()

    # Create strict version
    print("--- STRICT VERSION ---")
    create_chemicals_only_strict(args.strict_input, args.strict_output)
    print()

    # Create hydrate version
    print("--- HYDRATE VERSION ---")
    create_chemicals_only_hydrate(args.hydrate_input, args.hydrate_output)
    print()

    print("=" * 70)
    print("✓ Chemicals-only mapping files created successfully")
    print("=" * 70)


if __name__ == '__main__':
    main()
