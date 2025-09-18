#!/usr/bin/env python3
"""
PubChem Chemical Data Downloader

Downloads chemical property data from PubChem using both bulk FTP files and REST API:
- Bulk FTP files for comprehensive coverage (SDF, IUPAC names, SMILES, synonyms)
- REST API for specific compound queries and property data
- Focus on pKa, charge states, ionization, solubility, and molecular properties

Author: MicroMediaParam Project
"""

import asyncio
import aiohttp
import aiofiles
import json
import gzip
import ftplib
import xml.etree.ElementTree as ET
import logging
import time
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, asdict
from urllib.parse import quote
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class PubChemCompoundData:
    """Container for PubChem chemical data."""
    cid: Optional[str] = None
    name: str = ""
    iupac_name: Optional[str] = None
    molecular_formula: Optional[str] = None
    molecular_weight: Optional[float] = None
    canonical_smiles: Optional[str] = None
    inchi: Optional[str] = None
    inchi_key: Optional[str] = None
    synonyms: List[str] = None
    
    # Chemical properties
    heavy_atom_count: Optional[int] = None
    formal_charge: Optional[int] = None
    hydrogen_bond_donor_count: Optional[int] = None
    hydrogen_bond_acceptor_count: Optional[int] = None
    rotatable_bond_count: Optional[int] = None
    topological_polar_surface_area: Optional[float] = None
    
    # Computed properties
    xlogp: Optional[float] = None  # Log P (partition coefficient)
    complexity: Optional[float] = None
    
    # Experimental properties
    melting_point: Optional[float] = None
    boiling_point: Optional[float] = None
    solubility: Optional[float] = None  # Water solubility in g/L
    pka_values: List[float] = None
    
    # Ionization and charge properties
    charge_states: List[int] = None
    ion_charges: Dict[str, int] = None
    
    # Source tracking
    source: str = "pubchem"
    
    def __post_init__(self):
        if self.synonyms is None:
            self.synonyms = []
        if self.pka_values is None:
            self.pka_values = []
        if self.charge_states is None:
            self.charge_states = []
        if self.ion_charges is None:
            self.ion_charges = {}

