#!/usr/bin/env python3
"""
Compound Name Normalization Utilities

This module provides utilities for normalizing chemical compound names
to improve matching accuracy across different naming conventions.

Consolidates normalization logic previously duplicated across multiple
mapping scripts.
"""

import re
import pandas as pd
from typing import Optional, Tuple


class CompoundNameNormalizer:
    """
    Normalizes chemical compound names for better matching.

    Handles:
    - Stereochemistry prefixes (D-/L-/DL-/+/-)
    - Hydration notation (x N H2O, ·N H2O, .N H2O, N-hydrate)
    - Concentration prefixes (%, M, mg, g)
    - Parenthetical information
    - Whitespace and punctuation
    """

    # Hydration patterns with their regex patterns
    HYDRATION_PATTERNS = [
        (r'\s*[x×]\s*(\d+)\s*H2O', r'·\1H2O'),  # x N H2O → ·NH2O
        (r'\s*[•·]\s*(\d+)\s*H2O', r'·\1H2O'),  # • N H2O → ·NH2O
        (r'\s*\.\s*(\d+)\s*H2O', r'·\1H2O'),    # . N H2O → ·NH2O
        (r'\s+(\d+)-hydrate', r'·\1H2O'),       # N-hydrate → ·NH2O
    ]

    def __init__(self):
        """Initialize the normalizer."""
        pass

    def normalize(self, name: str,
                  remove_hydration: bool = True,
                  remove_stereochemistry: bool = True,
                  remove_concentrations: bool = True,
                  remove_parenthetical: bool = True) -> str:
        """
        Normalize a chemical compound name.

        Args:
            name: Chemical compound name to normalize
            remove_hydration: Remove hydration notation (default: True)
            remove_stereochemistry: Remove D-/L-/DL- prefixes (default: True)
            remove_concentrations: Remove concentration prefixes (default: True)
            remove_parenthetical: Remove parenthetical info (default: True)

        Returns:
            Normalized compound name (lowercase, trimmed)
        """
        if pd.isna(name) or name == "" or not isinstance(name, str):
            return ""

        # Convert to lowercase
        normalized = name.lower().strip()

        # Remove concentration/quantity prefixes if requested
        if remove_concentrations:
            # Matches: percentages (0.2%), molarities (1 M), weights (100 mg, 1 g), or "G " prefix
            normalized = re.sub(
                r'^(?:\d+\.?\d*\s*%\s+|\d+\.?\d*\s+[mM]\s+|\d+\.?\d*\s*[Mm]?[Gg]\s+|[Gg]\s+)',
                '',
                normalized
            )

        # Remove stereochemistry prefixes if requested
        if remove_stereochemistry:
            # Combined prefix removal (D-/L-/DL- and +/-)
            normalized = re.sub(r'^(?:[dl]|dl|\+|-)-?\s*', '', normalized)

        # Remove or normalize hydration notation
        if remove_hydration:
            # Remove hydration notation entirely
            normalized = re.sub(r'\s*[x•\.×·]\s*\d+\s*h2o', '', normalized)
            normalized = re.sub(r'\s+\d+-hydrate\b', '', normalized)

        # Remove parenthetical information if requested
        if remove_parenthetical:
            normalized = re.sub(r'\([^)]*\)', '', normalized)

        # Normalize whitespace and punctuation
        normalized = re.sub(r'[,;\s]+', ' ', normalized).strip()

        return normalized

    def standardize_hydrate_notation(self, name: str) -> str:
        """
        Standardize hydration notation to ·NH2O format.

        Converts various formats:
        - "CoCl2 x 6 H2O" → "CoCl2·6H2O"
        - "MgSO4 6-hydrate" → "MgSO4·6H2O"
        - "Na2SO4.10H2O" → "Na2SO4·10H2O"

        Args:
            name: Chemical compound name

        Returns:
            Compound name with standardized hydration notation
        """
        if not name or not isinstance(name, str):
            return name

        result = name

        # Apply each hydration pattern
        for pattern, replacement in self.HYDRATION_PATTERNS:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

        return result

    def extract_hydrate_info(self, name: str) -> Tuple[str, Optional[int]]:
        """
        Extract base compound and hydration number.

        Args:
            name: Chemical compound name

        Returns:
            Tuple of (base_compound, water_molecules)
            water_molecules is None if no hydration found

        Examples:
            >>> normalizer.extract_hydrate_info("CoCl2 x 6 H2O")
            ("CoCl2", 6)
            >>> normalizer.extract_hydrate_info("MgSO4 7-hydrate")
            ("MgSO4", 7)
            >>> normalizer.extract_hydrate_info("NaCl")
            ("NaCl", None)
        """
        if not name or not isinstance(name, str):
            return (name, None)

        # Try each hydration pattern
        patterns = [
            (r'(.+?)\s*[x×]\s*(\d+)\s*H2O', 'x N H2O'),
            (r'(.+?)\s*[•·]\s*(\d+)\s*H2O', '· N H2O'),
            (r'(.+?)\s*\.\s*(\d+)\s*H2O', '. N H2O'),
            (r'(.+?)\s+(\d+)-hydrate', 'N-hydrate'),
        ]

        for pattern, _ in patterns:
            match = re.search(pattern, name, re.IGNORECASE)
            if match:
                base_compound = match.group(1).strip()
                water_count = int(match.group(2))
                return (base_compound, water_count)

        # No hydration found
        return (name, None)

    def is_chemical_formula(self, name: str) -> bool:
        """
        Detect if a string looks like a chemical formula.

        Looks for patterns like:
        - NaCl
        - CaCl2
        - H2SO4
        - Fe(NO3)3
        - CoCl2 x 6 H2O

        Args:
            name: String to check

        Returns:
            True if it looks like a chemical formula
        """
        if not name or not isinstance(name, str):
            return False

        # Remove hydration notation for formula detection
        cleaned = re.sub(r'\s*[x•\.×·]\s*\d+\s*H2O', '', name, flags=re.IGNORECASE)
        cleaned = re.sub(r'\s+\d+-hydrate\b', '', cleaned, flags=re.IGNORECASE)
        cleaned = cleaned.strip()

        # Pattern for chemical formulas:
        # - Starts with uppercase letter
        # - Contains element symbols (1-2 letters)
        # - May contain numbers, parentheses, brackets
        # - May contain charges (+/-/2+/2-/etc)
        formula_pattern = r'^[A-Z][a-z]?(\d+)?(\([A-Z][a-z]?(\d+)?\))?([A-Z][a-z]?(\d+)?)*(\d*[+-])?$'

        return bool(re.match(formula_pattern, cleaned))

    def clean_malformed_entry(self, name: str) -> str:
        """
        Clean malformed entries with prefixes/suffixes.

        Handles:
        - Leading numbers: "(1) CaCl2" → "CaCl2"
        - Hash marks: "# Vitamin solution" → "Vitamin solution"
        - Asterisks: "*Tryptone" → "Tryptone"
        - Plus/minus: "+ 0.02% Yeast extract" → "Yeast extract"

        Args:
            name: Potentially malformed compound name

        Returns:
            Cleaned compound name
        """
        if not name or not isinstance(name, str):
            return name

        cleaned = name.strip()

        # Remove leading special characters and numbers in parentheses
        cleaned = re.sub(r'^\([0-9]+\)\s*', '', cleaned)
        cleaned = re.sub(r'^[#\*\+\-]\s*', '', cleaned)

        # Remove trailing special characters
        cleaned = re.sub(r'\s*[\*\+\-]$', '', cleaned)

        return cleaned.strip()


# Singleton instance for convenient access
_normalizer = CompoundNameNormalizer()

# Convenience functions
def normalize_name(name: str, **kwargs) -> str:
    """Normalize a chemical compound name (convenience function)."""
    return _normalizer.normalize(name, **kwargs)

def extract_hydrate_info(name: str) -> Tuple[str, Optional[int]]:
    """Extract base compound and hydration info (convenience function)."""
    return _normalizer.extract_hydrate_info(name)

def is_chemical_formula(name: str) -> bool:
    """Check if string looks like a chemical formula (convenience function)."""
    return _normalizer.is_chemical_formula(name)

def clean_malformed(name: str) -> str:
    """Clean malformed entry (convenience function)."""
    return _normalizer.clean_malformed_entry(name)
