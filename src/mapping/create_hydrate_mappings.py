#!/usr/bin/env python3
"""
Create Hydrate-Specific Compound Mappings.

Generates compound_mappings_strict_final_hydrate.tsv with specific hydrated ChEBI IDs.

The base file (compound_mappings_strict_final.tsv) maps all hydrates to their
parent/anhydrous ChEBI ID (degenerate mapping). This script creates a variant
that includes specific hydrated ChEBI IDs for each hydration state.

New columns added:
- hydrated_chebi_id: Specific ChEBI ID for hydrated form (e.g., CHEBI:86158)
- hydrated_chebi_label: Label (e.g., "calcium chloride dihydrate")
- hydrate_mapping_source: How the hydrate ID was found (formula_match, name_match, etc.)

Usage:
    python -m src.mapping.create_hydrate_mappings \\
        --input pipeline_output/merge_mappings/compound_mappings_strict_final.tsv \\
        --chebi-formulas data/curated/chebi_formulas.tsv \\
        --output pipeline_output/merge_mappings/compound_mappings_strict_final_hydrate.tsv
"""

import argparse
import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Hydrate name patterns for label matching
HYDRATE_NUMBER_WORDS = {
    1: ['mono', 'monohydrate'],
    2: ['di', 'dihydrate'],
    3: ['tri', 'trihydrate'],
    4: ['tetra', 'tetrahydrate'],
    5: ['penta', 'pentahydrate'],
    6: ['hexa', 'hexahydrate'],
    7: ['hepta', 'heptahydrate'],
    8: ['octa', 'octahydrate'],
    9: ['nona', 'nonahydrate'],
    10: ['deca', 'decahydrate'],
    11: ['undeca', 'undecahydrate'],
    12: ['dodeca', 'dodecahydrate'],
}


def parse_hydration_from_formula(formula: str) -> Tuple[Optional[str], Optional[int]]:
    """
    Parse hydration info from ChEBI formula notation.

    Examples:
        "Ca.2Cl.2H2O" -> ("Ca.2Cl", 2)
        "Cu.5H2O.O4S" -> ("Cu.O4S", 5)
        "C10H14N2O4.H2O" -> ("C10H14N2O4", 1)

    Args:
        formula: ChEBI formula string

    Returns:
        Tuple of (base_formula, water_count) or (None, None) if no hydration
    """
    if not formula or not isinstance(formula, str):
        return None, None

    # Pattern for hydration in formula: (N)H2O or H2O
    # Match patterns like .2H2O, .5H2O, .H2O, 3H2O, etc.
    hydrate_patterns = [
        r'\.(\d+)H2O',      # .2H2O, .5H2O
        r'\.H2O',           # .H2O (single hydrate)
        r'(\d+)H2O',        # 2H2O, 5H2O (at component boundary)
    ]

    water_count = None
    base_formula = formula

    # Try each pattern
    for pattern in hydrate_patterns:
        match = re.search(pattern, formula)
        if match:
            if match.groups() and match.group(1):
                water_count = int(match.group(1))
            else:
                water_count = 1
            # Remove the hydrate part from formula
            base_formula = re.sub(r'\.?\d*H2O', '', formula).strip('.')
            break

    return base_formula, water_count


def parse_hydration_from_label(label: str) -> Tuple[Optional[str], Optional[int]]:
    """
    Parse hydration info from ChEBI label.

    Examples:
        "calcium chloride dihydrate" -> ("calcium chloride", 2)
        "copper(II) sulfate pentahydrate" -> ("copper(II) sulfate", 5)

    Args:
        label: ChEBI label string

    Returns:
        Tuple of (base_label, water_count) or (None, None) if no hydration
    """
    if not label or not isinstance(label, str):
        return None, None

    label_lower = label.lower().strip()

    # Check for hydrate word patterns
    for water_count, patterns in HYDRATE_NUMBER_WORDS.items():
        for pattern in patterns:
            if label_lower.endswith(pattern):
                base_label = label[:-(len(pattern))].strip()
                return base_label, water_count

    # Check for "N-hydrate" pattern
    match = re.search(r'(\d+)-?hydrate$', label_lower)
    if match:
        water_count = int(match.group(1))
        base_label = label[:match.start()].strip()
        return base_label, water_count

    # Check for just "hydrate" at end (assume 1)
    if label_lower.endswith('hydrate'):
        base_label = label[:-7].strip()
        return base_label, 1

    return None, None


