#!/usr/bin/env python3
"""
PubChem Chemical Property Extractor

Converts PubChem data to standardized chemical properties format
compatible with the MicroMediaParam pipeline.

Focus on:
- pKa values and charge states
- Ionization properties
- Solubility data
- Molecular properties for pH/salinity calculations

Author: MicroMediaParam Project
"""

import json
import math
import logging
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from .data_downloader import PubChemCompoundData

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ProcessedChemicalProperties:
    """Standardized chemical properties format for MicroMediaParam."""
    compound_name: str
    molecular_weight: float
    pka_values: List[float]
    charge_states: List[int]
    ion_charges: Dict[str, int]
    solubility_g_per_L: float
    activity_coefficient: float
    description: str
    formula: Optional[str] = None
    source: str = "pubchem"

class PubChemPropertyExtractor:
    """
    Extract and process chemical properties from PubChem data.
    
    Converts PubChem compound data to the standardized format used
    by the MicroMediaParam chemical_properties.tsv file.
    """
    
    def __init__(self):
        # Functional group patterns for pKa estimation
        self.functional_group_pka = {
            # Acids
            'carboxylic_acid': 4.75,
            'phenol': 10.0,
            'alcohol': 15.5,
            'thiol': 10.5,
            
            # Bases
            'primary_amine': 10.8,
            'secondary_amine': 11.0,
            'tertiary_amine': 9.8,
            'imidazole': 6.0,
            'guanidine': 12.5,
            
            # Phosphates
            'phosphate_1': 2.15,
            'phosphate_2': 7.20,
            'phosphate_3': 12.35,
            
            # Sulfates
            'sulfonic_acid': -3.0,
            'sulfate': 1.9
        }
        
        # SMILES patterns for functional group detection
        self.smiles_patterns = {
            'carboxylic_acid': r'C\(=O\)O[H]?',
            'phenol': r'c[OH]',
            'alcohol': r'[CH][OH]',
            'primary_amine': r'[CH2]N[H2]?',
            'secondary_amine': r'[CH]N[H]?[CH]',
            'tertiary_amine': r'[N][CH3]{3}|[N]\([CH]\)',
            'phosphate': r'P\(=O\)\(O\)',
            'sulfonic_acid': r'S\(=O\)\(=O\)O',
        }
        
        # Element atomic masses for molecular weight estimation
        self.atomic_masses = {
            'H': 1.008, 'C': 12.011, 'N': 14.007, 'O': 15.999,
            'F': 18.998, 'Na': 22.990, 'Mg': 24.305, 'P': 30.974,
            'S': 32.065, 'Cl': 35.453, 'K': 39.098, 'Ca': 40.078,
            'Fe': 55.845, 'Zn': 65.38, 'Br': 79.904, 'I': 126.90
        }
    
    def process_pubchem_compound(self, pubchem_data: PubChemCompoundData) -> ProcessedChemicalProperties:
        """
        Convert PubChem compound data to standardized format.
        
        Args:
            pubchem_data: PubChemCompoundData object
            
        Returns:
            ProcessedChemicalProperties object
        """
        # Get molecular weight
        molecular_weight = pubchem_data.molecular_weight
        
        # Convert string to float if needed
        if isinstance(molecular_weight, str):
            try:
                molecular_weight = float(molecular_weight)
            except (ValueError, TypeError):
                molecular_weight = None
        
        if not molecular_weight and pubchem_data.molecular_formula:
            molecular_weight = self.estimate_molecular_weight(pubchem_data.molecular_formula)
        if not molecular_weight:
            molecular_weight = 100.0  # Default fallback
        
        # Process pKa values
        pka_values = pubchem_data.pka_values or []
        
        # If no experimental pKa values, estimate from structure
        if not pka_values and pubchem_data.canonical_smiles:
            estimated_pka = self.estimate_pka_from_smiles(pubchem_data.canonical_smiles)
            if estimated_pka:
                pka_values = estimated_pka
        
        # If still no pKa, try from name/formula
        if not pka_values:
            estimated_pka = self.estimate_pka_from_name_formula(
                pubchem_data.name, 
                pubchem_data.molecular_formula or ""
            )
            if estimated_pka:
                pka_values = estimated_pka
        
        # Determine charge states
        charge_states = self.determine_charge_states(pka_values, pubchem_data.formal_charge)
        
        # Process ion charges
        ion_charges = pubchem_data.ion_charges or {}
        if not ion_charges and pubchem_data.molecular_formula:
            ion_charges = self.extract_ion_charges_from_formula(pubchem_data.molecular_formula)
        
        # Process solubility
        solubility = pubchem_data.solubility
        if solubility is None:
            solubility = self.estimate_solubility(
                pubchem_data.name,
                pubchem_data.molecular_formula or "",
                pubchem_data.xlogp
            )
        
        # Estimate activity coefficient (simple model)
        activity_coefficient = self.estimate_activity_coefficient(
            molecular_weight, 
            ion_charges,
            pubchem_data.topological_polar_surface_area
        )
        
        # Create description
        description = f"PubChem CID:{pubchem_data.cid}"
        if pubchem_data.iupac_name:
            description += f" - {pubchem_data.iupac_name[:50]}{'...' if len(pubchem_data.iupac_name) > 50 else ''}"
        
        return ProcessedChemicalProperties(
            compound_name=pubchem_data.name,
            molecular_weight=molecular_weight,
            pka_values=pka_values,
            charge_states=charge_states,
            ion_charges=ion_charges,
            solubility_g_per_L=solubility,
            activity_coefficient=activity_coefficient,
            description=description,
            formula=pubchem_data.molecular_formula,
            source=f"pubchem_cid_{pubchem_data.cid}"
        )
    
    def estimate_molecular_weight(self, molecular_formula: str) -> float:
        """
        Estimate molecular weight from molecular formula.
        
        Args:
            molecular_formula: Chemical formula (e.g., "C6H12O6")
            
        Returns:
            Estimated molecular weight in g/mol
        """
        if not molecular_formula:
            return 100.0
        
        # Parse molecular formula
        pattern = r'([A-Z][a-z]?)(\d*)'
        matches = re.findall(pattern, molecular_formula)
        
        total_weight = 0.0
        for element, count_str in matches:
            count = int(count_str) if count_str else 1
            atomic_mass = self.atomic_masses.get(element, 12.0)  # Default to carbon
            total_weight += atomic_mass * count
        
        return round(total_weight, 2)
    
    def estimate_pka_from_smiles(self, smiles: str) -> List[float]:
        """
        Estimate pKa values from SMILES structure.
        
        Args:
            smiles: Canonical SMILES string
            
        Returns:
            List of estimated pKa values
        """
        pka_values = []
        
        for group_name, pattern in self.smiles_patterns.items():
            if re.search(pattern, smiles):
                if group_name in self.functional_group_pka:
                    pka_val = self.functional_group_pka[group_name]
                    if pka_val not in pka_values:
                        pka_values.append(pka_val)
        
        # Special case for phosphates (multiple pKa values)
        if 'phosphate' in smiles.lower():
            pka_values.extend([2.15, 7.20, 12.35])
        
        return sorted(list(set(pka_values)))
    
    def estimate_pka_from_name_formula(self, name: str, formula: str) -> List[float]:
        """
        Estimate pKa values from compound name and formula.
        
        Args:
            name: Compound name
            formula: Molecular formula
            
        Returns:
            List of estimated pKa values
        """
        name_lower = name.lower()
        pka_values = []
        
        # Name-based patterns
        if any(acid in name_lower for acid in ['acid', 'carboxylic']):
            pka_values.append(4.75)
        
        if any(base in name_lower for base in ['amine', 'amino']):
            pka_values.append(10.8)
        
        if 'phosphate' in name_lower:
            pka_values.extend([2.15, 7.20, 12.35])
        
        if 'acetate' in name_lower:
            pka_values.append(4.76)
        
        if 'tris' in name_lower:
            pka_values.append(8.07)
        
        if 'hepes' in name_lower:
            pka_values.append(7.55)
        
        # Formula-based patterns
        if formula:
            if 'PO4' in formula or 'HPO4' in formula:
                pka_values.extend([2.15, 7.20, 12.35])
            
            if 'CO3' in formula or 'HCO3' in formula:
                pka_values.extend([6.37, 10.33])
        
        return sorted(list(set(pka_values)))
    
    def determine_charge_states(self, pka_values: List[float], formal_charge: Optional[int] = None) -> List[int]:
        """
        Determine possible charge states from pKa values and formal charge.
        
        Args:
            pka_values: List of pKa values
            formal_charge: Formal charge from structure
            
        Returns:
            List of possible charge states
        """
        if pka_values:
            num_ionizable = len(pka_values)
            charge_states = list(range(-num_ionizable, num_ionizable + 1))
        elif formal_charge is not None:
            # Use formal charge as center point
            charge_states = [formal_charge - 1, formal_charge, formal_charge + 1]
        else:
            # Default to neutral
            charge_states = [0]
        
        # Remove extreme charge states (unlikely)
        charge_states = [c for c in charge_states if -3 <= c <= 3]
        
        return sorted(charge_states)
    
    def extract_ion_charges_from_formula(self, formula: str) -> Dict[str, int]:
        """
        Extract ion charges from molecular formula.
        
        Args:
            formula: Molecular formula
            
        Returns:
            Dictionary mapping ion names to charges
        """
        ion_charges = {}
        
        # Common ionic patterns
        ion_patterns = {
            'Na': {'Na+': 1},
            'K': {'K+': 1},
            'Ca': {'Ca2+': 2},
            'Mg': {'Mg2+': 2},
            'Fe': {'Fe2+': 2, 'Fe3+': 3},
            'Zn': {'Zn2+': 2},
            'Cu': {'Cu2+': 2},
            'Mn': {'Mn2+': 2},
            'Co': {'Co2+': 2},
            'Ni': {'Ni2+': 2},
            'Cl': {'Cl-': -1},
            'Br': {'Br-': -1},
            'I': {'I-': -1},
        }
        
        # Polyatomic ions
        if 'SO4' in formula:
            ion_charges['SO42-'] = -2
        if 'PO4' in formula:
            ion_charges['PO43-'] = -3
        if 'HPO4' in formula:
            ion_charges['HPO42-'] = -2
        if 'H2PO4' in formula:
            ion_charges['H2PO4-'] = -1
        if 'CO3' in formula:
            ion_charges['CO32-'] = -2
        if 'HCO3' in formula:
            ion_charges['HCO3-'] = -1
        if 'NO3' in formula:
            ion_charges['NO3-'] = -1
        
        # Monatomic ions
        for element, charges in ion_patterns.items():
            if element in formula:
                # Simple heuristic: use most common oxidation state
                most_common = min(charges.items(), key=lambda x: abs(x[1]))
                ion_charges[most_common[0]] = most_common[1]
        
        return ion_charges
    
    def estimate_solubility(self, name: str, formula: str, xlogp: Optional[float] = None) -> float:
        """
        Estimate water solubility in g/L.
        
        Args:
            name: Compound name
            formula: Molecular formula  
            xlogp: Log P value from PubChem
            
        Returns:
            Estimated solubility in g/L
        """
        name_lower = name.lower()
        
        # Known high solubility compounds
        high_solubility = [
            'sodium', 'potassium', 'chloride', 'acetate', 'glucose',
            'sucrose', 'glycine', 'alanine', 'tris', 'hepes'
        ]
        
        # Known low solubility compounds
        low_solubility = [
            'carbonate', 'phosphate', 'sulfate', 'hydroxide'
        ]
        
        # Use XLogP if available
        if xlogp is not None:
            # Rough correlation: log(solubility) ≈ -0.5 * XLogP + 2
            estimated_log_sol = -0.5 * xlogp + 2
            estimated_sol = 10 ** estimated_log_sol
            return max(0.001, min(2000, estimated_sol))  # Clamp to reasonable range
        
        # Name-based estimation
        if any(high_sol in name_lower for high_sol in high_solubility):
            return 500.0  # High solubility
        
        if any(low_sol in name_lower for low_sol in low_solubility):
            return 1.0  # Low solubility
        
        # Ionic compounds are generally more soluble
        if self.is_likely_ionic(formula):
            return 200.0
        
        # Default moderate solubility
        return 100.0
    
    def is_likely_ionic(self, formula: str) -> bool:
        """Check if formula suggests an ionic compound."""
        if not formula:
            return False
        
        metals = ['Na', 'K', 'Ca', 'Mg', 'Fe', 'Zn', 'Cu', 'Mn', 'Co', 'Ni']
        has_metal = any(metal in formula for metal in metals)
        
        anions = ['Cl', 'Br', 'I', 'SO4', 'PO4', 'CO3', 'NO3']
        has_anion = any(anion in formula for anion in anions)
        
        return has_metal and has_anion
    
    def estimate_activity_coefficient(self, 
                                   molecular_weight: float,
                                   ion_charges: Dict[str, int],
                                   tpsa: Optional[float] = None) -> float:
        """
        Estimate activity coefficient for ionic strength calculations.
        
        Args:
            molecular_weight: Molecular weight
            ion_charges: Ion charge dictionary
            tpsa: Topological polar surface area
            
        Returns:
            Estimated activity coefficient
        """
        # Simple model based on charge and size
        if not ion_charges:
            return 1.0  # Neutral compounds
        
        # For ionic compounds, use charge-based estimation
        max_charge = max(abs(charge) for charge in ion_charges.values()) if ion_charges else 0
        
        # Davies equation approximation
        if max_charge == 1:
            return 0.9
        elif max_charge == 2:
            return 0.8
        elif max_charge >= 3:
            return 0.7
        else:
            return 1.0
    
    def process_raw_data_file(self, raw_data_file: Path) -> List[ProcessedChemicalProperties]:
        """
        Process PubChem raw data file to standardized format.
        
        Args:
            raw_data_file: Path to JSON file with PubChem data
            
        Returns:
            List of processed chemical properties
        """
        with open(raw_data_file, 'r') as f:
            raw_data = json.load(f)
        
        processed_compounds = []
        
        for compound_dict in raw_data:
            # Convert dict back to PubChemCompoundData
            pubchem_compound = PubChemCompoundData(**compound_dict)
            
            # Process to standardized format
            try:
                processed = self.process_pubchem_compound(pubchem_compound)
                processed_compounds.append(processed)
                logger.debug(f"Processed compound: {processed.compound_name}")
                
            except Exception as e:
                logger.warning(f"Failed to process compound {pubchem_compound.name}: {e}")
                continue
        
        logger.info(f"Successfully processed {len(processed_compounds)} compounds from PubChem data")
        return processed_compounds
    
    def save_processed_data(self, 
                          processed_compounds: List[ProcessedChemicalProperties], 
                          output_file: Path):
        """Save processed compounds to JSON file."""
        json_data = []
        
        for compound in processed_compounds:
            compound_dict = {
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
            }
            json_data.append(compound_dict)
        
        with open(output_file, 'w') as f:
            json.dump(json_data, f, indent=2)
        
        logger.info(f"Saved processed data for {len(processed_compounds)} compounds to: {output_file}")

def main():
    """Test the property extractor."""
    # This would normally be called by the pipeline
    extractor = PubChemPropertyExtractor()
    
    # Test with sample data
    test_compound = PubChemCompoundData(
        cid="5460",
        name="glucose",
        molecular_formula="C6H12O6",
        molecular_weight=180.16,
        canonical_smiles="C([C@@H]1[C@H]([C@@H]([C@H]([C@H](O1)O)O)O)O)O",
        pka_values=[],
        solubility=909.0
    )
    
    processed = extractor.process_pubchem_compound(test_compound)
    print(f"Processed compound: {processed.compound_name}")
    print(f"  MW: {processed.molecular_weight}")
    print(f"  pKa: {processed.pka_values}")
    print(f"  Charge states: {processed.charge_states}")
    print(f"  Ion charges: {processed.ion_charges}")
    print(f"  Solubility: {processed.solubility_g_per_L} g/L")

if __name__ == "__main__":
    main()