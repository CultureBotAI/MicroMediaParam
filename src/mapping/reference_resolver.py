#!/usr/bin/env python3
"""
Cross-Reference Resolver for Media Compositions

Resolves textual cross-references in media compositions, such as:
- "FeSO4 solution see below"
- "Trace vitamins (see Medium No.197)"
- "Solution (see medium 503)"

This enhances the existing solution expansion system which handles
structured "solution:XXX" codes, by also handling informal textual references.

Expected improvement: +30 compounds from Complex/Buffer Solutions cluster
"""

import pandas as pd
import re
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class CrossReference:
    """Represents a cross-reference to another medium or solution."""
    original_text: str
    reference_type: str  # "medium", "solution", "see_below", "unknown"
    target_medium_id: Optional[str]
    target_component: Optional[str]
    confidence: str  # "high", "medium", "low"


class MediaReferenceResolver:
    """
    Resolves cross-references in media composition descriptions.

    Handles references like:
    - "(see Medium No.197)" → look up Medium 197
    - "see below" → look in same medium for component
    - "solution (see medium 503)" → look up Medium 503 for solution
    """

    def __init__(self, compositions_dir: str = "media_compositions"):
        """
        Initialize the reference resolver.

        Args:
            compositions_dir: Directory containing composition JSON files
        """
        self.compositions_dir = Path(compositions_dir)
        self.media_index = {}  # medium_id → composition data
        self.reference_patterns = self._build_reference_patterns()

        self._build_media_index()

    def _build_reference_patterns(self) -> List[Tuple[str, str, re.Pattern]]:
        """
        Build regex patterns for detecting cross-references.

        Returns:
            List of (name, type, pattern) tuples
        """
        patterns = [
            # "see Medium No.197" or "(see Medium No.197)"
            (
                "medium_no",
                "medium",
                re.compile(r'\(?\s*see\s+Medium\s+No\.?\s*(\d+)\s*\)?', re.IGNORECASE)
            ),
            # "see medium 503" or "(see medium 503)"
            (
                "see_medium",
                "medium",
                re.compile(r'\(?\s*see\s+medium\s+(\d+)\s*\)?', re.IGNORECASE)
            ),
            # "see Medium No.976)" - note missing opening paren
            (
                "medium_no_partial",
                "medium",
                re.compile(r'see\s+Medium\s+No\.?\s*(\d+)\s*\)', re.IGNORECASE)
            ),
            # "solution see below"
            (
                "solution_below",
                "see_below",
                re.compile(r'solution\s+see\s+below', re.IGNORECASE)
            ),
            # "see below" in general
            (
                "see_below",
                "see_below",
                re.compile(r'see\s+below', re.IGNORECASE)
            ),
            # "(see below)" or "* (see below)"
            (
                "see_below_paren",
                "see_below",
                re.compile(r'\(?\s*see\s+below\s*\)?', re.IGNORECASE)
            ),
        ]

        return patterns

    def _build_media_index(self):
        """Build index of all media compositions."""
        logger.info("Building media index...")

        json_files = list(self.compositions_dir.glob("*_composition.json"))

        for json_file in json_files:
            # Extract medium ID
            match = re.search(r'medium_([^_]+)', json_file.name)
            if not match:
                continue

            medium_id = match.group(1)

            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                self.media_index[medium_id] = {
                    'file': str(json_file),
                    'data': data
                }

            except Exception as e:
                logger.debug(f"Error loading {json_file}: {e}")

        logger.info(f"Indexed {len(self.media_index)} media compositions")

    def detect_references(self, compound_name: str) -> List[CrossReference]:
        """
        Detect cross-references in a compound name.

        Args:
            compound_name: Compound name to analyze

        Returns:
            List of detected cross-references
        """
        references = []

        for pattern_name, ref_type, pattern in self.reference_patterns:
            matches = pattern.finditer(compound_name)

            for match in matches:
                # Extract target medium ID if present
                target_medium_id = None
                if ref_type == "medium" and match.groups():
                    target_medium_id = match.group(1)

                ref = CrossReference(
                    original_text=match.group(0),
                    reference_type=ref_type,
                    target_medium_id=target_medium_id,
                    target_component=None,  # Will be filled by resolution
                    confidence="high" if target_medium_id else "medium"
                )

                references.append(ref)

        return references

    def resolve_reference(self, reference: CrossReference,
                         source_medium_id: str) -> Optional[Dict]:
        """
        Resolve a cross-reference to actual composition data.

        Args:
            reference: CrossReference to resolve
            source_medium_id: ID of the medium containing the reference

        Returns:
            Dictionary with resolved data, or None if couldn't resolve
        """
        if reference.reference_type == "medium":
            # Cross-reference to another medium
            return self._resolve_medium_reference(reference)

        elif reference.reference_type == "see_below":
            # Reference to component later in same medium
            return self._resolve_see_below(reference, source_medium_id)

        return None

    def _resolve_medium_reference(self, reference: CrossReference) -> Optional[Dict]:
        """Resolve reference to another medium."""
        if not reference.target_medium_id:
            return None

        # Look up target medium
        target_data = self.media_index.get(reference.target_medium_id)

        if not target_data:
            logger.debug(f"Medium {reference.target_medium_id} not found in index")
            return None

        # Extract composition components
        data = target_data['data']
        components = []

        if isinstance(data, list):
            components = data
        elif isinstance(data, dict):
            components = data.get('components', data.get('composition', []))

        return {
            'medium_id': reference.target_medium_id,
            'components': components,
            'source': target_data['file']
        }

    def _resolve_see_below(self, reference: CrossReference,
                          source_medium_id: str) -> Optional[Dict]:
        """
        Resolve 'see below' reference within same medium.

        This is tricky because we need to find what component
        comes 'below' in the medium description.
        """
        # Get source medium data
        source_data = self.media_index.get(source_medium_id)

        if not source_data:
            return None

        # For 'see below', we return a placeholder
        # indicating manual review is needed
        return {
            'medium_id': source_medium_id,
            'components': [],
            'note': 'Manual review required - reference to component within same medium',
            'source': source_data['file']
        }

    def analyze_mapping_file(self, mapping_file: str) -> Dict:
        """
        Analyze a mapping file for cross-references.

        Args:
            mapping_file: Path to compound mapping TSV

        Returns:
            Dictionary with analysis results
        """
        logger.info(f"Analyzing cross-references in {mapping_file}")

        df = pd.read_csv(mapping_file, sep='\t', low_memory=False)

        # Statistics
        stats = {
            'total_entries': len(df),
            'entries_with_references': 0,
            'references_by_type': defaultdict(int),
            'resolvable_references': 0,
            'unresolvable_references': 0,
            'examples': []
        }

        # Analyze each compound
        for _, row in df.iterrows():
            compound = row['original']
            medium_id = row.get('medium_id', '')

            references = self.detect_references(compound)

            if references:
                stats['entries_with_references'] += 1

                for ref in references:
                    stats['references_by_type'][ref.reference_type] += 1

                    # Try to resolve
                    resolved = self.resolve_reference(ref, medium_id)

                    if resolved and resolved.get('components'):
                        stats['resolvable_references'] += 1
                    else:
                        stats['unresolvable_references'] += 1

                    # Store examples
                    if len(stats['examples']) < 20:
                        stats['examples'].append({
                            'compound': compound,
                            'medium_id': medium_id,
                            'reference': ref.original_text,
                            'type': ref.reference_type,
                            'target': ref.target_medium_id,
                            'resolved': bool(resolved and resolved.get('components'))
                        })

        self._log_analysis(stats)
        return stats

    def _log_analysis(self, stats: Dict):
        """Log analysis statistics."""
        logger.info(f"""
╔════════════════════════════════════════════════════════════════════════╗
║                  CROSS-REFERENCE ANALYSIS REPORT                        ║
╚════════════════════════════════════════════════════════════════════════╝

Total entries analyzed:      {stats['total_entries']:,}
Entries with references:     {stats['entries_with_references']:,}

References by type:
{self._format_reference_types(stats['references_by_type'])}

Resolution status:
  ✓ Resolvable:   {stats['resolvable_references']:,}
  ✗ Unresolvable: {stats['unresolvable_references']:,}
        """)

        if stats['examples']:
            logger.info("\nSample references:")
            for i, example in enumerate(stats['examples'][:10], 1):
                status = "✓" if example['resolved'] else "✗"
                logger.info(f"{i}. {status} {example['compound']}")
                logger.info(f"   Medium: {example['medium_id']}, "
                          f"Ref: '{example['reference']}', "
                          f"Type: {example['type']}")

    def _format_reference_types(self, type_counts: Dict[str, int]) -> str:
        """Format reference type counts for display."""
        if not type_counts:
            return "  (none found)"

        lines = []
        for ref_type, count in sorted(type_counts.items(), key=lambda x: -x[1]):
            lines.append(f"  - {ref_type}: {count}")

        return "\n".join(lines)

    def export_reference_report(self, mapping_file: str, output_file: str):
        """
        Export detailed reference analysis to JSON.

        Args:
            mapping_file: Input mapping TSV
            output_file: Output JSON report
        """
        stats = self.analyze_mapping_file(mapping_file)

        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            json.dump(stats, f, indent=2, default=str)

        logger.info(f"Saved reference report to {output_path}")


def main():
    """Main function for command-line execution."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Analyze and resolve cross-references in media compositions",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--compositions-dir',
        default='media_compositions',
        help='Directory containing composition JSON files'
    )
    parser.add_argument(
        '--mapping-file',
        default='pipeline_output/merge_mappings/high_confidence_compound_mappings.tsv',
        help='Compound mapping TSV file to analyze'
    )
    parser.add_argument(
        '--output',
        default='analysis_reports/cross_reference_analysis.json',
        help='Output JSON report file'
    )

    args = parser.parse_args()

    # Initialize resolver
    resolver = MediaReferenceResolver(args.compositions_dir)

    # Analyze and export report
    resolver.export_reference_report(args.mapping_file, args.output)

    logger.info("\n✓ Cross-reference analysis complete!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
