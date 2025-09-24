#!/usr/bin/env python3
"""
Clean up base compounds list to remove procedure text and keep only valid chemical names.
"""

import re
import argparse
from pathlib import Path

def is_valid_chemical_compound(compound: str) -> bool:
    """Check if a string looks like a valid chemical compound."""
    compound = compound.strip()
    
    # Skip if empty or too short
    if not compound or len(compound) < 2:
        return False
    
    # Skip if it's clearly procedure text
    procedure_patterns = [
        r'\b(ml|ml/10|room|temperature|hour|times|washed|three|distilled|water)\b',
        r'\b(Agar|Difco|EDTAFeNa|EDTANa2)\b',
        r'^\(\d+\).*\d+(\.\d+)?\s*g\b',  # "(3) 2.68 g NH4Cl"
        r'^\(\d+\).*ml\b',  # "(0.2 ml/10 ml)"
        r'and\s+\d+M',
        r'thiosulphate',
        r'glycerophosphate',
        r'sodium\s+thiosulphate',
        r'glucose.*ml',
        r'^\(\d{4}\)',  # Year references like "(1983)"
    ]
    
    for pattern in procedure_patterns:
        if re.search(pattern, compound, re.IGNORECASE):
            return False
    
    # Skip if it starts with a number in parentheses followed by long text
    if re.match(r'^\(\d+\).*[,\.]', compound):
        return False
    
    # Skip if it contains common procedure words
    procedure_words = ['distilled', 'washed', 'room', 'temperature', 'hour', 'times', 'three', 'Difco', 'Agar']
    if any(word in compound for word in procedure_words):
        return False
    
    # Keep if it looks like a chemical formula
    # Common patterns: starts with capital letter, contains elements
    chemical_patterns = [
        r'^[A-Z][a-z]?[A-Z0-9]',  # Like NaCl, MgSO4
        r'^[A-Z][a-z]*\s',  # Like "Sodium", "Potassium"
        r'[A-Z][a-z]?[0-9]',  # Contains element with number
        r'(Cl|SO4|PO4|NO3|CO3|HCO3|acetate|citrate|phosphate|sulfate|chloride|nitrate)',
    ]
    
    for pattern in chemical_patterns:
        if re.search(pattern, compound):
            return True
    
    # If compound is short and doesn't match chemical patterns, probably not a chemical
    if len(compound) < 5:
        return False
    
    return True

def clean_compounds_file(input_file: Path, output_file: Path):
    """Clean compounds file to keep only valid chemical names."""
    
    with open(input_file, 'r') as f:
        compounds = f.read().splitlines()
    
    # Filter and clean compounds
    clean_compounds = []
    for compound in compounds:
        compound = compound.strip()
        if compound and is_valid_chemical_compound(compound):
            # Additional cleaning
            # Remove leading parenthetical numbers like "(1) CaCl2" → "CaCl2"
            compound = re.sub(r'^\(\d+\)\s*', '', compound)
            # Remove trailing procedure text
            compound = re.sub(r'\s+\(\d+.*$', '', compound)
            
            if compound and is_valid_chemical_compound(compound):
                clean_compounds.append(compound)
    
    # Remove duplicates and sort
    unique_compounds = sorted(set(clean_compounds))
    
    # Save cleaned list
    with open(output_file, 'w') as f:
        for compound in unique_compounds:
            f.write(f"{compound}\n")
    
    print(f"Original compounds: {len(compounds)}")
    print(f"Cleaned compounds: {len(unique_compounds)}")
    print(f"Saved to: {output_file}")
    
    # Show some examples
    print("\nSample cleaned compounds:")
    for i, compound in enumerate(unique_compounds[:15]):
        print(f"  {i+1:2d}. {compound}")

def main():
    parser = argparse.ArgumentParser(description="Clean base compounds list")
    parser.add_argument("--input", required=True, help="Input compounds file")
    parser.add_argument("--output", required=True, help="Output cleaned compounds file")
    
    args = parser.parse_args()
    clean_compounds_file(Path(args.input), Path(args.output))

if __name__ == "__main__":
    main()