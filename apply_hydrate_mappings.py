#!/usr/bin/env python3
"""
Apply manual mappings for common hydrated salts to ChEBI.
This handles the most frequent unmapped compounds efficiently.
"""

import pandas as pd
import argparse
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_manual_hydrate_mappings():
    """Manual mappings for common hydrated salts."""
    return {
        # Common hydrated salts - map base compound to ChEBI
        'MgCl2': 'CHEBI:6636',      # magnesium dichloride
        'CaCl2': 'CHEBI:3312',      # calcium dichloride  
        'MgSO4': 'CHEBI:32599',     # magnesium sulfate
        'FeSO4': 'CHEBI:75832',     # iron(2+) sulfate
        'CoSO4': 'CHEBI:53470',     # cobalt(2+) sulfate
        'ZnSO4': 'CHEBI:35176',     # zinc sulfate
        'CuSO4': 'CHEBI:23414',     # copper(II) sulfate
        'Na2MoO4': 'CHEBI:75215',   # sodium molybdate
        'NiCl2': 'CHEBI:34887',     # nickel dichloride
        'Na2SeO3': 'CHEBI:48843',   # disodium selenite
        'Na2WO4': 'CHEBI:77885',    # sodium tungstate
        'MnCl2': 'CHEBI:7773',      # manganese dichloride
        'MnSO4': 'CHEBI:75214',     # manganese sulfate
        'CuCl2': 'CHEBI:49553',     # copper dichloride
        'FeCl2': 'CHEBI:30808',     # iron dichloride
        'FeCl3': 'CHEBI:30808',     # iron trichloride
        'ZnCl2': 'CHEBI:49976',     # zinc dichloride
        'CoCl2': 'CHEBI:35696',     # cobalt dichloride
        'CaSO4': 'CHEBI:31346',     # calcium sulfate
        'BaCl2': 'CHEBI:28575',     # barium dichloride
        'AlCl3': 'CHEBI:28104',     # aluminum trichloride
        'Na2S': 'CHEBI:75769',      # sodium sulfide
        'Na2S2O3': 'CHEBI:76208',   # sodium thiosulfate
        
        # Additional common compounds
        'EDTA': 'CHEBI:42191',      # ethylenediaminetetraacetic acid
        'Tryptone': 'CHEBI:73210',  # tryptone (if available)
        'Casitone': 'CHEBI:73210',  # similar to tryptone
        
        # Common organic compounds
        'citric acid': 'CHEBI:30769',
        'acetic acid': 'CHEBI:15366',
        'lactic acid': 'CHEBI:28358',
        'succinic acid': 'CHEBI:15741',
        'malic acid': 'CHEBI:15595',
        
        # Vitamins and cofactors
        'biotin': 'CHEBI:15956',
        'thiamine': 'CHEBI:18385',
        'riboflavin': 'CHEBI:17015',
        'niacin': 'CHEBI:15940',
        'folic acid': 'CHEBI:27470',
        'cyanocobalamin': 'CHEBI:17439',
        
        # Common salts with alternative names
        'sodium chloride': 'CHEBI:26710',
        'potassium chloride': 'CHEBI:32588',
        'calcium chloride': 'CHEBI:3312',
        'magnesium chloride': 'CHEBI:6636',
        'sodium sulfate': 'CHEBI:32149',
        'potassium sulfate': 'CHEBI:32036',
        'ammonium chloride': 'CHEBI:31206',
        'sodium carbonate': 'CHEBI:29377',
        'sodium bicarbonate': 'CHEBI:32139',
        'potassium phosphate': 'CHEBI:131527',  # K2HPO4
        'sodium phosphate': 'CHEBI:37585',
        'calcium phosphate': 'CHEBI:3390',
    }

def apply_hydrate_mappings(input_file: Path, output_file: Path):
    """Apply manual mappings for hydrated salts."""
    
    logger.info(f"Loading mapping file: {input_file}")
    df = pd.read_csv(input_file, sep='\t')
    
    # Get manual mappings
    manual_mappings = get_manual_hydrate_mappings()
    
    # Apply mappings to unmapped compounds
    updated_count = 0
    for idx, row in df.iterrows():
        # Only update if not already mapped
        if pd.isna(row['mapped']) or row['mapped'] == '':
            base_compound = row.get('base_compound_for_mapping', '')
            
            if base_compound in manual_mappings:
                df.at[idx, 'mapped'] = manual_mappings[base_compound]
                updated_count += 1
    
    logger.info(f"Applied manual mappings to {updated_count} compounds")
    
    # Save updated file
    df.to_csv(output_file, sep='\t', index=False)
    
    # Report statistics
    total_rows = len(df)
    chebi_mapped = len(df[df['mapped'].str.startswith('CHEBI:', na=False)])
    pubchem_mapped = len(df[df['mapped'].str.startswith('PubChem:', na=False)])
    cas_mapped = len(df[df['mapped'].str.startswith('CAS-RN:', na=False)])
    other_mapped = len(df[df['mapped'].notna() & ~df['mapped'].str.startswith(('CHEBI:', 'PubChem:', 'CAS-RN:'), na=False)])
    unmapped = len(df[df['mapped'].isna() | (df['mapped'] == '')])
    
    logger.info(f"\nFinal mapping statistics:")
    logger.info(f"  Total entries: {total_rows}")
    logger.info(f"  ChEBI mapped: {chebi_mapped} ({chebi_mapped/total_rows*100:.1f}%)")
    logger.info(f"  PubChem mapped: {pubchem_mapped} ({pubchem_mapped/total_rows*100:.1f}%)")
    logger.info(f"  CAS-RN mapped: {cas_mapped} ({cas_mapped/total_rows*100:.1f}%)")
    logger.info(f"  Other databases: {other_mapped} ({other_mapped/total_rows*100:.1f}%)")
    logger.info(f"  Still unmapped: {unmapped} ({unmapped/total_rows*100:.1f}%)")
    
    total_mapped = chebi_mapped + pubchem_mapped + cas_mapped + other_mapped
    logger.info(f"  Total mapped: {total_mapped} ({total_mapped/total_rows*100:.1f}%)")
    
    # Show examples of newly mapped compounds
    newly_mapped = df[df['mapped'].isin(manual_mappings.values())]
    if not newly_mapped.empty:
        logger.info(f"\nExamples of newly mapped hydrated compounds:")
        examples = newly_mapped.head(10)
        for _, row in examples.iterrows():
            original = row['original']
            base = row.get('base_compound_for_mapping', '')
            mapped = row['mapped']
            hydration = row.get('hydration_number_extracted', '')
            logger.info(f"  {original} → {base} [{mapped}] ({hydration} H2O)")

def main():
    parser = argparse.ArgumentParser(description="Apply manual hydrate mappings")
    parser.add_argument("--input", required=True, help="Input TSV file")
    parser.add_argument("--output", required=True, help="Output TSV file")
    
    args = parser.parse_args()
    apply_hydrate_mappings(Path(args.input), Path(args.output))

if __name__ == "__main__":
    main()