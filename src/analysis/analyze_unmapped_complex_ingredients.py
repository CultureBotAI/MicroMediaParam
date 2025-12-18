#!/usr/bin/env python3
"""
Analyze unmapped complex ingredients from compound mappings.

This script identifies complex biological ingredients (peptones, extracts, sera, etc.)
that are not yet mapped to ChEBI or other ontology terms, and prioritizes them
based on frequency and potential impact on coverage.

Usage:
    python src/analysis/analyze_unmapped_complex_ingredients.py \
        --mappings pipeline_output/merge_mappings/high_confidence_compound_mappings_final.tsv \
        --compositions data/curated/complex_ingredients/complex_ingredient_compositions.yaml \
        --output pipeline_output/analysis/unmapped_complex_ingredients_priority.tsv
"""

import pandas as pd
import yaml
import argparse
import logging
from pathlib import Path
from typing import Dict, List, Set
import re

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ComplexIngredientAnalyzer:
    """Analyze and prioritize unmapped complex ingredients."""

    # Patterns that indicate complex biological ingredients
    COMPLEX_PATTERNS = [
        r'\bpeptone\b',
        r'\btryptone\b',
        r'\bcasitone\b',
        r'\bproteose\b',
        r'\bextract\b',
        r'\bbroth\b',
        r'\binfusion\b',
        r'\bdigest\b',
        r'\bhydrolysate\b',
        r'\bhydrolyzate\b',
        r'\bserum\b',
        r'\bplasma\b',
        r'\bblood\b',
        r'\bmilk\b',
        r'\bagar\b',
        r'\bbactotryptone\b',
        r'\bbacto\b',
        r'\bdifco\b',
        r'\bvitamin\s+solution\b',
        r'\btrace\s+element',
        r'\bmineral\s+solution\b',
        r'\bmeat\s+extract\b',
        r'\bbeef\s+extract\b',
        r'\bheart\s+infusion\b',
        r'\bbrain\s+heart\b',
    ]

    def __init__(self, mappings_file: str, compositions_file: str):
        self.mappings_file = mappings_file
        self.compositions_file = compositions_file
        self.known_complex_ingredients: Set[str] = set()
        self.unmapped_complex_ingredients: Dict = {}

    def load_known_complex_ingredients(self) -> Set[str]:
        """Load names of complex ingredients already documented in YAML."""
        logger.info(f"Loading known complex ingredients from {self.compositions_file}")

        try:
            with open(self.compositions_file, 'r') as f:
                data = yaml.safe_load(f)

            known = set()

            # Access the ingredients section of the YAML
            ingredients = data.get('ingredients', {})
            if not ingredients:
                # Fallback: if no 'ingredients' key, treat whole data as ingredients
                ingredients = data

            for ingredient_name, ingredient_data in ingredients.items():
                # Skip metadata or non-ingredient entries
                if ingredient_name == 'metadata':
                    continue

                # Add the main ingredient name (replace underscores with spaces for matching)
                known.add(ingredient_name.lower())
                known.add(ingredient_name.replace('_', ' ').lower())

                # Add common name if available
                if isinstance(ingredient_data, dict):
                    common_name = ingredient_data.get('common_name')
                    if common_name:
                        known.add(common_name.lower())

                    # Add synonyms if available
                    synonyms = ingredient_data.get('synonyms', [])
                    for synonym in synonyms:
                        known.add(synonym.lower())

            logger.info(f"Found {len(known)} known complex ingredient names")
            return known

        except FileNotFoundError:
            logger.warning(f"Compositions file not found: {self.compositions_file}")
            return set()
        except Exception as e:
            logger.error(f"Error loading compositions: {e}")
            return set()

    def is_complex_ingredient(self, ingredient_name: str) -> bool:
        """Check if an ingredient name matches complex ingredient patterns."""
        name_lower = ingredient_name.lower()

        for pattern in self.COMPLEX_PATTERNS:
            if re.search(pattern, name_lower, re.IGNORECASE):
                return True

        return False

    def analyze_unmapped_ingredients(self) -> pd.DataFrame:
        """Analyze compound mappings to find unmapped complex ingredients."""
        logger.info(f"Loading compound mappings from {self.mappings_file}")

        # Load mappings
        df = pd.read_csv(self.mappings_file, sep='\t', dtype=str, low_memory=False)
        logger.info(f"Loaded {len(df)} mapping entries")

        # Load known complex ingredients
        self.known_complex_ingredients = self.load_known_complex_ingredients()

        # Find unmapped entries (no ChEBI ID in mapped column)
        unmapped = df[
            (df['mapped'].isna()) |
            (df['mapped'] == '') |
            (~df['mapped'].str.startswith('CHEBI:', na=False))
        ].copy()

        logger.info(f"Found {len(unmapped)} unmapped entries")

        # Filter for complex ingredients
        unmapped['is_complex'] = unmapped['original'].apply(self.is_complex_ingredient)
        complex_unmapped = unmapped[unmapped['is_complex']].copy()

        logger.info(f"Found {len(complex_unmapped)} unmapped complex ingredient entries")

        # Convert value to numeric
        complex_unmapped['value_numeric'] = pd.to_numeric(complex_unmapped['value'], errors='coerce')

        # Aggregate by ingredient name
        analysis = complex_unmapped.groupby('original').agg({
            'medium_id': 'count',  # Occurrence count
            'value_numeric': ['mean', 'min', 'max', 'std'],  # Concentration statistics
            'unit': lambda x: x.mode()[0] if len(x.mode()) > 0 else '',  # Most common unit
        }).reset_index()

        # Flatten multi-level columns
        analysis.columns = ['ingredient_name', 'occurrence_count', 'mean_concentration',
                           'min_concentration', 'max_concentration', 'std_concentration',
                           'common_unit']

        # Check if already documented
        analysis['is_documented'] = analysis['ingredient_name'].apply(
            lambda x: x.lower() in self.known_complex_ingredients
        )

        # Calculate priority score
        # Priority = occurrence_count * (1 if not documented else 0.1)
        analysis['priority_score'] = analysis.apply(
            lambda row: row['occurrence_count'] * (1.0 if not row['is_documented'] else 0.1),
            axis=1
        )

        # Add category classification
        analysis['category'] = analysis['ingredient_name'].apply(self.classify_ingredient)

        # Sort by priority score
        analysis = analysis.sort_values('priority_score', ascending=False)

        logger.info(f"Identified {len(analysis)} unique unmapped complex ingredients")
        logger.info(f"  - {(~analysis['is_documented']).sum()} not yet documented")
        logger.info(f"  - {analysis['is_documented'].sum()} already documented (need expansion)")

        return analysis

    def classify_ingredient(self, name: str) -> str:
        """Classify ingredient into category for better organization."""
        name_lower = name.lower()

        if any(p in name_lower for p in ['peptone', 'tryptone', 'casitone', 'proteose']):
            return 'peptone_digest'
        elif any(p in name_lower for p in ['yeast extract', 'beef extract', 'meat extract', 'malt extract']):
            return 'extract'
        elif any(p in name_lower for p in ['serum', 'plasma', 'blood']):
            return 'blood_product'
        elif any(p in name_lower for p in ['broth', 'infusion']):
            return 'complex_medium'
        elif any(p in name_lower for p in ['vitamin', 'trace element', 'mineral']):
            return 'supplement_solution'
        elif any(p in name_lower for p in ['agar']):
            return 'solidifying_agent'
        elif any(p in name_lower for p in ['digest', 'hydrolysate', 'hydrolyzate']):
            return 'hydrolysate'
        else:
            return 'other_complex'

    def generate_curation_recommendations(self, analysis_df: pd.DataFrame, top_n: int = 20) -> str:
        """Generate human-readable recommendations for curation priorities."""

        report_lines = [
            "=" * 80,
            "UNMAPPED COMPLEX INGREDIENTS - CURATION PRIORITIES",
            "=" * 80,
            "",
            f"Total unique complex ingredients analyzed: {len(analysis_df)}",
            f"Not yet documented: {(~analysis_df['is_documented']).sum()}",
            f"Already documented (need expansion): {analysis_df['is_documented'].sum()}",
            "",
            "=" * 80,
            f"TOP {top_n} PRIORITY INGREDIENTS (by occurrence count)",
            "=" * 80,
            ""
        ]

        for idx, row in analysis_df.head(top_n).iterrows():
            status = "✓ DOCUMENTED" if row['is_documented'] else "✗ UNDOCUMENTED"
            report_lines.extend([
                f"{idx + 1}. {row['ingredient_name']}",
                f"   Category: {row['category']}",
                f"   Status: {status}",
                f"   Occurrences: {int(row['occurrence_count'])}",
                f"   Priority Score: {row['priority_score']:.1f}",
                f"   Typical Concentration: {row['mean_concentration']:.2f} {row['common_unit']} "
                f"(range: {row['min_concentration']:.2f}-{row['max_concentration']:.2f})",
                ""
            ])

        # Summary by category
        report_lines.extend([
            "=" * 80,
            "SUMMARY BY CATEGORY",
            "=" * 80,
            ""
        ])

        category_summary = analysis_df.groupby('category').agg({
            'ingredient_name': 'count',
            'occurrence_count': 'sum',
            'is_documented': lambda x: (~x).sum()  # Count undocumented
        }).reset_index()

        category_summary.columns = ['category', 'unique_ingredients', 'total_occurrences', 'undocumented']
        category_summary = category_summary.sort_values('total_occurrences', ascending=False)

        for _, row in category_summary.iterrows():
            report_lines.append(
                f"{row['category']}: {int(row['unique_ingredients'])} unique "
                f"({int(row['undocumented'])} undocumented), "
                f"{int(row['total_occurrences'])} total occurrences"
            )

        report_lines.extend([
            "",
            "=" * 80,
            "RECOMMENDED ACTIONS",
            "=" * 80,
            "",
            "1. HIGH PRIORITY (>100 occurrences, undocumented):",
        ])

        high_priority = analysis_df[
            (~analysis_df['is_documented']) &
            (analysis_df['occurrence_count'] > 100)
        ]

        if len(high_priority) > 0:
            for _, row in high_priority.iterrows():
                report_lines.append(f"   - {row['ingredient_name']} ({int(row['occurrence_count'])} occurrences)")
        else:
            report_lines.append("   - None found")

        report_lines.extend([
            "",
            "2. MEDIUM PRIORITY (10-100 occurrences, undocumented):",
        ])

        medium_priority = analysis_df[
            (~analysis_df['is_documented']) &
            (analysis_df['occurrence_count'] >= 10) &
            (analysis_df['occurrence_count'] <= 100)
        ]

        if len(medium_priority) > 0:
            for _, row in medium_priority.head(10).iterrows():
                report_lines.append(f"   - {row['ingredient_name']} ({int(row['occurrence_count'])} occurrences)")
            if len(medium_priority) > 10:
                report_lines.append(f"   ... and {len(medium_priority) - 10} more")
        else:
            report_lines.append("   - None found")

        report_lines.extend([
            "",
            "3. EXPAND DOCUMENTED (already in YAML, needs constituent expansion):",
        ])

        expand_documented = analysis_df[
            (analysis_df['is_documented']) &
            (analysis_df['occurrence_count'] > 10)
        ]

        if len(expand_documented) > 0:
            for _, row in expand_documented.head(10).iterrows():
                report_lines.append(f"   - {row['ingredient_name']} ({int(row['occurrence_count'])} occurrences)")
            if len(expand_documented) > 10:
                report_lines.append(f"   ... and {len(expand_documented) - 10} more")
        else:
            report_lines.append("   - None found")

        report_lines.extend([
            "",
            "=" * 80,
            ""
        ])

        return "\n".join(report_lines)


