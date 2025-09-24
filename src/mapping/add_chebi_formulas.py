#!/usr/bin/env python3
"""
Add base_chebi_formula column to provide chemical formulas for ChEBI IDs.
"""

import pandas as pd
import argparse
import logging
import requests
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_chebi_formula(chebi_id):
    """Get the chemical formula for a ChEBI ID from the ChEBI web service."""
    if not chebi_id or pd.isna(chebi_id) or chebi_id == '':
        return ''
    
    try:
        # Extract numeric ID from CHEBI:xxxxx format
        if chebi_id.startswith('CHEBI:'):
            numeric_id = chebi_id.replace('CHEBI:', '')
        else:
            numeric_id = chebi_id
        
        # ChEBI REST API endpoint
        url = f"https://www.ebi.ac.uk/chebi/webServices/2.0/test/getCompleteEntity"
        params = {'chebiId': numeric_id}
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            # Parse XML response to get the formula
            content = response.text
            # Look for <Formulae> section and <data> tag
            if '<Formulae>' in content:
                formulae_start = content.find('<Formulae>')
                formulae_end = content.find('</Formulae>')
                if formulae_start > 0 and formulae_end > formulae_start:
                    formulae_section = content[formulae_start:formulae_end]
                    # Look for <data> tag within Formulae
                    if '<data>' in formulae_section:
                        start = formulae_section.find('<data>') + len('<data>')
                        end = formulae_section.find('</data>')
                        if start > 5 and end > start:
                            formula = formulae_section[start:end].strip()
                            if formula and formula != 'null':
                                return formula
        
        logger.warning(f"Could not fetch formula for {chebi_id}")
        return ''
        
    except Exception as e:
        logger.warning(f"Error fetching formula for {chebi_id}: {e}")
        return ''

