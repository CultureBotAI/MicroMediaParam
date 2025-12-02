#!/usr/bin/env python3
"""
Multi-ontology lookup via EBI OLS4 API.

Searches UBERON, FOODON, and ENVO ontologies for biological materials
that don't have ChEBI mappings (extracts, peptones, blood products, etc.).

Usage:
    python -m src.mapping.ols_multi_ontology_lookup \
        --input unmapped_ingredients.tsv \
        --output ols_mappings.tsv \
        --cache data/cache/ols_multi_ontology_cache.tsv
"""

import argparse
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# EBI OLS4 API endpoint
OLS4_SEARCH_URL = "https://www.ebi.ac.uk/ols4/api/search"

# Default ontologies for biological materials
DEFAULT_ONTOLOGIES = ["uberon", "foodon", "envo"]

# Rate limiting
REQUEST_DELAY = 0.25  # seconds between requests

# Ontology prefixes to exclude from results (not chemical compounds)
# GO = Gene Ontology (biological processes/functions)
# NCBITaxon = Organism taxonomy
EXCLUDED_PREFIXES = ["GO:", "NCBITaxon:"]


def search_ols_single(
    name: str,
    ontologies: List[str] = None,
    exact_first: bool = True
) -> Optional[Tuple[str, str, str]]:
    """
    Search EBI OLS4 for a term across multiple ontologies.

    Args:
        name: Term to search for
        ontologies: List of ontology names to search (default: uberon, foodon, envo)
        exact_first: Try exact match first, then fuzzy

    Returns:
        Tuple of (ontology_id, term_label, ontology_source) or None
        Example: ("UBERON:0000178", "blood", "uberon")
    """
    if ontologies is None:
        ontologies = DEFAULT_ONTOLOGIES

    ontology_str = ",".join(ontologies)

    # Try exact match first
    if exact_first:
        result = _search_ols_api(name, ontology_str, exact=True)
        if result:
            return result

    # Fall back to fuzzy search
    return _search_ols_api(name, ontology_str, exact=False)


