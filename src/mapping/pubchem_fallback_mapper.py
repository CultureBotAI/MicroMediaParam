#!/usr/bin/env python3
"""
PubChem Fallback Mapper

Maps compounds via PubChem CID when ChEBI entries are unavailable.
Provides fallback mapping for organic compounds that exist in PubChem but not ChEBI.
"""

import requests
import time
import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class PubChemFallbackMapper:
    """
    Map compounds via PubChem CID when ChEBI unavailable.

    Use this for compounds like:
    - trimethoxybenzoate
    - Organic compounds not in ChEBI
    - Specialized research chemicals
    """

    BASE_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
    RATE_LIMIT_DELAY = 0.2  # 200ms between requests

    def __init__(self):
        """Initialize PubChem fallback mapper."""
        self.last_request_time = 0

    def _rate_limit(self):
        """Enforce rate limiting for PubChem API."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.RATE_LIMIT_DELAY:
            time.sleep(self.RATE_LIMIT_DELAY - elapsed)
        self.last_request_time = time.time()

    def search_by_name(self, compound_name: str) -> Optional[Dict]:
        """
        Search PubChem by compound name.

        Args:
            compound_name: Chemical compound name

        Returns:
            Dict with pubchem_cid and source, or None if not found

        Example:
            >>> mapper = PubChemFallbackMapper()
            >>> result = mapper.search_by_name("trimethoxybenzoate")
            >>> result
            {'pubchem_cid': 'PubChem:12345', 'source': 'pubchem_api'}
        """
        if not compound_name or not isinstance(compound_name, str):
            return None

        self._rate_limit()

        url = f"{self.BASE_URL}/compound/name/{requests.utils.quote(compound_name)}/JSON"

        try:
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                data = response.json()

                # Extract CID from response
                if 'PC_Compounds' in data and len(data['PC_Compounds']) > 0:
                    cid = data['PC_Compounds'][0]['id']['id']['cid']

                    logger.info(f"PubChem match: {compound_name} → CID:{cid}")

                    return {
                        'pubchem_cid': f"PubChem:{cid}",
                        'source': 'pubchem_api',
                        'compound_name': compound_name
                    }

            elif response.status_code == 404:
                logger.debug(f"PubChem: No match for '{compound_name}'")
                return None

            else:
                logger.warning(f"PubChem API error {response.status_code} for '{compound_name}'")
                return None

        except requests.exceptions.Timeout:
            logger.warning(f"PubChem API timeout for '{compound_name}'")
            return None

        except requests.exceptions.RequestException as e:
            logger.error(f"PubChem API request failed for '{compound_name}': {e}")
            return None

        except (KeyError, IndexError, ValueError) as e:
            logger.error(f"Failed to parse PubChem response for '{compound_name}': {e}")
            return None

    def search_batch(self, compound_names: list) -> Dict[str, Optional[Dict]]:
        """
        Search multiple compounds with rate limiting.

        Args:
            compound_names: List of compound names to search

        Returns:
            Dictionary mapping compound name → result dict (or None)

        Example:
            >>> mapper = PubChemFallbackMapper()
            >>> results = mapper.search_batch(["compound1", "compound2"])
            >>> results
            {'compound1': {'pubchem_cid': 'PubChem:123', ...}, 'compound2': None}
        """
        results = {}

        logger.info(f"Searching PubChem for {len(compound_names)} compounds...")

        for i, compound_name in enumerate(compound_names, 1):
            if i % 10 == 0:
                logger.info(f"Progress: {i}/{len(compound_names)}")

            results[compound_name] = self.search_by_name(compound_name)

        # Summary
        found = sum(1 for r in results.values() if r is not None)
        logger.info(f"PubChem search complete: {found}/{len(compound_names)} found")

        return results


def main():
    """Demo/test function."""
    import sys

    # Test compounds
    test_compounds = [
        "trimethoxybenzoate",
        "synanthrin",
        "peptone",
        "this_compound_does_not_exist_xyz123"
    ]

    print("\n=== PubChem Fallback Mapper Test ===\n")

    mapper = PubChemFallbackMapper()

    for compound in test_compounds:
        result = mapper.search_by_name(compound)
        if result:
            print(f"✓ {compound}")
            print(f"  → {result['pubchem_cid']}")
            print(f"  Source: {result['source']}")
            print()
        else:
            print(f"✗ {compound} - No PubChem match found\n")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
