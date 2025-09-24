#!/usr/bin/env python3
"""
Apply fuzzy ChEBI mappings to composition mapping file.
"""

import pandas as pd
import json
import argparse
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="Apply fuzzy ChEBI mappings")
    parser.add_argument("--input", required=True, help="Input TSV file")
    parser.add_argument("--fuzzy-mappings", default="chebi_fuzzy_mappings.json", help="Fuzzy mappings JSON file")
    parser.add_argument("--output", required=True, help="Output TSV file")
    
    args = parser.parse_args()
    
    # Load the composition mapping
    logger.info(f"Loading composition mapping from: {args.input}")
    df = pd.read_csv(args.input, sep='\t')
    
    # Load fuzzy mappings
    fuzzy_mappings = {}
    fuzzy_file = Path(args.fuzzy_mappings)
    if fuzzy_file.exists():
        logger.info(f"Loading fuzzy mappings from: {args.fuzzy_mappings}")
        with open(fuzzy_file, 'r') as f:
            data = json.load(f)
            for item in data:
                compound_name = item['query']
                if item['matches']:
                    best_match = item['matches'][0]  # Take the best match
                    fuzzy_mappings[compound_name] = best_match['chebi_id']
    
    # Apply fuzzy mappings
    updated_count = 0
    for idx, row in df.iterrows():
        original_compound = row['original']
        current_mapping = row['mapped']
        
        # Only update if not already mapped to ChEBI or if mapped to non-ChEBI
        if (pd.isna(current_mapping) or current_mapping == '' or 
            not str(current_mapping).startswith('CHEBI:')):
            if original_compound in fuzzy_mappings:
                df.at[idx, 'mapped'] = fuzzy_mappings[original_compound]
                updated_count += 1
    
    logger.info(f"Updated {updated_count} mappings with fuzzy matches")
    
    # Save the updated mapping
    logger.info(f"Saving updated mapping to: {args.output}")
    df.to_csv(args.output, sep='\t', index=False)
    
    # Report statistics
    total_rows = len(df)
    chebi_mapped = len(df[df['mapped'].str.startswith('CHEBI:', na=False)])
    logger.info(f"Final statistics: {chebi_mapped}/{total_rows} ({chebi_mapped/total_rows*100:.1f}%) mapped to ChEBI")

if __name__ == "__main__":
    main()