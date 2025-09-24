#!/usr/bin/env python3
"""
Calculate molecular weights for chemical compounds based on their formulas.
"""

import pandas as pd
import re
import argparse
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MolecularWeightCalculator:
    """Calculate molecular weights from chemical formulas."""
    
    def __init__(self):
        # Atomic weights (g/mol)
        self.atomic_weights = {
            'H': 1.008, 'He': 4.003, 'Li': 6.941, 'Be': 9.012,
            'B': 10.81, 'C': 12.01, 'N': 14.01, 'O': 16.00,
            'F': 19.00, 'Ne': 20.18, 'Na': 22.99, 'Mg': 24.31,
            'Al': 26.98, 'Si': 28.09, 'P': 30.97, 'S': 32.07,
            'Cl': 35.45, 'Ar': 39.95, 'K': 39.10, 'Ca': 40.08,
            'Sc': 44.96, 'Ti': 47.87, 'V': 50.94, 'Cr': 52.00,
            'Mn': 54.94, 'Fe': 55.85, 'Co': 58.93, 'Ni': 58.69,
            'Cu': 63.55, 'Zn': 65.39, 'Ga': 69.72, 'Ge': 72.64,
            'As': 74.92, 'Se': 78.96, 'Br': 79.90, 'Kr': 83.80,
            'Rb': 85.47, 'Sr': 87.62, 'Y': 88.91, 'Zr': 91.22,
            'Nb': 92.91, 'Mo': 95.94, 'Tc': 98.00, 'Ru': 101.07,
            'Rh': 102.91, 'Pd': 106.42, 'Ag': 107.87, 'Cd': 112.41,
            'In': 114.82, 'Sn': 118.71, 'Sb': 121.76, 'Te': 127.60,
            'I': 126.90, 'Xe': 131.29, 'Cs': 132.91, 'Ba': 137.33,
            'La': 138.91, 'Ce': 140.12, 'Pr': 140.91, 'Nd': 144.24,
            'Pm': 145.00, 'Sm': 150.36, 'Eu': 151.96, 'Gd': 157.25,
            'Tb': 158.93, 'Dy': 162.50, 'Ho': 164.93, 'Er': 167.26,
            'Tm': 168.93, 'Yb': 173.04, 'Lu': 174.97, 'Hf': 178.49,
            'Ta': 180.95, 'W': 183.84, 'Re': 186.21, 'Os': 190.23,
            'Ir': 192.22, 'Pt': 195.08, 'Au': 196.97, 'Hg': 200.59,
            'Tl': 204.38, 'Pb': 207.20, 'Bi': 208.98, 'Po': 209.00,
            'At': 210.00, 'Rn': 222.00, 'Fr': 223.00, 'Ra': 226.00,
            'Ac': 227.00, 'Th': 232.04, 'Pa': 231.04, 'U': 238.03
        }
        
        # Common molecular formulas for compounds that might not have clean formulas
        self.known_compounds = {
            # Common salts
            'NaCl': 58.44, 'KCl': 74.55, 'CaCl2': 110.98, 'MgCl2': 95.21,
            'MgSO4': 120.37, 'FeSO4': 151.91, 'ZnSO4': 161.47, 'CuSO4': 159.61,
            'CoSO4': 154.99, 'MnSO4': 151.00, 'NiCl2': 129.60, 'K2HPO4': 174.18,
            'KH2PO4': 136.09, 'Na2CO3': 105.99, 'NaHCO3': 84.01, 'NH4Cl': 53.49,
            'CaCO3': 100.09, 'Na2SO4': 142.04, 'Na2MoO4': 205.92, 'Na2SeO3': 172.94,
            'Na2WO4': 293.82, 'FeCl2': 126.75, 'FeCl3': 162.20, 'ZnCl2': 136.29,
            'CuCl2': 134.45, 'MnCl2': 125.84, 'H3BO3': 61.83, 'NaNO3': 84.99,
            'Na2S': 78.05, 'Na2S2O3': 158.11, 'CoCl2': 129.84, 'CaSO4': 136.14,
            'BaCl2': 208.23, 'AlCl3': 133.34, 'K2SO4': 174.26, 'Na3PO4': 163.94,
            'Ca3(PO4)2': 310.18, '(NH4)2SO4': 132.14, 'NH4NO3': 80.04,
            'KNO3': 101.10, 'Ca(NO3)2': 164.09, 'Mg(NO3)2': 148.31,
            'Fe2(SO4)3': 399.88, 'Al2(SO4)3': 342.15, 'CuSO2': 127.61,
            'FeSO2': 119.97, 'Co(NO3)2': 182.94,
            
            # Organics
            'glucose': 180.16, 'C6H12O6': 180.16, 'sucrose': 342.30, 'C12H22O11': 342.30,
            'fructose': 180.16, 'lactose': 342.30, 'maltose': 342.30,
            'glycerol': 92.09, 'C3H8O3': 92.09, 'ethanol': 46.07, 'C2H5OH': 46.07,
            'acetate': 59.04, 'CH3COO': 59.04, 'citrate': 189.10, 'C6H5O7': 189.10,
            'lactate': 89.07, 'C3H5O3': 89.07, 'pyruvate': 87.05, 'C3H3O3': 87.05,
            
            # Common buffers
            'HEPES': 238.31, 'MOPS': 209.26, 'Tris': 121.14, 'Tricine': 179.17,
            'Bicine': 163.17, 'PIPES': 302.37, 'MES': 195.24, 'ADA': 190.20,
            
            # Amino acids
            'glycine': 75.07, 'alanine': 89.09, 'valine': 117.15, 'leucine': 131.17,
            'isoleucine': 131.17, 'serine': 105.09, 'threonine': 119.12,
            'cysteine': 121.16, 'methionine': 149.21, 'asparagine': 132.12,
            'glutamine': 146.15, 'proline': 115.13, 'phenylalanine': 165.19,
            'tyrosine': 181.19, 'tryptophan': 204.23, 'aspartate': 133.10,
            'glutamate': 147.13, 'lysine': 146.19, 'arginine': 174.20,
            'histidine': 155.16,
            
            # Vitamins
            'biotin': 244.31, 'thiamine': 265.36, 'riboflavin': 376.37,
            'niacin': 123.11, 'nicotinic acid': 123.11, 'folic acid': 441.40,
            'cyanocobalamin': 1355.37, 'ascorbic acid': 176.12, 'vitamin C': 176.12,
            'pyridoxine': 169.18, 'pantothenic acid': 219.23,
            
            # EDTA and variants
            'EDTA': 292.24, 'Na2EDTA': 336.21, 'EDTANa2': 336.21,
            'CaEDTA': 332.32, 'FeEDTA': 347.09, 'EDTAFeNa': 367.05,
        }
    
    def parse_formula(self, formula: str) -> Dict[str, int]:
        """Parse a chemical formula into element counts."""
        if not formula or pd.isna(formula):
            return {}
            
        # Check if it's a known compound
        if formula in self.known_compounds:
            return {'_molecular_weight': self.known_compounds[formula]}
        
        # Clean the formula
        formula = formula.strip()
        
        # Handle parenthetical groups like Ca(OH)2
        # First, expand parentheses
        while '(' in formula:
            match = re.search(r'\(([^()]+)\)(\d*)', formula)
            if match:
                group = match.group(1)
                multiplier = int(match.group(2)) if match.group(2) else 1
                # Expand the group
                expanded = ''
                elements = re.findall(r'([A-Z][a-z]?)(\d*)', group)
                for elem, count in elements:
                    n = int(count) if count else 1
                    expanded += f"{elem}{n * multiplier}"
                formula = formula[:match.start()] + expanded + formula[match.end():]
            else:
                break
        
        # Parse elements and counts
        element_counts = {}
        pattern = r'([A-Z][a-z]?)(\d*)'
        matches = re.findall(pattern, formula)
        
        for element, count in matches:
            if element in self.atomic_weights:
                n = int(count) if count else 1
                if element in element_counts:
                    element_counts[element] += n
                else:
                    element_counts[element] = n
        
        return element_counts
    
    def calculate_molecular_weight(self, formula: str) -> float:
        """Calculate molecular weight from formula."""
        element_counts = self.parse_formula(formula)
        
        # Check if we have a pre-calculated weight
        if '_molecular_weight' in element_counts:
            return element_counts['_molecular_weight']
        
        # Calculate from elements
        mw = 0.0
        for element, count in element_counts.items():
            if element in self.atomic_weights:
                mw += self.atomic_weights[element] * count
        
        return mw if mw > 0 else 100.0  # Default if calculation fails
    
    def get_formula_from_compound_name(self, compound: str, base_compound: str = None) -> Optional[str]:
        """Try to extract or determine formula from compound name."""
        # Handle None or NaN values
        if pd.isna(compound) or not compound:
            return None
            
        compound = str(compound).strip()
        
        # First check if the compound itself is a formula
        if re.match(r'^[A-Z][a-z]?[A-Z0-9]', compound):
            return compound
            
        # Check known compounds
        if compound in self.known_compounds:
            return compound
            
        # Check base compound if provided
        if base_compound and not pd.isna(base_compound) and base_compound != compound:
            base_compound = str(base_compound).strip()
            if re.match(r'^[A-Z][a-z]?[A-Z0-9]', base_compound):
                return base_compound
            if base_compound in self.known_compounds:
                return base_compound
        
        # Common name to formula mappings
        name_to_formula = {
            'sodium chloride': 'NaCl', 'salt': 'NaCl',
            'potassium chloride': 'KCl', 'calcium chloride': 'CaCl2',
            'magnesium chloride': 'MgCl2', 'magnesium sulfate': 'MgSO4',
            'iron sulfate': 'FeSO4', 'ferrous sulfate': 'FeSO4',
            'zinc sulfate': 'ZnSO4', 'copper sulfate': 'CuSO4',
            'cobalt sulfate': 'CoSO4', 'manganese sulfate': 'MnSO4',
            'nickel chloride': 'NiCl2', 'ammonium chloride': 'NH4Cl',
            'sodium carbonate': 'Na2CO3', 'sodium bicarbonate': 'NaHCO3',
            'potassium phosphate': 'K2HPO4', 'sodium phosphate': 'Na3PO4',
            'calcium carbonate': 'CaCO3', 'sodium sulfate': 'Na2SO4',
            'sodium molybdate': 'Na2MoO4', 'sodium selenite': 'Na2SeO3',
            'sodium tungstate': 'Na2WO4', 'boric acid': 'H3BO3',
            'sodium nitrate': 'NaNO3', 'calcium sulfate': 'CaSO4',
            'barium chloride': 'BaCl2', 'aluminum chloride': 'AlCl3',
        }
        
        # Check name mappings
        compound_lower = compound.lower()
        for name, formula in name_to_formula.items():
            if name in compound_lower:
                return formula
        
        return None
    
    def calculate_hydrated_weight(self, base_mw: float, hydration_number: str) -> float:
        """Calculate molecular weight of hydrated compound."""
        try:
            if pd.isna(hydration_number) or hydration_number == '' or hydration_number == '0':
                return base_mw
                
            # Handle special cases
            if hydration_number in ['n', 'x']:
                # Can't calculate exact weight for variable hydration
                return base_mw
                
            # Convert to number
            n_water = int(hydration_number)
            water_mw = 18.015  # H2O molecular weight
            
            return base_mw + (n_water * water_mw)
            
        except:
            return base_mw

