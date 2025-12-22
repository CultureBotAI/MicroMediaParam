#!/usr/bin/env python3
"""
Create chemicals-only mapping files excluding complex ingredients, media, and solutions.

This script filters the simplified mapping files to include only pure chemicals
(both mapped and unmapped), excluding complex biological mixtures.

Included chemical types:
- CHEBI: mapped chemicals with ChEBI IDs
- CAS-RN: unmapped chemicals with CAS registry numbers
- PubChem/PUBCHEM.COMPOUND: unmapped chemicals with PubChem IDs
- KEGG: chemicals with KEGG IDs
- UBERON: anatomical entities
- ingredient: entries WITH chemical formulas (unmapped pure chemicals)

Excluded (not pure chemicals):
- FOODON: biological/complex ingredients (yeast extract, peptone, etc.)
- medium: media formulations and broths
- ingredient: entries WITHOUT formulas (complex mixtures/solutions)

Output columns:
- Strict version: original, mapped, chebi_label, chebi_formula
- Hydrate version: + hydrated_chebi_id, hydrated_chebi_label
"""

import argparse
import pandas as pd
from pathlib import Path
import re


def is_chemical_formula_name(name: str) -> bool:
    """Check if a chemical name looks like a chemical formula (not a complex mixture).

    Returns True for:
    - Inorganic salt hydrates: NaCl, CaCl2·6H2O, MnSO4 x X H2O
    - Simple compounds: H3BO4, K2HSO4, Fe2(SO4)3
    - Amino acid derivatives: L-Cysteine·HCl·H2O

    Returns False for:
    - Solution references: SL10, SL-6, Trace element solution
    - Complex mixtures: peptone, casein, yeast extract
    - Media/broths: Marine broth, LB broth
    - Vitamin solutions: Vitamin B12 solution
    """
    if pd.isna(name) or name == '':
        return False

    name_lower = name.lower()

    # Exclude solution references and complex mixtures
    exclude_patterns = [
        r'\bsolution\b', r'\bbroth\b', r'\bmedium\b', r'\bmixture\b',
        r'\bextract\b', r'\bpeptone\b', r'\bcasein\b', r'\byeast\b',
        r'\bbeef\b', r'\bmeat\b', r'\bmalt\b', r'\btryptone\b',
        r'\bsoy\b', r'\bblood\b', r'\bserum\b', r'\bagar\b',
        r'\btrace\b.*\belement\b', r'\bvitamin\b.*\bsolution\b',
        r'\bsl-?\d+\b', r'\bsl\d+\b',  # SL10, SL-6, etc.
        r'\bsee\b.*\bno\.\d+', r'\b#\d+\b',  # "see Medium No.197"
        r'\bbasal\b', r'\bbase\b', r'\bsalts?\b'
    ]

    for pattern in exclude_patterns:
        if re.search(pattern, name_lower):
            return False

    # Include if it has chemical formula patterns
    # Element symbols, numbers, hydration notation
    chemical_patterns = [
        r'^[A-Z][a-z]?[0-9]+',  # Starts with element + number: NaCl, H3BO4
        r'[A-Z][a-z]?[0-9]*\([A-Z]',  # Contains groups: Fe2(SO4)3
        r'·[0-9]*H2O|\.?[0-9]*H2O',  # Hydration: ·6H2O, .6H2O, 6H2O
        r'\bx\s*[0-9XxNn]*\s*H2?O',  # Hydration: x 6 H2O, x X H2O, x n H2O
        r'(SO4|PO4|NO3|NH4|WO4|SeO3|Cl[0-9])',  # Common anions
    ]

    for pattern in chemical_patterns:
        if re.search(pattern, name):
            return True

    # Also include L-/D- amino acid derivatives (but exclude if has "solution")
    if re.match(r'^[LD]-[A-Z]', name) and 'solution' not in name_lower:
        return True

    return False


def is_chemical(row: pd.Series) -> bool:
    """Check if entry represents a pure chemical (not complex ingredient/media).

    Includes:
    - Entries with ChEBI, CAS-RN, PubChem, KEGG, UBERON IDs
    - ingredient: entries where the original name is a chemical formula

    Excludes:
    - FOODON: biological/complex ingredients
    - medium: media formulations
    - ingredient: entries that are complex mixtures/solutions
    """
    mapped_id = row['mapped']
    original = row.get('original', '')

    if pd.isna(mapped_id) or mapped_id == '':
        return False

    # Include pure chemicals with database IDs
    chemical_prefixes = ['CHEBI:', 'CAS-RN:', 'PubChem:', 'PUBCHEM.COMPOUND:', 'KEGG:', 'UBERON:']
    if any(mapped_id.startswith(prefix) for prefix in chemical_prefixes):
        return True

    # Include ingredient: entries IF the original name is a chemical formula
    # (these are unmapped pure chemicals like NaH2PO4.2H2O, CoCl2.6H2O)
    if mapped_id.startswith('ingredient:'):
        return is_chemical_formula_name(original)

    # Exclude complex biological ingredients and media
    exclude_prefixes = ['FOODON:', 'medium:']
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

    # Filter to only pure chemicals (pass whole row to check formula)
    df['is_chemical'] = df.apply(is_chemical, axis=1)
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

    # Filter to only pure chemicals (pass whole row to check formula)
    df['is_chemical'] = df.apply(is_chemical, axis=1)
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
