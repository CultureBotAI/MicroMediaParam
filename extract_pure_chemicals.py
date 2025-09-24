#!/usr/bin/env python3
"""
Extract pure chemical compounds from the mapping file, excluding procedure text.
"""

import pandas as pd
import re
import argparse
from pathlib import Path

def is_pure_chemical(compound: str) -> bool:
    """Check if compound is a pure chemical name (not procedure text)."""
    compound = compound.strip()
    
    # Skip empty or very short
    if not compound or len(compound) < 2:
        return False
    
    # Exclude obvious procedure text patterns
    exclude_patterns = [
        r'\[.*\.md\]',  # File references like [ccap_E26_Biotin.md]
        r'using\s+a\s+syringe',
        r'sterile\s+stock',
        r'brackish\s+organisms',
        r'instead\s+of',
        r'neutralized.*vitamins',
        r'ml.*medium',
        r'For\s+nitrogen',
        r'prepare\s+standard',
        r'omitting\s+Stock',
        r'Due\s+to\s+precipitation',
        r'larger\s+volumes',
        r'autoclaved\s+separately',
        r'filter\s+sterilised',
        r'sterile\s+medium',
        r'airflow\s+cabinet',
        r'fixing\s+cyanobacteria',
        r'Nov\s+\d{4}',  # Dates
        r'^\*',  # Lines starting with asterisk
        r'^\+',  # Lines starting with plus
        r'^\-',  # Lines starting with dash
        r'%.*extract',  # "0.02 % Yeast extract"
        r'^\d+(\.\d+)?%',  # Percentages at start
        r'^\d+(\.\d+)?g\s',  # "0.01g d‐Biotin"
        r'ml/.*ml',  # "10ml NaHCO3/ 90ml medium"
    ]
    
    for pattern in exclude_patterns:
        if re.search(pattern, compound, re.IGNORECASE):
            return False
    
    # Must contain at least one chemical element or common chemical group
    chemical_indicators = [
        r'\b(Na|K|Ca|Mg|Fe|Mn|Zn|Cu|Co|Ni|Al|Cl|SO4|PO4|NO3|CO3|HCO3)\b',
        r'\b(chloride|sulfate|phosphate|nitrate|carbonate|acetate|citrate)\b',
        r'\b(NaCl|KCl|CaCl2|MgCl2|MgSO4|FeSO4|ZnSO4|CuSO4|CoSO4|MnSO4|NiCl2)\b',
        r'\b(glucose|sucrose|fructose|agar|biotin|thiamine|glycine)\b',
        r'^[A-Z][a-z]*[A-Z0-9]',  # Chemical formula pattern
    ]
    
    has_chemical = any(re.search(pattern, compound, re.IGNORECASE) for pattern in chemical_indicators)
    
    if not has_chemical:
        return False
    
    # Additional filters for obvious non-chemicals
    if any(word in compound.lower() for word in ['tryptone', 'extract', 'peptone', 'solution', 'medium', 'vitamin']):
        # These are valid if they're simple like "Yeast extract" but not if complex
        if len(compound.split()) > 3:
            return False
    
    return True

def extract_pure_chemicals(input_file: Path, output_file: Path):
    """Extract pure chemical compounds from mapping file."""
    
    # Load the mapping file
    df = pd.read_csv(input_file, sep='\t')
    
    # Get unmapped compounds that need base compound mapping
    unmapped = df[(df['hydration_state'].isin(['hydrated', 'anhydrous'])) & 
                  (df['mapped'].isna() | (df['mapped'] == ''))]
    
    # Extract base compounds
    base_compounds = unmapped['base_compound_for_mapping'].dropna().unique()
    
    # Filter for pure chemicals
    pure_chemicals = []
    for compound in base_compounds:
        if is_pure_chemical(compound):
            pure_chemicals.append(compound)
    
    # Sort and save
    pure_chemicals = sorted(set(pure_chemicals))
    
    with open(output_file, 'w') as f:
        for compound in pure_chemicals:
            f.write(f"{compound}\n")
    
    print(f"Total base compounds: {len(base_compounds)}")
    print(f"Pure chemical compounds: {len(pure_chemicals)}")
    print(f"Saved to: {output_file}")
    
    # Show examples
    print("\nSample pure chemical compounds:")
    for i, compound in enumerate(pure_chemicals[:20]):
        print(f"  {i+1:2d}. {compound}")
    
    return pure_chemicals

def main():
    parser = argparse.ArgumentParser(description="Extract pure chemical compounds")
    parser.add_argument("--input", required=True, help="Input TSV mapping file")
    parser.add_argument("--output", required=True, help="Output pure chemicals file")
    
    args = parser.parse_args()
    extract_pure_chemicals(Path(args.input), Path(args.output))

if __name__ == "__main__":
    main()