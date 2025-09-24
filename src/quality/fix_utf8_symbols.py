#!/usr/bin/env python3
"""
Fix UTF-8 encoded symbols that might display as strange characters.
Replace with standard ASCII characters.
"""

import pandas as pd
import argparse
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_utf8_symbols(input_file, output_file):
    """Fix UTF-8 symbols in hydrate formulas."""
    
    logger.info(f"Loading file: {input_file}")
    
    # Read with explicit UTF-8 encoding
    df = pd.read_csv(input_file, sep='\t', encoding='utf-8')
    
    # Fix hydrate_formula column
    fixes = 0
    for idx, row in df.iterrows():
        hydrate_formula = row.get('hydrate_formula', '')
        if pd.notna(hydrate_formula) and hydrate_formula:
            original = str(hydrate_formula)
            
            # Replace UTF-8 middle dot and other symbols with standard dot
            fixed = original
            fixed = fixed.replace('·', '.')  # UTF-8 middle dot to ASCII dot
            fixed = fixed.replace('•', '.')  # Bullet point
            fixed = fixed.replace('⋅', '.')  # Dot operator
            fixed = fixed.replace('∑', '')   # Sigma symbol (remove)
            fixed = fixed.replace('¬', '')   # Not symbol (remove)
            
            if fixed != original:
                df.at[idx, 'hydrate_formula'] = fixed
                fixes += 1
                logger.info(f"  Fixed: '{original}' → '{fixed}'")
    
    # Save with explicit UTF-8 encoding
    df.to_csv(output_file, sep='\t', index=False, encoding='utf-8')
    
    logger.info(f"Fixed {fixes} UTF-8 symbol issues")
    
    # Show examples of current hydrate formulas
    hydrates = df[df['hydrate_formula'].str.contains(r'\..*H2O', na=False)]
    logger.info(f"\nExamples of hydrate formulas with ASCII dots ({len(hydrates)} total):")
    for _, row in hydrates.head(10).iterrows():
        logger.info(f"  {row['original']}: {row['hydrate_formula']}")

def main():
    parser = argparse.ArgumentParser(description="Fix UTF-8 symbols")
    parser.add_argument("--input", required=True, help="Input TSV file")
    parser.add_argument("--output", required=True, help="Output TSV file")
    
    args = parser.parse_args()
    fix_utf8_symbols(args.input, args.output)

if __name__ == "__main__":
    main()