def add_chebi_formulas(input_file, output_file):
    """Add base_chebi_formula column with chemical formulas."""
    
    logger.info(f"Loading file: {input_file}")
    df = pd.read_csv(input_file, sep='\t')
    
    # Get unique ChEBI IDs
    unique_chebi_ids = df['base_chebi_id'].dropna().unique()
    unique_chebi_ids = [cid for cid in unique_chebi_ids if cid != '']
    
    logger.info(f"Found {len(unique_chebi_ids)} unique ChEBI IDs to lookup")
    
    # Common ChEBI formulas (to avoid API calls for common compounds)
    known_formulas = {
        'CHEBI:26710': 'NaCl',
        'CHEBI:31206': 'ClH4N', 
        'CHEBI:6636': 'Cl2Mg',
        'CHEBI:3312': 'CaCl2',
        'CHEBI:32588': 'ClK',
        'CHEBI:32139': 'CHNaO3',
        'CHEBI:29377': 'CNa2O3',
        'CHEBI:131527': 'HK2O4P',
        'CHEBI:63036': 'H2KO4P',
        'CHEBI:32599': 'MgO4S',
        'CHEBI:75832': 'FeO4S',
        'CHEBI:75211': 'MnO4S',
        'CHEBI:35176': 'O4SZn',
        'CHEBI:23414': 'CuO4S',
        'CHEBI:33118': 'BH3O3',
        'CHEBI:75215': 'MoNa2O4',
        'CHEBI:34887': 'Cl2Ni',
        'CHEBI:48843': 'Na2O3Se',
        'CHEBI:77885': 'Na2O4W',
        'CHEBI:15956': 'C10H16N2O3S',
        'CHEBI:27470': 'C19H19N7O6',
        'CHEBI:30961': 'C8H12ClNO3',
        'CHEBI:49105': 'C12H18Cl2N4OS',
        'CHEBI:15940': 'C6H5NO2',
        'CHEBI:30753': 'C7H7NO2',
        'CHEBI:43796': 'C8H14O2S2',
        'CHEBI:42758': 'C6H12O6',
        'CHEBI:48095': 'C6H12O6',
        'CHEBI:91247': 'C3H8ClNO2S',
        'CHEBI:63005': 'NNaO3',
        'CHEBI:63038': 'H4N2O3',
        'CHEBI:62982': 'H6NO4P',
        'CHEBI:75769': 'Na2S',
        'CHEBI:7773': 'Cl2Mn',
        'CHEBI:35696': 'Cl2Co',
        'CHEBI:49553': 'Cl2Cu',
        'CHEBI:30808': 'Cl2Fe',
        'CHEBI:49976': 'Cl2Zn',
        'CHEBI:53470': 'CoO4S',
        'CHEBI:44557': 'C6H9NO6',
        'CHEBI:88550': 'C2H3NaO2',
        'CHEBI:30114': 'AlCl3',
        'CHEBI:88174': 'BaCl2',
        'CHEBI:47674': 'CdCl2',
        'CHEBI:37003': 'Cl2Pb',
        'CHEBI:50341': 'Cl2Sn',
        'CHEBI:9754': 'C4H11NO3',
        'CHEBI:46756': 'C8H18N2O4S',
        'CHEBI:53580': 'C7H15NO4S',
    }
    
    # Create a mapping of ChEBI ID to formula
    chebi_to_formula = {}
    
    # Use known formulas first
    for chebi_id in unique_chebi_ids:
        if chebi_id in known_formulas:
            chebi_to_formula[chebi_id] = known_formulas[chebi_id]
            logger.info(f"Using known formula: {chebi_id} -> {known_formulas[chebi_id]}")
    
    # For remaining IDs, try to fetch from API (but limit to avoid overloading)
    remaining_ids = [cid for cid in unique_chebi_ids if cid not in chebi_to_formula]
    logger.info(f"Need to fetch {len(remaining_ids)} formulas from ChEBI API")
    
    # Limit API calls to avoid timeout/rate limiting
    max_api_calls = min(30, len(remaining_ids))
    
    for i, chebi_id in enumerate(remaining_ids[:max_api_calls]):
        if i > 0 and i % 5 == 0:
            logger.info(f"Fetched {i}/{max_api_calls} formulas...")
            time.sleep(2)  # Rate limiting
        
        formula = get_chebi_formula(chebi_id)
        if formula:
            chebi_to_formula[chebi_id] = formula
            logger.info(f"Fetched: {chebi_id} -> {formula}")
        else:
            chebi_to_formula[chebi_id] = ''
    
    # For any remaining IDs, use empty formulas
    for chebi_id in remaining_ids[max_api_calls:]:
        chebi_to_formula[chebi_id] = ''
    
    # Add the base_chebi_formula column
    logger.info("Adding base_chebi_formula column...")
    
    # Find the position to insert the new column (after base_chebi_label)
    columns = list(df.columns)
    base_chebi_label_index = columns.index('base_chebi_label')
    
    # Create the new column
    df['base_chebi_formula'] = df['base_chebi_id'].map(
        lambda x: chebi_to_formula.get(x, '') if pd.notna(x) and x != '' else ''
    )
    
    # Reorder columns to put base_chebi_formula right after base_chebi_label
    new_columns = (columns[:base_chebi_label_index + 1] + 
                   ['base_chebi_formula'] + 
                   columns[base_chebi_label_index + 1:])
    
    # Remove the duplicate base_chebi_formula column that was added at the end
    new_columns = [col for i, col in enumerate(new_columns) 
                   if col != 'base_chebi_formula' or i == base_chebi_label_index + 1]
    
    df = df[new_columns]
    
    # Count how many formulas we have
    formulas_added = df['base_chebi_formula'].notna().sum() - (df['base_chebi_formula'] == '').sum()
    total_chebi_ids = df['base_chebi_id'].notna().sum() - (df['base_chebi_id'] == '').sum()
    
    logger.info(f"Added {formulas_added}/{total_chebi_ids} ChEBI formulas ({formulas_added/total_chebi_ids*100:.1f}%)")
    
    # Save the updated file
    df.to_csv(output_file, sep='\t', index=False)
    logger.info(f"Saved updated file: {output_file}")
    
    # Show examples
    formula_examples = df[df['base_chebi_formula'] != ''].head(10)
    logger.info(f"\nExamples of compounds with ChEBI formulas:")
    for _, row in formula_examples.iterrows():
        logger.info(f"  {row['base_compound']}: {row['base_chebi_id']} -> {row['base_chebi_formula']}")
    
    # Compare with original formulas
    logger.info(f"\nComparison with base_formula:")
    comparison_examples = df[(df['base_chebi_formula'] != '') & (df['base_formula'] != '')].head(10)
    for _, row in comparison_examples.iterrows():
        original_formula = row['base_formula']
        chebi_formula = row['base_chebi_formula']
        match = "✓" if original_formula == chebi_formula else "✗"
        logger.info(f"  {row['base_compound']}: {original_formula} vs {chebi_formula} {match}")

def main():
    parser = argparse.ArgumentParser(description="Add ChEBI formulas column")
    parser.add_argument("--input", required=True, help="Input TSV file")
    parser.add_argument("--output", required=True, help="Output TSV file")
    
    args = parser.parse_args()
    add_chebi_formulas(args.input, args.output)

if __name__ == "__main__":
    main()