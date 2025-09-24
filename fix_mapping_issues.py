#!/usr/bin/env python3
"""
Fix two types of mapping issues:
1. Separate concentration notation from chemical names (e.g., "NaHCO3 (10% (w/v))")
2. Fix incorrect K-acetate → sodium acetate mappings
"""

import pandas as pd
import argparse
import logging
import re
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_mapping_issues(input_file, output_file):
    """Fix concentration notation and incorrect mappings."""
    
    logger.info(f"Loading file: {input_file}")
    df = pd.read_csv(input_file, sep='\t')
    
    logger.info(f"Original dataset shape: {df.shape}")
    
    # 1. Fix concentration notation in compound names
    logger.info("Fixing concentration notation in compound names...")
    
    concentration_fixes = 0
    concentration_patterns = [
        r'\s*\(\s*\d+%\s*\([wv]/[wv]\)\s*\)',  # (10% (w/v))
        r'\s*\(\s*\d+%\s*w/v\s*\)',             # (10% w/v)
        r'\s*\(\s*\d+%\s*\(w/v\)\s*\)',         # (10% (w/v))
        r'\s*\(\s*\d+\.\d+%\s*\([wv]/[wv]\)\s*\)', # (2.5% (w/v))
        r'\s*\(\s*\d+\.\d+%\s*w/v\s*\)',        # (2.5% w/v)
        r'\s*\(\s*\d+\.\d+%\s*\(w/v\)\s*\)',    # (2.5% (w/v))
    ]
    
    for idx, row in df.iterrows():
        original = str(row['original'])
        base_compound = str(row['base_compound'])
        
        # Check if original contains concentration notation
        for pattern in concentration_patterns:
            if re.search(pattern, original, re.IGNORECASE):
                # Extract the clean compound name
                clean_original = re.sub(pattern, '', original, flags=re.IGNORECASE).strip()
                clean_base = re.sub(pattern, '', base_compound, flags=re.IGNORECASE).strip()
                
                if clean_original != original:
                    df.at[idx, 'original'] = clean_original
                    concentration_fixes += 1
                    logger.info(f"  Fixed: '{original}' → '{clean_original}'")
                
                if clean_base != base_compound:
                    df.at[idx, 'base_compound'] = clean_base
                
                break
    
    logger.info(f"✓ Fixed {concentration_fixes} concentration notation issues")
    
    # 2. Fix K-acetate mapping errors
    logger.info("Fixing K-acetate mapping errors...")
    
    # Find K-acetate entries mapped to sodium acetate (CHEBI:88550)
    k_acetate_errors = df[
        (df['original'].str.contains('K-acetate', case=False, na=False)) &
        (df['base_chebi_id'] == 'CHEBI:88550')
    ]
    
    logger.info(f"Found {len(k_acetate_errors)} K-acetate entries incorrectly mapped to sodium acetate")
    
    # Correct ChEBI ID for potassium acetate
    # CHEBI:32047 is potassium acetate
    correct_k_acetate_chebi = 'CHEBI:32047'
    correct_k_acetate_label = 'potassium acetate'
    correct_k_acetate_formula = 'C2H3KO2'
    
    mapping_fixes = 0
    for idx in k_acetate_errors.index:
        # Update the mapping information
        df.at[idx, 'mapped'] = correct_k_acetate_chebi
        df.at[idx, 'base_chebi_id'] = correct_k_acetate_chebi
        df.at[idx, 'base_chebi_label'] = correct_k_acetate_label
        df.at[idx, 'base_chebi_formula'] = correct_k_acetate_formula
        
        mapping_fixes += 1
        logger.info(f"  Fixed: '{df.at[idx, 'original']}' → {correct_k_acetate_chebi} ({correct_k_acetate_label})")
    
    logger.info(f"✓ Fixed {mapping_fixes} K-acetate mapping errors")
    
    # 3. Check for similar salt mapping issues
    logger.info("Checking for other potential salt mapping issues...")
    
    # Look for other cases where salt names might be mismatched
    potential_salt_issues = []
    
    # Check for patterns like "Na-compound" mapped to potassium, etc.
    salt_patterns = {
        'Na-': 'sodium',
        'K-': 'potassium',
        'Ca-': 'calcium',
        'Mg-': 'magnesium'
    }
    
    for idx, row in df.iterrows():
        original = str(row['original']).lower()
        label = str(row['base_chebi_label']).lower()
        
        if pd.isna(row['base_chebi_label']) or row['base_chebi_label'] == '':
            continue
        
        for prefix, expected_metal in salt_patterns.items():
            if prefix.lower() in original:
                # Check if the expected metal is in the ChEBI label
                if expected_metal not in label:
                    # But check if another metal is present
                    other_metals = [metal for pre, metal in salt_patterns.items() if metal != expected_metal]
                    if any(metal in label for metal in other_metals):
                        potential_salt_issues.append({
                            'index': idx,
                            'original': row['original'],
                            'expected_metal': expected_metal,
                            'chebi_label': row['base_chebi_label'],
                            'chebi_id': row['base_chebi_id']
                        })
    
    if potential_salt_issues:
        logger.info(f"Found {len(potential_salt_issues)} potential additional salt mapping issues:")
        for issue in potential_salt_issues[:5]:  # Show first 5
            logger.info(f"  '{issue['original']}' expects {issue['expected_metal']} but mapped to '{issue['chebi_label']}'")
    else:
        logger.info("No additional salt mapping issues found")
    
    # 4. Update molecular weights for corrected K-acetate entries
    if mapping_fixes > 0:
        logger.info("Updating molecular weights for corrected K-acetate entries...")
        
        # Potassium acetate molecular weight: K (39.1) + C2H3O2 (59.0) = 98.1
        k_acetate_mw = 98.1
        
        corrected_indices = k_acetate_errors.index
        for idx in corrected_indices:
            df.at[idx, 'base_molecular_weight'] = k_acetate_mw
            # Update hydrated molecular weight if needed
            water_molecules = df.at[idx, 'water_molecules']
            if water_molecules and str(water_molecules).isdigit() and int(water_molecules) > 0:
                water_mw = 18.015 * int(water_molecules)
                df.at[idx, 'water_molecular_weight'] = water_mw
                df.at[idx, 'hydrated_molecular_weight'] = k_acetate_mw + water_mw
            else:
                df.at[idx, 'hydrated_molecular_weight'] = k_acetate_mw
    
    # 5. Summary of changes
    total_fixes = concentration_fixes + mapping_fixes
    logger.info(f"\nSummary of fixes:")
    logger.info(f"  Concentration notation fixes: {concentration_fixes}")
    logger.info(f"  K-acetate mapping fixes: {mapping_fixes}")
    logger.info(f"  Total fixes applied: {total_fixes}")
    
    if potential_salt_issues:
        logger.info(f"  Additional potential issues identified: {len(potential_salt_issues)}")
    
    # 6. Show examples of corrected entries
    if total_fixes > 0:
        logger.info(f"\nExamples of corrected entries:")
        
        # Show corrected K-acetate entries
        corrected_k_acetate = df[df['base_chebi_id'] == correct_k_acetate_chebi]
        for _, row in corrected_k_acetate.head(3).iterrows():
            logger.info(f"  {row['original']}: {row['base_chebi_id']} → {row['base_chebi_label']}")
        
        # Show entries with cleaned concentration notation
        if concentration_fixes > 0:
            logger.info(f"  Concentration notation cleaned for {concentration_fixes} entries")
    
    # Save the corrected dataset
    df.to_csv(output_file, sep='\t', index=False)
    logger.info(f"\n✓ Saved corrected dataset to: {output_file}")
    
    return df, total_fixes

def main():
    parser = argparse.ArgumentParser(description="Fix mapping issues")
    parser.add_argument("--input", required=True, help="Input TSV file")
    parser.add_argument("--output", required=True, help="Output TSV file")
    
    args = parser.parse_args()
    fix_mapping_issues(args.input, args.output)

if __name__ == "__main__":
    main()