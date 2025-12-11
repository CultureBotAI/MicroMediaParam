#!/usr/bin/env python3
"""
Deterministic API-based compound lookup functions.

Provides PubChem and ChEBI API functions for compound mapping.
All functions are stateless and deterministic given the same inputs.

For DETERMINISTIC PIPELINE RUNS:
- Set CACHE_ONLY_MODE = True to prevent any live API calls
- All lookups will use cached data only (returns None if not cached)
- This ensures reproducible results across runs

APIs used:
- PubChem REST API: https://pubchem.ncbi.nlm.nih.gov/rest/pug
- EBI OLS4 (Ontology Lookup Service): https://www.ebi.ac.uk/ols4/api

Usage:
    from src.mapping.api_lookup import (
        search_pubchem_by_name,
        get_chebi_from_pubchem_cid,
        verify_chebi_label,
        search_chebi_directly
    )
"""

import logging
import os
import time
import urllib.parse
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests

logger = logging.getLogger(__name__)

# DETERMINISM CONTROL: Set to True to prevent live API calls
# Can also be controlled via environment variable: CACHE_ONLY_MODE=1
CACHE_ONLY_MODE = os.environ.get('CACHE_ONLY_MODE', '0') == '1'

# Rate limiting - seconds between API requests
REQUEST_DELAY = 0.25

# API endpoints
PUBCHEM_BASE_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
OLS4_BASE_URL = "https://www.ebi.ac.uk/ols4/api"

# Request timeout in seconds
REQUEST_TIMEOUT = 30

# Cache file paths (relative to project root)
DEFAULT_PUBCHEM_CACHE = Path("data/cache/pubchem_lookup_cache.tsv")
DEFAULT_OLS_CACHE = Path("data/cache/ols_multi_ontology_cache.tsv")

# In-memory cache (populated from files on first use)
_pubchem_cache: Optional[Dict[str, Optional[int]]] = None
_ols_cache: Optional[Dict[str, Optional[Tuple[str, str]]]] = None


def _load_pubchem_cache() -> Dict[str, Optional[int]]:
    """Load PubChem cache from TSV file."""
    global _pubchem_cache
    if _pubchem_cache is not None:
        return _pubchem_cache

    _pubchem_cache = {}
    if DEFAULT_PUBCHEM_CACHE.exists():
        try:
            df = pd.read_csv(DEFAULT_PUBCHEM_CACHE, sep='\t')
            for _, row in df.iterrows():
                name = str(row.get('name', row.get('query', ''))).lower().strip()
                cid = row.get('cid', row.get('pubchem_cid', ''))
                if name:
                    if pd.notna(cid) and str(cid).strip():
                        cid_str = str(cid).strip()
                        if cid_str.startswith('PubChem:'):
                            _pubchem_cache[name] = int(cid_str.replace('PubChem:', ''))
                        else:
                            try:
                                _pubchem_cache[name] = int(float(cid_str))
                            except (ValueError, TypeError):
                                _pubchem_cache[name] = None
                    else:
                        _pubchem_cache[name] = None
            logger.info(f"Loaded {len(_pubchem_cache)} PubChem cache entries")
        except Exception as e:
            logger.warning(f"Failed to load PubChem cache: {e}")

    return _pubchem_cache


def _load_ols_cache() -> Dict[str, Optional[Tuple[str, str]]]:
    """Load OLS cache from TSV file."""
    global _ols_cache
    if _ols_cache is not None:
        return _ols_cache

    _ols_cache = {}
    if DEFAULT_OLS_CACHE.exists():
        try:
            df = pd.read_csv(DEFAULT_OLS_CACHE, sep='\t')
            for _, row in df.iterrows():
                query = str(row.get('query', '')).lower().strip()
                ontology_id = str(row.get('ontology_id', ''))
                label = str(row.get('label', ''))
                if query:
                    if ontology_id and ontology_id != 'nan' and ontology_id.strip():
                        _ols_cache[query] = (ontology_id, label)
                    else:
                        _ols_cache[query] = None
            logger.info(f"Loaded {len(_ols_cache)} OLS cache entries")
        except Exception as e:
            logger.warning(f"Failed to load OLS cache: {e}")

    return _ols_cache


