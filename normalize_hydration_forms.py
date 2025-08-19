#!/usr/bin/env python3
"""
Normalize hydrated compound forms to their unhydrated ChEBI equivalents and remove duplicates.

This script processes high and low confidence mapping files to:
1. Normalize hydrated forms (e.g., CaCl2.2H2O) to their unhydrated base compounds (CaCl2)
2. Use ChEBI API to find anhydrous forms when available
3. Remove duplicate entries after normalization
4. Preserve mapping quality and confidence information

Usage:
    python normalize_hydration_forms.py [--input-high FILE] [--input-low FILE] [--output-suffix SUFFIX]
"""

import pandas as pd
import numpy as np
import requests
import re
import json
import logging
import time
from pathlib import Path
import argparse
from typing import Dict, List, Optional, Tuple, Set

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('normalize_hydration_forms.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class HydrationNormalizer:
    """
    Normalize hydrated compound forms to their unhydrated equivalents.
    """
    
    def __init__(self,
                 high_confidence_file: str = "high_confidence_compound_mappings.tsv",
                 low_confidence_file: str = "low_confidence_compound_mappings.tsv",
                 output_suffix: str = "_normalized"):
        
        self.high_confidence_file = high_confidence_file
        self.low_confidence_file = low_confidence_file
        self.output_suffix = output_suffix
        
        # Cache for ChEBI API results
        self.chebi_cache = {}
        
        # Manual mappings for common hydrated -> anhydrous forms
        self.manual_hydration_map = {
            # Common salt hydrates to anhydrous forms
            'CHEBI:91243': 'CHEBI:3312',   # CaCl2.2H2O -> CaCl2 (corrected mapping)
            'CHEBI:86473': 'CHEBI:24840',  # MgSO4.7H2O -> MgSO4
            'CHEBI:131527': 'CHEBI:24840', # MgSO4.H2O -> MgSO4
            'CHEBI:75213': 'CHEBI:75216',  # Na2MoO4.2H2O -> Na2MoO4
            'CHEBI:63939': 'CHEBI:63940',  # Na2WO4.2H2O -> Na2WO4  
            'CHEBI:35696': 'CHEBI:23958',  # CoCl2.6H2O -> CoCl2
            'CHEBI:86249': 'CHEBI:30812',  # FeCl2.4H2O -> FeCl2
            'CHEBI:49553': 'CHEBI:49553',  # CuCl2.2H2O -> CuCl2 (keep same - already correct)
            'CHEBI:131394': 'CHEBI:6636',  # MgCl2.2H2O -> MgCl2
            'CHEBI:132095': 'CHEBI:132229', # NaVO3.H2O -> NaVO3
            # Ingredient-specific hydrate mappings
            'CHEBI:75211': 'CHEBI:24840',  # MnSO4.H2O -> MnSO4 (ingredient: common)
            'CHEBI:77732': 'CHEBI:77732',  # Ferric citrate monohydrate (keep same - specific form)
            'CHEBI:37774': 'CHEBI:35235',  # L-Cysteine HCl.H2O -> L-Cysteine HCl
            'CHEBI:86463': 'CHEBI:86463',  # Fe(NH4)2(SO4)2.12H2O (keep - specific form)
            # Add more as discovered
        }
        
    def is_hydrated_compound(self, compound_name: str, chebi_id: str) -> bool:
        """Check if a compound is in hydrated form."""
        hydration_patterns = [
            r'\.?\s*x?\s*\d*\s*H2O',  # .H2O, x H2O, x 2 H2O, etc.
            r'\s+(mono|di|tri|tetra|penta|hexa|hepta|octa|nona|deca)hydrate',
            r'hydrate',
            r'dihydrate',
            r'trihydrate',
            r'tetrahydrate',
            r'pentahydrate',
            r'hexahydrate',
            r'heptahydrate'
        ]
        
        compound_lower = compound_name.lower()
        for pattern in hydration_patterns:
            if re.search(pattern, compound_lower):
                return True
                
        return False
        
    def get_anhydrous_chebi_id(self, hydrated_chebi_id: str) -> Optional[str]:
        """Get the anhydrous form ChEBI ID for a hydrated compound."""
        
        # Check manual mapping first
        if hydrated_chebi_id in self.manual_hydration_map:
            return self.manual_hydration_map[hydrated_chebi_id]
            
        # Check cache
        if hydrated_chebi_id in self.chebi_cache:
            return self.chebi_cache[hydrated_chebi_id]
            
        try:
            # Query ChEBI API for compound details
            url = f"https://www.ebi.ac.uk/chebi/searchId.do?chebiId={hydrated_chebi_id}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                # Look for related anhydrous compounds
                # This is a simplified approach - in practice, you'd need more sophisticated parsing
                content = response.text
                
                # Look for "anhydrous" or "dehydrated" forms in related compounds
                anhydrous_matches = re.findall(r'CHEBI:(\d+)', content)
                for match in anhydrous_matches[:5]:  # Check first few matches
                    candidate_id = f"CHEBI:{match}"
                    if candidate_id != hydrated_chebi_id:
                        # Simple heuristic: if ID is close numerically, might be related
                        try:
                            orig_num = int(hydrated_chebi_id.split(':')[1])
                            cand_num = int(match)
                            if abs(orig_num - cand_num) < 1000:  # Within 1000 IDs
                                self.chebi_cache[hydrated_chebi_id] = candidate_id
                                return candidate_id
                        except ValueError:
                            continue
                            
            # Rate limiting
            time.sleep(0.1)
            
        except Exception as e:
            logger.warning(f"Error querying ChEBI API for {hydrated_chebi_id}: {e}")
            
        # No anhydrous form found
        self.chebi_cache[hydrated_chebi_id] = None
        return None
        
    def normalize_compound_entry(self, row: pd.Series) -> pd.Series:
        """Normalize a single compound entry."""
        
        original_name = str(row.get('original', ''))
        mapped_id = str(row.get('mapped', ''))
        chebi_id = str(row.get('chebi_id', ''))
        
        # Determine which ID to use for normalization
        # Prioritize chebi_id, but also check mapped field for ChEBI IDs
        # Now also handle ingredient: entries that got ChEBI matches
        target_chebi_id = None
        if chebi_id and chebi_id != 'nan' and str(chebi_id).startswith('CHEBI:'):
            target_chebi_id = chebi_id
        elif mapped_id and mapped_id != 'nan' and str(mapped_id).startswith('CHEBI:'):
            target_chebi_id = mapped_id
        # Note: ingredient: entries with ChEBI matches will be handled via chebi_id field
        
        if not target_chebi_id or target_chebi_id == 'nan':
            return row
            
        # Check if compound is hydrated
        is_hydrated = self.is_hydrated_compound(original_name, target_chebi_id)
        
        if is_hydrated and target_chebi_id.startswith('CHEBI:'):
            # Try to find anhydrous form
            anhydrous_id = self.get_anhydrous_chebi_id(target_chebi_id)
            
            if anhydrous_id:
                # Update the mapping to use anhydrous form
                row = row.copy()
                
                # Update mapped field if it was the hydrated ChEBI ID
                if row.get('mapped') == target_chebi_id:
                    row['mapped'] = anhydrous_id
                    
                # Update chebi_id field if it was the hydrated ChEBI ID
                if row.get('chebi_id') == target_chebi_id:
                    row['chebi_id'] = anhydrous_id
                    
                # Add note about normalization
                if pd.isna(row.get('notes_content', '')):
                    row['notes_content'] = f"Normalized from hydrated form {target_chebi_id}"
                else:
                    existing_notes = str(row['notes_content'])
                    row['notes_content'] = f"{existing_notes}; Normalized from hydrated form {target_chebi_id}"
                    
                logger.debug(f"Normalized {original_name}: {target_chebi_id} -> {anhydrous_id}")
                
        return row
        
    def normalize_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalize all entries in a DataFrame."""
        logger.info(f"Normalizing {len(df)} compound entries...")
        
        # Apply normalization to each row
        normalized_rows = []
        for idx, row in df.iterrows():
            try:
                normalized_row = self.normalize_compound_entry(row)
                normalized_rows.append(normalized_row)
            except Exception as e:
                logger.warning(f"Error normalizing row {idx}: {e}")
                normalized_rows.append(row)
                
        normalized_df = pd.DataFrame(normalized_rows)
        
        logger.info(f"Normalization completed for {len(normalized_df)} entries")
        return normalized_df
        
    def remove_duplicates(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove duplicate entries after normalization."""
        logger.info("Removing duplicates...")
        
        original_count = len(df)
        
        # Define key columns for duplicate detection
        key_columns = ['medium_id', 'original', 'mapped']
        
        # Remove exact duplicates first
        df_dedup = df.drop_duplicates(subset=key_columns, keep='first')
        
        exact_dups_removed = original_count - len(df_dedup)
        logger.info(f"Removed {exact_dups_removed} exact duplicates")
        
        # For entries with same medium_id and mapped ChEBI ID but different original names,
        # keep the one with highest confidence/quality
        def select_best_duplicate(group):
            if len(group) == 1:
                return group
                
            # Priority order for confidence
            confidence_priority = {'very_high': 4, 'high': 3, 'medium': 2, 'low': 1}
            quality_priority = {'excellent': 3, 'very_good': 2, 'good': 1}
            
            group = group.copy()
            
            # Add priority scores
            group['conf_score'] = group['match_confidence'].map(confidence_priority).fillna(0)
            group['qual_score'] = group['mapping_quality'].map(quality_priority).fillna(0)
            group['total_score'] = group['conf_score'] + group['qual_score']
            
            # Keep highest scoring entry
            best_entry = group.loc[group['total_score'].idxmax()]
            return best_entry.to_frame().T
            
        # Group by medium_id and mapped ChEBI ID
        grouped = df_dedup.groupby(['medium_id', 'mapped'], dropna=False)
        
        final_rows = []
        for name, group in grouped:
            best_group = select_best_duplicate(group)
            final_rows.append(best_group)
            
        final_df = pd.concat(final_rows, ignore_index=True)
        
        # Clean up temporary columns
        cols_to_drop = ['conf_score', 'qual_score', 'total_score']
        final_df = final_df.drop(columns=[col for col in cols_to_drop if col in final_df.columns])
        
        duplicates_removed = len(df_dedup) - len(final_df)
        total_removed = original_count - len(final_df)
        
        logger.info(f"Removed {duplicates_removed} semantic duplicates")
        logger.info(f"Total entries removed: {total_removed} ({total_removed/original_count*100:.1f}%)")
        logger.info(f"Final dataset: {len(final_df)} unique entries")
        
        return final_df
        
    def process_file(self, input_file: str, output_file: str) -> None:
        """Process a single mapping file."""
        logger.info(f"Processing {input_file}...")
        
        try:
            # Load data
            df = pd.read_csv(input_file, sep='\t', dtype=str, low_memory=False)
            logger.info(f"Loaded {len(df)} entries from {input_file}")
            
            # Convert numeric columns
            numeric_cols = ['value', 'mmol_l', 'hydration_number', 'similarity_score']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Normalize hydration forms
            df_normalized = self.normalize_dataframe(df)
            
            # Remove duplicates
            df_final = self.remove_duplicates(df_normalized)
            
            # Save result
            df_final.to_csv(output_file, sep='\t', index=False, na_rep='')
            logger.info(f"Saved normalized and deduplicated data to {output_file}")
            
        except Exception as e:
            logger.error(f"Error processing {input_file}: {e}")
            raise
            
    def process_all_files(self) -> None:
        """Process both high and low confidence files."""
        logger.info("Starting hydration normalization and deduplication process...")
        
        # Generate output filenames
        high_output = self.high_confidence_file.replace('.tsv', f'{self.output_suffix}.tsv')
        low_output = self.low_confidence_file.replace('.tsv', f'{self.output_suffix}.tsv')
        
        # Process high confidence file
        if Path(self.high_confidence_file).exists():
            self.process_file(self.high_confidence_file, high_output)
        else:
            logger.warning(f"High confidence file not found: {self.high_confidence_file}")
            
        # Process low confidence file
        if Path(self.low_confidence_file).exists():
            self.process_file(self.low_confidence_file, low_output)
        else:
            logger.warning(f"Low confidence file not found: {self.low_confidence_file}")
            
        logger.info("Normalization and deduplication process completed!")
        
        # Report cache statistics
        cache_hits = sum(1 for v in self.chebi_cache.values() if v is not None)
        cache_total = len(self.chebi_cache)
        if cache_total > 0:
            logger.info(f"ChEBI API cache: {cache_hits}/{cache_total} successful normalizations")

def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Normalize hydrated compound forms and remove duplicates"
    )
    parser.add_argument(
        '--input-high',
        default='high_confidence_compound_mappings.tsv',
        help='High confidence mappings file (default: high_confidence_compound_mappings.tsv)'
    )
    parser.add_argument(
        '--input-low',
        default='low_confidence_compound_mappings.tsv',
        help='Low confidence mappings file (default: low_confidence_compound_mappings.tsv)'
    )
    parser.add_argument(
        '--output-suffix',
        default='_normalized',
        help='Suffix for output files (default: _normalized)'
    )
    
    args = parser.parse_args()
    
    # Create and run normalizer
    normalizer = HydrationNormalizer(
        high_confidence_file=args.input_high,
        low_confidence_file=args.input_low,
        output_suffix=args.output_suffix
    )
    
    normalizer.process_all_files()

if __name__ == "__main__":
    main()