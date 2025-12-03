#!/usr/bin/env python3
"""
PubChem lookup for unmapped compounds.

Attempts to map remaining non-CHEBI compounds to PubChem CIDs.
This includes CAS-RN and ingredient: prefixed compounds.

Usage:
    python -m src.mapping.pubchem_lookup \
        --input pipeline_output/merge_mappings/compound_mappings_strict.tsv \
        --output pipeline_output/merge_mappings/compound_mappings_final.tsv \
        --cache data/cache/pubchem_name_cache.tsv
"""

import argparse
import logging
import time
from pathlib import Path
from typing import Dict, Optional, Tuple
import json

import pandas as pd
import requests

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# PubChem API endpoints
PUBCHEM_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"


class PubChemLookup:
    """Look up compounds in PubChem by name or CAS-RN."""

    def __init__(self, cache_file: Optional[Path] = None):
        """Initialize with optional cache file."""
        self.cache: Dict[str, Optional[str]] = {}
        self.cache_file = cache_file
        self.api_calls = 0
        self.cache_hits = 0

        if cache_file and cache_file.exists():
            self._load_cache()

    def _load_cache(self):
        """Load cache from file."""
        try:
            df = pd.read_csv(self.cache_file, sep='\t')
            for _, row in df.iterrows():
                name = str(row['name'])
                cid = str(row['pubchem_cid']) if pd.notna(row['pubchem_cid']) else None
                self.cache[name] = cid
            logger.info(f"Loaded {len(self.cache)} entries from cache")
        except Exception as e:
            logger.warning(f"Could not load cache: {e}")

    def _save_cache(self):
        """Save cache to file."""
        if not self.cache_file:
            return
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            data = [{'name': k, 'pubchem_cid': v} for k, v in self.cache.items()]
            df = pd.DataFrame(data)
            df.to_csv(self.cache_file, sep='\t', index=False)
            logger.info(f"Saved {len(self.cache)} entries to cache")
        except Exception as e:
            logger.warning(f"Could not save cache: {e}")

    def lookup_by_name(self, name: str) -> Optional[str]:
        """
        Look up compound by name in PubChem.

        Returns PubChem CID if found, None otherwise.
        """
        if name in self.cache:
            self.cache_hits += 1
            return self.cache[name]

        # Clean up name for search
        clean_name = name.strip()
        if not clean_name or len(clean_name) < 2:
            self.cache[name] = None
            return None

        # Try PubChem name search
        try:
            url = f"{PUBCHEM_BASE}/compound/name/{requests.utils.quote(clean_name)}/cids/JSON"
            self.api_calls += 1

            # Rate limiting
            if self.api_calls % 5 == 0:
                time.sleep(0.2)

            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                data = response.json()
                cids = data.get('IdentifierList', {}).get('CID', [])
                if cids:
                    cid = f"PubChem:{cids[0]}"
                    self.cache[name] = cid
                    return cid

            self.cache[name] = None
            return None

        except Exception as e:
            logger.debug(f"PubChem lookup failed for '{name}': {e}")
            self.cache[name] = None
            return None

    def lookup_by_cas(self, cas_rn: str) -> Optional[str]:
        """
        Look up compound by CAS-RN in PubChem.

        Returns PubChem CID if found, None otherwise.
        """
        # Extract CAS number from CAS-RN:XXXX-XX-X format
        if cas_rn.startswith('CAS-RN:'):
            cas_num = cas_rn[7:]
        else:
            cas_num = cas_rn

        cache_key = f"CAS:{cas_num}"
        if cache_key in self.cache:
            self.cache_hits += 1
            return self.cache[cache_key]

        try:
            # Search PubChem by CAS registry number
            url = f"{PUBCHEM_BASE}/compound/name/{cas_num}/cids/JSON"
            self.api_calls += 1

            if self.api_calls % 5 == 0:
                time.sleep(0.2)

            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                data = response.json()
                cids = data.get('IdentifierList', {}).get('CID', [])
                if cids:
                    cid = f"PubChem:{cids[0]}"
                    self.cache[cache_key] = cid
                    return cid

            self.cache[cache_key] = None
            return None

        except Exception as e:
            logger.debug(f"PubChem CAS lookup failed for '{cas_rn}': {e}")
            self.cache[cache_key] = None
            return None


