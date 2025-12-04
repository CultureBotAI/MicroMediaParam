#!/usr/bin/env python3
"""
Enhanced Hydrate Mapper

Maps hydrated compounds by:
1. Stripping hydrate suffixes (x N H2O, pentahydrate, etc.)
2. Looking up base compound in ChEBI and PubChem
3. Returning mapping for the base compound

Handles patterns like:
- "FeSO4 x 7 H2O" → FeSO4
- "Sodium thiosulfate pentahydrate" → Sodium thiosulfate
- "MgSO4 heptahydrate" → MgSO4
- "L-Cysteine HCl x H2O" → L-Cysteine HCl

Usage:
    python -m src.mapping.enhanced_hydrate_mapper \
        --input upstream_ingredients.tsv \
        --output upstream_ingredients_hydrate_enhanced.tsv \
        --chebi-file chebi_nodes.tsv \
        --pubchem-cache pubchem_cache.tsv
"""

import argparse
import logging
import re
from pathlib import Path
from typing import Optional, Tuple, Dict

import pandas as pd

from .compound_normalizer import (
    convert_formula_to_name,
    normalize_hcl_salt,
    normalize_for_mapping,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Word-based hydrate numbers
HYDRATE_WORDS = {
    'mono': 1, 'monohydrate': 1,
    'di': 2, 'dihydrate': 2,
    'tri': 3, 'trihydrate': 3,
    'tetra': 4, 'tetrahydrate': 4,
    'penta': 5, 'pentahydrate': 5,
    'hexa': 6, 'hexahydrate': 6,
    'hepta': 7, 'heptahydrate': 7,
    'octa': 8, 'octahydrate': 8,
    'nona': 9, 'nonahydrate': 9,
    'deca': 10, 'decahydrate': 10,
    'undeca': 11, 'undecahydrate': 11,
    'dodeca': 12, 'dodecahydrate': 12,
}


def extract_hydrate_enhanced(name: str) -> Tuple[str, Optional[int], str]:
    """
    Extract base compound from hydrated compound name.

    Args:
        name: Compound name (potentially hydrated)

    Returns:
        Tuple of (base_compound, water_count, pattern_matched)
    """
    if not name or not isinstance(name, str):
        return (name, None, '')

    original = name

    # Pattern 1: "x N H2O" notation
    match = re.search(r'(.+?)\s*[x×]\s*(\d+)\s*H2O\s*$', name, re.IGNORECASE)
    if match:
        return (match.group(1).strip(), int(match.group(2)), 'x N H2O')

    # Pattern 2: "x n H2O" (variable/unknown)
    match = re.search(r'(.+?)\s*[x×]\s*n\s*H2O\s*$', name, re.IGNORECASE)
    if match:
        return (match.group(1).strip(), None, 'x n H2O')

    # Pattern 3: "x H2O" (single hydrate, no number)
    match = re.search(r'(.+?)\s*[x×]\s*H2O\s*$', name, re.IGNORECASE)
    if match:
        return (match.group(1).strip(), 1, 'x H2O')

    # Pattern 4: "· N H2O" notation
    match = re.search(r'(.+?)\s*[•·]\s*(\d+)\s*H2O\s*$', name, re.IGNORECASE)
    if match:
        return (match.group(1).strip(), int(match.group(2)), '· N H2O')

    # Pattern 5: Word-based hydrates (pentahydrate, heptahydrate, etc.)
    for word, count in HYDRATE_WORDS.items():
        # Match at end of string with optional word boundary
        pattern = rf'(.+?)\s+{word}\s*$'
        match = re.search(pattern, name, re.IGNORECASE)
        if match:
            return (match.group(1).strip(), count, f'{word}')

    # Pattern 6: "N-hydrate" notation
    match = re.search(r'(.+?)\s+(\d+)-hydrate\s*$', name, re.IGNORECASE)
    if match:
        return (match.group(1).strip(), int(match.group(2)), 'N-hydrate')

    # Pattern 7: Just "hydrate" at the end
    match = re.search(r'(.+?)\s+hydrate\s*$', name, re.IGNORECASE)
    if match:
        return (match.group(1).strip(), None, 'hydrate')

    # No hydrate pattern found
    return (name, None, '')


class EnhancedHydrateMapper:
    """Maps hydrated compounds by looking up base compound."""

    def __init__(self, chebi_file: str, pubchem_cache: Optional[str] = None):
        """
        Initialize mapper with ChEBI data and optional PubChem cache.

        Args:
            chebi_file: Path to ChEBI nodes TSV
            pubchem_cache: Optional path to PubChem name cache TSV
        """
        self.chebi_lookup = self._load_chebi(chebi_file)
        self.pubchem_cache = self._load_pubchem_cache(pubchem_cache) if pubchem_cache else {}

    def _load_chebi(self, chebi_file: str) -> Dict[str, str]:
        """Load ChEBI name → ID lookup."""
        logger.info(f"Loading ChEBI from {chebi_file}")

        df = pd.read_csv(chebi_file, sep='\t', low_memory=False)
        chebi_df = df[df['id'].str.startswith('CHEBI:', na=False)]

        lookup = {}
        for _, row in chebi_df.iterrows():
            chebi_id = row['id']
            name = row.get('name', '')

            if pd.notna(name) and name.strip():
                # Add lowercase name
                lookup[name.lower().strip()] = chebi_id

                # Add common normalizations
                normalized = self._normalize_name(name)
                if normalized:
                    lookup[normalized] = chebi_id

            # Add synonyms
            synonyms = row.get('synonym', '')
            if pd.notna(synonyms) and synonyms.strip():
                for syn in synonyms.split('|'):
                    syn = syn.strip()
                    if syn:
                        lookup[syn.lower()] = chebi_id
                        normalized = self._normalize_name(syn)
                        if normalized:
                            lookup[normalized] = chebi_id

        logger.info(f"Loaded {len(lookup)} ChEBI name entries")
        return lookup

    def _load_pubchem_cache(self, cache_file: str) -> Dict[str, str]:
        """Load PubChem name cache."""
        if not Path(cache_file).exists():
            return {}

        logger.info(f"Loading PubChem cache from {cache_file}")
        df = pd.read_csv(cache_file, sep='\t')

        cache = {}
        for _, row in df.iterrows():
            name = row.get('query_name', '')
            cid = row.get('pubchem_cid', '')
            if pd.notna(name) and pd.notna(cid) and str(cid).strip():
                cid_str = str(cid).strip()
                # Handle both raw CID and "PubChem:CID" format
                if cid_str.startswith('PubChem:'):
                    cache[name.lower().strip()] = cid_str
                else:
                    try:
                        cache[name.lower().strip()] = f"PubChem:{int(float(cid_str))}"
                    except ValueError:
                        continue

        logger.info(f"Loaded {len(cache)} PubChem cache entries")
        return cache

    def _normalize_name(self, name: str) -> str:
        """Normalize compound name for matching."""
        if not name:
            return ''

        # Lowercase
        result = name.lower().strip()

        # Remove parentheses variants
        result = re.sub(r'\([IViv]+\)', '', result)  # Roman numerals
        result = re.sub(r'\(\d+[+-]?\)', '', result)  # Charges

        # Normalize spaces
        result = ' '.join(result.split())

        return result

    def map_compound(self, name: str) -> Tuple[Optional[str], str, str]:
        """
        Map a compound (potentially hydrated) to ChEBI or PubChem.

        Tries multiple strategies:
        1. Direct base compound lookup
        2. Formula-to-name conversion then lookup
        3. HCl salt normalization then lookup
        4. Full normalization then lookup

        Args:
            name: Compound name

        Returns:
            Tuple of (mapping_id, method, notes)
        """
        if not name or not isinstance(name, str):
            return (None, '', '')

        # Extract base compound and hydrate info
        base, water_count, hydrate_pattern = extract_hydrate_enhanced(name)

        if not hydrate_pattern:
            # Not a hydrate - no action needed
            return (None, '', 'not_hydrate')

        notes = f'base={base}, hydrate={hydrate_pattern}, water={water_count}'

        # Strategy 1: Direct base compound lookup
        base_lower = base.lower().strip()
        if base_lower in self.chebi_lookup:
            return (self.chebi_lookup[base_lower], 'chebi_exact', notes)

        # Strategy 2: Formula-to-name conversion
        # This handles cases like "MnCl2" → "manganese(II) chloride"
        base_name = convert_formula_to_name(base)
        if base_name != base:
            base_name_lower = base_name.lower().strip()
            if base_name_lower in self.chebi_lookup:
                return (self.chebi_lookup[base_name_lower], 'chebi_formula_to_name',
                        f'{notes}, converted={base_name}')

        # Strategy 3: HCl salt normalization
        # This handles "L-Cysteine HCl" → "L-Cysteine hydrochloride"
        if 'hcl' in base.lower() or '-hcl' in base.lower():
            base_hcl = normalize_hcl_salt(base)
            base_hcl_lower = base_hcl.lower().strip()
            if base_hcl_lower in self.chebi_lookup:
                return (self.chebi_lookup[base_hcl_lower], 'chebi_hcl_normalized',
                        f'{notes}, hcl_normalized={base_hcl}')

        # Strategy 4: Full normalization (from compound_normalizer)
        base_full_norm = normalize_for_mapping(base)
        if base_full_norm:
            base_full_lower = base_full_norm.lower().strip()
            if base_full_lower in self.chebi_lookup:
                return (self.chebi_lookup[base_full_lower], 'chebi_full_normalized',
                        f'{notes}, full_normalized={base_full_norm}')

        # Strategy 5: Custom normalization
        base_normalized = self._normalize_name(base)
        if base_normalized and base_normalized in self.chebi_lookup:
            return (self.chebi_lookup[base_normalized], 'chebi_custom_normalized', notes)

        # Strategy 6: PubChem cache (try all variants)
        for variant in [base_lower, base_name.lower() if base_name != base else None,
                        base_full_norm.lower() if base_full_norm else None]:
            if variant and variant in self.pubchem_cache:
                return (self.pubchem_cache[variant], 'pubchem_cache', notes)

        # No mapping found
        return (None, '', f'unmapped_{notes}')

    def process_file(self, input_file: str, output_file: str):
        """
        Process input TSV file and add hydrate-based mappings.

        Args:
            input_file: Input TSV with id, original, mapped columns
            output_file: Output TSV with enhanced mappings
        """
        logger.info(f"Processing {input_file}")

        df = pd.read_csv(input_file, sep='\t')

        # Track statistics
        stats = {
            'total': len(df),
            'hydrates_found': 0,
            'mapped_chebi': 0,
            'mapped_pubchem': 0,
            'unmapped_hydrates': 0,
            'already_mapped': 0,
        }

        # Process each row
        for idx, row in df.iterrows():
            original = row.get('original', '')
            current_mapping = row.get('mapped', '')

            # Skip if already has a good mapping
            if pd.notna(current_mapping) and current_mapping.strip():
                if not str(current_mapping).startswith('ingredient:'):
                    stats['already_mapped'] += 1
                    continue

            # Try hydrate-based mapping
            new_mapping, method, notes = self.map_compound(original)

            if new_mapping:
                df.at[idx, 'mapped'] = new_mapping
                if 'chebi' in method:
                    stats['mapped_chebi'] += 1
                elif 'pubchem' in method:
                    stats['mapped_pubchem'] += 1
                stats['hydrates_found'] += 1
            elif 'hydrate' in notes or 'H2O' in str(original):
                stats['hydrates_found'] += 1
                stats['unmapped_hydrates'] += 1

        # Save output
        df.to_csv(output_file, sep='\t', index=False)
        logger.info(f"Saved to {output_file}")

        # Print report
        print("\n" + "=" * 60)
        print("ENHANCED HYDRATE MAPPING REPORT")
        print("=" * 60)
        print(f"Total entries:        {stats['total']}")
        print(f"Already mapped:       {stats['already_mapped']}")
        print(f"Hydrates identified:  {stats['hydrates_found']}")
        print(f"  Mapped to ChEBI:    {stats['mapped_chebi']}")
        print(f"  Mapped to PubChem:  {stats['mapped_pubchem']}")
        print(f"  Still unmapped:     {stats['unmapped_hydrates']}")
        print("=" * 60)

        return stats


def main():
    parser = argparse.ArgumentParser(description="Enhanced hydrate compound mapper")
    parser.add_argument('--input', required=True, help='Input TSV file')
    parser.add_argument('--output', required=True, help='Output TSV file')
    parser.add_argument('--chebi-file', required=True, help='ChEBI nodes TSV')
    parser.add_argument('--pubchem-cache', help='Optional PubChem name cache TSV')

    args = parser.parse_args()

    mapper = EnhancedHydrateMapper(args.chebi_file, args.pubchem_cache)
    mapper.process_file(args.input, args.output)


if __name__ == '__main__':
    main()
