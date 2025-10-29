#!/usr/bin/env python3
"""
Chemical Formula Matcher

Specialized matcher for chemical formulas, especially hydrated compounds.
Handles various hydration notations and normalizes them for ChEBI lookup.

Examples handled:
- "CoCl2 x 6 H2O" → "CoCl2" (anhydrous form for lookup)
- "MnSO4 7-hydrate" → "MnSO4"
- "Fe2(SO4)3 x n H2O" → "Fe2(SO4)3"

Strategy:
1. Extract base compound by removing hydration
2. Lookup base compound in ChEBI
3. Return mapping with hydration metadata
"""

import pandas as pd
import re
import logging
from typing import Optional, Dict, Tuple
from dataclasses import dataclass

from .compound_normalizer import CompoundNameNormalizer

logger = logging.getLogger(__name__)


@dataclass
class FormulaMatch:
    """Result of formula matching with hydration info."""
    chebi_id: str
    base_formula: str
    water_molecules: Optional[int]
    hydrate_formula: str
    confidence: str  # "high", "medium", "low"
    method: str  # "exact_base", "normalized_base", "fuzzy_formula"


class FormulaToChEBIMatcher:
    """
    Matches chemical formulas to ChEBI IDs.

    Specialized for handling hydrated compounds by:
    1. Extracting the base (anhydrous) compound
    2. Looking up base compound in ChEBI
    3. Preserving hydration information
    """

    def __init__(self, chebi_nodes_file: str):
        """
        Initialize the formula matcher.

        Args:
            chebi_nodes_file: Path to ChEBI nodes TSV file
        """
        self.chebi_nodes_file = chebi_nodes_file
        self.normalizer = CompoundNameNormalizer()

        # Load ChEBI data
        self.chebi_data = self._load_chebi_nodes()

        # Build formula lookups
        self._build_formula_lookups()

    def _load_chebi_nodes(self) -> pd.DataFrame:
        """Load ChEBI nodes file."""
        logger.info(f"Loading ChEBI nodes from {self.chebi_nodes_file}")

        try:
            df = pd.read_csv(self.chebi_nodes_file, sep='\t', low_memory=False)

            # Filter for ChEBI entities
            chebi_df = df[df['id'].str.startswith('CHEBI:', na=False)]

            logger.info(f"Loaded {len(chebi_df)} ChEBI entities")
            return chebi_df

        except Exception as e:
            logger.error(f"Error loading ChEBI nodes: {e}")
            raise

    def _build_formula_lookups(self):
        """
        Build formula-based lookup dictionaries.

        Creates multiple lookup methods:
        - formula → ChEBI ID
        - name → ChEBI ID
        - normalized_name → ChEBI ID
        """
        self.formula_to_id = {}
        self.name_to_id = {}
        self.normalized_name_to_id = {}

        for _, row in self.chebi_data.iterrows():
            chebi_id = row['id']
            name = row.get('name', '')
            formula = row.get('formula', '')  # ChEBI has 'formula' column
            synonyms = row.get('synonym', '')

            # Add formula lookup
            if pd.notna(formula) and formula.strip():
                clean_formula = self._clean_formula(formula)
                if clean_formula:
                    self.formula_to_id[clean_formula] = chebi_id

            # Add name lookups
            if pd.notna(name) and name.strip():
                self.name_to_id[name.lower().strip()] = chebi_id
                norm_name = self.normalizer.normalize(name)
                if norm_name:
                    self.normalized_name_to_id[norm_name] = chebi_id

            # Add synonym lookups
            if pd.notna(synonyms) and synonyms.strip():
                synonym_list = [s.strip() for s in synonyms.split('|') if s.strip()]
                for synonym in synonym_list:
                    self.name_to_id[synonym.lower().strip()] = chebi_id
                    norm_syn = self.normalizer.normalize(synonym)
                    if norm_syn:
                        self.normalized_name_to_id[norm_syn] = chebi_id

        logger.info(f"Built lookups: {len(self.formula_to_id)} formulas, "
                   f"{len(self.name_to_id)} names, "
                   f"{len(self.normalized_name_to_id)} normalized names")

    def _clean_formula(self, formula: str) -> str:
        """
        Clean chemical formula for matching.

        Removes charges, spaces, and normalizes notation.

        Args:
            formula: Chemical formula

        Returns:
            Cleaned formula
        """
        if not formula or not isinstance(formula, str):
            return ""

        # Remove charges (+, -, 2+, 2-, etc.)
        cleaned = re.sub(r'[+-]\d*$', '', formula)
        cleaned = re.sub(r'\d*[+-]$', '', cleaned)

        # Remove spaces
        cleaned = cleaned.replace(' ', '')

        # Normalize case (formulas are case-sensitive)
        return cleaned.strip()

    def match(self, compound_name: str) -> Optional[FormulaMatch]:
        """
        Match a compound (potentially hydrated) to ChEBI.

        Args:
            compound_name: Compound name or formula to match

        Returns:
            FormulaMatch if successful, None otherwise
        """
        if not compound_name or not isinstance(compound_name, str):
            return None

        # Extract base compound and hydration info
        base_compound, water_molecules = self.normalizer.extract_hydrate_info(compound_name)

        # Try different matching strategies
        result = self._match_base_compound(base_compound)

        if result:
            # Add hydration information
            return FormulaMatch(
                chebi_id=result[0],
                base_formula=base_compound,
                water_molecules=water_molecules,
                hydrate_formula=compound_name,
                confidence=result[1],
                method=result[2]
            )

        return None

    def _match_base_compound(self, base_compound: str) -> Optional[Tuple[str, str, str]]:
        """
        Match base (anhydrous) compound to ChEBI.

        Tries multiple strategies:
        1. Exact name match
        2. Normalized name match
        3. Formula match (if looks like a formula)

        Args:
            base_compound: Base compound name/formula

        Returns:
            Tuple of (chebi_id, confidence, method) if match found
        """
        # Strategy 1: Exact name match
        key = base_compound.lower().strip()
        if key in self.name_to_id:
            return (self.name_to_id[key], "high", "exact_name")

        # Strategy 2: Normalized name match
        normalized = self.normalizer.normalize(base_compound)
        if normalized and normalized in self.normalized_name_to_id:
            return (self.normalized_name_to_id[normalized], "high", "normalized_name")

        # Strategy 3: Formula match (if it looks like a formula)
        if self.normalizer.is_chemical_formula(base_compound):
            clean_formula = self._clean_formula(base_compound)
            if clean_formula in self.formula_to_id:
                return (self.formula_to_id[clean_formula], "medium", "formula_match")

        return None

    def batch_match(self, compounds: list) -> Dict[str, Optional[FormulaMatch]]:
        """
        Match multiple compounds in batch.

        Args:
            compounds: List of compound names

        Returns:
            Dictionary mapping compound → FormulaMatch (or None)
        """
        results = {}

        for compound in compounds:
            results[compound] = self.match(compound)

        return results

    def get_statistics(self) -> Dict[str, int]:
        """
        Get statistics about the matcher's coverage.

        Returns:
            Dictionary with statistics
        """
        return {
            'total_chebi_entries': len(self.chebi_data),
            'formulas_indexed': len(self.formula_to_id),
            'names_indexed': len(self.name_to_id),
            'normalized_names_indexed': len(self.normalized_name_to_id)
        }


