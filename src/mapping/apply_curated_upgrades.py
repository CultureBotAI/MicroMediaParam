#!/usr/bin/env python3
"""
Apply curated dictionary mappings to upgrade ingredient: IDs to proper ontology IDs.

This script reads the high-confidence mappings file and replaces ingredient: IDs
with proper ChEBI/FOODON/UBERON/etc. IDs from the curated BIOLOGICAL_PRODUCTS dictionary.

Usage:
    python -m src.mapping.apply_curated_upgrades \
        --input high_confidence_compound_mappings_final.tsv \
        --output high_confidence_compound_mappings_upgraded_curated.tsv
"""

import argparse
import logging
from pathlib import Path

import pandas as pd

from src.mapping.compound_normalizer import CompoundNameNormalizer

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def apply_curated_upgrades(
    input_file: Path,
    output_file: Path,
) -> dict:
    """
    Apply curated dictionary mappings to upgrade ingredient: IDs.

    Args:
        input_file: Input mapping file
        output_file: Output file with upgraded mappings

    Returns:
        Statistics dictionary
    """
    normalizer = CompoundNameNormalizer()
    curated_dict = normalizer.BIOLOGICAL_PRODUCTS

    logger.info(f"Loaded {len(curated_dict)} curated mappings")

    # Read input file
    df = pd.read_csv(input_file, sep='\t', low_memory=False)
    logger.info(f"Read {len(df)} rows from {input_file}")

    # Count initial ingredient: mappings
    ingredient_mask = df['mapped'].str.startswith('ingredient:', na=False)
    initial_ingredient_count = ingredient_mask.sum()
    logger.info(f"Found {initial_ingredient_count} rows with ingredient: mappings")

    # Track upgrades
    upgrades = []
    upgraded_count = 0

    # Apply curated mappings
    for idx, row in df.iterrows():
        if pd.isna(row['mapped']) or not str(row['mapped']).startswith('ingredient:'):
            continue

        original_name = str(row['original']) if pd.notna(row['original']) else ''

        # Try exact match first
        if original_name in curated_dict:
            new_id = curated_dict[original_name]
            df.at[idx, 'mapped'] = new_id
            upgrades.append((original_name, row['mapped'], new_id))
            upgraded_count += 1
            continue

        # Try lowercase match
        if original_name.lower() in curated_dict:
            new_id = curated_dict[original_name.lower()]
            df.at[idx, 'mapped'] = new_id
            upgrades.append((original_name, row['mapped'], new_id))
            upgraded_count += 1
            continue

        # Try case-insensitive partial match
        for name, ontology_id in curated_dict.items():
            if name.lower() == original_name.lower():
                df.at[idx, 'mapped'] = ontology_id
                upgrades.append((original_name, row['mapped'], ontology_id))
                upgraded_count += 1
                break

    # Save output
    df.to_csv(output_file, sep='\t', index=False)
    logger.info(f"Saved {len(df)} rows to {output_file}")

    # Final stats
    final_ingredient_count = df['mapped'].str.startswith('ingredient:', na=False).sum()

    stats = {
        'total_rows': len(df),
        'initial_ingredient': initial_ingredient_count,
        'upgraded': upgraded_count,
        'final_ingredient': final_ingredient_count,
        'upgrades': upgrades
    }

    # Print summary
    print("\n" + "=" * 60)
    print("CURATED DICTIONARY UPGRADE COMPLETE")
    print("=" * 60)
    print(f"Total rows:            {stats['total_rows']:,}")
    print(f"Initial ingredient:    {stats['initial_ingredient']:,}")
    print(f"Upgraded to ontology:  {stats['upgraded']:,}")
    print(f"Remaining ingredient:  {stats['final_ingredient']:,}")
    print(f"\nOutput:                {output_file}")

    if upgrades:
        print(f"\nSample upgrades (first 10):")
        for name, old_id, new_id in upgrades[:10]:
            print(f"  {name}: {old_id} → {new_id}")

    print("=" * 60)

    return stats


def main():
    parser = argparse.ArgumentParser(
        description='Apply curated dictionary to upgrade ingredient: IDs'
    )
    parser.add_argument(
        '--input', '-i',
        type=Path,
        required=True,
        help='Input mapping file'
    )
    parser.add_argument(
        '--output', '-o',
        type=Path,
        required=True,
        help='Output file with upgraded mappings'
    )

    args = parser.parse_args()

    apply_curated_upgrades(args.input, args.output)


if __name__ == '__main__':
    main()
