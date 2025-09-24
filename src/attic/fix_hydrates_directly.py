#!/usr/bin/env python3
"""
Directly fix hydrate parsing in the mapping file.
"""

import pandas as pd
import re
import argparse
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def parse_hydrate(compound_name):
    """
    Parse hydrate information from compound name.
    Returns (base_compound, hydration_number)
    """
    if pd.isna(compound_name):
        return compound_name, 0
    
    compound_name = str(compound_name).strip()
    
    # Patterns to match various hydrate formats
    patterns = [
        # "X n-hydrate" or "X n hydrate"
        (r'^(.+?)\s+(\d+)\s*[-]?\s*hydrate$', lambda m: (m.group(1).strip(), int(m.group(2)))),
        
        # "X·nH2O" or "X.nH2O" or "X nH2O"
        (r'^(.+?)\s*[·•．.]\s*(\d+)\s*H2O$', lambda m: (m.group(1).strip(), int(m.group(2)))),
        (r'^(.+?)\s+(\d+)\s*H2O$', lambda m: (m.group(1).strip(), int(m.group(2)))),
        
        # "X x H2O" or "X x hydrate"
        (r'^(.+?)\s+x\s+H2O$', lambda m: (m.group(1).strip(), 'x')),
        (r'^(.+?)\s+x\s+hydrate$', lambda m: (m.group(1).strip(), 'x')),
        
        # "(X)·nH2O"
        (r'^\((.+?)\)\s*[·•．.]\s*(\d+)\s*H2O$', lambda m: (m.group(1).strip(), int(m.group(2)))),
        
        # Named hydrates
        (r'^(.+?)\s+(mono|uni)hydrate$', lambda m: (m.group(1).strip(), 1)),
        (r'^(.+?)\s+(di|bi)hydrate$', lambda m: (m.group(1).strip(), 2)),
        (r'^(.+?)\s+trihydrate$', lambda m: (m.group(1).strip(), 3)),
        (r'^(.+?)\s+tetrahydrate$', lambda m: (m.group(1).strip(), 4)),
        (r'^(.+?)\s+pentahydrate$', lambda m: (m.group(1).strip(), 5)),
        (r'^(.+?)\s+hexahydrate$', lambda m: (m.group(1).strip(), 6)),
        (r'^(.+?)\s+heptahydrate$', lambda m: (m.group(1).strip(), 7)),
        (r'^(.+?)\s+octahydrate$', lambda m: (m.group(1).strip(), 8)),
        (r'^(.+?)\s+nonahydrate$', lambda m: (m.group(1).strip(), 9)),
        (r'^(.+?)\s+decahydrate$', lambda m: (m.group(1).strip(), 10)),
    ]
    
    # Try each pattern
    for pattern, extractor in patterns:
        match = re.match(pattern, compound_name, re.IGNORECASE)
        if match:
            return extractor(match)
    
    # No hydrate found
    return compound_name, 0

def calculate_mw(formula):
    """Calculate molecular weight from formula."""
    atomic_weights = {
        'H': 1.008, 'C': 12.01, 'N': 14.01, 'O': 16.00, 'F': 19.00,
        'Na': 22.99, 'Mg': 24.31, 'Al': 26.98, 'Si': 28.09, 'P': 30.97,
        'S': 32.07, 'Cl': 35.45, 'K': 39.10, 'Ca': 40.08, 'Mn': 54.94,
        'Fe': 55.85, 'Co': 58.93, 'Ni': 58.69, 'Cu': 63.55, 'Zn': 65.39,
        'Se': 78.96, 'Mo': 95.94, 'Ba': 137.33, 'W': 183.84,
    }
    
    # Common compound molecular weights
    known_mw = {
        'NaCl': 58.44, 'KCl': 74.55, 'CaCl2': 110.98, 'MgCl2': 95.21,
        'MgSO4': 120.37, 'FeSO4': 151.91, 'ZnSO4': 161.47, 'CuSO4': 159.61,
        'CoSO4': 154.99, 'MnSO4': 151.00, 'NiCl2': 129.60, 'K2HPO4': 174.18,
        'KH2PO4': 136.09, 'Na2CO3': 105.99, 'NaHCO3': 84.01, 'NH4Cl': 53.49,
        'Na2MoO4': 205.92, 'Na2SeO3': 172.94, 'Na2WO4': 293.82,
        'FeCl2': 126.75, 'FeCl3': 162.20, 'ZnCl2': 136.29, 'CuCl2': 134.45,
        'MnCl2': 125.84, 'H3BO3': 61.83, 'NaNO3': 84.99, 'CoCl2': 129.84,
        'CaSO4': 136.14, 'BaCl2': 208.23, 'AlCl3': 133.34, 'Na2S': 78.05,
        'H2O': 18.015,
    }
    
    if formula in known_mw:
        return known_mw[formula]
    
    # Try to calculate from formula
    try:
        # Simple pattern matching for formulas like MgCl2, Na2SO4, etc.
        mw = 0
        # This is simplified - a full parser would be more complex
        elements = re.findall(r'([A-Z][a-z]?)(\d*)', formula)
        for element, count in elements:
            if element in atomic_weights:
                n = int(count) if count else 1
                mw += atomic_weights[element] * n
        return mw if mw > 0 else 100.0
    except:
        return 100.0

