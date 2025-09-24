#!/usr/bin/env python3
"""
Fix hydrate detection to properly parse compounds like "MgCl2 6-hydrate" as hydrates.
"""

import pandas as pd
import re
import argparse
import logging
from pathlib import Path
from typing import Tuple, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ImprovedHydrateParser:
    """Improved hydrate detection and parsing."""
    
    def __init__(self):
        # Comprehensive patterns for hydrate detection
        self.hydration_patterns = [
            # "n-hydrate" or "n hydrate" formats
            (r'(\d+)\s*[-]?\s*hydrate', r'\1'),
            
            # "n-H2O", "n H2O", "n-water" formats
            (r'(\d+)\s*[-]?\s*H2O', r'\1'),
            (r'(\d+)\s*[-]?\s*water', r'\1'),
            
            # "·nH2O" or ".nH2O" or "•nH2O"
            (r'[·•．.]\s*(\d+)\s*H2O', r'\1'),
            (r'[·•．.]\s*(\d+)\s*hydrate', r'\1'),
            
            # "x H2O" or "x hydrate" (variable hydration)
            (r'x\s*[-]?\s*H2O', 'x'),
            (r'x\s*[-]?\s*hydrate', 'x'),
            (r'n\s*[-]?\s*H2O', 'n'),
            (r'n\s*[-]?\s*hydrate', 'n'),
            
            # Space-separated like "MgCl2 6H2O" or "MgCl2 6 H2O"
            (r'\s+(\d+)\s*H2O$', r'\1'),
            (r'\s+(\d+)\s*hydrate$', r'\1'),
            
            # Parenthetical forms "(6H2O)" or "(6-hydrate)"
            (r'\(\s*(\d+)\s*[-]?\s*H2O\s*\)', r'\1'),
            (r'\(\s*(\d+)\s*[-]?\s*hydrate\s*\)', r'\1'),
            
            # Named hydrates
            (r'\b(mono|uni)hydrate', '1'),
            (r'\b(di|bi)hydrate', '2'),
            (r'\btrihydrate', '3'),
            (r'\btetrahydrate', '4'),
            (r'\bpentahydrate', '5'),
            (r'\bhexahydrate', '6'),
            (r'\bheptahydrate', '7'),
            (r'\boctahydrate', '8'),
            (r'\bnonahydrate', '9'),
            (r'\bdecahydrate', '10'),
            (r'\bundecahydrate', '11'),
            (r'\bdodecahydrate', '12'),
            
            # Just "hydrate" at end means monohydrate
            (r'\bhydrate$', '1'),
            
            # Special formats like "2H2O" directly attached
            (r'[-·•．.](\d+)H2O', r'\1'),
            
            # Formats with asterisk like "*6H2O"
            (r'\*\s*(\d+)\s*H2O', r'\1'),
            (r'\*\s*(\d+)\s*hydrate', r'\1'),
        ]
    
    def detect_and_parse_hydrate(self, compound: str) -> Tuple[str, Optional[str], bool]:
        """
        Detect if compound is hydrated and parse it.
        
        Returns:
            Tuple of (base_compound, hydration_number, is_hydrated)
        """
        if pd.isna(compound) or not compound:
            return compound, None, False
        
        compound = str(compound).strip()
        
        # Try each pattern
        for pattern, hydration_value in self.hydration_patterns:
            match = re.search(pattern, compound, re.IGNORECASE)
            if match:
                # Extract hydration number
                if '\\' in hydration_value:  # It's a regex group reference
                    hydration_num = match.group(int(hydration_value[1]))
                else:
                    hydration_num = hydration_value
                
                # Remove hydration part from compound name
                base_compound = re.sub(pattern, '', compound, flags=re.IGNORECASE).strip()
                
                # Clean up any remaining separators
                base_compound = re.sub(r'[·•．.*\s]+$', '', base_compound).strip()
                
                # Special handling for compounds ending with numbers
                # Don't remove trailing numbers that are part of the formula
                if base_compound and not re.match(r'.*\d$', base_compound):
                    base_compound = re.sub(r'\s+\d+$', '', base_compound)
                
                return base_compound, hydration_num, True
        
        # No hydration found
        return compound, None, False
    
    def get_formula_from_base_compound(self, base_compound: str) -> str:
        """Extract or normalize chemical formula from base compound."""
        # If it's already a formula-like string
        if re.match(r'^[A-Z][a-z]?\d*([A-Z][a-z]?\d*)*$', base_compound):
            return base_compound
            
        # Clean up common issues
        base_compound = base_compound.replace(' ', '')
        
        # Fix common typos/variations
        replacements = {
            'MgCl26-hydrate': 'MgCl2',
            'CaCl22-hydrate': 'CaCl2', 
            'MgSO47-hydrate': 'MgSO4',
            'FeSO47-hydrate': 'FeSO4',
            'CoSO47-hydrate': 'CoSO4',
            'ZnSO47-hydrate': 'ZnSO4',
            'CuSO45-hydrate': 'CuSO4',
            'Na2MoO42-hydrate': 'Na2MoO4',
            'NiCl26-hydrate': 'NiCl2',
            'Na2SeO35-hydrate': 'Na2SeO3',
            'Na2WO42-hydrate': 'Na2WO4',
            'Na2S9-hydrate': 'Na2S',
            'MnCl24-hydrate': 'MnCl2',
            'CoCl26-hydrate': 'CoCl2',
            'CuCl22-hydrate': 'CuCl2',
            'FeCl24-hydrate': 'FeCl2',
        }
        
        for old, new in replacements.items():
            if old in base_compound:
                return new
                
        return base_compound

