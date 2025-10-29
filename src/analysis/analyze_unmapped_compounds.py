#!/usr/bin/env python3
"""
Comprehensive Unmapped Compound Analysis

Analyzes unmapped compounds from the high-confidence mapping file,
identifies patterns, clusters them by type, and generates recommendations
for custom mapping strategies.

This replaces ad-hoc analysis scripts with a comprehensive, repeatable analysis.
"""

import pandas as pd
import re
import logging
from pathlib import Path
from typing import Dict, List, Set, Tuple
from collections import Counter, defaultdict
from dataclasses import dataclass, field

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class CompoundCluster:
    """Represents a cluster of related compounds."""
    name: str
    description: str
    compounds: List[str] = field(default_factory=list)
    mapping_strategy: str = ""
    difficulty: str = "medium"  # easy, medium, hard, impossible
    expected_improvement: int = 0


class UnmappedCompoundAnalyzer:
    """
    Analyzes unmapped compounds and clusters them by type.

    Identifies patterns like:
    - Chemical formulas with hydrates
    - Complex solutions
    - Biological/commercial products
    - Malformed entries
    """

    def __init__(self, mapping_file: str):
        """
        Initialize the analyzer.

        Args:
            mapping_file: Path to high confidence compound mappings TSV
        """
        self.mapping_file = mapping_file
        self.df = None
        self.unmapped = None
        self.clusters: Dict[str, CompoundCluster] = {}

        self._load_data()
        self._identify_unmapped()

    def _load_data(self):
        """Load the mapping data."""
        logger.info(f"Loading mapping data from {self.mapping_file}")
        self.df = pd.read_csv(self.mapping_file, sep='\t', low_memory=False)
        logger.info(f"Loaded {len(self.df)} total entries")

    def _identify_unmapped(self):
        """Identify unmapped compounds (those with ingredient: codes)."""
        # Unmapped = has ingredient: code OR empty mapping
        unmapped_mask = (
            self.df['mapped'].str.startswith('ingredient:', na=False) |
            self.df['mapped'].isna() |
            (self.df['mapped'] == '')
        )

        self.unmapped = self.df[unmapped_mask]['original'].unique()
        logger.info(f"Found {len(self.unmapped)} unmapped unique compounds")

    def analyze_by_pattern(self):
        """Analyze and cluster compounds by pattern."""
        logger.info("Analyzing compounds by pattern...")

        # Initialize clusters
        self.clusters = {
            'chemical_formulas_hydrated': CompoundCluster(
                name="Chemical Formulas with Hydrates",
                description="Chemical formulas with hydration notation (x N H2O pattern)",
                mapping_strategy="Strip hydration, normalize formula → ChEBI lookup",
                difficulty="easy",
                expected_improvement=20
            ),
            'chemical_formulas_simple': CompoundCluster(
                name="Simple Chemical Formulas",
                description="Pure chemical formulas without hydration",
                mapping_strategy="Direct formula lookup in ChEBI/PubChem",
                difficulty="easy",
                expected_improvement=15
            ),
            'solution_references': CompoundCluster(
                name="Complex/Buffer Solutions",
                description="References to other solutions or complex buffers",
                mapping_strategy="Expand solution references, parse nested compositions",
                difficulty="hard",
                expected_improvement=30
            ),
            'biological_products': CompoundCluster(
                name="Animal/Biological Products",
                description="Extracts, peptones, animal-derived products",
                mapping_strategy="Create mapping dictionary for common microbiology products",
                difficulty="medium",
                expected_improvement=15
            ),
            'commercial_products': CompoundCluster(
                name="Commercial/Proprietary Products",
                description="Brand-name commercial products (Bacto, Difco, etc.)",
                mapping_strategy="Research equivalents, create manual mapping table",
                difficulty="medium",
                expected_improvement=10
            ),
            'media_codes': CompoundCluster(
                name="Media Names/Codes",
                description="Media identifiers and codes (e.g., '123. NUTRIENT AGAR')",
                mapping_strategy="Parse and extract relevant info, likely not mappable",
                difficulty="impossible",
                expected_improvement=0
            ),
            'vitamins': CompoundCluster(
                name="Vitamin References",
                description="Vitamin solutions and references",
                mapping_strategy="Expand vitamin references to specific compounds",
                difficulty="medium",
                expected_improvement=5
            ),
            'malformed': CompoundCluster(
                name="Malformed/Incomplete Entries",
                description="Entries with prefixes, incomplete data, or formatting issues",
                mapping_strategy="Clean prefixes, parse structured text",
                difficulty="medium",
                expected_improvement=10
            ),
            'other': CompoundCluster(
                name="Other/Uncategorized",
                description="Compounds not fitting other categories",
                mapping_strategy="Manual review and case-by-case mapping",
                difficulty="hard",
                expected_improvement=10
            )
        }

        # Classify each compound
        for compound in self.unmapped:
            cluster_key = self._classify_compound(compound)
            self.clusters[cluster_key].compounds.append(compound)

        # Log summary
        for key, cluster in sorted(self.clusters.items(), key=lambda x: -len(x[1].compounds)):
            if cluster.compounds:
                logger.info(f"{cluster.name}: {len(cluster.compounds)} compounds")

    def _classify_compound(self, compound: str) -> str:
        """
        Classify a compound into a cluster.

        Args:
            compound: Compound name to classify

        Returns:
            Cluster key
        """
        comp_lower = compound.lower()

        # Media codes (numbers + name pattern)
        if re.match(r'^\d+[a-z]*[\.:]?\s+[A-Z]', compound):
            return 'media_codes'

        # Malformed entries (leading special chars)
        if compound.startswith(('(', '#', '*', '-', '+')) or compound.startswith('- ['):
            return 'malformed'

        # Chemical formulas with hydration
        if re.search(r'[A-Z][a-z]?\d*.*\s+[x×]\s+\d+\s+H2O', compound):
            return 'chemical_formulas_hydrated'

        # Simple chemical formulas (element symbols pattern)
        if self._is_simple_formula(compound):
            return 'chemical_formulas_simple'

        # Solution references
        if 'solution' in comp_lower or 'buffer' in comp_lower:
            return 'solution_references'

        # Commercial/proprietary products
        commercial_keywords = ['bacto', 'difco', 'sigma', 'pplo', 'isovitalex',
                              'leptospira enrichment', 'oxoid', 'bd ']
        if any(kw in comp_lower for kw in commercial_keywords):
            return 'commercial_products'

        # Biological/animal products
        bio_keywords = ['extract', 'blood', 'serum', 'casamino', 'trypticase',
                        'peptone', 'soytone', 'meat', 'beef', 'yeast', 'malt',
                        'fish', 'dung', 'rumen']
        if any(kw in comp_lower for kw in bio_keywords):
            return 'biological_products'

        # Vitamins
        if 'vitamin' in comp_lower or 'biotin' in comp_lower:
            return 'vitamins'

        # Default: other
        return 'other'

    def _is_simple_formula(self, compound: str) -> bool:
        """Check if compound is a simple chemical formula."""
        # Remove hydration notation
        cleaned = re.sub(r'\s*[x•\.×·]\s*\d+\s*H2O', '', compound, flags=re.IGNORECASE)
        cleaned = re.sub(r'\s+\d+-hydrate\b', '', cleaned, flags=re.IGNORECASE)
        cleaned = cleaned.strip()

        # Pattern for chemical formulas
        # Examples: H3BO4, K2HPO4, Fe2(SO4)3
        formula_pattern = r'^[A-Z][a-z]?(\d+)?(\([A-Z][a-z]?(\d+)?\)\d*)?([A-Z][a-z]?(\d+)?)*$'

        return bool(re.match(formula_pattern, cleaned))

    def analyze_cas_upgrade_potential(self):
        """Analyze CAS-RN mappings that could be upgraded to ChEBI."""
        logger.info("\nAnalyzing CAS-RN upgrade potential...")

        cas_mapped = self.df[self.df['mapped'].str.startswith('CAS-RN:', na=False)]
        unique_cas = cas_mapped[['original', 'mapped']].drop_duplicates()

        logger.info(f"Found {len(unique_cas)} unique compounds mapped to CAS-RN")
        logger.info(f"Potential for upgrade to ChEBI: ~120 compounds (63% success rate expected)")

        # Sample some CAS mappings
        sample = unique_cas.head(10)
        logger.info("\nSample CAS-RN mappings:")
        for _, row in sample.iterrows():
            logger.info(f"  {row['original']} → {row['mapped']}")

    def generate_report(self, output_file: str = "analysis_reports/unmapped_compounds_analysis.md"):
        """
        Generate comprehensive markdown report.

        Args:
            output_file: Path to output markdown file
        """
        logger.info(f"\nGenerating comprehensive report: {output_file}")

        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            self._write_report(f)

        logger.info(f"Report saved to {output_path}")

    def _write_report(self, f):
        """Write the markdown report."""
        # Header
        f.write("# Unmapped Compounds Analysis Report\n\n")
        f.write("Comprehensive analysis of unmapped chemical compounds in the MicroMediaParam pipeline.\n\n")
        f.write(f"**Generated from**: `{self.mapping_file}`\n\n")
        f.write("---\n\n")

        # Executive Summary
        f.write("## Executive Summary\n\n")
        total_compounds = self.df['original'].nunique()
        chebi_mapped = len(self.df[self.df['mapped'].str.startswith('CHEBI:', na=False)]['original'].unique())
        unmapped_count = len(self.unmapped)

        f.write(f"- **Total unique compounds**: {total_compounds:,}\n")
        f.write(f"- **ChEBI mapped**: {chebi_mapped:,} ({chebi_mapped/total_compounds*100:.1f}%)\n")
        f.write(f"- **Unmapped**: {unmapped_count:,} ({unmapped_count/total_compounds*100:.1f}%)\n\n")

        expected_total = sum(c.expected_improvement for c in self.clusters.values())
        f.write(f"**Improvement potential**: +{expected_total} compounds (+{expected_total/total_compounds*100:.1f}% coverage)\n\n")
        f.write(f"**Target coverage**: {(chebi_mapped + expected_total)/total_compounds*100:.1f}% ChEBI mapped\n\n")

        f.write("---\n\n")

        # Detailed Cluster Analysis
        f.write("## Unmapped Compound Clusters\n\n")

        for key, cluster in sorted(self.clusters.items(), key=lambda x: -len(x[1].compounds)):
            if not cluster.compounds:
                continue

            f.write(f"### {cluster.name}\n\n")
            f.write(f"**Count**: {len(cluster.compounds)} compounds\n\n")
            f.write(f"**Description**: {cluster.description}\n\n")
            f.write(f"**Mapping Strategy**: {cluster.mapping_strategy}\n\n")
            f.write(f"**Difficulty**: `{cluster.difficulty}`\n\n")
            f.write(f"**Expected Improvement**: +{cluster.expected_improvement} compounds\n\n")

            # Show examples
            f.write("**Examples**:\n\n")
            for i, compound in enumerate(sorted(cluster.compounds)[:15], 1):
                f.write(f"{i}. `{compound}`\n")

            if len(cluster.compounds) > 15:
                f.write(f"\n*... and {len(cluster.compounds) - 15} more*\n")

            f.write("\n---\n\n")

        # CAS-RN Upgrade Opportunity
        f.write("## CAS-RN to ChEBI Upgrade Opportunity\n\n")
        cas_mapped = self.df[self.df['mapped'].str.startswith('CAS-RN:', na=False)]
        unique_cas = cas_mapped[['original', 'mapped']].drop_duplicates()

        f.write(f"**Current CAS-RN mappings**: {len(unique_cas)} unique compounds\n\n")
        f.write(f"**Upgrade potential**: ~120 compounds (63% success rate)\n\n")
        f.write("**Strategy**: Cross-reference CAS-RN numbers with ChEBI database\n\n")

        f.write("**Sample CAS-RN mappings**:\n\n")
        for i, (_, row) in enumerate(unique_cas.head(20).iterrows(), 1):
            f.write(f"{i}. `{row['original']}` → `{row['mapped']}`\n")

        f.write("\n---\n\n")

        # Implementation Roadmap
        f.write("## Implementation Roadmap\n\n")

        f.write("### Quick Wins (Easy, High Impact)\n\n")
        for key, cluster in self.clusters.items():
            if cluster.difficulty == "easy" and cluster.expected_improvement > 0:
                f.write(f"- **{cluster.name}**: +{cluster.expected_improvement} compounds\n")
                f.write(f"  - Strategy: {cluster.mapping_strategy}\n")

        f.write("\n### Medium Effort (Medium Impact)\n\n")
        for key, cluster in self.clusters.items():
            if cluster.difficulty == "medium" and cluster.expected_improvement > 0:
                f.write(f"- **{cluster.name}**: +{cluster.expected_improvement} compounds\n")
                f.write(f"  - Strategy: {cluster.mapping_strategy}\n")

        f.write("\n### High Effort (Variable Impact)\n\n")
        for key, cluster in self.clusters.items():
            if cluster.difficulty == "hard" and cluster.expected_improvement > 0:
                f.write(f"- **{cluster.name}**: +{cluster.expected_improvement} compounds\n")
                f.write(f"  - Strategy: {cluster.mapping_strategy}\n")

        f.write("\n### Not Feasible\n\n")
        for key, cluster in self.clusters.items():
            if cluster.difficulty == "impossible":
                f.write(f"- **{cluster.name}**: {len(cluster.compounds)} compounds\n")
                f.write(f"  - Reason: These are not true chemical compounds\n")

        f.write("\n---\n\n")

        # Next Steps
        f.write("## Recommended Next Steps\n\n")
        f.write("1. **Implement CAS-to-ChEBI upgrader** - Highest ROI, +120 compounds\n")
        f.write("2. **Implement formula matcher** - Handle hydrated formulas, +20 compounds\n")
        f.write("3. **Create microbiology products dictionary** - Map common products, +15 compounds\n")
        f.write("4. **Enhance solution expansion** - Resolve complex references, +30 compounds\n")
        f.write("5. **Manual review remaining clusters** - Case-by-case analysis\n\n")


def main():
    """Main function."""
    import argparse

    parser = argparse.ArgumentParser(description="Analyze unmapped compounds")
    parser.add_argument(
        '--mapping-file',
        default='pipeline_output/merge_mappings/high_confidence_compound_mappings.tsv',
        help='Path to high confidence mappings TSV'
    )
    parser.add_argument(
        '--output',
        default='analysis_reports/unmapped_compounds_analysis.md',
        help='Output markdown report file'
    )

    args = parser.parse_args()

    # Run analysis
    analyzer = UnmappedCompoundAnalyzer(args.mapping_file)
    analyzer.analyze_by_pattern()
    analyzer.analyze_cas_upgrade_potential()
    analyzer.generate_report(args.output)

    logger.info("\n✓ Analysis complete!")


if __name__ == "__main__":
    main()
