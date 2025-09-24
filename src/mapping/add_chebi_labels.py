#!/usr/bin/env python3
"""
Add base_chebi_label column to provide human-readable names for ChEBI IDs.
"""

import pandas as pd
import argparse
import logging
import requests
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_chebi_label(chebi_id):
    """Get the label/name for a ChEBI ID from the ChEBI web service."""
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
            # Parse XML response to get the name
            content = response.text
            # Look for <chebiAsciiName> tag
            if '<chebiAsciiName>' in content:
                start = content.find('<chebiAsciiName>') + len('<chebiAsciiName>')
                end = content.find('</chebiAsciiName>')
                if start > 15 and end > start:
                    return content[start:end].strip()
        
        logger.warning(f"Could not fetch label for {chebi_id}")
        return ''
        
    except Exception as e:
        logger.warning(f"Error fetching label for {chebi_id}: {e}")
        return ''

def add_chebi_labels(input_file, output_file):
    """Add base_chebi_label column with human-readable ChEBI names."""
    
    logger.info(f"Loading file: {input_file}")
    df = pd.read_csv(input_file, sep='\t')
    
    # Get unique ChEBI IDs
    unique_chebi_ids = df['base_chebi_id'].dropna().unique()
    unique_chebi_ids = [cid for cid in unique_chebi_ids if cid != '']
    
    logger.info(f"Found {len(unique_chebi_ids)} unique ChEBI IDs to lookup")
    
    # Common ChEBI labels (to avoid API calls for common compounds)
    known_labels = {
        'CHEBI:26710': 'sodium chloride',
        'CHEBI:31206': 'ammonium chloride', 
        'CHEBI:6636': 'magnesium chloride',
        'CHEBI:3312': 'calcium chloride',
        'CHEBI:32588': 'potassium chloride',
        'CHEBI:32139': 'sodium hydrogencarbonate',
        'CHEBI:29377': 'sodium carbonate',
        'CHEBI:131527': 'dipotassium hydrogen phosphate',
        'CHEBI:63036': 'potassium dihydrogen phosphate',
        'CHEBI:32599': 'magnesium sulfate',
        'CHEBI:75832': 'iron(2+) sulfate',
        'CHEBI:75211': 'manganese(2+) sulfate',
        'CHEBI:35176': 'zinc sulfate',
        'CHEBI:23414': 'copper(2+) sulfate',
        'CHEBI:33118': 'boric acid',
        'CHEBI:75215': 'sodium molybdate',
        'CHEBI:34887': 'nickel(2+) chloride',
        'CHEBI:48843': 'sodium selenite',
        'CHEBI:77885': 'sodium tungstate',
        'CHEBI:15956': 'biotin',
        'CHEBI:27470': 'folic acid',
        'CHEBI:30961': 'pyridoxine hydrochloride',
        'CHEBI:49105': 'thiamine hydrochloride',
        'CHEBI:15940': 'nicotinic acid',
        'CHEBI:30753': '4-aminobenzoic acid',
        'CHEBI:43796': 'alpha-lipoic acid',
        'CHEBI:42758': 'D-glucose',
        'CHEBI:48095': 'D-fructose',
        'CHEBI:91247': 'L-cysteine hydrochloride',
        'CHEBI:63005': 'sodium nitrate',
        'CHEBI:63038': 'ammonium nitrate',
        'CHEBI:62982': 'ammonium dihydrogen phosphate',
        'CHEBI:75769': 'sodium sulfide',
        'CHEBI:7773': 'manganese(2+) chloride',
        'CHEBI:35696': 'cobalt(2+) chloride',
        'CHEBI:49553': 'copper(2+) chloride',
        'CHEBI:30808': 'iron(2+) chloride',
        'CHEBI:49976': 'zinc chloride',
        'CHEBI:53470': 'cobalt(2+) sulfate',
        'CHEBI:44557': 'nitrilotriacetic acid',
        'CHEBI:88550': 'sodium acetate',
        'CHEBI:30114': 'aluminium trichloride',
        'CHEBI:88174': 'barium dichloride',
        'CHEBI:47674': 'cadmium dichloride',
        'CHEBI:37003': 'lead(2+) chloride',
        'CHEBI:50341': 'tin(2+) chloride',
        'CHEBI:9754': 'tris',
        'CHEBI:46756': 'HEPES',
        'CHEBI:53580': 'MOPS',
    }
    
    # Create a mapping of ChEBI ID to label
    chebi_to_label = {}
    
    # Use known labels first
    for chebi_id in unique_chebi_ids:
        if chebi_id in known_labels:
            chebi_to_label[chebi_id] = known_labels[chebi_id]
            logger.info(f"Using known label: {chebi_id} -> {known_labels[chebi_id]}")
    
    # For remaining IDs, try to fetch from API (but limit to avoid overloading)
    remaining_ids = [cid for cid in unique_chebi_ids if cid not in chebi_to_label]
    logger.info(f"Need to fetch {len(remaining_ids)} labels from ChEBI API")
    
    # Limit API calls to avoid timeout/rate limiting
    max_api_calls = min(50, len(remaining_ids))
    
    for i, chebi_id in enumerate(remaining_ids[:max_api_calls]):
        if i > 0 and i % 10 == 0:
            logger.info(f"Fetched {i}/{max_api_calls} labels...")
            time.sleep(1)  # Rate limiting
        
        label = get_chebi_label(chebi_id)
        if label:
            chebi_to_label[chebi_id] = label
            logger.info(f"Fetched: {chebi_id} -> {label}")
        else:
            chebi_to_label[chebi_id] = ''
    
    # For any remaining IDs, use empty labels
    for chebi_id in remaining_ids[max_api_calls:]:
        chebi_to_label[chebi_id] = ''
    
    # Add the base_chebi_label column
    logger.info("Adding base_chebi_label column...")
    
    # Find the position to insert the new column (after base_chebi_id)
    columns = list(df.columns)
    base_chebi_id_index = columns.index('base_chebi_id')
    
    # Create the new column
    df['base_chebi_label'] = df['base_chebi_id'].map(lambda x: chebi_to_label.get(x, '') if pd.notna(x) and x != '' else '')
    
    # Reorder columns to put base_chebi_label right after base_chebi_id
    new_columns = (columns[:base_chebi_id_index + 1] + 
                   ['base_chebi_label'] + 
                   columns[base_chebi_id_index + 1:])
    
    # Remove the duplicate base_chebi_label column that was added at the end
    new_columns = [col for i, col in enumerate(new_columns) if col != 'base_chebi_label' or i == base_chebi_id_index + 1]
    
    df = df[new_columns]
    
    # Count how many labels we have
    labels_added = df['base_chebi_label'].notna().sum() - (df['base_chebi_label'] == '').sum()
    total_chebi_ids = df['base_chebi_id'].notna().sum() - (df['base_chebi_id'] == '').sum()
    
    logger.info(f"Added {labels_added}/{total_chebi_ids} ChEBI labels ({labels_added/total_chebi_ids*100:.1f}%)")
    
    # Save the updated file
    df.to_csv(output_file, sep='\t', index=False)
    logger.info(f"Saved updated file: {output_file}")
    
    # Show examples
    labeled_examples = df[df['base_chebi_label'] != ''].head(10)
    logger.info(f"\nExamples of compounds with ChEBI labels:")
    for _, row in labeled_examples.iterrows():
        logger.info(f"  {row['base_compound']}: {row['base_chebi_id']} -> {row['base_chebi_label']}")

def main():
    parser = argparse.ArgumentParser(description="Add ChEBI labels column")
    parser.add_argument("--input", required=True, help="Input TSV file")
    parser.add_argument("--output", required=True, help="Output TSV file")
    
    args = parser.parse_args()
    add_chebi_labels(args.input, args.output)

if __name__ == "__main__":
    main()