def process_mappings(
    input_file: Path,
    output_file: Path,
    cache_file: Optional[Path] = None,
    max_lookups: int = 0
) -> dict:
    """
    Process mapping file and add PubChem lookups for unmapped compounds.

    Args:
        input_file: Input mapping file
        output_file: Output file with PubChem mappings added
        cache_file: Optional cache file for PubChem lookups
        max_lookups: Maximum API lookups (0 = unlimited)

    Returns:
        Statistics dictionary
    """
    logger.info(f"Loading mappings from {input_file}")
    df = pd.read_csv(input_file, sep='\t', low_memory=False)

    # Find mapped column
    mapped_col = 'mapped' if 'mapped' in df.columns else df.columns[2]
    original_col = 'original' if 'original' in df.columns else df.columns[1]

    # Initialize PubChem lookup
    lookup = PubChemLookup(cache_file)

    # Track stats
    stats = {
        'total_rows': len(df),
        'already_chebi': 0,
        'cas_rn_lookup': 0,
        'cas_rn_found': 0,
        'ingredient_lookup': 0,
        'ingredient_found': 0,
        'other_skipped': 0,
    }

    # Collect unique compounds to look up
    compounds_to_lookup = {}  # original -> (row_indices, current_id)

    for idx, row in df.iterrows():
        mapped_id = str(row[mapped_col]) if pd.notna(row[mapped_col]) else ''
        original = str(row[original_col]) if pd.notna(row[original_col]) else ''

        if mapped_id.startswith('CHEBI:'):
            stats['already_chebi'] += 1
            continue

        if mapped_id.startswith('CAS-RN:'):
            if original not in compounds_to_lookup:
                compounds_to_lookup[original] = ([], mapped_id, 'cas')
            compounds_to_lookup[original][0].append(idx)

        elif mapped_id.startswith('ingredient:'):
            if original not in compounds_to_lookup:
                compounds_to_lookup[original] = ([], mapped_id, 'ingredient')
            compounds_to_lookup[original][0].append(idx)

        else:
            stats['other_skipped'] += 1

    logger.info(f"Found {len(compounds_to_lookup)} unique compounds to look up")

    # Perform lookups
    lookups_done = 0
    for original, (indices, current_id, lookup_type) in compounds_to_lookup.items():
        if max_lookups > 0 and lookups_done >= max_lookups:
            break

        if lookup_type == 'cas':
            stats['cas_rn_lookup'] += 1
            # Try CAS lookup first, then name
            pubchem_id = lookup.lookup_by_cas(current_id)
            if not pubchem_id:
                pubchem_id = lookup.lookup_by_name(original)
        else:
            stats['ingredient_lookup'] += 1
            pubchem_id = lookup.lookup_by_name(original)

        if pubchem_id:
            if lookup_type == 'cas':
                stats['cas_rn_found'] += 1
            else:
                stats['ingredient_found'] += 1

            # Update all rows with this compound
            for idx in indices:
                df.at[idx, mapped_col] = pubchem_id

        lookups_done += 1

        # Progress update
        if lookups_done % 100 == 0:
            logger.info(f"Processed {lookups_done}/{len(compounds_to_lookup)} compounds...")

    # Save cache
    lookup._save_cache()

    # Save output
    output_file.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_file, sep='\t', index=False)
    logger.info(f"Saved {len(df)} rows to {output_file}")

    # Add lookup stats
    stats['api_calls'] = lookup.api_calls
    stats['cache_hits'] = lookup.cache_hits

    # Print summary
    print("\n" + "=" * 70)
    print("PUBCHEM LOOKUP COMPLETE")
    print("=" * 70)
    print(f"Total rows:              {stats['total_rows']:,}")
    print(f"Already CHEBI:           {stats['already_chebi']:,}")
    print()
    print(f"CAS-RN lookups:          {stats['cas_rn_lookup']:,}")
    print(f"CAS-RN → PubChem:        {stats['cas_rn_found']:,}")
    print()
    print(f"Ingredient lookups:      {stats['ingredient_lookup']:,}")
    print(f"Ingredient → PubChem:    {stats['ingredient_found']:,}")
    print()
    print(f"API calls made:          {stats['api_calls']:,}")
    print(f"Cache hits:              {stats['cache_hits']:,}")
    print()
    print(f"Output: {output_file}")
    print("=" * 70)

    return stats


def main():
    parser = argparse.ArgumentParser(
        description='Look up unmapped compounds in PubChem'
    )
    parser.add_argument(
        '--input', '-i',
        type=Path,
        required=True,
        help='Input mapping file'
    )
    parser.add_argument(
        '--output', '-o',
        type=Path,
        required=True,
        help='Output file with PubChem mappings'
    )
    parser.add_argument(
        '--cache', '-c',
        type=Path,
        default=None,
        help='Cache file for PubChem lookups'
    )
    parser.add_argument(
        '--max-lookups', '-m',
        type=int,
        default=0,
        help='Maximum API lookups (0 = unlimited)'
    )

    args = parser.parse_args()

    process_mappings(args.input, args.output, args.cache, args.max_lookups)


if __name__ == '__main__':
    main()
