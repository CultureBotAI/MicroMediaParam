#!/usr/bin/env python3
"""
Create a compound name lookup table from enriched mappings.

Generates a many-to-1 mapping table where each unique observed compound name
(including different hydrate forms) gets its own row, even if they map to
the same ChEBI ID.

Input: high_confidence_compound_mappings_enriched.tsv (full composition data)
Output: compound_name_lookup.tsv (deduplicated name → ID lookup table)

Usage:
    python -m src.mapping.create_compound_lookup_table \
        --input pipeline_output/merge_mappings/high_confidence_compound_mappings_enriched.tsv \
        --output pipeline_output/merge_mappings/compound_name_lookup.tsv
"""

import argparse
import logging
from pathlib import Path
from typing import Dict, Tuple, Optional

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_lookup_table(input_file: Path, output_file: Path, chebi_data: Optional[Dict[str, Tuple[str, str]]] = None):
    """
    Create a compound name lookup table from enriched mappings.

    Each unique (original_name, mapped_id) pair gets one row.
    For hydrated compounds, maps to the parent (anhydrous) ChEBI ID.
    Includes ChEBI label and formula for CHEBI mappings.

    Args:
        input_file: Enriched mappings TSV file
        output_file: Output lookup table TSV file
        chebi_data: Optional dict of CHEBI:ID -> (label, formula) for parent lookups
    """
    logger.info(f"Reading enriched mappings from {input_file}")
    df = pd.read_csv(input_file, sep='\t', low_memory=False)

    logger.info(f"Input has {len(df)} rows")

    # Extract relevant columns
    # original = observed name from BacDive/MediaDive
    # mapped = identifier (CHEBI:xxx, CAS-RN:xxx, etc.)
    # base_chebi_id = parent compound ChEBI ID (for hydrates)
    # chebi_label = canonical ChEBI name
    # chebi_formula = molecular formula

    lookup_data: Dict[Tuple[str, str], Tuple[str, str, int]] = {}
    hydrate_normalization_count = 0

    for _, row in df.iterrows():
        original = str(row.get('original', '')).strip()
        mapped = str(row.get('mapped', '')).strip()
        chebi_label = str(row.get('chebi_label', '')) if pd.notna(row.get('chebi_label')) else ''
        chebi_formula = str(row.get('chebi_formula', '')) if pd.notna(row.get('chebi_formula')) else ''

        # Check for hydration - use base_chebi_id if available
        hydration_number = 0
        try:
            hydration_number = int(row.get('hydration_number', 0)) if pd.notna(row.get('hydration_number')) else 0
        except (ValueError, TypeError):
            hydration_number = 0

        base_chebi_id = str(row.get('base_chebi_id', '')) if pd.notna(row.get('base_chebi_id')) else ''

        # For hydrated compounds, use the parent (base) ChEBI ID
        if hydration_number > 0 and base_chebi_id and base_chebi_id.startswith('CHEBI:'):
            if mapped != base_chebi_id:
                hydrate_normalization_count += 1
            mapped = base_chebi_id

            # Get parent compound's label and formula from chebi_data if available
            if chebi_data and base_chebi_id in chebi_data:
                chebi_label, chebi_formula = chebi_data[base_chebi_id]
            else:
                # Try to get from base_chebi_label column
                base_label = str(row.get('base_chebi_label', '')) if pd.notna(row.get('base_chebi_label')) else ''
                base_formula = str(row.get('base_chebi_formula', '')) if pd.notna(row.get('base_chebi_formula')) else ''
                if base_label:
                    chebi_label = base_label
                if base_formula:
                    chebi_formula = base_formula

        if not original or not mapped:
            continue

        # Skip empty or invalid mappings
        if mapped in ['', 'nan', 'None']:
            continue

        key = (original, mapped)

        # Keep first occurrence (or update if we get better data)
        if key not in lookup_data:
            lookup_data[key] = (chebi_label, chebi_formula, hydration_number)
        else:
            # Update if current has better data
            existing_label, existing_formula, existing_hydration = lookup_data[key]
            if not existing_label and chebi_label:
                lookup_data[key] = (chebi_label, existing_formula, existing_hydration)
            if not existing_formula and chebi_formula:
                lookup_data[key] = (lookup_data[key][0], chebi_formula, existing_hydration)

    logger.info(f"Found {len(lookup_data):,} unique (name, ID) pairs")
    logger.info(f"Normalized {hydrate_normalization_count:,} hydrate → parent mappings")

    # Convert to DataFrame and sort
    rows = []
    for (original, mapped), (label, formula, hydration) in lookup_data.items():
        rows.append({
            'original_name': original,
            'mapped_id': mapped,
            'chebi_label': label,
            'chebi_formula': formula
        })

    result_df = pd.DataFrame(rows)

    # Sort by original name (case-insensitive)
    result_df = result_df.sort_values(
        by='original_name',
        key=lambda x: x.str.lower()
    )

    # Calculate statistics
    stats = {
        'total_mappings': len(result_df),
        'unique_names': result_df['original_name'].nunique(),
        'unique_ids': result_df['mapped_id'].nunique(),
        'chebi_mappings': len(result_df[result_df['mapped_id'].str.startswith('CHEBI:')]),
        'cas_mappings': len(result_df[result_df['mapped_id'].str.startswith('CAS-RN:')]),
        'with_label': len(result_df[result_df['chebi_label'] != '']),
        'with_formula': len(result_df[result_df['chebi_formula'] != ''])
    }

    # Save output
    output_file.parent.mkdir(parents=True, exist_ok=True)
    result_df.to_csv(output_file, sep='\t', index=False)

    logger.info(f"Saved lookup table to {output_file}")

    return stats