def _search_ols_api(
    query: str,
    ontologies: str,
    exact: bool = False
) -> Optional[Tuple[str, str, str]]:
    """
    Call OLS4 API and parse response.

    Args:
        query: Search term
        ontologies: Comma-separated ontology names
        exact: Whether to require exact match

    Returns:
        Tuple of (ontology_id, term_label, ontology_source) or None
    """
    params = {
        "q": query,
        "ontology": ontologies,
        "queryFields": "label,synonym",
        "exact": str(exact).lower(),
        "rows": 10,  # Get top 10 results
        "type": "class"  # Only get class terms, not properties
    }

    try:
        response = requests.get(OLS4_SEARCH_URL, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        # Check for results in response
        if "response" not in data or "docs" not in data["response"]:
            return None

        docs = data["response"]["docs"]
        if not docs:
            return None

        # Find first valid result, skipping excluded ontologies
        for doc in docs:
            # Extract ontology ID (OBO format like UBERON:0000178)
            obo_id = doc.get("obo_id")
            if not obo_id:
                # Try to construct from short_form
                short_form = doc.get("short_form", "")
                if "_" in short_form:
                    obo_id = short_form.replace("_", ":")

            if not obo_id:
                continue

            # Skip excluded ontology prefixes (GO, NCBITaxon)
            if any(obo_id.startswith(prefix) for prefix in EXCLUDED_PREFIXES):
                logger.debug(f"Skipping excluded ontology result: {obo_id}")
                continue

            label = doc.get("label", "")
            ontology = doc.get("ontology_name", "").lower()

            return (obo_id, label, ontology)

        # No valid result found after filtering
        return None

    except requests.RequestException as e:
        logger.warning(f"OLS API error for '{query}': {e}")
        return None
    except (KeyError, IndexError) as e:
        logger.warning(f"OLS API parse error for '{query}': {e}")
        return None


def load_cache(cache_file: Path) -> Dict[str, Tuple[str, str, str]]:
    """
    Load cached OLS results from TSV file.

    Returns:
        Dict mapping query -> (ontology_id, label, source)
    """
    cache = {}

    if not cache_file.exists():
        logger.info(f"No cache file found at {cache_file}")
        return cache

    logger.info(f"Loading cache from {cache_file}")

    df = pd.read_csv(cache_file, sep='\t')

    for _, row in df.iterrows():
        query = str(row.get('query', ''))
        ontology_id = str(row.get('ontology_id', ''))
        label = str(row.get('label', ''))
        source = str(row.get('source', ''))

        if query:
            if ontology_id and ontology_id != 'nan':
                cache[query] = (ontology_id, label, source)
            else:
                # Store empty result to avoid re-querying
                cache[query] = None

    logger.info(f"Loaded {len(cache)} cached entries")
    return cache


def save_cache(
    cache: Dict[str, Optional[Tuple[str, str, str]]],
    cache_file: Path
):
    """
    Save OLS results to cache TSV file.
    """
    cache_file.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    for query, result in cache.items():
        if result:
            ontology_id, label, source = result
            rows.append({
                'query': query,
                'ontology_id': ontology_id,
                'label': label,
                'source': source
            })
        else:
            rows.append({
                'query': query,
                'ontology_id': '',
                'label': '',
                'source': ''
            })

    df = pd.DataFrame(rows)
    df.to_csv(cache_file, sep='\t', index=False)
    logger.info(f"Saved {len(cache)} entries to cache: {cache_file}")


def batch_search_ols(
    names: List[str],
    ontologies: List[str] = None,
    cache_file: Optional[Path] = None
) -> Dict[str, Optional[Tuple[str, str, str]]]:
    """
    Batch search OLS for multiple terms with caching.

    Args:
        names: List of terms to search
        ontologies: Ontologies to search
        cache_file: Optional path to cache file

    Returns:
        Dict mapping name -> (ontology_id, label, source) or None
    """
    if ontologies is None:
        ontologies = DEFAULT_ONTOLOGIES

    # Load existing cache
    cache = {}
    if cache_file:
        cache = load_cache(cache_file)

    results = {}
    new_lookups = 0

    for i, name in enumerate(names):
        # Clean the name
        name_clean = name.strip()
        if not name_clean:
            results[name] = None
            continue

        # Check cache first
        if name_clean in cache:
            results[name] = cache[name_clean]
            continue

        # Make API call
        result = search_ols_single(name_clean, ontologies)
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
        description="Multi-ontology lookup via EBI OLS4 API"
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Input TSV file with unmapped ingredients (id<TAB>name)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output TSV file with OLS mappings"
    )
    parser.add_argument(
        "--cache",
        type=Path,
        default=None,
        help="Cache file for OLS results"
    )
    parser.add_argument(
        "--ontologies",
        type=str,
        default="uberon,foodon,envo",
        help="Comma-separated list of ontologies to search"
    )
    parser.add_argument(
        "--name-column",
        type=str,
        default=None,
        help="Column name containing ingredient names (auto-detected if not specified)"
    )

    args = parser.parse_args()

    ontologies = [o.strip() for o in args.ontologies.split(",")]
    logger.info(f"Searching ontologies: {ontologies}")

    # Read input file
    logger.info(f"Reading input from {args.input}")
    df = pd.read_csv(args.input, sep='\t')

    # Auto-detect name column
    name_col = args.name_column
    if not name_col:
        # Try common column names
        for col in ['name', 'Name', 'ingredient_name', 'original_name']:
            if col in df.columns:
                name_col = col
                break
        if not name_col:
            # Use second column if no header match
            name_col = df.columns[1] if len(df.columns) > 1 else df.columns[0]

    logger.info(f"Using name column: {name_col}")

    # Get unique names
    names = df[name_col].dropna().unique().tolist()
    logger.info(f"Found {len(names)} unique names to search")

    # Batch search
    results = batch_search_ols(names, ontologies, args.cache)

    # Build output
    output_rows = []
    for _, row in df.iterrows():
        name = row[name_col]
        result = results.get(name)

        output_row = {
            'original_id': row.iloc[0] if len(row) > 0 else '',
            'original_name': name,
            'mapped_id': result[0] if result else '',
            'mapped_label': result[1] if result else '',
            'source_ontology': result[2] if result else '',
            'mapping_source': 'ols4' if result else ''
        }
        output_rows.append(output_row)

    # Save output
    output_df = pd.DataFrame(output_rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    output_df.to_csv(args.output, sep='\t', index=False)

    # Statistics
    mapped = sum(1 for r in results.values() if r)
    total = len(results)

    print("\n" + "=" * 60)
    print("OLS MULTI-ONTOLOGY LOOKUP COMPLETE")
    print("=" * 60)
    print(f"Total queries:     {total}")
    print(f"Mapped:            {mapped} ({mapped/total*100:.1f}%)")
    print(f"Unmapped:          {total - mapped}")
    print()

    # By ontology
    by_ontology = {}
    for result in results.values():
        if result:
            source = result[2]
            by_ontology[source] = by_ontology.get(source, 0) + 1

    print("By ontology:")
    for ont, count in sorted(by_ontology.items(), key=lambda x: -x[1]):
        print(f"  {ont.upper()}: {count}")

    print()
    print(f"Output: {args.output}")
    if args.cache:
        print(f"Cache:  {args.cache}")
    print("=" * 60)


if __name__ == "__main__":
    main()