class HydrateLookup:
    """Builds and queries hydrated ChEBI lookups."""

    def __init__(self, chebi_formulas_file: str):
        """
        Initialize with ChEBI formulas file.

        Args:
            chebi_formulas_file: Path to chebi_formulas.tsv
        """
        self.chebi_formulas_file = chebi_formulas_file

        # Lookup tables
        # Key: (base_formula_normalized, water_count) -> list of (chebi_id, label)
        self.formula_to_hydrate: Dict[Tuple[str, int], List[Tuple[str, str]]] = defaultdict(list)

        # Key: base_label_normalized -> dict of water_count -> (chebi_id, label)
        self.label_to_hydrate: Dict[str, Dict[int, Tuple[str, str]]] = defaultdict(dict)

        # All ChEBI entries for direct lookup
        # Key: chebi_id -> (label, formula)
        self.chebi_entries: Dict[str, Tuple[str, str]] = {}

        self._load_chebi_formulas()

    def _normalize_formula(self, formula: str) -> str:
        """Normalize formula for matching."""
        if not formula:
            return ''
        # Sort components alphabetically, remove dots
        parts = formula.replace('.', ' ').split()
        return ''.join(sorted(parts)).lower()

    def _normalize_label(self, label: str) -> str:
        """Normalize label for matching."""
        if not label:
            return ''
        # Lowercase, remove special chars
        return re.sub(r'[^a-z0-9]', '', label.lower())

    def _load_chebi_formulas(self):
        """Load ChEBI formulas and build lookup tables."""
        logger.info(f"Loading ChEBI formulas from {self.chebi_formulas_file}")

        df = pd.read_csv(self.chebi_formulas_file, sep='\t')

        hydrate_count = 0

        for _, row in df.iterrows():
            chebi_id = row['chebi_id']
            label = row.get('chebi_label', '')
            formula = row.get('chebi_formula', '')

            # Store all entries
            self.chebi_entries[chebi_id] = (label, formula)

            # Check if this is a hydrate by formula
            base_formula, water_count = parse_hydration_from_formula(formula)
            if water_count and base_formula:
                norm_formula = self._normalize_formula(base_formula)
                if norm_formula:
                    self.formula_to_hydrate[(norm_formula, water_count)].append(
                        (chebi_id, label)
                    )
                    hydrate_count += 1

            # Also check by label
            base_label, water_count_label = parse_hydration_from_label(label)
            if water_count_label and base_label:
                norm_label = self._normalize_label(base_label)
                if norm_label:
                    self.label_to_hydrate[norm_label][water_count_label] = (chebi_id, label)

        logger.info(f"Loaded {len(self.chebi_entries)} ChEBI entries")
        logger.info(f"Found {hydrate_count} hydrate entries by formula")
        logger.info(f"Built lookup with {len(self.formula_to_hydrate)} formula-based keys")
        logger.info(f"Built lookup with {len(self.label_to_hydrate)} label-based keys")

    def lookup_hydrate(self, base_formula: str, base_label: str,
                       water_count: int) -> Tuple[Optional[str], Optional[str], str]:
        """
        Look up specific hydrated ChEBI ID.

        Args:
            base_formula: Base compound formula (e.g., "CaCl2")
            base_label: Base compound label (e.g., "calcium chloride")
            water_count: Number of water molecules

        Returns:
            Tuple of (hydrated_chebi_id, hydrated_chebi_label, source)
        """
        if not water_count or water_count <= 0:
            return None, None, ''

        # Strategy 1: Formula-based lookup
        if base_formula:
            norm_formula = self._normalize_formula(base_formula)
            key = (norm_formula, water_count)
            if key in self.formula_to_hydrate:
                matches = self.formula_to_hydrate[key]
                if len(matches) == 1:
                    return matches[0][0], matches[0][1], 'formula_match'
                elif len(matches) > 1:
                    # Multiple matches - return first but note ambiguity
                    return matches[0][0], matches[0][1], 'formula_match_ambiguous'

        # Strategy 2: Label-based lookup
        if base_label:
            norm_label = self._normalize_label(base_label)
            if norm_label in self.label_to_hydrate:
                hydrates = self.label_to_hydrate[norm_label]
                if water_count in hydrates:
                    return hydrates[water_count][0], hydrates[water_count][1], 'label_match'

        # Strategy 3: Try common synonyms/variations
        if base_label:
            # Try without common suffixes
            for suffix in [' salt', ' acid', ' base']:
                if base_label.lower().endswith(suffix):
                    alt_label = base_label[:-len(suffix)]
                    result = self._try_label_lookup(alt_label, water_count)
                    if result[0]:
                        return result

        return None, None, 'no_match'

    def _try_label_lookup(self, label: str, water_count: int) -> Tuple[Optional[str], Optional[str], str]:
        """Try label-based lookup with variations."""
        norm_label = self._normalize_label(label)
        if norm_label in self.label_to_hydrate:
            hydrates = self.label_to_hydrate[norm_label]
            if water_count in hydrates:
                return hydrates[water_count][0], hydrates[water_count][1], 'label_variant_match'
        return None, None, ''

    def get_chebi_info(self, chebi_id: str) -> Tuple[Optional[str], Optional[str]]:
        """Get label and formula for a ChEBI ID."""
        if chebi_id in self.chebi_entries:
            return self.chebi_entries[chebi_id]
        return None, None