def search_pubchem_by_name(compound_name: str) -> Optional[int]:
    """
    Search PubChem for a compound by name, return CID if found.

    In CACHE_ONLY_MODE, only returns cached results (no API calls).

    Args:
        compound_name: Chemical compound name to search

    Returns:
        PubChem CID (Compound ID) if found, None otherwise
    """
    # Check cache first
    cache = _load_pubchem_cache()
    cache_key = compound_name.lower().strip()
    if cache_key in cache:
        return cache[cache_key]

    # In cache-only mode, return None for uncached entries
    if CACHE_ONLY_MODE:
        logger.debug(f"CACHE_ONLY_MODE: No cached PubChem result for '{compound_name}'")
        return None

    # Make live API call (non-deterministic)
    try:
        encoded_name = urllib.parse.quote(compound_name)
        url = f"{PUBCHEM_BASE_URL}/compound/name/{encoded_name}/cids/JSON"
        response = requests.get(url, timeout=REQUEST_TIMEOUT)

        if response.status_code == 200:
            data = response.json()
            cids = data.get('IdentifierList', {}).get('CID', [])
            if cids:
                return cids[0]  # Return first (most common) CID
        return None
    except Exception as e:
        logger.debug(f"PubChem search error for '{compound_name}': {e}")
        return None


def get_chebi_from_pubchem_cid(cid: int) -> Optional[Tuple[str, str]]:
    """
    Get ChEBI ID and label from a PubChem CID via cross-reference.

    Args:
        cid: PubChem Compound ID

    Returns:
        Tuple of (ChEBI ID, label) if found, None otherwise
    """
    try:
        url = f"{PUBCHEM_BASE_URL}/compound/cid/{cid}/xrefs/RegistryID/JSON"
        response = requests.get(url, timeout=REQUEST_TIMEOUT)

        if response.status_code == 200:
            data = response.json()
            info_list = data.get('InformationList', {}).get('Information', [])
            if info_list:
                registry_ids = info_list[0].get('RegistryID', [])
                for reg_id in registry_ids:
                    if reg_id.startswith('CHEBI:'):
                        # Verify the ChEBI label exists
                        chebi_label = verify_chebi_label(reg_id)
                        if chebi_label:
                            return reg_id, chebi_label
        return None
    except Exception as e:
        logger.debug(f"PubChem xref error for CID {cid}: {e}")
        return None


def verify_chebi_label(chebi_id: str) -> Optional[str]:
    """
    Verify ChEBI ID exists and get its label from OLS4.

    In CACHE_ONLY_MODE, returns None (no API calls).

    Args:
        chebi_id: ChEBI ID in format "CHEBI:XXXXX"

    Returns:
        Label/name of the compound if found, None otherwise
    """
    # In cache-only mode, skip verification (assume valid if in local ChEBI)
    if CACHE_ONLY_MODE:
        logger.debug(f"CACHE_ONLY_MODE: Skipping ChEBI verification for {chebi_id}")
        return chebi_id  # Return ID as placeholder

    try:
        url = f"{OLS4_BASE_URL}/ontologies/chebi/terms?obo_id={chebi_id}"
        response = requests.get(url, timeout=REQUEST_TIMEOUT)

        if response.status_code == 200:
            data = response.json()
            terms = data.get('_embedded', {}).get('terms', [])
            if terms:
                label = terms[0].get('label', '')
                # Check if label is the ID itself (OLS bug workaround)
                if not label.startswith('CHEBI_'):
                    return label
                # Fallback to synonyms if label is malformed
                synonyms = terms[0].get('synonyms', [])
                if synonyms:
                    return synonyms[0]
        return None
    except Exception as e:
        logger.debug(f"ChEBI verification error for {chebi_id}: {e}")
        return None