def load_chebi_formulas(formulas_file: Path) -> Dict[str, Tuple[str, str]]:
    """
    Load ChEBI labels and formulas from chebi_formulas.tsv.

    Returns:
        Dict mapping CHEBI:ID -> (label, formula)
    """
    chebi_data = {}

    if not formulas_file.exists():
        logger.warning(f"ChEBI formulas file not found: {formulas_file}")
        return chebi_data

    logger.info(f"Loading ChEBI data from {formulas_file}")

    df = pd.read_csv(formulas_file, sep='\t')

    for _, row in df.iterrows():
        chebi_id = str(row.get('chebi_id', ''))
        label = str(row.get('chebi_label', '')) if pd.notna(row.get('chebi_label')) else ''
        formula = str(row.get('chebi_formula', '')) if pd.notna(row.get('chebi_formula')) else ''

        if chebi_id:
            chebi_data[chebi_id] = (label, formula)

    logger.info(f"Loaded {len(chebi_data):,} ChEBI entries")

    return chebi_data


def main():
    parser = argparse.ArgumentParser(
        description="Create compound name lookup table from enriched mappings"
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Input enriched mappings TSV file"
    )
    parser.add_argument(
        "--chebi-formulas",
        type=Path,
        default=None,
        help="ChEBI formulas TSV file for parent compound lookups"
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output lookup table TSV file"
    )

    args = parser.parse_args()

    # Load ChEBI data for parent compound lookups
    chebi_data = None
    if args.chebi_formulas:
        chebi_data = load_chebi_formulas(args.chebi_formulas)

    stats = create_lookup_table(args.input, args.output, chebi_data)

    # Print summary
    print("\n" + "=" * 60)
    print("COMPOUND LOOKUP TABLE CREATED")
    print("=" * 60)
    print(f"Total mappings:    {stats['total_mappings']:,}")
    print(f"Unique names:      {stats['unique_names']:,}")
    print(f"Unique IDs:        {stats['unique_ids']:,}")
    print()
    print("By ID type:")
    print(f"  CHEBI:           {stats['chebi_mappings']:,}")
    print(f"  CAS-RN:          {stats['cas_mappings']:,}")
    print()
    print("Enrichment:")
    print(f"  With label:      {stats['with_label']:,}")
    print(f"  With formula:    {stats['with_formula']:,}")
    print()
    print(f"Output:            {args.output}")
    print("=" * 60)


if __name__ == "__main__":
    main()