def process_file(input_file, output_file):
    """Process the mapping file to fix hydrates."""
    
    logger.info(f"Loading file: {input_file}")
    df = pd.read_csv(input_file, sep='\t')
    
    # Process each row
    fixed_count = 0
    for idx, row in df.iterrows():
        original = row['original']
        
        # Parse hydrate
        base_compound, hydration_num = parse_hydrate(original)
        
        # Update if hydrate detected
        if hydration_num != 0:
            # Update base compound fields
            df.at[idx, 'base_compound'] = base_compound
            df.at[idx, 'base_formula'] = base_compound  # Will be cleaned up later
            df.at[idx, 'hydration_number'] = hydration_num
            
            # Calculate molecular weights
            base_mw = calculate_mw(base_compound)
            if isinstance(hydration_num, int):
                water_mw = hydration_num * 18.015
                hydrated_mw = base_mw + water_mw
            else:  # 'x' or 'n'
                water_mw = 0
                hydrated_mw = base_mw
            
            df.at[idx, 'base_molecular_weight'] = base_mw
            df.at[idx, 'water_molecular_weight'] = water_mw
            df.at[idx, 'hydrated_molecular_weight'] = hydrated_mw
            
            # Update hydration fields
            df.at[idx, 'hydrate_formula'] = f"{base_compound}·{hydration_num}H2O"
            df.at[idx, 'hydration_confidence'] = 'high'
            df.at[idx, 'hydration_parsing_method'] = 'direct_parse'
            
            # Update mapping fields
            if 'base_compound_for_mapping' in df.columns:
                df.at[idx, 'base_compound_for_mapping'] = base_compound
            if 'hydration_state' in df.columns:
                df.at[idx, 'hydration_state'] = 'hydrated'
            if 'hydration_number_extracted' in df.columns:
                df.at[idx, 'hydration_number_extracted'] = str(hydration_num)
            
            fixed_count += 1
    
    # Save the file
    df.to_csv(output_file, sep='\t', index=False)
    
    logger.info(f"Fixed {fixed_count} hydrated compounds")
    
    # Show examples
    hydrated = df[df['hydration_number'] != 0]
    if len(hydrated) > 0:
        logger.info("\nExamples of parsed hydrates:")
        for _, row in hydrated.head(15).iterrows():
            orig = row['original']
            base = row['base_compound']
            num = row['hydration_number']
            base_mw = row.get('base_molecular_weight', 0)
            hyd_mw = row.get('hydrated_molecular_weight', 0)
            logger.info(f"  {orig} → {base} + {num} H2O (MW: {base_mw:.1f} → {hyd_mw:.1f})")

def main():
    parser = argparse.ArgumentParser(description="Fix hydrates directly")
    parser.add_argument("--input", required=True, help="Input TSV file")
    parser.add_argument("--output", required=True, help="Output TSV file")
    
    args = parser.parse_args()
    process_file(args.input, args.output)

if __name__ == "__main__":
    main()