def search_chebi_directly(compound_name: str) -> Optional[Tuple[str, str]]:
    """
    Search ChEBI directly using OLS4 search API.

    In CACHE_ONLY_MODE, checks OLS cache first, returns None if not cached.

    Args:
        compound_name: Chemical compound name to search

    Returns:
        Tuple of (ChEBI ID, label) if found, None otherwise
    """
    # Check OLS cache first
    cache = _load_ols_cache()
    cache_key = compound_name.lower().strip()
    if cache_key in cache:
        result = cache[cache_key]
        if result and result[0].startswith('CHEBI:'):
            return result
        return None

    # In cache-only mode, return None for uncached entries
    if CACHE_ONLY_MODE:
        logger.debug(f"CACHE_ONLY_MODE: No cached ChEBI result for '{compound_name}'")
        return None

    try:
        encoded_name = urllib.parse.quote(compound_name)
        url = f"{OLS4_BASE_URL}/search?q={encoded_name}&ontology=chebi&exact=true"
        response = requests.get(url, timeout=REQUEST_TIMEOUT)

        if response.status_code == 200:
            data = response.json()
            docs = data.get('response', {}).get('docs', [])
            if docs:
                # Try to find exact match first
                for doc in docs:
                    obo_id = doc.get('obo_id', '')
                    label = doc.get('label', '')
                    if obo_id.startswith('CHEBI:') and label.lower() == compound_name.lower():
                        return obo_id, label
                # Fallback: return first ChEBI result
                if docs[0].get('obo_id', '').startswith('CHEBI:'):
                    return docs[0].get('obo_id'), docs[0].get('label', '')
        return None
    except Exception as e:
        logger.debug(f"ChEBI search error for '{compound_name}': {e}")
        return None


def lookup_compound(compound_name: str) -> Optional[Dict]:
    """
    Comprehensive compound lookup using multiple strategies.

    Tries in order:
    1. PubChem name search → ChEBI cross-reference
    2. Direct ChEBI/OLS4 search

    Args:
        compound_name: Chemical compound name to lookup

    Returns:
        Dict with 'chebi_id', 'chebi_label', 'source' if found, None otherwise
    """
    # Strategy 1: PubChem → ChEBI cross-reference
    cid = search_pubchem_by_name(compound_name)
    if cid:
        time.sleep(REQUEST_DELAY)
        result = get_chebi_from_pubchem_cid(cid)
        if result:
            chebi_id, chebi_label = result
            return {
                'chebi_id': chebi_id,
                'chebi_label': chebi_label,
                'source': f'pubchem_cid:{cid}'
            }

    time.sleep(REQUEST_DELAY)

    # Strategy 2: Direct ChEBI search
    result = search_chebi_directly(compound_name)
    if result:
        chebi_id, chebi_label = result
        return {
            'chebi_id': chebi_id,
            'chebi_label': chebi_label,
            'source': 'ols4_search'
        }

    return None


def get_pubchem_synonyms(cid: int, limit: int = 50) -> List[str]:
    """
    Get synonyms for a PubChem compound.

    Args:
        cid: PubChem Compound ID
        limit: Maximum number of synonyms to return

    Returns:
        List of synonym strings
    """
    try:
        url = f"{PUBCHEM_BASE_URL}/compound/cid/{cid}/synonyms/JSON"
        response = requests.get(url, timeout=REQUEST_TIMEOUT)

        if response.status_code == 200:
            data = response.json()
            info_list = data.get('InformationList', {}).get('Information', [])
            if info_list:
                synonyms = info_list[0].get('Synonym', [])
                return synonyms[:limit]
        return []
    except Exception as e:
        logger.debug(f"PubChem synonyms error for CID {cid}: {e}")
        return []


def get_chebi_synonyms(chebi_id: str) -> List[str]:
    """
    Get synonyms for a ChEBI compound from OLS4.

    Args:
        chebi_id: ChEBI ID in format "CHEBI:XXXXX"

    Returns:
        List of synonym strings
    """
    try:
        url = f"{OLS4_BASE_URL}/ontologies/chebi/terms?obo_id={chebi_id}"
        response = requests.get(url, timeout=REQUEST_TIMEOUT)

        if response.status_code == 200:
            data = response.json()
            terms = data.get('_embedded', {}).get('terms', [])
            if terms:
                return terms[0].get('synonyms', [])
        return []
    except Exception as e:
        logger.debug(f"ChEBI synonyms error for {chebi_id}: {e}")
        return []