def main():
    """Demo/test function."""
    import argparse

    parser = argparse.ArgumentParser(description="Formula matcher for hydrated compounds")
    parser.add_argument(
        '--chebi-file',
        required=True,
        help='Path to ChEBI nodes TSV file'
    )
    parser.add_argument(
        '--test-compounds',
        nargs='+',
        default=[
            "CoCl2 x 6 H2O",
            "MnSO4 7-hydrate",
            "Fe2(SO4)3 x n H2O",
            "NaCl",
            "H3BO4"
        ],
        help='Test compounds to match'
    )

    args = parser.parse_args()

    # Initialize matcher
    matcher = FormulaToChEBIMatcher(args.chebi_file)

    # Show statistics
    stats = matcher.get_statistics()
    print("\n=== Formula Matcher Statistics ===")
    for key, value in stats.items():
        print(f"{key}: {value:,}")

    # Test matching
    print("\n=== Test Matching ===")
    for compound in args.test_compounds:
        result = matcher.match(compound)
        if result:
            print(f"\n✓ {compound}")
            print(f"  ChEBI ID: {result.chebi_id}")
            print(f"  Base: {result.base_formula}")
            if result.water_molecules:
                print(f"  Hydration: {result.water_molecules} H2O")
            print(f"  Confidence: {result.confidence}")
            print(f"  Method: {result.method}")
        else:
            print(f"\n✗ {compound} - No match found")


if __name__ == "__main__":
    main()
