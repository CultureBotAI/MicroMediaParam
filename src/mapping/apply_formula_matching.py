#!/usr/bin/env python3
"""
Apply Formula Matcher to Compound Mappings

Processes compound mapping files to identify and map hydrated compounds
using the FormulaToChEBIMatcher. Targets compounds with:
- ingredient: codes
- Hydrate patterns (x N H2O, N-hydrate, etc.)

Expected improvement: +20 compounds
"""

import pandas as pd
import logging
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from mapping.formula_matcher import FormulaToChEBIMatcher
from mapping.compound_normalizer import CompoundNameNormalizer

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class FormulaMappingEnhancer:
    """Enhances compound mappings using formula matching."""

    def __init__(self, chebi_file: str):
        """
        Initialize the enhancer.

        Args:
            chebi_file: Path to ChEBI nodes TSV
        """
        self.matcher = FormulaToChEBIMatcher(chebi_file)
        self.normalizer = CompoundNameNormalizer()

    def has_hydrate_pattern(self, compound_name: str) -> bool:
        """Check if compound has hydration notation."""
        hydrate_patterns = [
            r'\s*[x×]\s*\d+\s*H2O',      # x 6 H2O
            r'\s*[•·]\s*\d+\s*H2O',      # · 6 H2O
            r'\s*\.\s*\d+\s*H2O',        # . 6 H2O
            r'\s+\d+-hydrate',           # 6-hydrate
            r'\s*[x×]\s*n\s*H2O',        # x n H2O (variable hydration)
        ]

        import re
        for pattern in hydrate_patterns:
            if re.search(pattern, compound_name, re.IGNORECASE):
                return True
        return False

    def should_try_formula_matching(self, compound_name: str, mapped_id: str) -> bool:
        """
        Determine if compound should be processed with formula matcher.

        Args:
            compound_name: Original compound name
            mapped_id: Current mapped ID

        Returns:
            True if should try formula matching
        """
        # Already has good ChEBI mapping
        if pd.notna(mapped_id) and isinstance(mapped_id, str) and mapped_id.startswith('CHEBI:'):
            return False

        # Has hydrate pattern - try matching
        if self.has_hydrate_pattern(compound_name):
            return True

        # Has ingredient: code and looks like a formula (contains chemical symbols)
        if pd.notna(mapped_id) and isinstance(mapped_id, str) and mapped_id.startswith('ingredient:'):
            # Check if name looks like a chemical formula
            import re
            # Simple heuristic: contains element symbols like Ca, Mg, Fe, etc.
            if re.search(r'\b([A-Z][a-z]?)\d', compound_name):
                return True

        return False

    def enhance_mapping_file(self, input_file: str, output_file: str) -> Dict:
        """
        Enhance mappings using formula matcher.

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

            # Check if should try formula matching
            if self.should_try_formula_matching(compound, mapped_id):
                stats['tried_matching'] += 1

                # Try formula matching
                result = self.matcher.match(compound)

                if result and result.chebi_id:
                    # Successful match!
                    df.at[idx, 'mapped'] = result.chebi_id
                    stats['successful_matches'] += 1

                    matches.append({
                        'compound': compound,
                        'old_id': mapped_id,
                        'new_id': result.chebi_id,
                        'base_formula': result.base_formula,
                        'water_molecules': result.water_molecules,
                        'method': result.method,
                        'confidence': result.confidence
                    })

                    logger.debug(f"✓ {compound} → {result.chebi_id} (base: {result.base_formula})")
                else:
                    stats['failed_matches'] += 1
                    logger.debug(f"✗ {compound} - No match found")

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
║                  FORMULA MATCHING ENHANCEMENT REPORT                    ║
╚════════════════════════════════════════════════════════════════════════╝

Total entries:           {stats['total_entries']:,}
Already mapped to ChEBI: {stats['already_mapped']:,}

Formula matching attempted: {stats['tried_matching']:,}
  ✓ Successful:  {stats['successful_matches']:,}
  ✗ Failed:      {stats['failed_matches']:,}

Success rate: {stats['successful_matches']/stats['tried_matching']*100 if stats['tried_matching'] > 0 else 0:.1f}%
        """)

        if matches:
            logger.info("\nSample successful matches:")
            for i, match in enumerate(matches[:10], 1):
                hydration = f" (·{match['water_molecules']}H2O)" if match['water_molecules'] else ""
                logger.info(f"{i}. {match['compound']}")
                logger.info(f"   {match['old_id']} → {match['new_id']}")
                logger.info(f"   Base: {match['base_formula']}{hydration}, "
                          f"Method: {match['method']}, Confidence: {match['confidence']}")


def main():
    """Main function for command-line execution."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Apply formula matching to enhance compound mappings",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--chebi-file',
        required=True,
        help='Path to ChEBI nodes TSV file'
    )
    parser.add_argument(
        '--input',
        default='pipeline_output/merge_mappings/high_confidence_compound_mappings_upgraded.tsv',
        help='Input compound mapping TSV'
    )
    parser.add_argument(
        '--output',
        default='pipeline_output/merge_mappings/high_confidence_compound_mappings_formula_enhanced.tsv',
        help='Output enhanced TSV file'
    )

    args = parser.parse_args()

    # Initialize enhancer
    enhancer = FormulaMappingEnhancer(args.chebi_file)

    # Enhance mappings
    enhancer.enhance_mapping_file(args.input, args.output)

    logger.info("\n✓ Formula matching enhancement complete!")


if __name__ == "__main__":
    main()
