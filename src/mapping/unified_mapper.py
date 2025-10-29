#!/usr/bin/env python3
"""
Unified Compound-to-KG Mapper

Consolidates mapping logic from 7 different scripts into one unified engine.
Uses strategy pattern for flexible matching approaches.

Previous scripts consolidated:
- map_compositions_to_kg.py
- map_compositions_comprehensive.py
- map_compositions_to_kg_enhanced.py
- map_compositions_exact.py
- map_compositions_fast.py
- map_compositions_demo.py
- map_compositions_sample.py
"""

import pandas as pd
import json
import re
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from .compound_normalizer import CompoundNameNormalizer
from .matching_strategies import ChainedMatcher, ExactMatcher, NormalizedMatcher, FuzzyMatcher

logger = logging.getLogger(__name__)


@dataclass
class MappingConfig:
    """Configuration for the mapping process."""
    kg_nodes_file: str
    composition_dir: str = "media_compositions"
    output_file: str = "composition_kg_mapping.tsv"
    fuzzy_threshold: int = 85
    enable_fuzzy: bool = True
    log_level: str = "INFO"

    # Optional filters
    filter_water: bool = True
    min_compound_length: int = 2


@dataclass
class MappingResult:
    """Result of mapping a single compound."""
    medium_id: str
    original: str
    mapped: str  # Node ID or empty if unmapped
    value: str  # Concentration value
    unit: str
    mmol_l: str  # Millimolar concentration
    optional: str
    source: str  # 'json' or 'markdown'
    matching_strategy: str = ""  # Which strategy succeeded


