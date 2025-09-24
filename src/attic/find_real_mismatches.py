#!/usr/bin/env python3
"""
Find cases where the compound mapping might be chemically incorrect,
not just formatting differences.
"""

import pandas as pd
import argparse
import logging
import re
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def extract_chemical_elements(text):
    """Extract chemical elements from a compound name or formula."""
    if not text or pd.isna(text):
        return set()
    
    text = str(text).upper()
    
    # Remove common non-element words
    text = re.sub(r'\b(ACID|SALT|HYDRATE|MONOHYDRATE|DIHYDRATE|TRIHYDRATE|TETRAHYDRATE|PENTAHYDRATE|HEXAHYDRATE|HEPTAHYDRATE|OCTAHYDRATE|NONAHYDRATE|DECAHYDRATE|ANHYDROUS|HYDROCHLORIDE|SULFATE|NITRATE|CARBONATE|PHOSPHATE|ACETATE|CITRATE|CHLORIDE|BROMIDE|IODIDE|FLUORIDE|OXIDE|HYDROXIDE|HYDRO|MONO|DI|TRI|TETRA|PENTA|HEXA|HEPTA|OCTA|NONA|DECA)\b', '', text)
    
    # Extract element patterns
    elements = set()
    
    # Common element patterns in names
    element_patterns = {
        'SODIUM': 'NA', 'POTASSIUM': 'K', 'CALCIUM': 'CA', 'MAGNESIUM': 'MG',
        'IRON': 'FE', 'COPPER': 'CU', 'ZINC': 'ZN', 'MANGANESE': 'MN',
        'COBALT': 'CO', 'NICKEL': 'NI', 'ALUMINUM': 'AL', 'ALUMINIUM': 'AL',
        'LEAD': 'PB', 'TIN': 'SN', 'SILVER': 'AG', 'GOLD': 'AU',
        'MERCURY': 'HG', 'CHROMIUM': 'CR', 'MOLYBDENUM': 'MO', 'TUNGSTEN': 'W',
        'SELENIUM': 'SE', 'SULFUR': 'S', 'PHOSPHORUS': 'P', 'NITROGEN': 'N',
        'CARBON': 'C', 'OXYGEN': 'O', 'HYDROGEN': 'H', 'CHLORINE': 'CL',
        'BROMINE': 'BR', 'IODINE': 'I', 'FLUORINE': 'F', 'BORON': 'B',
        'SILICON': 'SI', 'ARSENIC': 'AS', 'ANTIMONY': 'SB', 'BISMUTH': 'BI',
        'CADMIUM': 'CD', 'BARIUM': 'BA', 'STRONTIUM': 'SR', 'LITHIUM': 'LI',
        'RUBIDIUM': 'RB', 'CESIUM': 'CS', 'CAESIUM': 'CS', 'VANADIUM': 'V',
        'TITANIUM': 'TI', 'SCANDIUM': 'SC', 'YTTRIUM': 'Y', 'ZIRCONIUM': 'ZR',
        'NIOBIUM': 'NB', 'TANTALUM': 'TA', 'RHENIUM': 'RE', 'OSMIUM': 'OS',
        'IRIDIUM': 'IR', 'PLATINUM': 'PT', 'PALLADIUM': 'PD', 'RHODIUM': 'RH',
        'RUTHENIUM': 'RU', 'TECHNETIUM': 'TC', 'GALLIUM': 'GA', 'GERMANIUM': 'GE',
        'INDIUM': 'IN', 'THALLIUM': 'TL', 'LANTHANUM': 'LA', 'CERIUM': 'CE',
        'PRASEODYMIUM': 'PR', 'NEODYMIUM': 'ND', 'SAMARIUM': 'SM', 'EUROPIUM': 'EU',
        'GADOLINIUM': 'GD', 'TERBIUM': 'TB', 'DYSPROSIUM': 'DY', 'HOLMIUM': 'HO',
        'ERBIUM': 'ER', 'THULIUM': 'TM', 'YTTERBIUM': 'YB', 'LUTETIUM': 'LU'
    }
    
    # Check for element names
    for element_name, symbol in element_patterns.items():
        if element_name in text:
            elements.add(symbol)
    
    # Extract elements from formula patterns
    # Look for element symbols (capital letter possibly followed by lowercase)
    formula_elements = re.findall(r'\b([A-Z][a-z]?)\b', text)
    
    # Valid element symbols
    valid_elements = {
        'H', 'HE', 'LI', 'BE', 'B', 'C', 'N', 'O', 'F', 'NE',
        'NA', 'MG', 'AL', 'SI', 'P', 'S', 'CL', 'AR', 'K', 'CA',
        'SC', 'TI', 'V', 'CR', 'MN', 'FE', 'CO', 'NI', 'CU', 'ZN',
        'GA', 'GE', 'AS', 'SE', 'BR', 'KR', 'RB', 'SR', 'Y', 'ZR',
        'NB', 'MO', 'TC', 'RU', 'RH', 'PD', 'AG', 'CD', 'IN', 'SN',
        'SB', 'TE', 'I', 'XE', 'CS', 'BA', 'LA', 'CE', 'PR', 'ND',
        'PM', 'SM', 'EU', 'GD', 'TB', 'DY', 'HO', 'ER', 'TM', 'YB',
        'LU', 'HF', 'TA', 'W', 'RE', 'OS', 'IR', 'PT', 'AU', 'HG',
        'TL', 'PB', 'BI', 'PO', 'AT', 'RN', 'FR', 'RA', 'AC', 'TH',
        'PA', 'U', 'NP', 'PU', 'AM', 'CM', 'BK', 'CF', 'ES', 'FM'
    }
    
    for elem in formula_elements:
        if elem.upper() in valid_elements:
            elements.add(elem.upper())
    
    return elements

