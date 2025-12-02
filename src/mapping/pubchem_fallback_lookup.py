#!/usr/bin/env python3
"""
PubChem compound lookup for chemicals without ChEBI mappings.

Searches PubChem by compound name and returns PubChem CID.
Used as fallback when ChEBI/OLS lookups fail.

Usage:
    python -m src.mapping.pubchem_fallback_lookup \
        --input unmapped_chemicals.tsv \
        --output pubchem_mappings.tsv \
        --cache data/cache/pubchem_lookup_cache.tsv
"""

import argparse
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote

import pandas as pd
import requests

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# PubChem REST API endpoints
PUBCHEM_COMPOUND_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{name}/property/IUPACName,MolecularFormula/JSON"
PUBCHEM_SEARCH_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{name}/cids/JSON"

# Rate limiting (PubChem allows 5 req/sec, use 0.25s to be safe)
REQUEST_DELAY = 0.25


def search_pubchem_compound(name: str) -> Optional[Tuple[str, str, str]]:
    """
    Search PubChem for a compound by name.

    Args:
        name: Compound name to search for

    Returns:
        Tuple of (pubchem_cid, iupac_name, molecular_formula) or None
        Example: ("5988", "D-glucopyranose", "C6H12O6")
    """
    if not name or not name.strip():
        return None

    # URL encode the name
    encoded_name = quote(name.strip())

    # First try to get compound properties
    url = PUBCHEM_COMPOUND_URL.format(name=encoded_name)

    try:
        response = requests.get(url, timeout=30)

        if response.status_code == 404:
            # Compound not found - try alternate search
            return _search_pubchem_cids(name)

        response.raise_for_status()
        data = response.json()

        # Parse response
        if "PropertyTable" not in data:
            return None

        properties = data["PropertyTable"].get("Properties", [])
        if not properties:
            return None

        prop = properties[0]
        cid = str(prop.get("CID", ""))
        iupac = prop.get("IUPACName", "")
        formula = prop.get("MolecularFormula", "")

        if cid:
            return (cid, iupac, formula)

        return None

    except requests.RequestException as e:
        logger.debug(f"PubChem API error for '{name}': {e}")
        return None
    except (KeyError, ValueError) as e:
        logger.debug(f"PubChem parse error for '{name}': {e}")
        return None


def _search_pubchem_cids(name: str) -> Optional[Tuple[str, str, str]]:
    """
    Fallback search to get just CIDs when property lookup fails.
    """
    encoded_name = quote(name.strip())
    url = PUBCHEM_SEARCH_URL.format(name=encoded_name)

    try:
        response = requests.get(url, timeout=30)

        if response.status_code == 404:
            return None

        response.raise_for_status()
        data = response.json()

        cids = data.get("IdentifierList", {}).get("CID", [])
        if cids:
            # Return first CID, empty name/formula
            return (str(cids[0]), "", "")

        return None

    except (requests.RequestException, KeyError, ValueError):
        return None


def load_cache(cache_file: Path) -> Dict[str, Optional[Tuple[str, str, str]]]:
    """
    Load cached PubChem results from TSV file.

    Returns:
        Dict mapping query -> (pubchem_cid, iupac_name, formula) or None
    """
    cache = {}

    if not cache_file.exists():
        logger.info(f"No cache file found at {cache_file}")
        return cache

    logger.info(f"Loading cache from {cache_file}")

    df = pd.read_csv(cache_file, sep='\t')

    for _, row in df.iterrows():
        query = str(row.get('query', ''))
        cid = str(row.get('pubchem_cid', ''))
        iupac = str(row.get('iupac_name', '')) if pd.notna(row.get('iupac_name')) else ''
        formula = str(row.get('formula', '')) if pd.notna(row.get('formula')) else ''

        if query:
            if cid and cid != 'nan' and cid != '':
                cache[query] = (cid, iupac, formula)
            else:
                # Store None to indicate we searched but found nothing
                cache[query] = None

    logger.info(f"Loaded {len(cache)} cached entries")
    return cache


def save_cache(
    cache: Dict[str, Optional[Tuple[str, str, str]]],
    cache_file: Path
):
    """
    Save PubChem results to cache TSV file.
    """
    cache_file.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    for query, result in cache.items():
        if result:
            cid, iupac, formula = result
            rows.append({
                'query': query,
                'pubchem_cid': cid,
                'iupac_name': iupac,
                'formula': formula
            })
        else:
            rows.append({
                'query': query,
                'pubchem_cid': '',
                'iupac_name': '',
                'formula': ''
            })

    df = pd.DataFrame(rows)
    df.to_csv(cache_file, sep='\t', index=False)
    logger.info(f"Saved {len(cache)} entries to cache: {cache_file}")


