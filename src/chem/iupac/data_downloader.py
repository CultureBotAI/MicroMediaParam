#!/usr/bin/env python3
"""
IUPAC Chemical Data Downloader

Downloads chemical property data from multiple authoritative sources:
- NIST Chemistry WebBook
- ChEBI database
- PubChem
- IUPAC Nomenclature data

Author: MicroMediaParam Project
"""

import asyncio
import aiohttp
import aiofiles
import json
import csv
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from urllib.parse import urlencode, quote
import xml.etree.ElementTree as ET

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ChemicalData:
    """Container for chemical data from various sources."""
    name: str
    formula: str
    cas_number: Optional[str] = None
    chebi_id: Optional[str] = None
    pubchem_cid: Optional[str] = None
    molecular_weight: Optional[float] = None
    pka_values: Optional[List[float]] = None
    solubility: Optional[float] = None
    melting_point: Optional[float] = None
    boiling_point: Optional[float] = None
    source: str = "unknown"

class IUPACDataDownloader:
    """
    Download chemical property data from multiple authoritative sources.
    
    Supports:
    - NIST Chemistry WebBook API
    - ChEBI REST API  
    - PubChem REST API
    - Manual IUPAC compound lists
    """
    
    def __init__(self, output_dir: Path = Path("data/chemical_sources")):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Rate limiting
        self.request_delay = 0.5  # seconds between requests
        self.last_request_time = 0
        
        # Target compounds for media analysis
        self.target_compounds = [
            # Inorganic salts
            "sodium chloride", "potassium chloride", "magnesium chloride", 
            "calcium chloride", "ammonium chloride", "sodium sulfate",
            "magnesium sulfate", "calcium carbonate", "sodium bicarbonate",
            "sodium carbonate", "potassium phosphate", "sodium phosphate",
            
            # Trace elements
            "iron sulfate", "zinc sulfate", "copper sulfate", "manganese sulfate",
            "iron chloride", "zinc chloride", "nickel chloride", "cobalt chloride",
            "copper chloride", "boric acid",
            
            # Nutrients and carbon sources
            "glucose", "sucrose", "fructose", "lactose", "maltose",
            "sodium acetate", "sodium pyruvate", "sodium citrate",
            
            # Amino acids
            "glycine", "alanine", "cysteine", "glutamine", "asparagine",
            
            # Buffers
            "tris", "hepes", "mes", "mops", "pipes",
            
            # Growth factors
            "thiamine", "riboflavin", "nicotinic acid", "biotin",
            "folic acid", "pyridoxine", "cobalamin"
        ]
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={'User-Agent': 'MicroMediaParam/1.0 (Chemical Data Downloader)'}
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    async def _rate_limited_request(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """Make rate-limited HTTP request."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.request_delay:
            await asyncio.sleep(self.request_delay - time_since_last)
        
        self.last_request_time = time.time()
        return await self.session.get(url, **kwargs)
    
    async def download_chebi_data(self, compound_names: List[str]) -> List[ChemicalData]:
        """
        Download chemical data from ChEBI REST API.
        
        Args:
            compound_names: List of compound names to search
            
        Returns:
            List of ChemicalData objects
        """
        results = []
        
        for compound_name in compound_names:
            try:
                # Search ChEBI by name
                search_url = f"https://www.ebi.ac.uk/chebi/searchId.do"
                params = {
                    'chebiName': compound_name,
                    'searchCategory': 'CHEBI NAME',
                    'maximumResults': 5
                }
                
                async with await self._rate_limited_request(search_url, params=params) as response:
                    if response.status == 200:
                        # Parse ChEBI search results (simplified)
                        text = await response.text()
                        # Note: ChEBI returns HTML, would need proper parsing
                        # For now, create placeholder data
                        
                        result = ChemicalData(
                            name=compound_name,
                            formula="",  # Would extract from response
                            source="chebi"
                        )
                        results.append(result)
                        
                        logger.info(f"Downloaded ChEBI data for {compound_name}")
                    else:
                        logger.warning(f"ChEBI request failed for {compound_name}: {response.status}")
                        
            except Exception as e:
                logger.error(f"Error downloading ChEBI data for {compound_name}: {e}")
                
        return results
    
    async def download_pubchem_data(self, compound_names: List[str]) -> List[ChemicalData]:
        """
        Download chemical data from PubChem REST API.
        
        Args:
            compound_names: List of compound names to search
            
        Returns:
            List of ChemicalData objects
        """
        results = []
        
        for compound_name in compound_names:
            try:
                # Search PubChem by name
                search_url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{quote(compound_name)}/JSON"
                
                async with await self._rate_limited_request(search_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if 'PC_Compounds' in data and data['PC_Compounds']:
                            compound = data['PC_Compounds'][0]
                            
                            # Extract molecular formula
                            formula = ""
                            if 'props' in compound:
                                for prop in compound['props']:
                                    if prop.get('urn', {}).get('label') == 'Molecular Formula':
                                        formula = prop.get('value', {}).get('sval', '')
                                        break
                            
                            # Extract molecular weight
                            molecular_weight = None
                            if 'props' in compound:
                                for prop in compound['props']:
                                    if prop.get('urn', {}).get('label') == 'Molecular Weight':
                                        molecular_weight = prop.get('value', {}).get('fval')
                                        break
                            
                            result = ChemicalData(
                                name=compound_name,
                                formula=formula,
                                pubchem_cid=str(compound.get('id', {}).get('id', {}).get('cid', '')),
                                molecular_weight=molecular_weight,
                                source="pubchem"
                            )
                            results.append(result)
                            
                            logger.info(f"Downloaded PubChem data for {compound_name}")
                        else:
                            logger.warning(f"No PubChem data found for {compound_name}")
                            
                    else:
                        logger.warning(f"PubChem request failed for {compound_name}: {response.status}")
                        
            except Exception as e:
                logger.error(f"Error downloading PubChem data for {compound_name}: {e}")
                
        return results
    
    async def download_nist_data(self, compound_names: List[str]) -> List[ChemicalData]:
        """
        Download chemical data from NIST Chemistry WebBook.
        
        Note: NIST doesn't have a public API, so this would require web scraping
        or manual data entry. For now, returns placeholder data.
        
        Args:
            compound_names: List of compound names to search
            
        Returns:
            List of ChemicalData objects
        """
        results = []
        
        # NIST data would require web scraping or manual entry
        # For demonstration, create placeholder entries
        nist_data = {
            "sodium chloride": {
                "formula": "NaCl", 
                "molecular_weight": 58.44,
                "solubility": 360.0  # g/L at 20°C
            },
            "glucose": {
                "formula": "C6H12O6",
                "molecular_weight": 180.16,
                "solubility": 909.0
            },
            "calcium carbonate": {
                "formula": "CaCO3",
                "molecular_weight": 100.09,
                "solubility": 0.0013
            }
        }
        
        for compound_name in compound_names:
            if compound_name.lower() in nist_data:
                data = nist_data[compound_name.lower()]
                result = ChemicalData(
                    name=compound_name,
                    formula=data["formula"],
                    molecular_weight=data["molecular_weight"],
                    solubility=data.get("solubility"),
                    source="nist"
                )
                results.append(result)
                logger.info(f"Found NIST data for {compound_name}")
        
        return results
    
    async def download_all_sources(self, compound_names: Optional[List[str]] = None) -> Dict[str, List[ChemicalData]]:
        """
        Download chemical data from all available sources.
        
        Args:
            compound_names: List of compound names. If None, uses target_compounds
            
        Returns:
            Dictionary mapping source names to lists of ChemicalData
        """
        if compound_names is None:
            compound_names = self.target_compounds
        
        logger.info(f"Downloading chemical data for {len(compound_names)} compounds")
        
        # Download from all sources concurrently
        results = {}
        
        try:
            # PubChem (most reliable API)
            logger.info("Downloading from PubChem...")
            results['pubchem'] = await self.download_pubchem_data(compound_names)
            
            # NIST (manual/curated data)
            logger.info("Loading NIST data...")
            results['nist'] = await self.download_nist_data(compound_names)
            
            # ChEBI (would need proper implementation)
            logger.info("Downloading from ChEBI...")
            results['chebi'] = await self.download_chebi_data(compound_names[:5])  # Limit for demo
            
        except Exception as e:
            logger.error(f"Error downloading chemical data: {e}")
            
        return results
    
    async def save_raw_data(self, data: Dict[str, List[ChemicalData]], filename: str = "raw_chemical_data.json"):
        """Save raw downloaded data to JSON file."""
        output_file = self.output_dir / filename
        
        # Convert dataclasses to dictionaries for JSON serialization
        json_data = {}
        for source, compounds in data.items():
            json_data[source] = []
            for compound in compounds:
                compound_dict = {
                    'name': compound.name,
                    'formula': compound.formula,
                    'cas_number': compound.cas_number,
                    'chebi_id': compound.chebi_id,
                    'pubchem_cid': compound.pubchem_cid,
                    'molecular_weight': compound.molecular_weight,
                    'pka_values': compound.pka_values,
                    'solubility': compound.solubility,
                    'melting_point': compound.melting_point,
                    'boiling_point': compound.boiling_point,
                    'source': compound.source
                }
                json_data[source].append(compound_dict)
        
        async with aiofiles.open(output_file, 'w') as f:
            await f.write(json.dumps(json_data, indent=2))
        
        logger.info(f"Saved raw chemical data to {output_file}")

async def main():
    """Main function for testing the downloader."""
    async with IUPACDataDownloader() as downloader:
        # Download data for a subset of compounds
        test_compounds = [
            "sodium chloride", "glucose", "calcium carbonate", 
            "potassium phosphate", "glycine"
        ]
        
        data = await downloader.download_all_sources(test_compounds)
        await downloader.save_raw_data(data)
        
        # Print summary
        total_compounds = sum(len(compounds) for compounds in data.values())
        logger.info(f"Downloaded data for {total_compounds} total compound entries")
        
        for source, compounds in data.items():
            logger.info(f"{source}: {len(compounds)} compounds")

if __name__ == "__main__":
    asyncio.run(main())