def find_real_mismatches(input_file, output_file):
    """Find potential real chemical mismatches, not just formatting differences."""
    
    logger.info(f"Loading file: {input_file}")
    df = pd.read_csv(input_file, sep='\t')
    
    # Only look at entries with ChEBI labels
    chebi_entries = df[df['base_chebi_label'].notna() & (df['base_chebi_label'] != '')].copy()
    logger.info(f"Found {len(chebi_entries)} entries with ChEBI labels")
    
    # Extract elements from original and ChEBI label
    chebi_entries['original_elements'] = chebi_entries['original'].apply(extract_chemical_elements)
    chebi_entries['label_elements'] = chebi_entries['base_chebi_label'].apply(extract_chemical_elements)
    chebi_entries['formula_elements'] = chebi_entries['base_chebi_formula'].apply(extract_chemical_elements)
    
    # Find element mismatches
    potential_mismatches = []
    
    for idx, row in chebi_entries.iterrows():
        original_elems = row['original_elements']
        label_elems = row['label_elements']
        formula_elems = row['formula_elements']
        
        # Combine label and formula elements for comparison
        chebi_elems = label_elems.union(formula_elems)
        
        # Skip if no elements found
        if not original_elems or not chebi_elems:
            continue
        
        # Check for element differences
        missing_from_chebi = original_elems - chebi_elems
        extra_in_chebi = chebi_elems - original_elems
        
        # Ignore certain differences
        ignore_elements = {'H', 'O'}  # Water/hydration differences
        missing_from_chebi = missing_from_chebi - ignore_elements
        extra_in_chebi = extra_in_chebi - ignore_elements
        
        if missing_from_chebi or extra_in_chebi:
            potential_mismatches.append({
                'medium_id': row['medium_id'],
                'original': row['original'],
                'base_compound': row['base_compound'],
                'base_chebi_id': row['base_chebi_id'],
                'base_chebi_label': row['base_chebi_label'],
                'base_chebi_formula': row['base_chebi_formula'],
                'original_elements': ', '.join(sorted(original_elems)),
                'chebi_elements': ', '.join(sorted(chebi_elems)),
                'missing_from_chebi': ', '.join(sorted(missing_from_chebi)),
                'extra_in_chebi': ', '.join(sorted(extra_in_chebi))
            })
    
    # Create output dataframe
    mismatch_df = pd.DataFrame(potential_mismatches)
    
    if len(mismatch_df) > 0:
        mismatch_df.to_csv(output_file, sep='\t', index=False)
        logger.info(f"Saved {len(mismatch_df)} potential real mismatches to: {output_file}")
    else:
        logger.info("No potential real mismatches found!")
        # Create empty file
        pd.DataFrame(columns=['medium_id', 'original', 'base_compound', 'base_chebi_id', 
                            'base_chebi_label', 'base_chebi_formula']).to_csv(output_file, sep='\t', index=False)
    
    # Show statistics
    total_checked = len(chebi_entries)
    mismatch_count = len(mismatch_df) if len(mismatch_df) > 0 else 0
    mismatch_percent = (mismatch_count / total_checked) * 100 if total_checked > 0 else 0
    
    logger.info(f"\nReal Mismatch Analysis:")
    logger.info(f"  Total entries checked: {total_checked:,}")
    logger.info(f"  Potential real mismatches: {mismatch_count:,} ({mismatch_percent:.2f}%)")
    
    if len(mismatch_df) > 0:
        # Show examples
        logger.info(f"\nExamples of potential real mismatches:")
        for _, row in mismatch_df.head(10).iterrows():
            logger.info(f"\n  Original: '{row['original']}'")
            logger.info(f"  ChEBI: '{row['base_chebi_label']}' ({row['base_chebi_formula']})")
            if row['missing_from_chebi']:
                logger.info(f"  Missing elements: {row['missing_from_chebi']}")
            if row['extra_in_chebi']:
                logger.info(f"  Extra elements: {row['extra_in_chebi']}")
        
        # Analyze patterns
        logger.info(f"\nMismatch patterns:")
        
        # Group by missing/extra elements
        if 'missing_from_chebi' in mismatch_df.columns:
            missing_counts = mismatch_df[mismatch_df['missing_from_chebi'] != '']['missing_from_chebi'].value_counts()
            logger.info(f"\nMost common missing elements:")
            for elem, count in missing_counts.head(5).items():
                logger.info(f"  {elem}: {count} cases")
        
        if 'extra_in_chebi' in mismatch_df.columns:
            extra_counts = mismatch_df[mismatch_df['extra_in_chebi'] != '']['extra_in_chebi'].value_counts()
            logger.info(f"\nMost common extra elements:")
            for elem, count in extra_counts.head(5).items():
                logger.info(f"  {elem}: {count} cases")

def main():
    parser = argparse.ArgumentParser(description="Find real chemical mismatches")
    parser.add_argument("--input", required=True, help="Input TSV file")
    parser.add_argument("--output", required=True, help="Output TSV file for real mismatches")
    
    args = parser.parse_args()
    find_real_mismatches(args.input, args.output)

if __name__ == "__main__":
    main()