def process_file_with_improved_hydration(input_file: Path, output_file: Path):
    """Reprocess file with improved hydrate detection."""
    
    logger.info(f"Loading file: {input_file}")
    df = pd.read_csv(input_file, sep='\t')
    
    parser = ImprovedHydrateParser()
    
    # Track fixes
    fixed_count = 0
    previously_missed = 0
    
    for idx, row in df.iterrows():
        original = row['original']
        current_base = row.get('base_compound', '')
        current_hydration_num = row.get('hydration_number', 0)
        
        # Parse with improved detection
        new_base, new_hydration_num, is_hydrated = parser.detect_and_parse_hydrate(original)
        
        # Check if this fixes a previously missed hydrate
        if is_hydrated and (current_hydration_num == 0 or pd.isna(current_hydration_num)):
            # This was missed before
            previously_missed += 1
            
            # Update fields
            df.at[idx, 'base_compound'] = new_base
            df.at[idx, 'base_formula'] = parser.get_formula_from_base_compound(new_base)
            df.at[idx, 'hydration_number'] = int(new_hydration_num) if new_hydration_num.isdigit() else new_hydration_num
            df.at[idx, 'hydrate_formula'] = f"{new_base}·{new_hydration_num}H2O"
            df.at[idx, 'hydration_confidence'] = 'high'
            df.at[idx, 'hydration_parsing_method'] = 'improved_parser'
            
            # Update mapping fields
            df.at[idx, 'base_compound_for_mapping'] = new_base
            df.at[idx, 'hydration_state'] = 'hydrated'
            df.at[idx, 'hydration_number_extracted'] = new_hydration_num
            
            fixed_count += 1
        
        # Also fix any that have wrong base compound (like "MgCl26-hydrate")
        elif current_base and ('hydrate' in str(current_base) or re.search(r'\d+-', str(current_base))):
            cleaned_base = parser.get_formula_from_base_compound(current_base)
            if cleaned_base != current_base:
                df.at[idx, 'base_compound'] = cleaned_base
                df.at[idx, 'base_formula'] = cleaned_base
                df.at[idx, 'base_compound_for_mapping'] = cleaned_base
                fixed_count += 1
    
    # Save updated file
    logger.info(f"Fixed {fixed_count} compounds ({previously_missed} were previously missed hydrates)")
    df.to_csv(output_file, sep='\t', index=False)
    
    # Show examples of fixes
    if previously_missed > 0:
        logger.info("\nExamples of fixed hydrates:")
        fixed_examples = df[df['hydration_parsing_method'] == 'improved_parser'].head(15)
        for _, row in fixed_examples.iterrows():
            orig = row['original']
            base = row['base_compound']
            hydration = row['hydration_number']
            logger.info(f"  {orig} → {base} + {hydration} H2O")
    
    # Statistics
    # Convert hydration_number to numeric for comparison, treating 'x' and 'n' as hydrated
    df['hydration_number_numeric'] = pd.to_numeric(df['hydration_number'], errors='coerce')
    total_hydrated = len(df[(df['hydration_number_numeric'] > 0) | (df['hydration_number'].isin(['x', 'n']))])
    total_entries = len(df)
    logger.info(f"\nTotal hydrated compounds: {total_hydrated}/{total_entries} ({total_hydrated/total_entries*100:.1f}%)")

def main():
    parser = argparse.ArgumentParser(description="Fix hydrate detection")
    parser.add_argument("--input", required=True, help="Input TSV file")
    parser.add_argument("--output", required=True, help="Output TSV file")
    
    args = parser.parse_args()
    process_file_with_improved_hydration(Path(args.input), Path(args.output))

if __name__ == "__main__":
    main()