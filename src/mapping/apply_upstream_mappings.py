#!/usr/bin/env python3
"""
Apply upstream ingredient mappings to strict mapping file.

Matches by normalized compound name and applies mappings from
upstream_ingredients_hydrate_enhanced.tsv to compound_mappings_strict.tsv.
"""

import argparse
import logging
import re
from pathlib import Path

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def normalize_name(name: str) -> str:
    """Normalize compound name for matching."""
    if not name or not isinstance(name, str):
        return ''
    # Lowercase, strip, normalize whitespace
    result = ' '.join(name.lower().strip().split())
    # Remove common suffixes for matching
    result = re.sub(r'\s*\(.*?\)\s*$', '', result)
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Apply upstream ingredient mappings to strict file"
    )
    parser.add_argument(
        '--upstream', required=True,
        help='Upstream ingredients TSV (id, original, mapped)'
    )
    parser.add_argument(
        '--strict', required=True,
        help='Strict mappings TSV file'
    )
    parser.add_argument(
        '--output', required=True,
        help='Output TSV file'
    )
    parser.add_argument(
        '--upgrade-cas', action='store_true',
        help='Also upgrade CAS-RN mappings to ChEBI/PubChem'
    )

    args = parser.parse_args()

    # Load upstream mappings
    logger.info(f"Loading upstream mappings from {args.upstream}")
    upstream_df = pd.read_csv(args.upstream, sep='\t')

    # Build lookup: normalized_name → mapped_id
    upstream_lookup = {}
    for _, row in upstream_df.iterrows():
        original = row.get('original', '')
        mapped = row.get('mapped', '')
        if pd.notna(original) and pd.notna(mapped) and str(mapped).strip():
            mapped_str = str(mapped).strip()
            # Only use semantic IDs (CHEBI, PubChem, FOODON, UBERON, ENVO)
            if any(mapped_str.startswith(prefix) for prefix in
                   ['CHEBI:', 'PubChem:', 'PUBCHEM', 'FOODON:', 'UBERON:', 'ENVO:']):
                norm_name = normalize_name(str(original))
                if norm_name:
                    upstream_lookup[norm_name] = mapped_str

    logger.info(f"Built lookup with {len(upstream_lookup)} mappings")

    # Load strict file
    logger.info(f"Loading strict mappings from {args.strict}")
    strict_df = pd.read_csv(args.strict, sep='\t')

    # Track statistics
    stats = {
        'total': len(strict_df),
        'already_mapped': 0,
        'upgraded_from_unmapped': 0,
        'upgraded_from_cas': 0,
        'upgraded_from_ingredient': 0,
        'still_unmapped': 0,
    }

    # Process each row
    for idx, row in strict_df.iterrows():
        original = row.get('original', '')
        current_mapped = row.get('mapped', '')
        current_str = str(current_mapped).strip() if pd.notna(current_mapped) else ''

        # Check if already has good mapping
        has_good_mapping = any(current_str.startswith(prefix) for prefix in
                              ['CHEBI:', 'PubChem:', 'PUBCHEM', 'FOODON:', 'UBERON:', 'ENVO:'])

        if has_good_mapping:
            stats['already_mapped'] += 1
            continue

        # Try to find in upstream lookup
        norm_name = normalize_name(str(original))
        if norm_name in upstream_lookup:
            new_mapping = upstream_lookup[norm_name]
            strict_df.at[idx, 'mapped'] = new_mapping

            if not current_str:
                stats['upgraded_from_unmapped'] += 1
            elif current_str.startswith('CAS-RN:'):
                stats['upgraded_from_cas'] += 1
            elif current_str.startswith('ingredient:'):
                stats['upgraded_from_ingredient'] += 1
            else:
                stats['upgraded_from_unmapped'] += 1
        else:
            stats['still_unmapped'] += 1

    # Save output
    strict_df.to_csv(args.output, sep='\t', index=False)
    logger.info(f"Saved to {args.output}")

    # Print report
    total_upgraded = (stats['upgraded_from_unmapped'] +
                      stats['upgraded_from_cas'] +
                      stats['upgraded_from_ingredient'])

    print("\n" + "=" * 60)
    print("APPLY UPSTREAM MAPPINGS REPORT")
    print("=" * 60)
    print(f"Total entries:           {stats['total']}")
    print(f"Already mapped:          {stats['already_mapped']}")
    print(f"Upgraded from upstream:  {total_upgraded}")
    print(f"  From unmapped:         {stats['upgraded_from_unmapped']}")
    print(f"  From CAS-RN:           {stats['upgraded_from_cas']}")
    print(f"  From ingredient:       {stats['upgraded_from_ingredient']}")
    print(f"Still unmapped:          {stats['still_unmapped']}")
    print("=" * 60)

    # Final mapping stats
    final_chebi = strict_df['mapped'].str.startswith('CHEBI:', na=False).sum()
    final_pubchem = strict_df['mapped'].str.contains('PubChem|PUBCHEM', na=False, case=False).sum()
    final_other = strict_df['mapped'].str.contains('FOODON:|UBERON:|ENVO:', na=False).sum()
    final_unmapped = stats['still_unmapped']

    print(f"\nFinal mapping breakdown:")
    print(f"  ChEBI:    {final_chebi}")
    print(f"  PubChem:  {final_pubchem}")
    print(f"  Other:    {final_other}")
    print(f"  Unmapped: {final_unmapped}")
    print("=" * 60)


if __name__ == '__main__':
    main()
