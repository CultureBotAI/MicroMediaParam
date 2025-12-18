#!/usr/bin/env python3
"""
PubChem Composition Fetcher for Complex Ingredients Curation

Fetches chemical compound data from PubChem API to support complex ingredient
curation in YAML format. Focused on retrieving:
- ChEBI cross-references
- Molecular formulas and weights
- CAS numbers
- Synonyms and common names
- Literature references

Usage:
    python -m src.curation.evidence_collectors.pubchem_composition_fetcher \\
        --compound "Potassium 5-ketogluconate" \\
        --output compound_data.json

    # Batch mode
    python -m src.curation.evidence_collectors.pubchem_composition_fetcher \\
        --batch compounds.txt \\
        --output-dir evidence/pubchem/

Version: 1.0.0
"""

import argparse
import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from urllib.parse import quote

import aiohttp
import aiofiles

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class PubChemCompoundInfo:
    """Container for PubChem compound information relevant to curation."""
    query_name: str
    cid: Optional[str] = None
    iupac_name: Optional[str] = None
    molecular_formula: Optional[str] = None
    molecular_weight: Optional[float] = None
    cas_number: Optional[str] = None
    chebi_id: Optional[str] = None
    synonyms: List[str] = None
    pmid_references: List[str] = None
    success: bool = False
    error: Optional[str] = None

    def __post_init__(self):
        if self.synonyms is None:
            self.synonyms = []
        if self.pmid_references is None:
            self.pmid_references = []


