#!/usr/bin/env python3
"""
Deterministic API-based compound lookup functions.

Provides PubChem and ChEBI API functions for compound mapping.
All functions are stateless and deterministic given the same inputs.

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
import time
import urllib.parse
from typing import Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

# Rate limiting - seconds between API requests
REQUEST_DELAY = 0.25

# API endpoints
PUBCHEM_BASE_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
OLS4_BASE_URL = "https://www.ebi.ac.uk/ols4/api"

# Request timeout in seconds
REQUEST_TIMEOUT = 30


def search_pubchem_by_name(compound_name: str) -> Optional[int]:
    """
    Search PubChem for a compound by name, return CID if found.

    Args:
        compound_name: Chemical compound name to search

    Returns:
        PubChem CID (Compound ID) if found, None otherwise
    """
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

    Args:
        chebi_id: ChEBI ID in format "CHEBI:XXXXX"

    Returns:
        Label/name of the compound if found, None otherwise
    """
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

    Args:
        compound_name: Chemical compound name to search

    Returns:
        Tuple of (ChEBI ID, label) if found, None otherwise
    """
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