class UnifiedCompositionMapper:
    """
    Unified compound-to-knowledge-graph mapper.

    Consolidates all mapping logic into a single, maintainable engine
    with pluggable matching strategies.
    """

    def __init__(self, config: MappingConfig):
        """
        Initialize the unified mapper.

        Args:
            config: Mapping configuration
        """
        self.config = config
        self.normalizer = CompoundNameNormalizer()
        self.results: List[MappingResult] = []

        # Setup logging
        logging.basicConfig(
            level=getattr(logging, config.log_level),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('unified_mapping.log'),
                logging.StreamHandler()
            ]
        )

        # Load KG data
        self.kg_data = self._load_kg_nodes()

        # Initialize matching strategy
        self.matcher = ChainedMatcher(
            self.kg_data,
            fuzzy_threshold=config.fuzzy_threshold,
            enable_fuzzy=config.enable_fuzzy
        )

        # Statistics
        self.stats = {
            'total_compounds': 0,
            'mapped_compounds': 0,
            'unmapped_compounds': 0,
            'by_strategy': {},
            'by_medium': {}
        }

    def _load_kg_nodes(self) -> pd.DataFrame:
        """Load the KG-Microbe nodes file."""
        logger.info(f"Loading KG nodes from {self.config.kg_nodes_file}")

        try:
            df = pd.read_csv(self.config.kg_nodes_file, sep='\t', low_memory=False)

            # Filter for chemical entities
            chemical_df = df[df['category'].str.contains(
                'ChemicalEntity|ChemicalSubstance',
                na=False,
                case=False
            )]

            logger.info(f"Loaded {len(chemical_df)} chemical entities from {len(df)} total nodes")
            return chemical_df

        except Exception as e:
            logger.error(f"Error loading KG nodes: {e}")
            raise

    def _should_skip_compound(self, compound_name: str) -> bool:
        """
        Check if a compound should be skipped.

        Args:
            compound_name: Compound name to check

        Returns:
            True if compound should be skipped
        """
        if not compound_name or not isinstance(compound_name, str):
            return True

        # Check length
        if len(compound_name.strip()) < self.config.min_compound_length:
            return True

        # Filter water
        if self.config.filter_water:
            if compound_name.lower().strip() in ['distilled water', 'water', 'h2o']:
                return True

        return False

    def _extract_compositions_from_json(self, json_file: Path) -> List[Dict]:
        """
        Extract composition data from JSON file.

        Handles multiple JSON formats:
        - Array format: [{"compound": "...", "g_l": "..."}, ...]
        - Dict format: {"components": [...]}
        - MediaDive format: {"composition": [...]}

        Args:
            json_file: Path to JSON file

        Returns:
            List of composition dictionaries
        """
        compositions = []

        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            medium_id = re.search(r'medium_([^_]+)', json_file.name)
            medium_id = medium_id.group(1) if medium_id else json_file.stem

            # Handle array format
            if isinstance(data, list):
                for component in data:
                    if isinstance(component, dict):
                        compositions.append({
                            'compound': component.get('compound', ''),
                            'g_l': component.get('g_l'),
                            'mmol_l': component.get('mmol_l'),
                            'optional': component.get('optional', ''),
                            'medium_id': component.get('medium_id', medium_id)
                        })

            # Handle dictionary format
            elif isinstance(data, dict):
                components = data.get('components', data.get('composition', []))
                for component in components:
                    if isinstance(component, dict):
                        compound = component.get('name', component.get('compound', ''))
                        amount = component.get('amount', component.get('concentration', component.get('g_l')))
                        unit = component.get('unit', 'g/L')

                        compositions.append({
                            'compound': compound,
                            'value': amount,
                            'unit': unit,
                            'optional': component.get('optional', ''),
                            'medium_id': data.get('medium_id', medium_id)
                        })

        except Exception as e:
            logger.debug(f"Error reading JSON {json_file}: {e}")

        return compositions

    def _map_compound(self, compound_name: str) -> Tuple[Optional[str], str]:
        """
        Map a compound name to a KG node ID.

        Args:
            compound_name: Compound name to map

        Returns:
            Tuple of (node_id, strategy_name) if match found, (None, "unmapped") otherwise
        """
        if self._should_skip_compound(compound_name):
            return (None, "skipped")

        # Use chained matcher
        result_id, strategy = self.matcher.match_with_method(compound_name)

        if result_id:
            return (result_id, strategy)

        return (None, "unmapped")

    def process_compositions(self):
        """
        Process all composition files and perform mapping.

        Main entry point for the mapping process.
        """
        logger.info("Starting unified composition mapping process...")

        composition_dir = Path(self.config.composition_dir)

        # Find all JSON composition files
        json_files = list(composition_dir.glob("*_composition.json"))
        logger.info(f"Found {len(json_files)} JSON composition files")

        if not json_files:
            logger.warning(f"No composition files found in {composition_dir}")
            return

        # Process each file
        for i, json_file in enumerate(json_files, 1):
            medium_id = re.search(r'medium_([^_]+)', json_file.name)
            medium_id = medium_id.group(1) if medium_id else json_file.stem

            # Progress reporting
            if i % 50 == 0 or i == len(json_files):
                progress_pct = (i / len(json_files)) * 100
                mapping_rate = (self.stats['mapped_compounds'] / max(self.stats['total_compounds'], 1)) * 100
                logger.info(
                    f"Progress: {i}/{len(json_files)} ({progress_pct:.1f}%) - "
                    f"Medium {medium_id} - "
                    f"{self.stats['mapped_compounds']}/{self.stats['total_compounds']} mapped ({mapping_rate:.1f}%)"
                )

            # Extract compositions
            compositions = self._extract_compositions_from_json(json_file)

            # Map each compound
            medium_mapped = 0
            medium_total = 0

            for comp in compositions:
                compound = comp.get('compound', '')

                if self._should_skip_compound(compound):
                    continue

                medium_total += 1
                self.stats['total_compounds'] += 1

                # Perform mapping
                node_id, strategy = self._map_compound(compound)

                if node_id:
                    self.stats['mapped_compounds'] += 1
                    medium_mapped += 1
                    # Track by strategy
                    self.stats['by_strategy'][strategy] = self.stats['by_strategy'].get(strategy, 0) + 1
                else:
                    self.stats['unmapped_compounds'] += 1

                # Create result
                result = MappingResult(
                    medium_id=medium_id,
                    original=compound,
                    mapped=node_id if node_id else '',
                    value=str(comp.get('value', comp.get('g_l', ''))),
                    unit=comp.get('unit', 'g/L'),
                    mmol_l=str(comp.get('mmol_l', '')),
                    optional=comp.get('optional', ''),
                    source='json',
                    matching_strategy=strategy if node_id else ''
                )

                self.results.append(result)

            # Track by medium
            if medium_total > 0:
                mapping_rate = (medium_mapped / medium_total) * 100
                self.stats['by_medium'][medium_id] = {
                    'total': medium_total,
                    'mapped': medium_mapped,
                    'rate': mapping_rate
                }

        logger.info(f"Processed {len(json_files)} files, extracted {len(self.results)} compound entries")

    def save_results(self):
        """Save mapping results to TSV file."""
        if not self.results:
            logger.warning("No results to save")
            return

        # Convert results to DataFrame
        df = pd.DataFrame([vars(r) for r in self.results])

        # Reorder columns
        column_order = [
            'medium_id', 'original', 'mapped', 'value', 'unit',
            'mmol_l', 'optional', 'source', 'matching_strategy'
        ]
        df = df.reindex(columns=column_order)

        # Save to TSV
        output_path = Path(self.config.output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, sep='\t', index=False)

        logger.info(f"Saved {len(df)} mappings to {output_path}")

        # Generate summary
        self._generate_summary(df)

    def _generate_summary(self, df: pd.DataFrame):
        """Generate and log summary statistics."""
        total = len(df)
        mapped = len(df[df['mapped'] != ''])
        unmapped = total - mapped

        unique_compounds = df['original'].nunique()
        unique_mapped = df[df['mapped'] != '']['mapped'].nunique()

        logger.info(f"""
╔════════════════════════════════════════════════════════════════════════╗
║                        MAPPING SUMMARY                                  ║
╚════════════════════════════════════════════════════════════════════════╝

Total compound entries: {total:,}
Successfully mapped:    {mapped:,} ({mapped/total*100:.1f}%)
Unmapped:              {unmapped:,} ({unmapped/total*100:.1f}%)

Unique compound names:  {unique_compounds:,}
Unique KG nodes used:   {unique_mapped:,}

Mapping by strategy:
{self._format_strategy_stats()}

Media statistics:
- Total media processed: {len(self.stats['by_medium'])}
- Media with 100% mapping: {sum(1 for m in self.stats['by_medium'].values() if m['rate'] == 100)}
- Media with 0% mapping: {sum(1 for m in self.stats['by_medium'].values() if m['rate'] == 0)}
- Average mapping rate: {sum(m['rate'] for m in self.stats['by_medium'].values()) / len(self.stats['by_medium']):.1f}%
        """)

        # Top unmapped compounds
        unmapped_counts = df[df['mapped'] == '']['original'].value_counts().head(10)
        if not unmapped_counts.empty:
            logger.info("\nTop 10 unmapped compounds:")
            for compound, count in unmapped_counts.items():
                logger.info(f"  - {compound}: {count} occurrences")

    def _format_strategy_stats(self) -> str:
        """Format strategy statistics for display."""
        if not self.stats['by_strategy']:
            return "  No strategies used"

        lines = []
        for strategy, count in sorted(self.stats['by_strategy'].items(), key=lambda x: -x[1]):
            pct = count / self.stats['mapped_compounds'] * 100 if self.stats['mapped_compounds'] > 0 else 0
            lines.append(f"  - {strategy}: {count:,} ({pct:.1f}%)")

        return "\n".join(lines)

    def run(self):
        """
        Run the complete mapping workflow.

        Main entry point for executing the entire mapping process.
        """
        logger.info("=" * 80)
        logger.info("UNIFIED COMPOSITION-TO-KG MAPPING")
        logger.info("=" * 80)

        self.process_compositions()
        self.save_results()

        logger.info("=" * 80)
        logger.info("MAPPING PROCESS COMPLETED!")
        logger.info("=" * 80)


