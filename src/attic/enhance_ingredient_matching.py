#!/usr/bin/env python3
"""
Enhance ingredient: prefix compound matching to ChEBI.

This script processes mapping files to find ingredient: entries that represent
chemical compounds and attempts to match them to ChEBI IDs, including handling
hydrated forms and complex chemical names.

Usage:
    python enhance_ingredient_matching.py [--input-high FILE] [--input-low FILE] [--output-suffix SUFFIX]
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
from fuzzywuzzy import fuzz, process
import urllib.parse

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('enhance_ingredient_matching.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class IngredientChEBIMatcher:
    """
    Enhanced matching for ingredient: prefix compounds to ChEBI IDs.
    """
    
    def __init__(self,
                 high_confidence_file: str = "high_confidence_compound_mappings_normalized.tsv",
                 low_confidence_file: str = "low_confidence_compound_mappings_normalized.tsv",
                 output_suffix: str = "_ingredient_enhanced"):
        
        self.high_confidence_file = high_confidence_file
        self.low_confidence_file = low_confidence_file
        self.output_suffix = output_suffix
        
        # Cache for ChEBI API results
        self.chebi_cache = {}
        
        # Chemical compound patterns to identify matchable ingredients
        self.chemical_patterns = [
            r'.*H2O.*',  # Hydrates
            r'.*SO4.*',  # Sulfates
            r'.*Cl\d*\s*$',  # Chlorides  
            r'.*PO4.*',  # Phosphates
            r'.*NO3.*',  # Nitrates
            r'^[A-Z][a-z]?\d*[A-Z][a-z]?\d*',  # Chemical formulas like MgSO4, CaCl2
            r'.*citrate.*',  # Citrates
            r'.*sulfate.*',  # Sulfate names
            r'.*phosphate.*',  # Phosphate names
            r'.*chloride.*',  # Chloride names
            r'.*oxide.*',  # Oxides
            r'.*hydroxide.*',  # Hydroxides
            r'.*carbonate.*',  # Carbonates
            r'.*acetate.*',  # Acetates
            r'L-[A-Z][a-z]+.*',  # L-amino acids
            r'D-[A-Z][a-z]+.*',  # D-amino acids
        ]
        
        # Manual mappings for known ingredient: -> ChEBI
        self.manual_ingredient_mappings = {
            'Na2WO4 x 2 H2O': 'CHEBI:63939',
            'MnSO4 x H2O': 'CHEBI:75211', 
            'L-Cysteine HCl x H2O': 'CHEBI:37774',
            'Ferric citrate monohydrate': 'CHEBI:77732',
            'Na2S2O4': 'CHEBI:26709',
            'Vitamin K3': 'CHEBI:28384',
            'Fe(NH4)2(SO4)2 x 12 H2O': 'CHEBI:86463',
            'Fe2(SO4)3 x n H2O': 'CHEBI:33895',
            'Cysteine-HCl': 'CHEBI:37774',
            'Cystein-HCl x 2 H2O': 'CHEBI:37774',
            # Add more as discovered
        }
        
    def is_chemical_compound(self, compound_name: str) -> bool:
        """Check if an ingredient name represents a chemical compound."""
        compound_lower = compound_name.lower().strip()
        
        # Skip obvious biological/complex ingredients
        biological_terms = [
            'extract', 'broth', 'blood', 'seawater', 'sea water', 'agar base',
            'medium', 'peptone', 'trypticase', 'casein', 'amino acids', 'sludge',
            'beef', 'horse', 'sheep', 'columbia', 'brain heart', 'pplo', 'rcm'
        ]
        
        for term in biological_terms:
            if term in compound_lower:
                return False
                
        # Check if matches chemical patterns
        for pattern in self.chemical_patterns:
            if re.match(pattern, compound_name, re.IGNORECASE):
                return True
                
        return False
        
    def normalize_compound_name(self, compound_name: str) -> str:
        """Normalize compound name for ChEBI matching."""
        # Remove common prefixes/suffixes
        normalized = compound_name.strip()
        
        # Handle hydration notation variations
        hydration_patterns = [
            (r'\s*x\s*(\d+)\s*H2O', r'.\1H2O'),  # x 2 H2O -> .2H2O
            (r'\.(\d+)\s*H2O', r'.\1H2O'),       # .2 H2O -> .2H2O
            (r'\s*monohydrate', '.H2O'),          # monohydrate -> .H2O
            (r'\s*dihydrate', '.2H2O'),           # dihydrate -> .2H2O
            (r'\s*trihydrate', '.3H2O'),          # trihydrate -> .3H2O
            (r'\s*tetrahydrate', '.4H2O'),        # tetrahydrate -> .4H2O
            (r'\s*pentahydrate', '.5H2O'),        # pentahydrate -> .5H2O
            (r'\s*hexahydrate', '.6H2O'),         # hexahydrate -> .6H2O
            (r'\s*heptahydrate', '.7H2O'),        # heptahydrate -> .7H2O
            (r'\s*n\s*H2O', ''),                  # n H2O -> remove (variable hydration)
        ]
        
        for pattern, replacement in hydration_patterns:
            normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)
            
        return normalized.strip()
        
    def query_chebi_api(self, compound_name: str) -> Optional[Dict]:
        """Query ChEBI API for compound information."""
        if compound_name in self.chebi_cache:
            return self.chebi_cache[compound_name]
            
        try:
            # Normalize name for search
            search_name = self.normalize_compound_name(compound_name)
            
            # Try multiple search strategies
            search_terms = [search_name, compound_name]
            
            # Add variations without hydration for better matching
            base_compound = re.sub(r'[.\s]*\d*\s*H2O.*$', '', search_name, flags=re.IGNORECASE)
            if base_compound != search_name:
                search_terms.append(base_compound)
                
            best_match = None
            best_score = 0
            
            for term in search_terms:
                if not term.strip():
                    continue
                    
                # Use ChEBI web search API
                encoded_term = urllib.parse.quote(term)
                url = f"https://www.ebi.ac.uk/chebi/advancedSearchFT.do?searchString={encoded_term}"
                
                try:
                    response = requests.get(url, timeout=15)
                    if response.status_code == 200:
                        content = response.text
                        
                        # Extract ChEBI IDs and names from results
                        chebi_matches = re.findall(r'compound_id=(\d+)[^>]*>([^<]+)</a>', content)
                        
                        for chebi_id, chebi_name in chebi_matches[:10]:  # Check top 10 matches
                            # Calculate similarity score
                            similarity = max(
                                fuzz.ratio(term.lower(), chebi_name.lower()),
                                fuzz.ratio(compound_name.lower(), chebi_name.lower())
                            )
                            
                            if similarity > best_score and similarity >= 75:  # Minimum threshold
                                best_score = similarity
                                best_match = {
                                    'chebi_id': f'CHEBI:{chebi_id}',
                                    'chebi_name': chebi_name.strip(),
                                    'similarity_score': similarity,
                                    'search_term': term,
                                    'match_confidence': self._get_confidence_level(similarity)
                                }
                                
                    time.sleep(0.2)  # Rate limiting
                    
                except requests.RequestException as e:
                    logger.warning(f"Error querying ChEBI for '{term}': {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error in ChEBI query for '{compound_name}': {e}")
            
        self.chebi_cache[compound_name] = best_match
        return best_match
        
    def _get_confidence_level(self, similarity_score: float) -> str:
        """Convert similarity score to confidence level."""
        if similarity_score >= 95:
            return 'very_high'
        elif similarity_score >= 85:
            return 'high' 
        elif similarity_score >= 75:
            return 'medium'
        elif similarity_score >= 70:
            return 'low'
        else:
            return 'no_match'
            
    def enhance_ingredient_entry(self, row: pd.Series) -> pd.Series:
        """Enhance a single ingredient: entry with ChEBI matching."""
        
        original_name = str(row.get('original', ''))
        mapped_id = str(row.get('mapped', ''))
        
        # Only process ingredient: entries
        if not mapped_id.startswith('ingredient:'):
            return row
            
        # Skip if already has ChEBI match
        existing_chebi = str(row.get('chebi_id', ''))
        if existing_chebi and existing_chebi != 'nan' and existing_chebi.startswith('CHEBI:'):
            return row
            
        # Check if this looks like a chemical compound
        if not self.is_chemical_compound(original_name):
            return row
            
        logger.info(f"Attempting ChEBI match for ingredient: {original_name}")
        
        # Check manual mappings first
        if original_name in self.manual_ingredient_mappings:
            chebi_id = self.manual_ingredient_mappings[original_name]
            logger.info(f"Manual mapping found: {original_name} -> {chebi_id}")
            
            row = row.copy()
            row['chebi_id'] = chebi_id
            row['chebi_match'] = original_name  # Use original name as match
            row['chebi_original_name'] = original_name
            row['similarity_score'] = 100.0
            row['match_confidence'] = 'very_high'
            row['matching_method'] = 'manual_ingredient_mapping'
            row['mapping_status'] = 'ingredient_plus_chebi_match'
            row['mapping_quality'] = 'excellent'
            
            return row
            
        # Try API matching
        match_result = self.query_chebi_api(original_name)
        
        if match_result:
            logger.info(f"ChEBI match found: {original_name} -> {match_result['chebi_id']} "
                       f"(score: {match_result['similarity_score']})")
            
            row = row.copy()
            row['chebi_id'] = match_result['chebi_id']
            row['chebi_match'] = original_name
            row['chebi_original_name'] = match_result['chebi_name']
            row['similarity_score'] = match_result['similarity_score']
            row['match_confidence'] = match_result['match_confidence']
            row['matching_method'] = 'api_ingredient_search'
            row['mapping_status'] = 'ingredient_plus_chebi_match'
            row['mapping_quality'] = 'very_good' if match_result['similarity_score'] >= 85 else 'good'
            
        return row
        
    def process_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Process all ingredient: entries in a DataFrame."""
        
        # Find ingredient: entries that might be chemical compounds
        ingredient_mask = df['mapped'].str.startswith('ingredient:', na=False)
        ingredient_df = df[ingredient_mask].copy()
        
        logger.info(f"Found {len(ingredient_df)} ingredient: entries")
        
        chemical_candidates = []
        for _, row in ingredient_df.iterrows():
            if self.is_chemical_compound(str(row.get('original', ''))):
                chemical_candidates.append(row['original'])
                
        unique_candidates = list(set(chemical_candidates))
        logger.info(f"Identified {len(unique_candidates)} chemical compound candidates")
        logger.info(f"Top candidates: {unique_candidates[:10]}")
        
        # Process all rows
        enhanced_rows = []
        processed_count = 0
        matched_count = 0
        total_rows = len(df)
        
        logger.info(f"Processing {total_rows} total entries...")
        
        for idx, row in df.iterrows():
            # Progress reporting
            if (idx + 1) % 1000 == 0 or (idx + 1) == total_rows:
                progress_pct = ((idx + 1) / total_rows) * 100
                logger.info(f"Progress: {idx + 1}/{total_rows} entries ({progress_pct:.1f}%) - {matched_count} ingredients matched")
            try:
                enhanced_row = self.enhance_ingredient_entry(row)
                enhanced_rows.append(enhanced_row)
                
                # Check if we added a ChEBI match
                if (enhanced_row.get('chebi_id', '') != row.get('chebi_id', '') and 
                    str(enhanced_row.get('chebi_id', '')).startswith('CHEBI:')):
                    matched_count += 1
                    
                if str(row.get('mapped', '')).startswith('ingredient:'):
                    processed_count += 1
                    
            except Exception as e:
                logger.warning(f"Error processing row {idx}: {e}")
                enhanced_rows.append(row)
                
        enhanced_df = pd.DataFrame(enhanced_rows)
        
        logger.info(f"Processed {processed_count} ingredient: entries")
        logger.info(f"Successfully matched {matched_count} to ChEBI IDs")
        
        return enhanced_df
        
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
            
            # Process ingredient: entries
            enhanced_df = self.process_dataframe(df)
            
            # Save result
            enhanced_df.to_csv(output_file, sep='\t', index=False, na_rep='')
            logger.info(f"Saved enhanced data to {output_file}")
            
        except Exception as e:
            logger.error(f"Error processing {input_file}: {e}")
            raise
            
    def process_all_files(self) -> None:
        """Process both high and low confidence files."""
        logger.info("Starting ingredient: enhancement process...")
        
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
            
        logger.info("Ingredient: enhancement process completed!")
        
        # Report cache statistics
        successful_matches = sum(1 for v in self.chebi_cache.values() if v is not None)
        total_queries = len(self.chebi_cache)
        if total_queries > 0:
            logger.info(f"ChEBI API results: {successful_matches}/{total_queries} successful matches")

def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Enhance ingredient: prefix compounds with ChEBI matching"
    )
    parser.add_argument(
        '--input-high',
        default='high_confidence_compound_mappings_normalized.tsv',
        help='High confidence mappings file (default: high_confidence_compound_mappings_normalized.tsv)'
    )
    parser.add_argument(
        '--input-low',
        default='low_confidence_compound_mappings_normalized.tsv',
        help='Low confidence mappings file (default: low_confidence_compound_mappings_normalized.tsv)'
    )
    parser.add_argument(
        '--output-suffix',
        default='_ingredient_enhanced',
        help='Suffix for output files (default: _ingredient_enhanced)'
    )
    
    args = parser.parse_args()
    
    # Create and run enhancer
    enhancer = IngredientChEBIMatcher(
        high_confidence_file=args.input_high,
        low_confidence_file=args.input_low,
        output_suffix=args.output_suffix
    )
    
    enhancer.process_all_files()

if __name__ == "__main__":
    main()