class PubChemCompositionFetcher:
    """
    Fetches compound composition data from PubChem REST API.

    Optimized for complex ingredients curation workflow.
    """

    BASE_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
    BASE_URL_VIEW = "https://pubchem.ncbi.nlm.nih.gov/rest/pug_view"

    # Rate limiting (NCBI guideline: max 5 requests/second)
    REQUEST_DELAY = 0.2  # 200ms between requests

    def __init__(self, cache_dir: Optional[Path] = None):
        """
        Initialize fetcher.

        Args:
            cache_dir: Directory for caching API responses
        """
        self.cache_dir = cache_dir or Path("data/pubchem_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()

    async def fetch_compound(self, compound_name: str) -> PubChemCompoundInfo:
        """
        Fetch compound information from PubChem.

        Args:
            compound_name: Name to search for

        Returns:
            PubChemCompoundInfo with fetched data
        """
        logger.info(f"Fetching data for: {compound_name}")

        info = PubChemCompoundInfo(query_name=compound_name)

        try:
            # Step 1: Get CID from compound name
            cid = await self._get_cid_from_name(compound_name)
            if not cid:
                info.error = "Compound not found in PubChem"
                return info

            info.cid = cid
            logger.info(f"Found CID: {cid} for {compound_name}")

            # Step 2: Get compound properties
            properties = await self._get_compound_properties(cid)
            if properties:
                info.molecular_formula = properties.get('MolecularFormula')
                info.molecular_weight = properties.get('MolecularWeight')
                info.iupac_name = properties.get('IUPACName')
                info.cas_number = self._extract_cas_number(properties)

            # Step 3: Get synonyms
            synonyms = await self._get_synonyms(cid)
            if synonyms:
                info.synonyms = synonyms[:20]  # Limit to top 20

            # Step 4: Get ChEBI cross-reference
            chebi_id = await self._get_chebi_xref(cid)
            if chebi_id:
                info.chebi_id = chebi_id

            # Step 5: Get literature references
            pmids = await self._get_pmid_references(cid)
            if pmids:
                info.pmid_references = pmids[:5]  # Top 5 references

            info.success = True

        except Exception as e:
            logger.error(f"Error fetching {compound_name}: {e}")
            info.error = str(e)

        return info

    async def _get_cid_from_name(self, name: str) -> Optional[str]:
        """Get PubChem CID from compound name."""
        cache_file = self.cache_dir / f"cid_{name.replace(' ', '_')}.json"

        # Check cache
        if cache_file.exists():
            async with aiofiles.open(cache_file, 'r') as f:
                data = json.loads(await f.read())
                return data.get('cid')

        # Query API
        url = f"{self.BASE_URL}/compound/name/{quote(name)}/cids/JSON"

        try:
            await asyncio.sleep(self.REQUEST_DELAY)
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    cid = str(data['IdentifierList']['CID'][0])

                    # Cache result
                    async with aiofiles.open(cache_file, 'w') as f:
                        await f.write(json.dumps({'cid': cid}))

                    return cid
                else:
                    logger.warning(f"Failed to get CID for {name}: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Error getting CID for {name}: {e}")
            return None

    async def _get_compound_properties(self, cid: str) -> Optional[Dict[str, Any]]:
        """Get compound properties from PubChem."""
        cache_file = self.cache_dir / f"props_{cid}.json"

        # Check cache
        if cache_file.exists():
            async with aiofiles.open(cache_file, 'r') as f:
                return json.loads(await f.read())

        # Query API
        url = (f"{self.BASE_URL}/compound/cid/{cid}/property/"
               f"MolecularFormula,MolecularWeight,IUPACName,IsomericSMILES/JSON")

        try:
            await asyncio.sleep(self.REQUEST_DELAY)
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    props = data['PropertyTable']['Properties'][0]

                    # Cache result
                    async with aiofiles.open(cache_file, 'w') as f:
                        await f.write(json.dumps(props))

                    return props
                else:
                    logger.warning(f"Failed to get properties for CID {cid}")
                    return None
        except Exception as e:
            logger.error(f"Error getting properties for CID {cid}: {e}")
            return None

    async def _get_synonyms(self, cid: str) -> List[str]:
        """Get compound synonyms from PubChem."""
        cache_file = self.cache_dir / f"synonyms_{cid}.json"

        # Check cache
        if cache_file.exists():
            async with aiofiles.open(cache_file, 'r') as f:
                return json.loads(await f.read())

        # Query API
        url = f"{self.BASE_URL}/compound/cid/{cid}/synonyms/JSON"

        try:
            await asyncio.sleep(self.REQUEST_DELAY)
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    synonyms = data['InformationList']['Information'][0].get('Synonym', [])

                    # Cache result
                    async with aiofiles.open(cache_file, 'w') as f:
                        await f.write(json.dumps(synonyms))

                    return synonyms
                else:
                    return []
        except Exception as e:
            logger.error(f"Error getting synonyms for CID {cid}: {e}")
            return []

    def _extract_cas_number(self, properties: Dict[str, Any]) -> Optional[str]:
        """Extract CAS number from properties (if available in synonyms)."""
        # Note: CAS numbers are typically in synonyms, not direct properties
        # This is a placeholder - real implementation would check synonyms
        return None

    async def _get_chebi_xref(self, cid: str) -> Optional[str]:
        """Get ChEBI cross-reference for PubChem CID."""
        cache_file = self.cache_dir / f"chebi_xref_{cid}.json"

        # Check cache
        if cache_file.exists():
            async with aiofiles.open(cache_file, 'r') as f:
                data = json.loads(await f.read())
                return data.get('chebi_id')

        # Query PubChem xrefs
        url = f"{self.BASE_URL}/compound/cid/{cid}/xrefs/RegistryID/JSON"

        try:
            await asyncio.sleep(self.REQUEST_DELAY)
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    xrefs = data.get('InformationList', {}).get('Information', [])

                    if xrefs:
                        registry_ids = xrefs[0].get('RegistryID', [])

                        # Look for ChEBI IDs (format: ChEBI:##### or CHEBI:#####)
                        for rid in registry_ids:
                            if 'chebi' in rid.lower():
                                # Normalize to CHEBI:##### format
                                if ':' in rid:
                                    chebi_id = rid.upper().replace('CHEBI:', 'CHEBI:')
                                else:
                                    chebi_id = f"CHEBI:{rid}"

                                # Cache and return
                                async with aiofiles.open(cache_file, 'w') as f:
                                    await f.write(json.dumps({'chebi_id': chebi_id}))

                                return chebi_id

                    return None
        except Exception as e:
            logger.error(f"Error getting ChEBI xref for CID {cid}: {e}")
            return None

    async def _get_pmid_references(self, cid: str) -> List[str]:
        """Get PubMed references for compound."""
        cache_file = self.cache_dir / f"pmids_{cid}.json"

        # Check cache
        if cache_file.exists():
            async with aiofiles.open(cache_file, 'r') as f:
                return json.loads(await f.read())

        # Query PubChem for literature xrefs
        url = f"{self.BASE_URL}/compound/cid/{cid}/xrefs/PubMedID/JSON"

        try:
            await asyncio.sleep(self.REQUEST_DELAY)
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    info_list = data.get('InformationList', {}).get('Information', [])

                    if info_list:
                        pmids = info_list[0].get('PubMedID', [])

                        # Cache result
                        async with aiofiles.open(cache_file, 'w') as f:
                            await f.write(json.dumps(pmids))

                        return pmids
                    return []
        except Exception as e:
            logger.error(f"Error getting PMIDs for CID {cid}: {e}")
            return []

    async def fetch_batch(self, compound_names: List[str]) -> List[PubChemCompoundInfo]:
        """
        Fetch data for multiple compounds.

        Args:
            compound_names: List of compound names to fetch

        Returns:
            List of PubChemCompoundInfo objects
        """
        results = []

        for i, name in enumerate(compound_names, 1):
            logger.info(f"Processing {i}/{len(compound_names)}: {name}")
            info = await self.fetch_compound(name)
            results.append(info)

            # Progress indicator
            if i % 10 == 0:
                logger.info(f"Progress: {i}/{len(compound_names)} compounds processed")

        return results


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Fetch compound composition data from PubChem'
    )
    parser.add_argument(
        '--compound',
        help='Single compound name to fetch'
    )
    parser.add_argument(
        '--batch',
        help='File with compound names (one per line)'
    )
    parser.add_argument(
        '--output',
        help='Output JSON file for single compound'
    )
    parser.add_argument(
        '--output-dir',
        help='Output directory for batch results'
    )
    parser.add_argument(
        '--cache-dir',
        default='data/pubchem_cache',
        help='Cache directory for API responses'
    )

    args = parser.parse_args()

    cache_dir = Path(args.cache_dir)

    async with PubChemCompositionFetcher(cache_dir=cache_dir) as fetcher:
        if args.compound:
            # Single compound mode
            info = await fetcher.fetch_compound(args.compound)

            print("\n" + "=" * 70)
            print(f"Compound: {info.query_name}")
            print("=" * 70)
            if info.success:
                print(f"PubChem CID: {info.cid}")
                print(f"ChEBI ID: {info.chebi_id or 'Not found'}")
                print(f"Molecular Formula: {info.molecular_formula}")
                print(f"Molecular Weight: {info.molecular_weight}")
                print(f"IUPAC Name: {info.iupac_name}")
                print(f"Synonyms: {', '.join(info.synonyms[:5])}...")
                print(f"PMIDs: {', '.join(info.pmid_references)}")
            else:
                print(f"ERROR: {info.error}")
            print("=" * 70)

            # Save to file if requested
            if args.output:
                output_file = Path(args.output)
                output_file.parent.mkdir(parents=True, exist_ok=True)
                async with aiofiles.open(output_file, 'w') as f:
                    await f.write(json.dumps(asdict(info), indent=2))
                logger.info(f"Saved to {output_file}")

        elif args.batch:
            # Batch mode
            with open(args.batch, 'r') as f:
                compound_names = [line.strip() for line in f if line.strip()]

            logger.info(f"Processing {len(compound_names)} compounds from {args.batch}")

            results = await fetcher.fetch_batch(compound_names)

            # Save results
            if args.output_dir:
                output_dir = Path(args.output_dir)
                output_dir.mkdir(parents=True, exist_ok=True)

                for info in results:
                    filename = f"{info.query_name.replace(' ', '_')}.json"
                    filepath = output_dir / filename
                    async with aiofiles.open(filepath, 'w') as f:
                        await f.write(json.dumps(asdict(info), indent=2))

                logger.info(f"Saved {len(results)} results to {output_dir}")

            # Print summary
            successful = sum(1 for r in results if r.success)
            with_chebi = sum(1 for r in results if r.chebi_id)

            print("\n" + "=" * 70)
            print("BATCH SUMMARY")
            print("=" * 70)
            print(f"Total compounds: {len(results)}")
            print(f"Successful: {successful}")
            print(f"With ChEBI ID: {with_chebi}")
            print(f"Failed: {len(results) - successful}")
            print("=" * 70)

        else:
            parser.print_help()


if __name__ == '__main__':
    asyncio.run(main())