def main():
    """Main function for command-line execution."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Unified compound-to-knowledge-graph mapper",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--kg-nodes',
        required=True,
        help='Path to KG nodes TSV file'
    )
    parser.add_argument(
        '--composition-dir',
        default='media_compositions',
        help='Directory containing composition JSON files (default: media_compositions)'
    )
    parser.add_argument(
        '--output',
        default='composition_kg_mapping.tsv',
        help='Output TSV file (default: composition_kg_mapping.tsv)'
    )
    parser.add_argument(
        '--fuzzy-threshold',
        type=int,
        default=85,
        help='Fuzzy matching threshold 0-100 (default: 85)'
    )
    parser.add_argument(
        '--disable-fuzzy',
        action='store_true',
        help='Disable fuzzy matching (faster but less coverage)'
    )
    parser.add_argument(
        '--log-level',
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Logging level (default: INFO)'
    )

    args = parser.parse_args()

    # Create config
    config = MappingConfig(
        kg_nodes_file=args.kg_nodes,
        composition_dir=args.composition_dir,
        output_file=args.output,
        fuzzy_threshold=args.fuzzy_threshold,
        enable_fuzzy=not args.disable_fuzzy,
        log_level=args.log_level
    )

    # Run mapper
    mapper = UnifiedCompositionMapper(config)
    mapper.run()


if __name__ == "__main__":
    main()