class PubChemDataDownloader:
    """
    Download chemical property data from PubChem using bulk files and REST API.
    
    Features:
    - Bulk FTP downloads for comprehensive coverage
    - REST API for specific queries
    - Property extraction focusing on ionization and solubility
    - Robust error handling and caching
    """
    
    def __init__(self, 
                 cache_dir: Path = Path("data/pubchem_cache"),
                 bulk_data_dir: Path = Path("data/pubchem_bulk")):
        self.cache_dir = Path(cache_dir)
        self.bulk_data_dir = Path(bulk_data_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.bulk_data_dir.mkdir(parents=True, exist_ok=True)
        
        # Rate limiting for API requests
        self.api_delay = 0.2  # seconds between API requests
        self.last_api_request = 0
        
        # PubChem API endpoints
        self.rest_api_base = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
        self.power_user_gateway = "https://pubchem.ncbi.nlm.nih.gov/rest/pug_view"
        
        # FTP paths for bulk data
        self.ftp_base = "ftp.ncbi.nlm.nih.gov"
        self.ftp_paths = {
            'iupac_names': '/pubchem/Compound/Extras/CID-IUPAC.gz',
            'smiles': '/pubchem/Compound/Extras/CID-SMILES.gz',
            'synonyms_filtered': '/pubchem/Compound/Extras/CID-Synonym-filtered.gz',
            'synonyms_unfiltered': '/pubchem/Compound/Extras/CID-Synonym-unfiltered.gz'
        }
        
        # Property mapping for API requests
        self.property_keys = [
            'MolecularFormula', 'MolecularWeight', 'IsomericSMILES', 
            'IUPACName', 'InChI', 'InChIKey', 'HeavyAtomCount',
            'Charge', 'HBondDonorCount', 'HBondAcceptorCount',
            'RotatableBondCount', 'TPSA', 'XLogP', 'Complexity'
        ]
        
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=60),
            headers={'User-Agent': 'MicroMediaParam/1.0 (PubChem Chemical Data Pipeline)'}
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    async def _rate_limit_api(self):
        """Enforce rate limiting for API requests."""
        current_time = time.time()
        time_since_last = current_time - self.last_api_request
        if time_since_last < self.api_delay:
            await asyncio.sleep(self.api_delay - time_since_last)
        self.last_api_request = time.time()
    
    def download_bulk_file(self, file_key: str, force_update: bool = False) -> Path:
        """
        Download bulk data file from PubChem FTP.
        
        Args:
            file_key: Key from self.ftp_paths
            force_update: Force re-download even if file exists
            
        Returns:
            Path to downloaded file
        """
        if file_key not in self.ftp_paths:
            raise ValueError(f"Unknown file key: {file_key}")
        
        ftp_path = self.ftp_paths[file_key]
        local_file = self.bulk_data_dir / Path(ftp_path).name
        
        if local_file.exists() and not force_update:
            logger.info(f"Using cached bulk file: {local_file}")
            return local_file
        
        logger.info(f"Downloading bulk file from FTP: {ftp_path}")
        
        try:
            with ftplib.FTP(self.ftp_base) as ftp:
                ftp.login()  # anonymous login
                ftp.cwd(str(Path(ftp_path).parent))
                
                with open(local_file, 'wb') as f:
                    ftp.retrbinary(f'RETR {Path(ftp_path).name}', f.write)
                
                logger.info(f"Downloaded bulk file: {local_file} ({local_file.stat().st_size / 1024 / 1024:.1f} MB)")
                return local_file
                
        except Exception as e:
            logger.error(f"Failed to download bulk file {file_key}: {e}")
            raise
    
    def build_cid_lookup_index(self, force_rebuild: bool = False) -> Dict[str, str]:
        """
        Build CID lookup index from synonyms and IUPAC names for fast compound matching.
        
        Args:
            force_rebuild: Force rebuild even if cached index exists
            
        Returns:
            Dictionary mapping compound names to CIDs
        """
        index_file = self.cache_dir / "cid_lookup_index.json"
        
        if index_file.exists() and not force_rebuild:
            logger.info(f"Loading cached CID lookup index: {index_file}")
            with open(index_file, 'r') as f:
                return json.load(f)
        
        logger.info("Building CID lookup index from bulk data...")
        name_to_cid = {}
        
        # Process IUPAC names
        try:
            iupac_file = self.download_bulk_file('iupac_names')
            logger.info("Processing IUPAC names...")
            
            with gzip.open(iupac_file, 'rt') as f:
                for line_num, line in enumerate(f, 1):
                    if line_num % 100000 == 0:
                        logger.info(f"Processed {line_num:,} IUPAC names")
                    
                    parts = line.strip().split('\t', 1)
                    if len(parts) == 2:
                        cid, iupac_name = parts
                        name_key = iupac_name.lower().strip()
                        if name_key:
                            name_to_cid[name_key] = cid
            
            logger.info(f"Processed {line_num:,} IUPAC names")
            
        except Exception as e:
            logger.warning(f"Failed to process IUPAC names: {e}")
        
        # Process filtered synonyms (more curated)
        try:
            synonyms_file = self.download_bulk_file('synonyms_filtered')
            logger.info("Processing filtered synonyms...")
            
            with gzip.open(synonyms_file, 'rt') as f:
                for line_num, line in enumerate(f, 1):
                    if line_num % 100000 == 0:
                        logger.info(f"Processed {line_num:,} synonym entries")
                    
                    parts = line.strip().split('\t', 1)
                    if len(parts) == 2:
                        cid, synonym = parts
                        name_key = synonym.lower().strip()
                        if name_key and name_key not in name_to_cid:
                            name_to_cid[name_key] = cid
            
            logger.info(f"Processed {line_num:,} synonym entries")
            
        except Exception as e:
            logger.warning(f"Failed to process synonyms: {e}")
        
        # Save index
        logger.info(f"Saving CID lookup index with {len(name_to_cid):,} entries: {index_file}")
        with open(index_file, 'w') as f:
            json.dump(name_to_cid, f, indent=2)
        
        return name_to_cid
    
    def find_cid_for_compound(self, compound_name: str, cid_index: Dict[str, str]) -> Optional[str]:
        """
        Find PubChem CID for a compound name using the lookup index.
        
        Args:
            compound_name: Name of compound to find
            cid_index: CID lookup index
            
        Returns:
            CID string if found, None otherwise
        """
        name_key = compound_name.lower().strip()
        
        # Direct match
        if name_key in cid_index:
            return cid_index[name_key]
        
        # Try common variations
        variations = [
            name_key.replace('-', ' '),
            name_key.replace(' ', '-'),
            name_key.replace('_', ' '),
            name_key.replace(' ', ''),
            name_key.replace('(', '').replace(')', ''),
            name_key.replace('[', '').replace(']', ''),
        ]
        
        for variation in variations:
            if variation in cid_index:
                return cid_index[variation]
        
        # Partial matches for compound names with hydration, stereochemistry, etc.
        for indexed_name, cid in cid_index.items():
            if name_key in indexed_name or indexed_name in name_key:
                if len(name_key) > 3 and len(indexed_name) > 3:  # Avoid very short matches
                    return cid
        
        return None
    
    async def get_compound_properties_by_cid(self, cid: str) -> Optional[Dict]:
        """
        Get compound properties from PubChem API using CID.
        
        Args:
            cid: PubChem Compound ID
            
        Returns:
            Dictionary with compound properties
        """
        await self._rate_limit_api()
        
        try:
            # Get basic properties
            props_url = f"{self.rest_api_base}/compound/cid/{cid}/property/{','.join(self.property_keys)}/JSON"
            
            async with self.session.get(props_url) as response:
                if response.status == 200:
                    data = await response.json()
                    properties = data.get('PropertyTable', {}).get('Properties', [{}])[0]
                    
                    # Get additional experimental data
                    experimental_data = await self.get_experimental_properties(cid)
                    
                    # Combine basic and experimental properties
                    combined_data = {
                        'cid': cid,
                        'properties': properties,
                        'experimental': experimental_data
                    }
                    
                    return combined_data
                else:
                    logger.debug(f"API request failed for CID {cid}: {response.status}")
                    return None
                    
        except Exception as e:
            logger.warning(f"Failed to get properties for CID {cid}: {e}")
            return None
    
    async def get_experimental_properties(self, cid: str) -> Dict:
        """
        Get experimental properties like pKa, solubility from PubChem annotations.
        
        Args:
            cid: PubChem Compound ID
            
        Returns:
            Dictionary with experimental properties
        """
        await self._rate_limit_api()
        
        experimental_data = {
            'pka_values': [],
            'solubility': None,
            'melting_point': None,
            'boiling_point': None
        }
        
        try:
            # Get experimental data from PubChem annotations
            annotations_url = f"{self.power_user_gateway}/data/compound/{cid}/JSON"
            
            async with self.session.get(annotations_url) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Extract experimental properties from annotations
                    record = data.get('Record', {})
                    sections = record.get('Section', [])
                    
                    # Parse experimental data sections
                    for section in sections:
                        section_name = section.get('TOCHeading', '').lower()
                        
                        if 'physical' in section_name or 'chemical' in section_name:
                            self._extract_physical_properties(section, experimental_data)
                        elif 'pharmacology' in section_name:
                            self._extract_pka_values(section, experimental_data)
                
        except Exception as e:
            logger.debug(f"Failed to get experimental data for CID {cid}: {e}")
        
        return experimental_data
    
    def _extract_physical_properties(self, section: Dict, experimental_data: Dict):
        """Extract physical properties from PubChem section data."""
        subsections = section.get('Section', [])
        
        for subsection in subsections:
            heading = subsection.get('TOCHeading', '').lower()
            
            if 'solubility' in heading:
                self._extract_solubility(subsection, experimental_data)
            elif 'melting' in heading or 'mp' in heading:
                self._extract_melting_point(subsection, experimental_data)
            elif 'boiling' in heading or 'bp' in heading:
                self._extract_boiling_point(subsection, experimental_data)
    
    def _extract_pka_values(self, section: Dict, experimental_data: Dict):
        """Extract pKa values from PubChem section data."""
        # Look for pKa values in text content
        information = section.get('Information', [])
        
        for info in information:
            description = info.get('Description', '')
            value_info = info.get('Value', {})
            string_values = value_info.get('StringWithMarkup', [])
            
            # Search for pKa patterns in text
            for string_val in string_values:
                text = string_val.get('String', '')
                pka_matches = re.findall(r'pka?\s*[=:]?\s*([0-9]+\.?[0-9]*)', text.lower())
                
                for match in pka_matches:
                    try:
                        pka_val = float(match)
                        if 0 <= pka_val <= 14:  # Reasonable pKa range
                            experimental_data['pka_values'].append(pka_val)
                    except ValueError:
                        continue
    
    def _extract_solubility(self, section: Dict, experimental_data: Dict):
        """Extract water solubility from PubChem section data."""
        information = section.get('Information', [])
        
        for info in information:
            value_info = info.get('Value', {})
            string_values = value_info.get('StringWithMarkup', [])
            
            for string_val in string_values:
                text = string_val.get('String', '')
                
                # Look for solubility in g/L or mg/mL patterns
                solubility_patterns = [
                    r'([0-9]+\.?[0-9]*)\s*g/l',
                    r'([0-9]+\.?[0-9]*)\s*mg/ml',
                    r'([0-9]+\.?[0-9]*)\s*g\s*/\s*l',
                    r'([0-9]+\.?[0-9]*)\s*mg\s*/\s*ml'
                ]
                
                for pattern in solubility_patterns:
                    matches = re.findall(pattern, text.lower())
                    if matches:
                        try:
                            value = float(matches[0])
                            if 'mg/ml' in pattern:
                                value = value  # mg/mL is same as g/L
                            experimental_data['solubility'] = value
                            return
                        except ValueError:
                            continue
    
    def _extract_melting_point(self, section: Dict, experimental_data: Dict):
        """Extract melting point from PubChem section data."""
        # Similar pattern to solubility extraction
        pass  # Implement if needed
    
    def _extract_boiling_point(self, section: Dict, experimental_data: Dict):
        """Extract boiling point from PubChem section data."""
        # Similar pattern to solubility extraction
        pass  # Implement if needed
    
    async def download_compound_data(self, compound_name: str, cid_index: Dict[str, str]) -> Optional[PubChemCompoundData]:
        """
        Download comprehensive data for a single compound.
        
        Args:
            compound_name: Name of compound to download
            cid_index: CID lookup index for name resolution
            
        Returns:
            PubChemCompoundData object or None if not found
        """
        # Find CID
        cid = self.find_cid_for_compound(compound_name, cid_index)
        if not cid:
            logger.debug(f"No CID found for compound: {compound_name}")
            return None
        
        # Get properties
        compound_data = await self.get_compound_properties_by_cid(cid)
        if not compound_data:
            logger.debug(f"No properties found for CID {cid} ({compound_name})")
            return None
        
        # Parse and structure the data
        properties = compound_data.get('properties', {})
        experimental = compound_data.get('experimental', {})
        
        # Create compound data object
        pubchem_compound = PubChemCompoundData(
            cid=cid,
            name=compound_name,
            iupac_name=properties.get('IUPACName'),
            molecular_formula=properties.get('MolecularFormula'),
            molecular_weight=float(properties.get('MolecularWeight', 0)) if properties.get('MolecularWeight') else None,
            canonical_smiles=properties.get('IsomericSMILES'),
            inchi=properties.get('InChI'),
            inchi_key=properties.get('InChIKey'),
            
            # Structural properties
            heavy_atom_count=properties.get('HeavyAtomCount'),
            formal_charge=properties.get('Charge'),
            hydrogen_bond_donor_count=properties.get('HBondDonorCount'),
            hydrogen_bond_acceptor_count=properties.get('HBondAcceptorCount'),
            rotatable_bond_count=properties.get('RotatableBondCount'),
            topological_polar_surface_area=properties.get('TPSA'),
            
            # Computed properties
            xlogp=properties.get('XLogP'),
            complexity=properties.get('Complexity'),
            
            # Experimental properties
            pka_values=experimental.get('pka_values', []),
            solubility=experimental.get('solubility'),
            melting_point=experimental.get('melting_point'),
            boiling_point=experimental.get('boiling_point'),
            
            source="pubchem"
        )
        
        # Estimate charge states and ion charges from molecular formula and pKa
        self._estimate_ionization_properties(pubchem_compound)
        
        return pubchem_compound
    
    def _estimate_ionization_properties(self, compound: PubChemCompoundData):
        """
        Estimate charge states and ion charges from molecular formula and pKa values.
        
        Args:
            compound: PubChemCompoundData object to update
        """
        # Determine charge states from pKa values
        if compound.pka_values:
            num_ionizable = len(compound.pka_values)
            compound.charge_states = list(range(-num_ionizable, num_ionizable + 1))
        else:
            # Default to neutral if no pKa data
            compound.charge_states = [0]
        
        # Parse molecular formula for common ions
        if compound.molecular_formula:
            compound.ion_charges = self._parse_ion_charges_from_formula(compound.molecular_formula)
    
    def _parse_ion_charges_from_formula(self, formula: str) -> Dict[str, int]:
        """Parse ion charges from molecular formula."""
        ion_charges = {}
        
        # Common ion patterns
        common_ions = {
            'Na': {'Na+': 1},
            'K': {'K+': 1},
            'Ca': {'Ca2+': 2},
            'Mg': {'Mg2+': 2},
            'Cl': {'Cl-': -1},
            'SO4': {'SO42-': -2},
            'PO4': {'PO43-': -3},
            'CO3': {'CO32-': -2},
            'NO3': {'NO3-': -1}
        }
        
        # Simple pattern matching for common ionic compounds
        for element, charges in common_ions.items():
            if element in formula:
                ion_charges.update(charges)
        
        return ion_charges
    
    async def download_compounds_batch(self, compound_names: List[str]) -> List[PubChemCompoundData]:
        """
        Download data for multiple compounds with robust error handling.
        
        Args:
            compound_names: List of compound names to download
            
        Returns:
            List of PubChemCompoundData objects
        """
        logger.info(f"Starting PubChem data download for {len(compound_names)} compounds")
        
        # Build CID lookup index
        cid_index = self.build_cid_lookup_index()
        logger.info(f"CID lookup index loaded with {len(cid_index):,} entries")
        
        # Download compounds
        results = []
        failed_compounds = []
        
        for i, compound_name in enumerate(compound_names, 1):
            if i % 50 == 0:
                logger.info(f"Progress: {i}/{len(compound_names)} compounds processed")
            
            try:
                compound_data = await self.download_compound_data(compound_name, cid_index)
                if compound_data:
                    results.append(compound_data)
                    logger.debug(f"Downloaded data for: {compound_name}")
                else:
                    failed_compounds.append(compound_name)
                    logger.debug(f"No data found for: {compound_name}")
                    
            except Exception as e:
                failed_compounds.append(compound_name)
                logger.warning(f"Download failed for {compound_name}: {e}")
        
        logger.info(f"PubChem download completed: {len(results)} successful, {len(failed_compounds)} failed")
        
        if failed_compounds:
            logger.info(f"Failed compounds: {failed_compounds[:10]}{'...' if len(failed_compounds) > 10 else ''}")
        
        return results
    
    async def save_compounds_data(self, compounds: List[PubChemCompoundData], output_file: Path):
        """Save compound data to JSON file."""
        json_data = [asdict(compound) for compound in compounds]
        
        async with aiofiles.open(output_file, 'w') as f:
            await f.write(json.dumps(json_data, indent=2))
        
        logger.info(f"Saved PubChem data for {len(compounds)} compounds to: {output_file}")

async def main():
    """Test the PubChem downloader."""
    test_compounds = [
        "sodium chloride", "glucose", "calcium carbonate", 
        "glycine", "aspirin", "caffeine"
    ]
    
    async with PubChemDataDownloader() as downloader:
        compounds = await downloader.download_compounds_batch(test_compounds)
        
        print(f"\nDownloaded data for {len(compounds)} compounds:")
        for compound in compounds:
            print(f"- {compound.name} (CID: {compound.cid})")
            print(f"  Formula: {compound.molecular_formula}")
            print(f"  MW: {compound.molecular_weight}")
            print(f"  pKa: {compound.pka_values}")
            print(f"  Solubility: {compound.solubility} g/L")
            print()

if __name__ == "__main__":
    asyncio.run(main())