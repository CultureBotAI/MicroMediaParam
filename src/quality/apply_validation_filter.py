#!/usr/bin/env python3
"""
Apply validation filter to create strict mapping file.

Reads the validation report and removes critical errors from mappings,
reverting them to ingredient: prefixes.

Usage:
    python -m src.quality.apply_validation_filter \
        --mappings pipeline_output/merge_mappings/compound_mappings.tsv \
        --validation pipeline_output/quality/mapping_validation_report.tsv \
        --output pipeline_output/merge_mappings/compound_mappings_strict.tsv
"""

import argparse
import logging
from pathlib import Path
from typing import Set, Tuple

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_critical_issues(validation_file: Path) -> Set[Tuple[str, str]]:
    """
    Load critical issues from validation report.

    Returns set of (original, mapped_id) tuples to reject.
    """
    df = pd.read_csv(validation_file, sep='\t', low_memory=False)

    # Filter for critical issues only
    critical_df = df[df['severity'] == 'critical']

    # Create set of (original, mapped_id) pairs to reject
    reject_set = set()
    for _, row in critical_df.iterrows():
        original = str(row['original']).strip()
        mapped_id = str(row['mapped_id']).strip()
        reject_set.add((original, mapped_id))

    logger.info(f"Loaded {len(reject_set)} unique critical mappings to reject")
    return reject_set


def create_ingredient_id(name: str) -> str:
    """Create a normalized ingredient: ID from compound name."""
    # Normalize: lowercase, remove special chars, replace spaces with underscores
    normalized = name.lower().strip()
    normalized = ''.join(c if c.isalnum() or c == ' ' else '_' for c in normalized)
    normalized = '_'.join(normalized.split())
    return f"ingredient:{normalized}"


def apply_filter(
    mappings_file: Path,
    validation_file: Path,
    output_file: Path
) -> dict:
    """
    Apply validation filter to mappings.

    Args:
        mappings_file: Input compound mappings file
        validation_file: Validation report with issues
        output_file: Output file for strict mappings

    Returns:
        Statistics dictionary
    """
    # Load critical issues to reject
    reject_set = load_critical_issues(validation_file)

    # Load mappings
    logger.info(f"Loading mappings from {mappings_file}")
    df = pd.read_csv(mappings_file, sep='\t', low_memory=False)
    original_count = len(df)

    # Find the mapped column (usually 'mapped' or column index 2)
    mapped_col = 'mapped' if 'mapped' in df.columns else df.columns[2]
    original_col = 'original' if 'original' in df.columns else df.columns[1]

    # Track rejections
    rejected_count = 0
    rejected_examples = []

    # Apply filter
    for idx, row in df.iterrows():
        original = str(row[original_col]).strip() if pd.notna(row[original_col]) else ''
        mapped_id = str(row[mapped_col]).strip() if pd.notna(row[mapped_col]) else ''

        if (original, mapped_id) in reject_set:
            # Revert to ingredient: prefix
            new_id = create_ingredient_id(original)
            df.at[idx, mapped_col] = new_id

            # Clear ChEBI-related columns if they exist
            if 'chebi_label' in df.columns:
                df.at[idx, 'chebi_label'] = ''
            if 'chebi_formula' in df.columns:
                df.at[idx, 'chebi_formula'] = ''

            rejected_count += 1
            if len(rejected_examples) < 10:
                rejected_examples.append((original, mapped_id, new_id))

    # Save output
    output_file.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_file, sep='\t', index=False)
    logger.info(f"Saved {len(df)} rows to {output_file}")

    # Calculate stats
    stats = {
        'total_rows': original_count,
        'rejected': rejected_count,
        'retained': original_count,  # Same row count, just IDs changed
        'rejection_rate': rejected_count / original_count * 100 if original_count > 0 else 0,
        'examples': rejected_examples
    }

    # Print summary
    print("\n" + "=" * 70)
    print("VALIDATION FILTER APPLIED")
    print("=" * 70)
    print(f"Total rows:              {stats['total_rows']:,}")
    print(f"Mappings rejected:       {stats['rejected']:,} ({stats['rejection_rate']:.1f}%)")
    print(f"Reverted to ingredient:  {stats['rejected']:,}")
    print()
    print(f"Output file: {output_file}")

    if rejected_examples:
        print(f"\nSample rejections (first {len(rejected_examples)}):")
        for original, old_id, new_id in rejected_examples:
            print(f"  '{original}': {old_id} → {new_id}")

    print("=" * 70)

    return stats


def main():
    parser = argparse.ArgumentParser(
        description='Apply validation filter to create strict mapping file'
    )
    parser.add_argument(
        '--mappings', '-m',
        type=Path,
        required=True,
        help='Input compound mappings file'
    )
    parser.add_argument(
        '--validation', '-v',
        type=Path,
        required=True,
        help='Validation report file'
    )
    parser.add_argument(
        '--output', '-o',
        type=Path,
        required=True,
        help='Output file for strict mappings'
    )

    args = parser.parse_args()

    apply_filter(args.mappings, args.validation, args.output)


if __name__ == '__main__':
    main()
