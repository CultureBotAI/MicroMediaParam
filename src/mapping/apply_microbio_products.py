#!/usr/bin/env python3
"""
Apply Microbiology Products Mapper to Compound Mappings

Processes compound mapping files to identify and map biological products
(peptones, extracts, commercial media) using the curated dictionary.

Expected improvement: +15 compounds
"""

import pandas as pd
import logging
import sys
from pathlib import Path
from typing import Dict, List

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from mapping.microbio_products import MicrobiologyProductMapper

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class MicrobioMappingEnhancer:
    """Enhances compound mappings using microbiology products dictionary."""

    def __init__(self):
        """Initialize the enhancer."""
        self.mapper = MicrobiologyProductMapper()

    def should_try_microbio_matching(self, compound_name: str, mapped_id: str) -> bool:
        """
        Determine if compound should be processed with microbio mapper.

        Args:
            compound_name: Original compound name
            mapped_id: Current mapped ID

        Returns:
            True if should try microbio matching
        """
        # Already has good ChEBI mapping - skip
        if pd.notna(mapped_id) and isinstance(mapped_id, str) and mapped_id.startswith('CHEBI:'):
            return False

        # Try matching anything that's not already mapped
        if pd.isna(mapped_id) or not isinstance(mapped_id, str):
            return True

        # Try matching ingredient: codes
        if mapped_id.startswith('ingredient:'):
            return True

        return False

    def enhance_mapping_file(self, input_file: str, output_file: str) -> Dict:
        """
        Enhance mappings using microbio products dictionary.

        Args:
            input_file: Input mapping TSV
            output_file: Output enhanced TSV

        Returns:
            Statistics dictionary
        """
        logger.info(f"Loading mappings from {input_file}")
        df = pd.read_csv(input_file, sep='\t', low_memory=False)

        stats = {
            'total_entries': len(df),
            'tried_matching': 0,
            'successful_matches': 0,
            'failed_matches': 0,
            'already_mapped': 0
        }

        matches = []

        # Process each compound
        for idx, row in df.iterrows():
            compound = row['original']
            mapped_id = row.get('mapped', '')

            # Check if should try microbio matching
            if self.should_try_microbio_matching(compound, mapped_id):
                stats['tried_matching'] += 1

                # Try microbio product matching
                result = self.mapper.match(compound)

                if result:
                    # Successful match!
                    df.at[idx, 'mapped'] = result.chebi_id
                    stats['successful_matches'] += 1

                    matches.append({
                        'compound': compound,
                        'old_id': mapped_id,
                        'new_id': result.chebi_id,
                        'product_name': result.product_name,
                        'confidence': result.confidence,
                        'description': result.description
                    })

                    logger.debug(f"✓ {compound} → {result.chebi_id} ({result.product_name})")
                else:
                    stats['failed_matches'] += 1

            elif pd.notna(mapped_id) and isinstance(mapped_id, str) and mapped_id.startswith('CHEBI:'):
                stats['already_mapped'] += 1

        # Save enhanced file
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, sep='\t', index=False)

        logger.info(f"Saved enhanced mappings to {output_path}")
        self._log_statistics(stats, matches)

        return stats

    def _log_statistics(self, stats: Dict, matches: List[Dict]):
        """Log statistics."""
        logger.info(f"""
╔════════════════════════════════════════════════════════════════════════╗
║              MICROBIOLOGY PRODUCTS ENHANCEMENT REPORT                   ║
╚════════════════════════════════════════════════════════════════════════╝

Total entries:           {stats['total_entries']:,}
Already mapped to ChEBI: {stats['already_mapped']:,}

Microbio matching attempted: {stats['tried_matching']:,}
  ✓ Successful:  {stats['successful_matches']:,}
  ✗ Failed:      {stats['failed_matches']:,}

Success rate: {stats['successful_matches']/stats['tried_matching']*100 if stats['tried_matching'] > 0 else 0:.1f}%
        """)

        if matches:
            logger.info("\nAll successful matches:")
            for i, match in enumerate(matches, 1):
                logger.info(f"{i}. {match['compound']}")
                logger.info(f"   {match['old_id']} → {match['new_id']}")
                logger.info(f"   Product: {match['product_name']}, "
                          f"Confidence: {match['confidence']}")
                logger.info(f"   {match['description']}")


def main():
    """Main function for command-line execution."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Apply microbio products mapping to enhance compound mappings",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--input',
        default='pipeline_output/merge_mappings/high_confidence_compound_mappings_formula_enhanced.tsv',
        help='Input compound mapping TSV'
    )
    parser.add_argument(
        '--output',
        default='pipeline_output/merge_mappings/high_confidence_compound_mappings_final.tsv',
        help='Output enhanced TSV file'
    )

    args = parser.parse_args()

    # Initialize enhancer
    enhancer = MicrobioMappingEnhancer()

    # Enhance mappings
    enhancer.enhance_mapping_file(args.input, args.output)

    logger.info("\n✓ Microbiology products enhancement complete!")


if __name__ == "__main__":
    main()