def main():
    parser = argparse.ArgumentParser(
        description="Analyze and prioritize unmapped complex ingredients"
    )
    parser.add_argument(
        '--mappings',
        required=True,
        help='Input TSV file with compound mappings'
    )
    parser.add_argument(
        '--compositions',
        default='data/curated/complex_ingredients/complex_ingredient_compositions.yaml',
        help='YAML file with known complex ingredient compositions'
    )
    parser.add_argument(
        '--output',
        required=True,
        help='Output TSV file for prioritized complex ingredients'
    )
    parser.add_argument(
        '--report',
        help='Optional text report file with recommendations'
    )
    parser.add_argument(
        '--top-n',
        type=int,
        default=50,
        help='Number of top priority ingredients to highlight (default: 50)'
    )

    args = parser.parse_args()

    # Create output directory
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)

    # Analyze
    analyzer = ComplexIngredientAnalyzer(args.mappings, args.compositions)
    analysis_df = analyzer.analyze_unmapped_ingredients()

    # Save TSV
    logger.info(f"Saving analysis to {args.output}")
    analysis_df.to_csv(args.output, sep='\t', index=False)

    # Generate and save report
    report = analyzer.generate_curation_recommendations(analysis_df, top_n=args.top_n)

    if args.report:
        logger.info(f"Saving report to {args.report}")
        with open(args.report, 'w') as f:
            f.write(report)
    else:
        print(report)

    logger.info("Analysis completed!")


if __name__ == "__main__":
    main()