def create_hydrate_mappings(input_file: str, chebi_formulas_file: str,
                            output_file: str) -> Dict[str, int]:
    """
    Create hydrate-specific mapping file.

    Args:
        input_file: Input compound_mappings_strict_final.tsv
        chebi_formulas_file: ChEBI formulas TSV
        output_file: Output file path

    Returns:
        Statistics dictionary
    """
    logger.info(f"Reading input file: {input_file}")
    df = pd.read_csv(input_file, sep='\t', low_memory=False)

    logger.info(f"Loaded {len(df)} compound entries")

    # Build hydrate lookup
    lookup = HydrateLookup(chebi_formulas_file)

    # Statistics
    stats = {
        'total_entries': len(df),
        'entries_with_hydration': 0,
        'hydrates_mapped': 0,
        'hydrates_unmapped': 0,
        'formula_matches': 0,
        'label_matches': 0,
        'ambiguous_matches': 0,
    }

    # Add new columns
    df['hydrated_chebi_id'] = ''
    df['hydrated_chebi_label'] = ''
    df['hydrate_mapping_source'] = ''

    # Process each row
    for idx, row in df.iterrows():
        # Check if this compound has hydration info
        hydration_number = row.get('hydration_number', 0)

        # Try to get water count from different columns
        water_count = None
        if pd.notna(hydration_number) and hydration_number not in ['', '0', 0]:
            try:
                water_count = int(float(hydration_number))
            except (ValueError, TypeError):
                pass

        if not water_count:
            # Check water_molecules column
            water_molecules = row.get('water_molecules', '')
            if pd.notna(water_molecules) and water_molecules not in ['', '0', 0]:
                try:
                    water_count = int(float(water_molecules))
                except (ValueError, TypeError):
                    pass

        if not water_count:
            continue

        stats['entries_with_hydration'] += 1

        # Get base compound info
        base_formula = row.get('base_formula', '') or row.get('base_compound', '')
        base_label = row.get('base_chebi_label', '') or row.get('chebi_label', '')

        # Also try the current mapped compound's label
        if not base_label or pd.isna(base_label):
            mapped_id = row.get('mapped', '')
            if pd.notna(mapped_id) and str(mapped_id).startswith('CHEBI:'):
                info = lookup.get_chebi_info(str(mapped_id))
                if info[0]:
                    base_label = info[0]

        # Look up hydrated ChEBI ID
        hydrated_id, hydrated_label, source = lookup.lookup_hydrate(
            str(base_formula) if pd.notna(base_formula) else '',
            str(base_label) if pd.notna(base_label) else '',
            water_count
        )

        if hydrated_id:
            df.at[idx, 'hydrated_chebi_id'] = hydrated_id
            df.at[idx, 'hydrated_chebi_label'] = hydrated_label or ''
            df.at[idx, 'hydrate_mapping_source'] = source

            stats['hydrates_mapped'] += 1

            if 'formula' in source:
                stats['formula_matches'] += 1
            elif 'label' in source:
                stats['label_matches'] += 1

            if 'ambiguous' in source:
                stats['ambiguous_matches'] += 1
        else:
            df.at[idx, 'hydrate_mapping_source'] = 'no_match'
            stats['hydrates_unmapped'] += 1

    # Save output
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, sep='\t', index=False)

    logger.info(f"Saved hydrate mappings to {output_file}")

    # Print report
    _print_report(stats)

    return stats


def _print_report(stats: Dict[str, int]):
    """Print summary report."""
    print("\n" + "=" * 70)
    print("HYDRATE MAPPING REPORT")
    print("=" * 70)
    print(f"\nTotal compound entries:           {stats['total_entries']:,}")
    print(f"Entries with hydration info:      {stats['entries_with_hydration']:,}")
    print(f"\nHydrate Mapping Results:")
    print(f"  ✓ Successfully mapped:          {stats['hydrates_mapped']:,}")
    print(f"    - Formula-based matches:      {stats['formula_matches']:,}")
    print(f"    - Label-based matches:        {stats['label_matches']:,}")
    print(f"    - Ambiguous matches:          {stats['ambiguous_matches']:,}")
    print(f"  ✗ Could not find hydrate ID:    {stats['hydrates_unmapped']:,}")

    if stats['entries_with_hydration'] > 0:
        success_rate = stats['hydrates_mapped'] / stats['entries_with_hydration'] * 100
        print(f"\nHydrate mapping success rate:     {success_rate:.1f}%")

    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Create hydrate-specific compound mapping file",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--input', '-i',
        required=True,
        help='Input compound_mappings_strict_final.tsv file'
    )
    parser.add_argument(
        '--chebi-formulas', '-c',
        required=True,
        help='ChEBI formulas TSV file (data/curated/chebi_formulas.tsv)'
    )
    parser.add_argument(
        '--output', '-o',
        required=True,
        help='Output file path for hydrate mappings'
    )

    args = parser.parse_args()

    create_hydrate_mappings(args.input, args.chebi_formulas, args.output)


if __name__ == '__main__':
    main()
