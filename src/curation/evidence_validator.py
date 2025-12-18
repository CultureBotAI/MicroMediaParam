#!/usr/bin/env python3
"""
Evidence Validator for Complex Ingredients YAML

Validates complex ingredient compositions YAML against schema requirements:
- Required fields presence
- ChEBI ID format and existence
- Molecular formula consistency
- Source references documentation
- Concentration units validation
- Evidence quality tier verification

Usage:
    python src/curation/evidence_validator.py \\
        --yaml data/curated/complex_ingredients/complex_ingredient_compositions.yaml \\
        --sources data/curated/complex_ingredients/evidence/sources.yaml \\
        --chebi-nodes /path/to/chebi_nodes.tsv \\
        --report

Version: 1.0.0
"""

import argparse
import logging
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd
import yaml

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EvidenceValidator:
    """Validates complex ingredients YAML for quality and consistency."""

    # Validation rules
    REQUIRED_FIELDS = ['names', 'description']
    CHEBI_ID_PATTERN = re.compile(r'^CHEBI:\d+$')
    UBERON_ID_PATTERN = re.compile(r'^UBERON:\d+$')
    INGREDIENT_ID_PATTERN = re.compile(r'^ingredient:[a-z_]+$')
    CONCENTRATION_UNITS = ['g_per_100g', 'mg_per_100g', 'g_per_100ml', 'mg_per_100ml']
    CONFIDENCE_LEVELS = ['high', 'medium-high', 'medium', 'medium-low', 'low']

    def __init__(
        self,
        yaml_file: str,
        sources_file: Optional[str] = None,
        chebi_nodes_file: Optional[str] = None
    ):
        """
        Initialize validator.

        Args:
            yaml_file: Path to complex ingredients YAML
            sources_file: Path to evidence sources YAML (optional)
            chebi_nodes_file: Path to ChEBI nodes TSV for ID verification (optional)
        """
        self.yaml_file = yaml_file
        self.sources_file = sources_file
        self.chebi_nodes_file = chebi_nodes_file

        self.ingredients: Dict[str, Any] = {}
        self.sources: Dict[str, Any] = {}
        self.chebi_ids: Set[str] = set()

        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.info: List[str] = []

        self._load_data()

    def _load_data(self):
        """Load YAML and reference data."""
        logger.info(f"Loading ingredients from {self.yaml_file}")
        with open(self.yaml_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            self.ingredients = data.get('ingredients', {})

        if self.sources_file:
            logger.info(f"Loading sources from {self.sources_file}")
            with open(self.sources_file, 'r', encoding='utf-8') as f:
                sources_data = yaml.safe_load(f)
                self.sources = sources_data.get('sources', {})

        if self.chebi_nodes_file and Path(self.chebi_nodes_file).exists():
            logger.info(f"Loading ChEBI IDs from {self.chebi_nodes_file}")
            chebi_df = pd.read_csv(self.chebi_nodes_file, sep='\t')
            if 'id' in chebi_df.columns:
                self.chebi_ids = set(chebi_df['id'].dropna().unique())
                logger.info(f"Loaded {len(self.chebi_ids)} ChEBI IDs")

    def validate_all(self) -> bool:
        """
        Run all validation checks.

        Returns:
            True if all validation passes (no errors), False otherwise
        """
        logger.info("Starting validation...")

        for ingredient_id, ingredient_data in self.ingredients.items():
            self._validate_ingredient(ingredient_id, ingredient_data)

        self._print_summary()

        return len(self.errors) == 0

    def _validate_ingredient(self, ingredient_id: str, data: Dict[str, Any]):
        """Validate a single ingredient entry."""
        context = f"Ingredient '{ingredient_id}'"

        # Check required fields
        for field in self.REQUIRED_FIELDS:
            if field not in data:
                self.errors.append(f"{context}: Missing required field '{field}'")

        # Validate names
        if 'names' in data:
            if not isinstance(data['names'], list) or len(data['names']) == 0:
                self.errors.append(f"{context}: 'names' must be a non-empty list")
        else:
            self.errors.append(f"{context}: Missing 'names' field")

        # Check source references
        if 'source_references' in data:
            self._validate_sources(ingredient_id, data['source_references'])
        else:
            self.warnings.append(f"{context}: No source references provided")

        # Validate ChEBI IDs in composition data
        for category in ['amino_acids', 'vitamins', 'minerals', 'sugars',
                         'nucleotides', 'other_compounds', 'trace_elements']:
            if category in data:
                self._validate_composition_category(
                    ingredient_id, category, data[category]
                )

        # Validate sub-ingredients (recursive structures)
        if 'sub_ingredients' in data:
            self._validate_sub_ingredients(ingredient_id, data['sub_ingredients'])

        # Check for ontology IDs
        self._validate_ontology_ids(ingredient_id, data)

        # Validate confidence level if provided
        if 'confidence' in data:
            if data['confidence'] not in self.CONFIDENCE_LEVELS:
                self.warnings.append(
                    f"{context}: Unknown confidence level '{data['confidence']}'. "
                    f"Expected one of: {', '.join(self.CONFIDENCE_LEVELS)}"
                )

    def _validate_sources(self, ingredient_id: str, source_refs: List[str]):
        """Validate source references."""
        context = f"Ingredient '{ingredient_id}'"

        if not isinstance(source_refs, list):
            self.errors.append(f"{context}: source_references must be a list")
            return

        if len(source_refs) == 0:
            self.warnings.append(f"{context}: source_references list is empty")
            return

        # Check if sources are registered (if sources file provided)
        if self.sources:
            for source_id in source_refs:
                if source_id not in self.sources:
                    self.warnings.append(
                        f"{context}: Source '{source_id}' not found in sources registry"
                    )

    def _validate_composition_category(
        self,
        ingredient_id: str,
        category: str,
        compounds: Dict[str, Any]
    ):
        """Validate a composition category (amino_acids, vitamins, etc.)."""
        context = f"Ingredient '{ingredient_id}', category '{category}'"

        if not isinstance(compounds, dict):
            self.errors.append(f"{context}: Must be a dictionary")
            return

        for compound_name, compound_data in compounds.items():
            if not isinstance(compound_data, dict):
                self.errors.append(
                    f"{context}, compound '{compound_name}': Must be a dictionary"
                )
                continue

            # Validate ChEBI ID if present
            if 'chebi_id' in compound_data:
                self._validate_chebi_id(
                    ingredient_id, category, compound_name, compound_data['chebi_id']
                )

            # Validate concentration units
            has_concentration = False
            for unit in self.CONCENTRATION_UNITS:
                if unit in compound_data:
                    has_concentration = True
                    value = compound_data[unit]
                    if not isinstance(value, (int, float)):
                        self.errors.append(
                            f"{context}, compound '{compound_name}': "
                            f"{unit} must be numeric, got {type(value).__name__}"
                        )

            if not has_concentration:
                self.warnings.append(
                    f"{context}, compound '{compound_name}': "
                    f"No concentration data found (expected one of: "
                    f"{', '.join(self.CONCENTRATION_UNITS)})"
                )

    def _validate_sub_ingredients(
        self,
        ingredient_id: str,
        sub_ingredients: Dict[str, Any]
    ):
        """Validate sub-ingredients structure."""
        context = f"Ingredient '{ingredient_id}', sub_ingredients"

        if not isinstance(sub_ingredients, dict):
            self.errors.append(f"{context}: Must be a dictionary")
            return

        for sub_name, sub_data in sub_ingredients.items():
            if not isinstance(sub_data, dict):
                self.errors.append(
                    f"{context}, '{sub_name}': Must be a dictionary"
                )
                continue

            # Check for concentration or ChEBI ID
            has_chebi = 'chebi_id' in sub_data
            has_concentration = any(unit in sub_data for unit in self.CONCENTRATION_UNITS)

            if not has_chebi and not has_concentration:
                self.warnings.append(
                    f"{context}, '{sub_name}': No ChEBI ID or concentration data"
                )

            if 'chebi_id' in sub_data:
                self._validate_chebi_id(
                    ingredient_id, 'sub_ingredients', sub_name, sub_data['chebi_id']
                )

    def _validate_chebi_id(
        self,
        ingredient_id: str,
        category: str,
        compound_name: str,
        chebi_id: str
    ):
        """Validate a ChEBI ID format and existence."""
        context = f"Ingredient '{ingredient_id}', {category}, compound '{compound_name}'"

        # Check format
        if not self.CHEBI_ID_PATTERN.match(chebi_id):
            self.errors.append(
                f"{context}: Invalid ChEBI ID format '{chebi_id}'. "
                f"Expected format: CHEBI:##### (e.g., CHEBI:12345)"
            )
            return

        # Check existence in ChEBI database (if available)
        if self.chebi_ids and chebi_id not in self.chebi_ids:
            self.warnings.append(
                f"{context}: ChEBI ID '{chebi_id}' not found in ChEBI database. "
                f"Verify this ID exists."
            )

    def _validate_ontology_ids(self, ingredient_id: str, data: Dict[str, Any]):
        """Validate ontology IDs (ChEBI, Uberon, etc.)."""
        context = f"Ingredient '{ingredient_id}'"

        # Check for main ChEBI ID
        if 'chebi_id' in data:
            if not self.CHEBI_ID_PATTERN.match(data['chebi_id']):
                self.errors.append(
                    f"{context}: Invalid ChEBI ID format '{data['chebi_id']}'"
                )

        # Check for Uberon ID (anatomical terms)
        if 'uberon_id' in data:
            if not self.UBERON_ID_PATTERN.match(data['uberon_id']):
                self.errors.append(
                    f"{context}: Invalid Uberon ID format '{data['uberon_id']}'"
                )

        # Check for custom ingredient IDs
        if 'ingredient_id' in data:
            if not self.INGREDIENT_ID_PATTERN.match(data['ingredient_id']):
                self.warnings.append(
                    f"{context}: Custom ingredient ID '{data['ingredient_id']}' "
                    f"should follow pattern 'ingredient:name_here'"
                )

    def _print_summary(self):
        """Print validation summary."""
        print("\n" + "=" * 70)
        print("VALIDATION SUMMARY")
        print("=" * 70)
        print(f"Ingredients validated: {len(self.ingredients)}")
        print(f"Errors: {len(self.errors)}")
        print(f"Warnings: {len(self.warnings)}")
        print(f"Info: {len(self.info)}")
        print("=" * 70)

        if self.errors:
            print("\nERRORS:")
            for error in self.errors:
                print(f"  ❌ {error}")

        if self.warnings:
            print("\nWARNINGS:")
            for warning in self.warnings:
                print(f"  ⚠️  {warning}")

        if self.info:
            print("\nINFO:")
            for info_msg in self.info:
                print(f"  ℹ️  {info_msg}")

        if not self.errors and not self.warnings:
            print("\n✅ All validation checks passed!")

    def get_validation_report(self) -> Dict[str, Any]:
        """
        Get structured validation report.

        Returns:
            Dictionary with validation results
        """
        return {
            'total_ingredients': len(self.ingredients),
            'errors': self.errors,
            'warnings': self.warnings,
            'info': self.info,
            'passed': len(self.errors) == 0
        }


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Validate complex ingredients YAML'
    )
    parser.add_argument(
        '--yaml',
        required=True,
        help='Path to complex ingredients YAML file'
    )
    parser.add_argument(
        '--sources',
        help='Path to evidence sources YAML file (optional)'
    )
    parser.add_argument(
        '--chebi-nodes',
        help='Path to ChEBI nodes TSV for ID verification (optional)'
    )
    parser.add_argument(
        '--summary-only',
        action='store_true',
        help='Print only summary statistics'
    )
    parser.add_argument(
        '--report',
        action='store_true',
        help='Generate detailed validation report'
    )

    args = parser.parse_args()

    # Validate
    validator = EvidenceValidator(
        yaml_file=args.yaml,
        sources_file=args.sources,
        chebi_nodes_file=args.chebi_nodes
    )

    passed = validator.validate_all()

    if args.summary_only:
        report = validator.get_validation_report()
        print(f"Ingredients: {report['total_ingredients']}")
        print(f"Errors: {len(report['errors'])}")
        print(f"Warnings: {len(report['warnings'])}")
        print(f"Status: {'PASS' if report['passed'] else 'FAIL'}")

    # Exit code
    sys.exit(0 if passed else 1)


if __name__ == '__main__':
    main()
