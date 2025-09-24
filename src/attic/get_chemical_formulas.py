#!/usr/bin/env python3
"""
Extract only standard chemical formulas from the mapping data.
Focus on recognizable chemical compounds without procedure text.
"""

import pandas as pd
import re
import argparse
from pathlib import Path

def extract_chemical_formulas(input_file: Path, output_file: Path):
    """Extract recognizable chemical formulas from mapping file."""
    
    # Load the mapping file
    df = pd.read_csv(input_file, sep='\t')
    
    # Get unmapped compounds that need base compound mapping
    unmapped = df[(df['hydration_state'].isin(['hydrated', 'anhydrous'])) & 
                  (df['mapped'].isna() | (df['mapped'] == ''))]
    
    # Extract base compounds
    base_compounds = unmapped['base_compound_for_mapping'].dropna().unique()
    
    # Define patterns for recognizable chemical formulas
    chemical_patterns = [
        # Standard ionic compounds
        r'^[A-Z][a-z]?[A-Z][a-z]?\d*$',  # NaCl, MgSO4, etc.
        r'^[A-Z][a-z]?\d*[A-Z][a-z]?\d*$',  # CaCl2, etc.
        r'^[A-Z][a-z]?\([A-Z][a-z]?\d*\)\d*$',  # Ca(OH)2, etc.
        r'^[A-Z][a-z]?\d*[A-Z]\d*[A-Z]\d*$',  # Complex formulas
        
        # Common chemical names (simple)
        r'^(Na|K|Ca|Mg|Fe|Mn|Zn|Cu|Co|Ni|Al)[A-Z][a-z]*\d*$',
        r'^[A-Z][a-z]*\s+(chloride|sulfate|phosphate|nitrate|carbonate|acetate)$',
        
        # Specific known compounds
        r'^(glucose|sucrose|fructose|agar|agarose|biotin|thiamine|glycine|glycerol)$',
        r'^(Tryptone|Peptone)$',
    ]
    
    # Additional manual list of known chemicals that might not match patterns
    known_chemicals = {
        'NaCl', 'KCl', 'CaCl2', 'MgCl2', 'MgSO4', 'FeSO4', 'ZnSO4', 'CuSO4', 
        'CoSO4', 'MnSO4', 'NiCl2', 'K2HPO4', 'KH2PO4', 'Na2CO3', 'NaHCO3',
        'NH4Cl', 'CaCO3', 'Na2SO4', 'Na2MoO4', 'Na2SeO3', 'Na2WO4',
        'FeCl2', 'FeCl3', 'ZnCl2', 'CuCl2', 'MnCl2', 'H3BO3', 'NaNO3',
        'glucose', 'sucrose', 'fructose', 'agar', 'biotin', 'thiamine',
        'Yeast extract', 'Beef extract', 'Tryptone', 'Peptone',
        'Nicotinic acid', 'Folic acid', 'citric acid', 'acetic acid',
    }
    
    # Find chemicals
    pure_chemicals = set()
    
    for compound in base_compounds:
        compound = compound.strip()
        
        # Skip if obviously not a chemical
        if not compound or len(compound) < 2:
            continue
            
        # Skip procedure text indicators
        if any(indicator in compound.lower() for indicator in [
            'preparation', 'autoclave', 'sterilize', 'dissolve', 'adjust', 'mix',
            'temperature', 'culture', 'phase', 'days', 'centrifuge', 'plate',
            'broth', 'medium', 'agar plates', 'necessary', 'needed', 'difco',
            'stationary', 'reached', 'layered', '°c', 'ml/l', 'g/l '
        ]):
            continue
            
        # Clean up parenthetical prefixes
        clean_compound = re.sub(r'^\(\d+\)\s*', '', compound)
        clean_compound = re.sub(r'^\d+\.\s*', '', clean_compound)
        
        # Check if it's in known chemicals
        if clean_compound in known_chemicals:
            pure_chemicals.add(clean_compound)
            continue
            
        # Check against patterns
        for pattern in chemical_patterns:
            if re.match(pattern, clean_compound, re.IGNORECASE):
                pure_chemicals.add(clean_compound)
                break
    
    # Convert to sorted list
    chemicals_list = sorted(pure_chemicals)
    
    # Save to file
    with open(output_file, 'w') as f:
        for chemical in chemicals_list:
            f.write(f"{chemical}\n")
    
    print(f"Total base compounds: {len(base_compounds)}")
    print(f"Pure chemical formulas: {len(chemicals_list)}")
    print(f"Saved to: {output_file}")
    
    # Show examples
    print("\nPure chemical formulas for mapping:")
    for i, chemical in enumerate(chemicals_list[:30]):
        print(f"  {i+1:2d}. {chemical}")
    
    if len(chemicals_list) > 30:
        print(f"  ... and {len(chemicals_list) - 30} more")
    
    return chemicals_list

def main():
    parser = argparse.ArgumentParser(description="Extract chemical formulas for mapping")
    parser.add_argument("--input", required=True, help="Input TSV mapping file")
    parser.add_argument("--output", required=True, help="Output chemicals file")
    
    args = parser.parse_args()
    extract_chemical_formulas(Path(args.input), Path(args.output))

if __name__ == "__main__":
    main()