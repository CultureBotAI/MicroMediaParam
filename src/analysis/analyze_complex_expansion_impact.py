#!/usr/bin/env python3
"""
Analyze Complex Ingredients Expansion Impact

Compares media composition before and after complex ingredient expansion
to quantify the coverage improvement and new chemical entities added.

Usage:
    python src/analysis/analyze_complex_expansion_impact.py \\
        --before pipeline_output/media_summary/media_composition_table.tsv \\
        --after pipeline_output/media_summary/media_composition_expanded.tsv \\
        --yaml data/curated/complex_ingredients/complex_ingredient_compositions.yaml

Version: 1.0.0
"""

import argparse
import logging
from pathlib import Path
from typing import Dict, List, Set, Tuple

import pandas as pd
import yaml

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ComplexExpansionAnalyzer:
    """Analyzes the impact of complex ingredients expansion."""

    def __init__(
        self,
        before_file: Path,
        after_file: Path,
        yaml_file: Path
    ):
        """
        Initialize analyzer.

        Args:
            before_file: Original media composition table
            after_file: Expanded media composition table
            yaml_file: Complex ingredients YAML database
        """
        self.before_file = before_file
        self.after_file = after_file
        self.yaml_file = yaml_file

        self.before_df: pd.DataFrame = None
        self.after_df: pd.DataFrame = None
        self.yaml_data: Dict = {}

    def load_data(self):
        """Load all input files."""
        logger.info(f"Loading before: {self.before_file}")
        self.before_df = pd.read_csv(self.before_file, sep='\t')

        logger.info(f"Loading after: {self.after_file}")
        self.after_df = pd.read_csv(self.after_file, sep='\t')

        logger.info(f"Loading YAML: {self.yaml_file}")
        with open(self.yaml_file, 'r') as f:
            self.yaml_data = yaml.safe_load(f)

    def analyze_coverage(self) -> Dict:
        """
        Analyze ChEBI ID coverage before and after expansion.

        Returns:
            Dictionary with coverage metrics
        """
        # Count ChEBI IDs
        before_chebi = self.before_df['ingredient_id'].dropna()
        before_chebi = before_chebi[before_chebi.str.startswith('CHEBI:', na=False)]
        before_chebi_count = before_chebi.nunique()
        before_total = len(self.before_df)

        after_chebi = self.after_df['ingredient_id'].dropna()
        after_chebi = after_chebi[after_chebi.str.startswith('CHEBI:', na=False)]
        after_chebi_count = after_chebi.nunique()
        after_total = len(self.after_df)

        # Coverage percentages
        before_pct = (before_chebi_count / before_total * 100) if before_total > 0 else 0
        after_pct = (after_chebi_count / after_total * 100) if after_total > 0 else 0

        # New ChEBI IDs from expansion
        before_chebi_set = set(before_chebi)
        after_chebi_set = set(after_chebi)
        new_chebi_ids = after_chebi_set - before_chebi_set

        return {
            'before_total_rows': before_total,
            'before_chebi_count': before_chebi_count,
            'before_coverage_pct': before_pct,
            'after_total_rows': after_total,
            'after_chebi_count': after_chebi_count,
            'after_coverage_pct': after_pct,
            'new_chebi_ids': len(new_chebi_ids),
            'coverage_gain_pct': after_pct - before_pct,
            'new_rows_added': after_total - before_total,
        }

    def analyze_expanded_ingredients(self) -> Dict:
        """
        Analyze which complex ingredients were expanded.

        Returns:
            Dictionary with expansion metrics
        """
        if 'source_ingredient' not in self.after_df.columns:
            logger.warning("No 'source_ingredient' column found in expanded data")
            return {}

        # Count expanded entries
        expanded = self.after_df[self.after_df['source_ingredient'].notna()]
        expanded_count = len(expanded)

        # Unique source ingredients
        source_ingredients = expanded['source_ingredient'].unique()

        # Breakdown by source ingredient
        expansion_breakdown = {}
        for source in source_ingredients:
            source_rows = expanded[expanded['source_ingredient'] == source]
            expansion_breakdown[source] = {
                'expanded_rows': len(source_rows),
                'unique_chebi_ids': source_rows['ingredient_id'].nunique(),
                'media_count': source_rows['medium_id'].nunique() if 'medium_id' in source_rows else 0,
            }

        return {
            'total_expanded_rows': expanded_count,
            'unique_source_ingredients': len(source_ingredients),
            'source_ingredients': list(source_ingredients),
            'breakdown': expansion_breakdown,
        }

    def analyze_yaml_database(self) -> Dict:
        """
        Analyze the complex ingredients YAML database.

        Returns:
            Dictionary with YAML metrics
        """
        ingredients = self.yaml_data.get('ingredients', {})

        # Count by type
        type_counts = {}
        for ing_id, ing_data in ingredients.items():
            ing_type = ing_data.get('compound_type', 'complex_mixture')
            type_counts[ing_type] = type_counts.get(ing_type, 0) + 1

        # Count constituents per ingredient
        constituent_counts = {}
        for ing_id, ing_data in ingredients.items():
            total_constituents = 0
            for category in ['amino_acids', 'vitamins', 'minerals', 'sugars',
                             'nucleotides', 'other_compounds', 'trace_elements']:
                if category in ing_data:
                    total_constituents += len(ing_data[category])
            if total_constituents > 0:
                constituent_counts[ing_id] = total_constituents

        return {
            'total_ingredients': len(ingredients),
            'by_type': type_counts,
            'with_constituents': len(constituent_counts),
            'avg_constituents': sum(constituent_counts.values()) / len(constituent_counts) if constituent_counts else 0,
            'total_constituents_defined': sum(constituent_counts.values()),
        }

    def print_report(self):
        """Print comprehensive analysis report."""
        print("\n" + "=" * 70)
        print("COMPLEX INGREDIENTS EXPANSION IMPACT ANALYSIS")
        print("=" * 70)

        # YAML Database
        yaml_metrics = self.analyze_yaml_database()
        print("\n📚 YAML Database")
        print("-" * 70)
        print(f"Total ingredients in database: {yaml_metrics['total_ingredients']}")
        print(f"Ingredients with defined constituents: {yaml_metrics['with_constituents']}")
        print(f"Total chemical constituents defined: {yaml_metrics['total_constituents_defined']}")
        print(f"Average constituents per ingredient: {yaml_metrics['avg_constituents']:.1f}")
        print("\nBreakdown by type:")
        for ing_type, count in sorted(yaml_metrics['by_type'].items()):
            print(f"  {ing_type}: {count}")

        # Coverage Analysis
        coverage = self.analyze_coverage()
        print("\n📊 Coverage Analysis")
        print("-" * 70)
        print(f"BEFORE expansion:")
        print(f"  Total rows: {coverage['before_total_rows']:,}")
        print(f"  Unique ChEBI IDs: {coverage['before_chebi_count']:,}")
        print(f"  Coverage: {coverage['before_coverage_pct']:.2f}%")
        print(f"\nAFTER expansion:")
        print(f"  Total rows: {coverage['after_total_rows']:,}")
        print(f"  Unique ChEBI IDs: {coverage['after_chebi_count']:,}")
        print(f"  Coverage: {coverage['after_coverage_pct']:.2f}%")
        print(f"\n✨ IMPROVEMENT:")
        print(f"  New rows added: +{coverage['new_rows_added']:,}")
        print(f"  New unique ChEBI IDs: +{coverage['new_chebi_ids']}")
        print(f"  Coverage gain: +{coverage['coverage_gain_pct']:.2f} percentage points")

        # Expansion Details
        expansion = self.analyze_expanded_ingredients()
        if expansion:
            print("\n🔬 Expansion Details")
            print("-" * 70)
            print(f"Total expanded rows: {expansion['total_expanded_rows']:,}")
            print(f"Unique source ingredients expanded: {expansion['unique_source_ingredients']}")
            print("\nTop 10 expanded ingredients:")
            breakdown = expansion['breakdown']
            sorted_sources = sorted(
                breakdown.items(),
                key=lambda x: x[1]['expanded_rows'],
                reverse=True
            )[:10]
            for source, metrics in sorted_sources:
                print(f"  {source}:")
                print(f"    → {metrics['expanded_rows']} rows, {metrics['unique_chebi_ids']} unique ChEBI IDs, {metrics['media_count']} media")

        print("\n" + "=" * 70)

    def save_report(self, output_file: Path):
        """
        Save detailed report to file.

        Args:
            output_file: Path to output file
        """
        with open(output_file, 'w') as f:
            # Write header
            f.write("=" * 70 + "\n")
            f.write("COMPLEX INGREDIENTS EXPANSION IMPACT REPORT\n")
            f.write("=" * 70 + "\n\n")

            # YAML metrics
            yaml_metrics = self.analyze_yaml_database()
            f.write("YAML Database Metrics\n")
            f.write("-" * 70 + "\n")
            f.write(f"Total ingredients: {yaml_metrics['total_ingredients']}\n")
            f.write(f"With constituents: {yaml_metrics['with_constituents']}\n")
            f.write(f"Total constituents: {yaml_metrics['total_constituents_defined']}\n")
            f.write(f"Avg constituents/ingredient: {yaml_metrics['avg_constituents']:.1f}\n\n")

            # Coverage metrics
            coverage = self.analyze_coverage()
            f.write("Coverage Metrics\n")
            f.write("-" * 70 + "\n")
            f.write(f"Before: {coverage['before_chebi_count']:,} ChEBI IDs / {coverage['before_total_rows']:,} rows ({coverage['before_coverage_pct']:.2f}%)\n")
            f.write(f"After: {coverage['after_chebi_count']:,} ChEBI IDs / {coverage['after_total_rows']:,} rows ({coverage['after_coverage_pct']:.2f}%)\n")
            f.write(f"Gain: +{coverage['new_chebi_ids']} ChEBI IDs, +{coverage['coverage_gain_pct']:.2f}% coverage\n\n")

            # Expansion details
            expansion = self.analyze_expanded_ingredients()
            if expansion:
                f.write("Expansion Details\n")
                f.write("-" * 70 + "\n")
                f.write(f"Total expanded rows: {expansion['total_expanded_rows']:,}\n")
                f.write(f"Source ingredients: {expansion['unique_source_ingredients']}\n\n")
                for source, metrics in sorted(expansion['breakdown'].items(), key=lambda x: x[1]['expanded_rows'], reverse=True):
                    f.write(f"{source}: {metrics['expanded_rows']} rows, {metrics['unique_chebi_ids']} ChEBI IDs\n")

        logger.info(f"Report saved to {output_file}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Analyze complex ingredients expansion impact'
    )
    parser.add_argument(
        '--before',
        required=True,
        help='Original media composition table (before expansion)'
    )
    parser.add_argument(
        '--after',
        required=True,
        help='Expanded media composition table (after expansion)'
    )
    parser.add_argument(
        '--yaml',
        required=True,
        help='Complex ingredients YAML database'
    )
    parser.add_argument(
        '--output',
        help='Output file for detailed report (optional)'
    )

    args = parser.parse_args()

    before_file = Path(args.before)
    after_file = Path(args.after)
    yaml_file = Path(args.yaml)

    if not before_file.exists():
        logger.error(f"Before file not found: {before_file}")
        return 1

    if not after_file.exists():
        logger.error(f"After file not found: {after_file}")
        return 1

    if not yaml_file.exists():
        logger.error(f"YAML file not found: {yaml_file}")
        return 1

    # Analyze
    analyzer = ComplexExpansionAnalyzer(before_file, after_file, yaml_file)
    analyzer.load_data()
    analyzer.print_report()

    if args.output:
        analyzer.save_report(Path(args.output))

    return 0


if __name__ == '__main__':
    exit(main())
