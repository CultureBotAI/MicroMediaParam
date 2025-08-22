#!/usr/bin/env python3
"""
Chemical Property Extractor

Extracts and processes chemical properties from downloaded data sources.
Handles pKa calculation, ion charge determination, and solubility processing.

Author: MicroMediaParam Project
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ProcessedChemicalProperties:
    """Processed chemical properties ready for TSV generation."""
    compound_name: str
    molecular_weight: float
    pka_values: List[float]
    charge_states: List[int]
    ion_charges: Dict[str, int]
    solubility_g_per_L: float
    activity_coefficient: float
    description: str
    formula: Optional[str] = None
    source: str = "processed"

class ChemicalPropertyExtractor:
    """
    Extract and process chemical properties from raw downloaded data.
    
    Capabilities:
    - Parse molecular formulas to determine ion charges
    - Estimate pKa values based on functional groups
    - Process solubility data from multiple sources
    - Generate charge state information
    """
    
    def __init__(self):
        self.pka_database = self._build_pka_database()
        self.ion_charge_rules = self._build_ion_charge_rules()
        self.functional_group_patterns = self._build_functional_group_patterns()
    
    def _build_pka_database(self) -> Dict[str, List[float]]:
        """Build database of known pKa values for common compounds."""
        return {
            # Inorganic acids
            'phosphoric acid': [2.15, 7.20, 12.35],
            'carbonic acid': [6.37, 10.33],
            'sulfuric acid': [-3.0, 1.9],  # First pKa very low
            'hydrochloric acid': [-7.0],   # Strong acid
            'nitric acid': [-1.4],         # Strong acid
            'boric acid': [9.24, 12.74, 13.80],
            
            # Amino acids
            'glycine': [2.34, 9.60],
            'alanine': [2.34, 9.69], 
            'cysteine': [1.96, 8.18, 10.28],
            'glutamic acid': [2.19, 4.25, 9.67],
            'lysine': [2.18, 8.95, 10.53],
            'histidine': [1.82, 6.00, 9.17],
            
            # Organic acids
            'acetic acid': [4.76],
            'citric acid': [3.13, 4.76, 6.40],
            'lactic acid': [3.86],
            'pyruvic acid': [2.50],
            'formic acid': [3.75],
            'succinic acid': [4.21, 5.64],
            'malic acid': [3.40, 5.20],
            'fumaric acid': [3.03, 4.44],
            
            # Buffers
            'tris': [8.07],
            'hepes': [7.55],
            'mes': [6.15],
            'mops': [7.20],
            'pipes': [6.76],
            'bis-tris': [6.50],
            
            # Nitrogen compounds
            'ammonia': [9.25],
            'imidazole': [6.95],
            'ethanolamine': [9.50],
            
            # Vitamins and cofactors
            'ascorbic acid': [4.10, 11.79],
            'nicotinic acid': [2.00, 4.85],
            'pantothenic acid': [4.40]
        }
    
    def _build_ion_charge_rules(self) -> Dict[str, Dict[str, int]]:
        """Build rules for determining ion charges from chemical formulas."""
        return {
            # Common cations
            'Na': {'Na+': 1},
            'K': {'K+': 1},
            'Li': {'Li+': 1},
            'Mg': {'Mg2+': 2},
            'Ca': {'Ca2+': 2},
            'Fe': {'Fe2+': 2, 'Fe3+': 3},  # Can be both
            'Zn': {'Zn2+': 2},
            'Cu': {'Cu+': 1, 'Cu2+': 2},  # Can be both
            'Mn': {'Mn2+': 2},
            'Co': {'Co2+': 2},
            'Ni': {'Ni2+': 2},
            'Al': {'Al3+': 3},
            'NH4': {'NH4+': 1},
            
            # Common anions
            'Cl': {'Cl-': -1},
            'Br': {'Br-': -1},
            'I': {'I-': -1},
            'F': {'F-': -1},
            'SO4': {'SO42-': -2},
            'PO4': {'PO43-': -3},
            'NO3': {'NO3-': -1},
            'CO3': {'CO32-': -2},
            'HCO3': {'HCO3-': -1},
            'OH': {'OH-': -1},
            'HPO4': {'HPO42-': -2},
            'H2PO4': {'H2PO4-': -1},
            
            # Organic anions
            'CH3COO': {'CH3COO-': -1},   # Acetate
            'HCOO': {'HCOO-': -1},       # Formate
            'C6H5COO': {'C6H5COO-': -1}, # Benzoate
        }
    
    def _build_functional_group_patterns(self) -> Dict[str, float]:
        """Build patterns for estimating pKa values from functional groups."""
        return {
            r'COOH': 4.5,      # Carboxylic acid
            r'NH2': 9.0,       # Primary amine
            r'NH3\+': 9.5,     # Ammonium
            r'OH.*phenol': 10.0, # Phenolic OH
            r'SH': 8.5,        # Thiol
            r'PO4': 7.0,       # Phosphate (middle pKa)
            r'SO3H': 2.0,      # Sulfonic acid
            r'imidazole': 7.0, # Imidazole ring
        }
    
    def parse_molecular_formula(self, formula: str) -> Tuple[Dict[str, int], Dict[str, int]]:
        """
        Parse molecular formula to extract cations and anions.
        
        Args:
            formula: Chemical formula (e.g., "CaCl2", "Na2SO4")
            
        Returns:
            Tuple of (element_counts, ion_charges)
        """
        if not formula:
            return {}, {}
        
        # Simple formula parsing (would need more sophisticated parser for complex formulas)
        element_counts = {}
        ion_charges = {}
        
        # Pattern to match element and count: Element + optional count
        pattern = r'([A-Z][a-z]?)(\d*)'
        matches = re.findall(pattern, formula)
        
        for element, count_str in matches:
            count = int(count_str) if count_str else 1
            element_counts[element] = count
        
        # Determine likely ions based on common compounds
        if 'Na' in element_counts and 'Cl' in element_counts:
            ion_charges.update({'Na+': 1, 'Cl-': -1})
        elif 'Ca' in element_counts and 'Cl' in element_counts:
            ion_charges.update({'Ca2+': 2, 'Cl-': -1})
        elif 'Mg' in element_counts and 'SO4' in formula:
            ion_charges.update({'Mg2+': 2, 'SO42-': -2})
        # Add more rules as needed
        
        return element_counts, ion_charges
    
    def estimate_pka_values(self, compound_name: str, formula: str = "") -> List[float]:
        """
        Estimate pKa values for a compound.
        
        Args:
            compound_name: Name of the compound
            formula: Chemical formula
            
        Returns:
            List of estimated pKa values
        """
        name_lower = compound_name.lower()
        
        # Check direct database match
        for known_compound, pka_values in self.pka_database.items():
            if known_compound in name_lower or name_lower in known_compound:
                return pka_values
        
        # Pattern-based estimation
        estimated_pkas = []
        
        # Check for common patterns in name
        if 'phosphate' in name_lower:
            estimated_pkas = [2.15, 7.20, 12.35]
        elif 'carbonate' in name_lower:
            estimated_pkas = [6.37, 10.33]
        elif 'bicarbonate' in name_lower:
            estimated_pkas = [6.37, 10.33]
        elif 'acetate' in name_lower:
            estimated_pkas = [4.76]
        elif 'chloride' in name_lower or 'sulfate' in name_lower:
            estimated_pkas = []  # Strong electrolytes
        elif any(acid in name_lower for acid in ['amino', 'glycine', 'alanine']):
            estimated_pkas = [2.3, 9.6]  # Typical amino acid
        elif 'tris' in name_lower:
            estimated_pkas = [8.07]
        elif 'hepes' in name_lower:
            estimated_pkas = [7.55]
        
        return estimated_pkas
    
    def determine_charge_states(self, pka_values: List[float]) -> List[int]:
        """
        Determine possible charge states based on pKa values.
        
        Args:
            pka_values: List of pKa values
            
        Returns:
            List of possible charge states
        """
        if not pka_values:
            return [0]  # Neutral molecule
        
        # For each pKa, compound can lose a proton (become more negative)
        # Charge states range from +1 to -(len(pka_values))
        num_pkas = len(pka_values)
        charge_states = list(range(1, -num_pkas - 1, -1))
        
        return charge_states
    
    def estimate_solubility(self, compound_name: str, formula: str = "") -> float:
        """
        Estimate solubility in g/L based on compound type.
        
        Args:
            compound_name: Name of the compound
            formula: Chemical formula
            
        Returns:
            Estimated solubility in g/L
        """
        name_lower = compound_name.lower()
        
        # Known solubilities (g/L at 20°C)
        known_solubilities = {
            'sodium chloride': 360.0,
            'potassium chloride': 344.0,
            'magnesium chloride': 546.0,
            'calcium chloride': 745.0,
            'sodium sulfate': 284.0,
            'magnesium sulfate': 353.0,
            'glucose': 909.0,
            'sucrose': 2000.0,
            'calcium carbonate': 0.0013,
            'sodium bicarbonate': 96.0,
            'sodium carbonate': 215.0,
            'boric acid': 49.8,
        }
        
        # Direct lookup
        for known_compound, solubility in known_solubilities.items():
            if known_compound in name_lower:
                return solubility
        
        # Pattern-based estimation
        if 'chloride' in name_lower:
            return 400.0  # Most chlorides are highly soluble
        elif 'sulfate' in name_lower:
            return 300.0  # Most sulfates are soluble
        elif 'carbonate' in name_lower and 'sodium' not in name_lower:
            return 0.01   # Most carbonates (except Na, K) are insoluble
        elif 'phosphate' in name_lower:
            return 100.0  # Variable solubility
        elif any(sugar in name_lower for sugar in ['glucose', 'sucrose', 'fructose']):
            return 1000.0 # Sugars are highly soluble
        elif any(aa in name_lower for aa in ['glycine', 'alanine', 'amino']):
            return 200.0  # Amino acids are moderately soluble
        else:
            return 100.0  # Default moderate solubility
    
    def process_raw_data(self, raw_data_file: Path) -> List[ProcessedChemicalProperties]:
        """
        Process raw downloaded data into structured chemical properties.
        
        Args:
            raw_data_file: Path to JSON file with raw data
            
        Returns:
            List of ProcessedChemicalProperties objects
        """
        with open(raw_data_file, 'r') as f:
            raw_data = json.load(f)
        
        processed_compounds = []
        seen_compounds = set()  # Avoid duplicates
        
        # Process data from each source
        for source, compounds in raw_data.items():
            logger.info(f"Processing {len(compounds)} compounds from {source}")
            
            for compound_data in compounds:
                name = compound_data.get('name', '').strip()
                if not name or name.lower() in seen_compounds:
                    continue
                
                seen_compounds.add(name.lower())
                
                # Extract basic properties
                formula = compound_data.get('formula', '')
                molecular_weight = compound_data.get('molecular_weight')
                
                # If no molecular weight from source, estimate
                if not molecular_weight:
                    molecular_weight = self._estimate_molecular_weight(name, formula)
                
                # Estimate chemical properties
                pka_values = self.estimate_pka_values(name, formula)
                charge_states = self.determine_charge_states(pka_values)
                element_counts, ion_charges = self.parse_molecular_formula(formula)
                solubility = compound_data.get('solubility') or self.estimate_solubility(name, formula)
                
                # Create processed compound
                processed = ProcessedChemicalProperties(
                    compound_name=name.lower().replace(' ', '_'),
                    molecular_weight=molecular_weight or 100.0,  # Default if unknown
                    pka_values=pka_values,
                    charge_states=charge_states,
                    ion_charges=ion_charges,
                    solubility_g_per_L=solubility,
                    activity_coefficient=1.0,  # Default
                    description=name,
                    formula=formula,
                    source=source
                )
                
                processed_compounds.append(processed)
                logger.debug(f"Processed {name}: MW={molecular_weight}, pKa={pka_values}")
        
        logger.info(f"Processed {len(processed_compounds)} unique compounds")
        return processed_compounds
    
    def process_raw_data_list(self, raw_data_file: Path) -> List[ProcessedChemicalProperties]:
        """
        Process raw chemical data from list format JSON file.
        
        Args:
            raw_data_file: Path to JSON file with list of chemical data
            
        Returns:
            List of processed chemical properties
        """
        with open(raw_data_file, 'r') as f:
            raw_data = json.load(f)
        
        if not isinstance(raw_data, list):
            raise ValueError("Expected list format for raw data")
        
        processed_compounds = []
        seen_compounds = set()  # Avoid duplicates
        
        logger.info(f"Processing {len(raw_data)} compounds from list format")
        
        for compound_data in raw_data:
            name = compound_data.get('name', '').strip()
            if not name or name.lower() in seen_compounds:
                continue
            
            seen_compounds.add(name.lower())
            
            # Extract basic properties
            formula = compound_data.get('formula', '')
            molecular_weight = compound_data.get('molecular_weight')
            
            # If no molecular weight from source, estimate
            if not molecular_weight and formula:
                try:
                    molecular_weight = self.estimate_molecular_weight(formula)
                except:
                    molecular_weight = None
            
            # Get or estimate pKa values
            pka_values = compound_data.get('pka_values', [])
            if not pka_values and formula:
                pka_values = self.estimate_pka_values(name, formula)
            
            # Determine charge states
            charge_states = self.determine_charge_states(pka_values)
            
            # Get ion charges from molecular formula
            try:
                elements, ion_charges = self.parse_molecular_formula(formula)
            except:
                ion_charges = {}
            
            # Estimate solubility
            solubility = compound_data.get('solubility')
            if solubility is None:
                solubility = self.estimate_solubility(name, formula)
            
            # Create processed compound
            processed_compound = ProcessedChemicalProperties(
                compound_name=name,
                molecular_weight=molecular_weight or 100.0,  # Default if not available
                pka_values=pka_values,
                charge_states=charge_states,
                ion_charges=ion_charges,
                solubility_g_per_L=solubility,
                activity_coefficient=1.0,  # Default
                description=f"Processed from IUPAC sources",
                formula=formula,
                source=', '.join(compound_data.get('sources', ['unknown']))
            )
            
            processed_compounds.append(processed_compound)
            logger.debug(f"Processed compound: {name}")
        
        logger.info(f"Successfully processed {len(processed_compounds)} unique compounds")
        return processed_compounds
    
    def _estimate_molecular_weight(self, name: str, formula: str) -> Optional[float]:
        """Estimate molecular weight from name or formula."""
        # Simple estimation based on common compounds
        estimates = {
            'sodium chloride': 58.44,
            'glucose': 180.16,
            'calcium carbonate': 100.09,
            'potassium chloride': 74.55,
            'magnesium sulfate': 120.37,
        }
        
        name_lower = name.lower()
        for compound, mw in estimates.items():
            if compound in name_lower:
                return mw
        
        return None
    
    def save_processed_data(self, processed_compounds: List[ProcessedChemicalProperties], 
                          output_file: Path):
        """Save processed chemical properties to JSON file."""
        data = []
        for compound in processed_compounds:
            data.append({
                'compound_name': compound.compound_name,
                'molecular_weight': compound.molecular_weight,
                'pka_values': compound.pka_values,
                'charge_states': compound.charge_states,
                'ion_charges': compound.ion_charges,
                'solubility_g_per_L': compound.solubility_g_per_L,
                'activity_coefficient': compound.activity_coefficient,
                'description': compound.description,
                'formula': compound.formula,
                'source': compound.source
            })
        
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Saved processed data for {len(processed_compounds)} compounds to {output_file}")

def main():
    """Test the property extractor."""
    extractor = ChemicalPropertyExtractor()
    
    # Test individual functions
    print("Testing pKa estimation:")
    test_compounds = [
        "sodium chloride", "glucose", "glycine", "phosphoric acid",
        "calcium carbonate", "tris buffer"
    ]
    
    for compound in test_compounds:
        pka_values = extractor.estimate_pka_values(compound)
        solubility = extractor.estimate_solubility(compound)
        print(f"{compound}: pKa={pka_values}, solubility={solubility} g/L")

if __name__ == "__main__":
    main()