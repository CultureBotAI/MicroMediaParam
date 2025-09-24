#!/usr/bin/env python3
"""
Strip hydration information from compounds before mapping, then restore it.
This allows proper ChEBI mapping for compounds like "MnCl2 4-hydrate" → "MnCl2"
"""

import pandas as pd
import re
import argparse
import logging
from pathlib import Path
from typing import Tuple, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HydrateStripper:
    """Strip and restore hydration information for chemical mapping."""
    
    def __init__(self):
        # Patterns to match hydration in various formats
        self.hydration_patterns = [
            # "x H2O", "x-H2O", "xH2O"
            (r'(\s*[·•．.]?\s*)(\d+)\s*[-]?\s*H2O', r'\2'),
            (r'(\s*[·•．.]?\s*)(\d+)\s*[-]?\s*hydrate', r'\2'),
            
            # "·nH2O" or ".nH2O"
            (r'(\s*[·•．.]?\s*)n\s*[-]?\s*H2O', 'n'),
            (r'(\s*[·•．.]?\s*)n\s*[-]?\s*hydrate', 'n'),
            
            # "x H2O" with x
            (r'(\s*[·•．.]?\s*)x\s*[-]?\s*H2O', 'x'),
            (r'(\s*[·•．.]?\s*)x\s*[-]?\s*hydrate', 'x'),
            
            # Parenthetical forms
            (r'\s*\(\s*(\d+)\s*[-]?\s*H2O\s*\)', r'\1'),
            (r'\s*\(\s*(\d+)\s*[-]?\s*hydrate\s*\)', r'\1'),
            
            # Special cases
            (r'(\s+)heptahydrate', '7'),
            (r'(\s+)hexahydrate', '6'),
            (r'(\s+)pentahydrate', '5'),
            (r'(\s+)tetrahydrate', '4'),
            (r'(\s+)trihydrate', '3'),
            (r'(\s+)dihydrate', '2'),
            (r'(\s+)monohydrate', '1'),
            (r'(\s+)hydrate', '1'),  # If just "hydrate", assume monohydrate
        ]
    
    def strip_hydration(self, compound: str) -> Tuple[str, Optional[str]]:
        """
        Strip hydration from compound name and return base compound + hydration number.
        
        Args:
            compound: Original compound name
            
        Returns:
            Tuple of (base_compound, hydration_number)
        """
        if pd.isna(compound) or not compound:
            return compound, None
            
        # Try each pattern
        for pattern, hydration in self.hydration_patterns:
            match = re.search(pattern, compound, re.IGNORECASE)
            if match:
                # Extract hydration number
                if '\\' in hydration:  # It's a regex group reference
                    hydration_num = match.group(int(hydration[1]))
                else:
                    hydration_num = hydration
                
                # Remove hydration from compound name
                base_compound = re.sub(pattern, '', compound, flags=re.IGNORECASE).strip()
                
                # Clean up any remaining dots or spaces
                base_compound = re.sub(r'\s*[·•．.]\s*$', '', base_compound).strip()
                
                return base_compound, hydration_num
        
        # No hydration found
        return compound, None
    
    def process_mapping_file(self, input_file: Path, output_file: Path):
        """Process a mapping file to strip hydration for mapping."""
        logger.info(f"Loading mapping file: {input_file}")
        df = pd.read_csv(input_file, sep='\t')
        
        # Add new columns for hydration info
        df['base_compound_for_mapping'] = ''
        df['hydration_state'] = ''
        df['hydration_number_extracted'] = ''
        
        # Process each row
        stripped_count = 0
        for idx, row in df.iterrows():
            original = row['original']
            
            # Only process unmapped compounds
            if pd.isna(row['mapped']) or row['mapped'] == '':
                base_compound, hydration_num = self.strip_hydration(original)
                
                if hydration_num:
                    df.at[idx, 'base_compound_for_mapping'] = base_compound
                    df.at[idx, 'hydration_state'] = 'hydrated'
                    df.at[idx, 'hydration_number_extracted'] = hydration_num
                    stripped_count += 1
                else:
                    df.at[idx, 'base_compound_for_mapping'] = original
                    df.at[idx, 'hydration_state'] = 'anhydrous'
                    df.at[idx, 'hydration_number_extracted'] = '0'
            else:
                # Already mapped - keep original
                df.at[idx, 'base_compound_for_mapping'] = original
                df.at[idx, 'hydration_state'] = 'already_mapped'
                df.at[idx, 'hydration_number_extracted'] = ''
        
        # Save the updated file
        logger.info(f"Stripped hydration from {stripped_count} compounds")
        df.to_csv(output_file, sep='\t', index=False)
        
        # Report statistics
        hydrated = len(df[df['hydration_state'] == 'hydrated'])
        anhydrous = len(df[df['hydration_state'] == 'anhydrous'])
        already_mapped = len(df[df['hydration_state'] == 'already_mapped'])
        
        logger.info(f"Hydration statistics:")
        logger.info(f"  - Hydrated compounds: {hydrated}")
        logger.info(f"  - Anhydrous compounds: {anhydrous}")
        logger.info(f"  - Already mapped: {already_mapped}")
        
        # Show examples of stripped compounds
        examples = df[df['hydration_state'] == 'hydrated'].head(10)
        if not examples.empty:
            logger.info("\nExamples of stripped hydrates:")
            for _, row in examples.iterrows():
                logger.info(f"  {row['original']} → {row['base_compound_for_mapping']} ({row['hydration_number_extracted']} H2O)")
        
        return df

def main():
    parser = argparse.ArgumentParser(description="Strip hydration for chemical mapping")
    parser.add_argument("--input", required=True, help="Input TSV file")
    parser.add_argument("--output", required=True, help="Output TSV file")
    
    args = parser.parse_args()
    
    stripper = HydrateStripper()
    stripper.process_mapping_file(Path(args.input), Path(args.output))
    
    # Create a separate file with just the base compounds for mapping
    logger.info("\nCreating base compounds file for mapping...")
    df = pd.read_csv(args.output, sep='\t')
    
    # Get unique unmapped base compounds
    unmapped = df[(df['hydration_state'].isin(['hydrated', 'anhydrous'])) & 
                  (df['mapped'].isna() | (df['mapped'] == ''))]
    unique_bases = unmapped['base_compound_for_mapping'].unique()
    
    # Save to compounds file
    compounds_file = Path(args.output).parent / 'base_compounds_for_mapping.txt'
    with open(compounds_file, 'w') as f:
        for compound in sorted(unique_bases):
            if compound and not pd.isna(compound):
                f.write(f"{compound}\n")
    
    logger.info(f"Saved {len(unique_bases)} unique base compounds to: {compounds_file}")

if __name__ == "__main__":
    main()