def process_mapping_file(input_file: Path, output_file: Path):
    """Process mapping file to calculate molecular weights."""
    
    logger.info(f"Loading mapping file: {input_file}")
    df = pd.read_csv(input_file, sep='\t')
    
    calculator = MolecularWeightCalculator()
    
    # Calculate molecular weights
    updated_count = 0
    for idx, row in df.iterrows():
        # Skip if already has valid molecular weight
        current_mw = row.get('base_molecular_weight', 100.0)
        if current_mw and current_mw != 100.0:
            continue
            
        # Get compound info
        original = row['original']
        base_compound = row.get('base_compound_for_mapping', original)
        base_formula = row.get('base_formula', '')
        hydration_num = row.get('hydration_number_extracted', '')
        
        # Try to get formula
        formula = calculator.get_formula_from_compound_name(original, base_compound)
        if not formula and base_formula:
            formula = base_formula
            
        if formula:
            # Calculate base molecular weight
            base_mw = calculator.calculate_molecular_weight(formula)
            
            if base_mw > 0 and base_mw != 100.0:
                df.at[idx, 'base_molecular_weight'] = round(base_mw, 2)
                df.at[idx, 'base_formula'] = formula
                
                # Calculate hydrated weight
                hydrated_mw = calculator.calculate_hydrated_weight(base_mw, hydration_num)
                df.at[idx, 'hydrated_molecular_weight'] = round(hydrated_mw, 2)
                
                # Calculate water weight
                water_weight = hydrated_mw - base_mw
                df.at[idx, 'water_molecular_weight'] = round(water_weight, 2)
                
                updated_count += 1
    
    logger.info(f"Updated molecular weights for {updated_count} compounds")
    
    # Save updated file
    df.to_csv(output_file, sep='\t', index=False)
    
    # Show statistics
    valid_mw = len(df[(df['base_molecular_weight'] > 0) & (df['base_molecular_weight'] != 100.0)])
    total = len(df)
    logger.info(f"Valid molecular weights: {valid_mw}/{total} ({valid_mw/total*100:.1f}%)")
    
    # Show examples
    examples = df[(df['base_molecular_weight'] > 0) & (df['base_molecular_weight'] != 100.0)].head(10)
    logger.info("\nExamples of calculated molecular weights:")
    for _, row in examples.iterrows():
        orig = row['original']
        base_mw = row['base_molecular_weight']
        hydrated_mw = row.get('hydrated_molecular_weight', base_mw)
        formula = row.get('base_formula', '')
        logger.info(f"  {orig}: {base_mw} g/mol (hydrated: {hydrated_mw} g/mol) [{formula}]")

def main():
    parser = argparse.ArgumentParser(description="Calculate molecular weights")
    parser.add_argument("--input", required=True, help="Input TSV file")
    parser.add_argument("--output", required=True, help="Output TSV file")
    
    args = parser.parse_args()
    process_mapping_file(Path(args.input), Path(args.output))

if __name__ == "__main__":
    main()