def batch_pubchem_lookup(
    names: List[str],
    cache_file: Optional[Path] = None
) -> Dict[str, Optional[Tuple[str, str, str]]]:
    """
    Batch lookup PubChem for multiple compound names with caching.

    Args:
        names: List of compound names to search
        cache_file: Optional path to cache file

    Returns:
        Dict mapping name -> (pubchem_cid, iupac_name, formula) or None
    """
    # Load existing cache
    cache = {}
    if cache_file:
        cache = load_cache(cache_file)

    results = {}
    new_lookups = 0

    for i, name in enumerate(names):
        # Clean the name
        name_clean = name.strip() if name else ""
        if not name_clean:
            results[name] = None
            continue

        # Check cache first
        if name_clean in cache:
            results[name] = cache[name_clean]
            continue

        # Make API call
        result = search_pubchem_compound(name_clean)
        results[name] = result
        cache[name_clean] = result
        new_lookups += 1

        # Progress logging
        if new_lookups % 50 == 0:
            logger.info(f"Processed {new_lookups} new lookups, {i+1}/{len(names)} total")

        # Rate limiting
        time.sleep(REQUEST_DELAY)

    logger.info(f"Completed {new_lookups} new API lookups")

    # Save updated cache
    if cache_file and new_lookups > 0:
        save_cache(cache, cache_file)

    return results


def main():
    parser = argparse.ArgumentParser(
        description="PubChem compound lookup for unmapped chemicals"
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Input TSV file with unmapped compounds (id<TAB>name)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output TSV file with PubChem mappings"
    )
    parser.add_argument(
        "--cache",
        type=Path,
        default=None,
        help="Cache file for PubChem results"
    )
    parser.add_argument(
        "--name-column",
        type=str,
        default=None,
        help="Column name containing compound names (auto-detected if not specified)"
    )

    args = parser.parse_args()

    # Read input file
    logger.info(f"Reading input from {args.input}")
    df = pd.read_csv(args.input, sep='\t')

    # Auto-detect name column
    name_col = args.name_column
    if not name_col:
        for col in ['name', 'Name', 'compound_name', 'original_name']:
            if col in df.columns:
                name_col = col
                break
        if not name_col:
            name_col = df.columns[1] if len(df.columns) > 1 else df.columns[0]

    logger.info(f"Using name column: {name_col}")

    # Get unique names
    names = df[name_col].dropna().unique().tolist()
    logger.info(f"Found {len(names)} unique names to search")

    # Batch lookup
    results = batch_pubchem_lookup(names, args.cache)

    # Build output
    output_rows = []
    for _, row in df.iterrows():
        name = row[name_col]
        result = results.get(name)

        output_row = {
            'original_id': row.iloc[0] if len(row) > 0 else '',
            'original_name': name,
            'mapped_id': f"PUBCHEM.COMPOUND:{result[0]}" if result else '',
            'mapped_label': result[1] if result else '',
            'molecular_formula': result[2] if result else '',
            'mapping_source': 'pubchem' if result else ''
        }
        output_rows.append(output_row)

    # Save output
    output_df = pd.DataFrame(output_rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    output_df.to_csv(args.output, sep='\t', index=False)

    # Statistics
    mapped = sum(1 for r in results.values() if r)
    total = len(results)
    with_iupac = sum(1 for r in results.values() if r and r[1])
    with_formula = sum(1 for r in results.values() if r and r[2])

    print("\n" + "=" * 60)
    print("PUBCHEM LOOKUP COMPLETE")
    print("=" * 60)
    print(f"Total queries:     {total}")
    print(f"Mapped:            {mapped} ({mapped/total*100:.1f}%)")
    print(f"Unmapped:          {total - mapped}")
    print()
    print("Data enrichment:")
    print(f"  With IUPAC name:    {with_iupac}")
    print(f"  With formula:       {with_formula}")
    print()
    print(f"Output: {args.output}")
    if args.cache:
        print(f"Cache:  {args.cache}")
    print("=" * 60)


if __name__ == "__main__":
    main()
