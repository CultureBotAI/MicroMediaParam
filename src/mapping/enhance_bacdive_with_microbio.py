#!/usr/bin/env python3
"""
Enhance BacDive metabolites mapping with microbio products dictionary.

Fills gaps in OAK-based mappings using curated biological product mappings.
"""

import argparse
import sys
import logging
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.mapping.microbio_products import MicrobiologyProductMapper
from src.mapping.compound_normalizer import CompoundNameNormalizer
from src.mapping.pubchem_fallback_mapper import PubChemFallbackMapper

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def enhance_mappings(input_file: Path, output_file: Path, use_pubchem: bool = True) -> dict:
    """
    Enhance BacDive metabolites with microbio products, normalizer, and PubChem fallback.

    Args:
        input_file: Input TSV with OAK-based mappings
        output_file: Output TSV with enhanced mappings
        use_pubchem: Enable PubChem fallback for unmapped compounds (default: True)

    Returns:
        Statistics dictionary
    """
    mapper = MicrobiologyProductMapper()
    normalizer = CompoundNameNormalizer()
    fallback = PubChemFallbackMapper() if use_pubchem else None

    stats = {
        'total': 0,
        'already_mapped': 0,
        'newly_mapped_microbio': 0,
        'newly_mapped_pubchem': 0,
        'still_unmapped': 0,
        'records_newly_covered': 0
    }

    rows = []
    with open(input_file, 'r', encoding='utf-8') as f:
        header = next(f).strip()
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) >= 6:
                rows.append({
                    'metabolite_name': parts[0],
                    'chebi_id': parts[1],
                    'chebi_label': parts[2],
                    'match_type': parts[3],
                    'score': parts[4],
                    'record_count': int(parts[5]) if parts[5] else 0
                })

    print(f"Loaded {len(rows)} metabolites from {input_file}")

    # Try to map unmapped entries using microbio products + normalizer + fallback
    for row in rows:
        stats['total'] += 1

        if row['chebi_id']:  # Already mapped
            stats['already_mapped'] += 1
            continue

        # Step 1: Normalize the metabolite name (remove concentration formatting)
        normalized_name = normalizer.remove_concentration_formatting(row['metabolite_name'])

        # Step 2: Try microbio products mapping with normalized name
        result = mapper.match(normalized_name)

        if result and result.chebi_id:
            row['chebi_id'] = result.chebi_id
            row['chebi_label'] = result.product_name
            row['match_type'] = 'microbio_product'
            row['score'] = '90'
            stats['newly_mapped_microbio'] += 1
            stats['records_newly_covered'] += row['record_count']
            logger.info(f"  Microbio: {row['metabolite_name']} → {result.chebi_id} ({result.product_name})")
            continue

        # Step 3: Try PubChem fallback for organic compounds
        if fallback and normalized_name != row['metabolite_name']:
            # If normalization changed the name, try PubChem with both
            for name_to_try in [normalized_name, row['metabolite_name']]:
                pubchem_result = fallback.search_by_name(name_to_try)

                if pubchem_result:
                    row['chebi_id'] = pubchem_result['pubchem_cid']
                    row['chebi_label'] = pubchem_result['compound_name']
                    row['match_type'] = 'pubchem_fallback'
                    row['score'] = '70'
                    stats['newly_mapped_pubchem'] += 1
                    stats['records_newly_covered'] += row['record_count']
                    logger.info(f"  PubChem: {row['metabolite_name']} → {pubchem_result['pubchem_cid']}")
                    break
        elif fallback:
            # Only normalized name
            pubchem_result = fallback.search_by_name(normalized_name)

            if pubchem_result:
                row['chebi_id'] = pubchem_result['pubchem_cid']
                row['chebi_label'] = pubchem_result['compound_name']
                row['match_type'] = 'pubchem_fallback'
                row['score'] = '70'
                stats['newly_mapped_pubchem'] += 1
                stats['records_newly_covered'] += row['record_count']
                logger.info(f"  PubChem: {row['metabolite_name']} → {pubchem_result['pubchem_cid']}")
                continue

        # Still unmapped after all strategies
        stats['still_unmapped'] += 1

    # Write enhanced output
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(header + '\n')
        for row in rows:
            f.write(f"{row['metabolite_name']}\t{row['chebi_id']}\t{row['chebi_label']}\t{row['match_type']}\t{row['score']}\t{row['record_count']}\n")

    return stats


def main():
    parser = argparse.ArgumentParser(description="Enhance BacDive metabolites with microbio products")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("pipeline_output/bacdive_metabolites/bacdive_metabolites_chebi_mappings.tsv"),
        help="Input mappings TSV"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("pipeline_output/bacdive_metabolites/bacdive_metabolites_chebi_mappings_enhanced.tsv"),
        help="Output enhanced TSV"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Enhancing BacDive Metabolites with Microbio Products")
    print("=" * 60)

    stats = enhance_mappings(args.input, args.output)

    print("\n" + "=" * 60)
    print("Enhancement Results")
    print("=" * 60)
    print(f"  Total metabolites:           {stats['total']}")
    print(f"  Already mapped (OAK):        {stats['already_mapped']}")
    print(f"  Newly mapped (microbio):     {stats['newly_mapped_microbio']}")
    print(f"  Newly mapped (PubChem):      {stats['newly_mapped_pubchem']}")
    print(f"  Still unmapped:              {stats['still_unmapped']}")
    print(f"  Additional records covered:  {stats['records_newly_covered']:,}")

    total_mapped = stats['already_mapped'] + stats['newly_mapped_microbio'] + stats['newly_mapped_pubchem']
    print(f"\n  Final coverage: {total_mapped}/{stats['total']} ({total_mapped/stats['total']*100:.1f}%)")
    print(f"\nOutput: {args.output}")


if __name__ == "__main__":
    main()
