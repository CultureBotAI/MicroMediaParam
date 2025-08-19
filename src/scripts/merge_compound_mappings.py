#!/usr/bin/env python3
"""
Merge composition_kg_mapping.tsv and unaccounted_compound_matches.tsv files.

This script combines the original KG mapping results with the newly found ChEBI matches
for previously unaccounted compounds, creating a comprehensive mapping file.

Usage:
    python merge_compound_mappings.py [--composition-file FILE] [--matches-file FILE] [--output FILE]
"""

import pandas as pd
import numpy as np
import logging
from pathlib import Path
import argparse
from typing import Dict, List, Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('merge_compound_mappings.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class CompoundMappingMerger:
    """
    Merge composition KG mappings with unaccounted compound ChEBI matches.
    
    Combines:
    1. composition_kg_mapping.tsv - Original KG mappings from media analysis
    2. unaccounted_compound_matches.tsv - ChEBI matches for previously unmapped compounds
    
    Creates a unified mapping file with comprehensive coverage.
    """
    
    def __init__(self, 
                 composition_file: str = "composition_kg_mapping.tsv",
                 matches_file: str = "unaccounted_compound_matches.tsv",
                 output_file: str = "unified_compound_mappings.tsv"):
        
        self.composition_file = composition_file
        self.matches_file = matches_file
        self.output_file = output_file
        
        # Storage for loaded data
        self.composition_df = None
        self.matches_df = None
        self.unified_df = None
        
    def load_composition_mappings(self) -> pd.DataFrame:
        """
        Load the original composition KG mapping file.
        
        Expected columns:
        - medium_id, original, mapped, value, concentration, unit, mmol_l, optional, source
        
        Returns:
            DataFrame with composition mappings
        """
        logger.info(f"Loading composition mappings from {self.composition_file}")
        
        try:
            df = pd.read_csv(self.composition_file, sep='\t', low_memory=False)
            logger.info(f"Loaded {len(df)} composition mapping entries")
            
            # Ensure required columns exist
            required_cols = ['medium_id', 'original', 'mapped']
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                raise ValueError(f"Missing required columns: {missing_cols}")
            
            return df
            
        except Exception as e:
            logger.error(f"Error loading composition mappings: {e}")
            raise
    
    def load_unaccounted_matches(self) -> pd.DataFrame:
        """
        Load the unaccounted compound ChEBI matches file.
        
        Expected columns:
        - original_compound, normalized_compound, hydration_number, frequency, 
          chebi_match, chebi_id, chebi_original_name, similarity_score, 
          match_confidence, matching_method
        
        Returns:
            DataFrame with ChEBI matches
        """
        logger.info(f"Loading unaccounted compound matches from {self.matches_file}")
        
        try:
            df = pd.read_csv(self.matches_file, sep='\t', low_memory=False)
            logger.info(f"Loaded {len(df)} unaccounted compound match entries")
            
            # Filter for successful matches only
            successful_matches = df[df['chebi_match'].notna() & (df['chebi_match'] != '')]
            logger.info(f"Found {len(successful_matches)} successful ChEBI matches")
            
            return successful_matches
            
        except Exception as e:
            logger.error(f"Error loading unaccounted matches: {e}")
            raise
    
    def create_unified_mapping(self) -> pd.DataFrame:
        """
        Create unified mapping by merging composition mappings with ChEBI matches.
        
        Strategy:
        1. Take all entries from composition_kg_mapping.tsv
        2. For entries with empty 'mapped' field, try to fill from ChEBI matches
        3. Add new columns from ChEBI matches where applicable
        4. Create comprehensive mapping with consistent schema
        
        Returns:
            Unified DataFrame with all mappings
        """
        logger.info("Creating unified compound mapping...")
        
        # Start with composition mappings
        unified = self.composition_df.copy()
        
        # Add new columns from matches file (initialize with NaN)
        new_columns = [
            'normalized_compound', 'hydration_number', 'chebi_match', 'chebi_id', 
            'chebi_original_name', 'similarity_score', 'match_confidence', 'matching_method'
        ]
        
        for col in new_columns:
            if col not in unified.columns:
                unified[col] = np.nan
        
        # Create lookup dictionary from matches for efficient merging
        matches_lookup = {}
        for _, row in self.matches_df.iterrows():
            original_compound = row['original_compound']
            matches_lookup[original_compound] = {
                'normalized_compound': row.get('normalized_compound', ''),
                'hydration_number': row.get('hydration_number', np.nan),
                'chebi_match': row.get('chebi_match', ''),
                'chebi_id': row.get('chebi_id', ''),
                'chebi_original_name': row.get('chebi_original_name', ''),
                'similarity_score': row.get('similarity_score', np.nan),
                'match_confidence': row.get('match_confidence', ''),
                'matching_method': row.get('matching_method', '')
            }
        
        # Update unified DataFrame
        enhanced_count = 0
        filled_count = 0
        
        for idx, row in unified.iterrows():
            original_compound = row['original']
            current_mapped = row['mapped']
            
            # Check if we have a ChEBI match for this compound
            if original_compound in matches_lookup:
                match_data = matches_lookup[original_compound]
                
                # Fill in the new columns from ChEBI matches
                for col, value in match_data.items():
                    unified.at[idx, col] = value
                
                # If the original mapping was empty, fill it with ChEBI match
                if pd.isna(current_mapped) or current_mapped == '':
                    unified.at[idx, 'mapped'] = match_data['chebi_id']
                    filled_count += 1
                    
                enhanced_count += 1
        
        logger.info(f"Enhanced {enhanced_count} entries with ChEBI match data")
        logger.info(f"Filled {filled_count} previously empty mappings with ChEBI IDs")
        
        # Add entries for compounds that were in matches but not in composition mappings
        # (This handles cases where compounds might have been missed in the original analysis)
        composition_compounds = set(unified['original'].values)
        new_entries = []
        
        for original_compound, match_data in matches_lookup.items():
            if original_compound not in composition_compounds:
                # Create new entry for this compound
                new_entry = {
                    'medium_id': 'multiple',  # Indicate this appears in multiple media
                    'original': original_compound,
                    'mapped': match_data['chebi_id'],
                    'value': np.nan,
                    'concentration': '',
                    'unit': '',
                    'mmol_l': np.nan,
                    'optional': '',
                    'source': 'chebi_match',
                    'normalized_compound': match_data['normalized_compound'],
                    'hydration_number': match_data['hydration_number'],
                    'chebi_match': match_data['chebi_match'],
                    'chebi_id': match_data['chebi_id'],
                    'chebi_original_name': match_data['chebi_original_name'],
                    'similarity_score': match_data['similarity_score'],
                    'match_confidence': match_data['match_confidence'],
                    'matching_method': match_data['matching_method']
                }
                new_entries.append(new_entry)
        
        if new_entries:
            new_entries_df = pd.DataFrame(new_entries)
            unified = pd.concat([unified, new_entries_df], ignore_index=True)
            logger.info(f"Added {len(new_entries)} new compound entries from ChEBI matches")
        
        return unified
    
    def add_mapping_statistics(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add mapping quality statistics to the unified DataFrame.
        
        Args:
            df: Unified DataFrame
            
        Returns:
            DataFrame with additional statistics columns
        """
        logger.info("Adding mapping quality statistics...")
        
        # Create mapping status column
        def get_mapping_status(row):
            mapped = row['mapped']
            chebi_id = row.get('chebi_id', '')
            
            if pd.notna(mapped) and mapped != '':
                if pd.notna(chebi_id) and chebi_id != '':
                    if mapped == chebi_id:
                        return 'original_and_chebi_match'
                    else:
                        return 'original_plus_chebi_alternative'
                else:
                    return 'original_only'
            elif pd.notna(chebi_id) and chebi_id != '':
                return 'chebi_only'
            else:
                return 'unmapped'
        
        df['mapping_status'] = df.apply(get_mapping_status, axis=1)
        
        # Create mapping quality score
        def get_mapping_quality(row):
            status = row['mapping_status']
            similarity_score = row.get('similarity_score', np.nan)
            match_confidence = row.get('match_confidence', '')
            
            if status == 'original_and_chebi_match':
                return 'excellent'
            elif status == 'original_plus_chebi_alternative':
                return 'very_good'
            elif status == 'original_only':
                return 'good'
            elif status == 'chebi_only':
                if match_confidence in ['very_high', 'high']:
                    return 'good'
                elif match_confidence == 'medium':
                    return 'fair'
                else:
                    return 'poor'
            else:
                return 'none'
        
        df['mapping_quality'] = df.apply(get_mapping_quality, axis=1)
        
        return df
    
    def save_unified_mapping(self, df: pd.DataFrame):
        """
        Save the unified mapping to a TSV file with proper column ordering.
        
        Args:
            df: Unified DataFrame to save
        """
        logger.info(f"Saving unified mapping to {self.output_file}")
        
        # Define column order for output
        primary_columns = [
            'medium_id', 'original', 'mapped', 'value', 'concentration', 
            'unit', 'mmol_l', 'optional', 'source'
        ]
        
        chebi_columns = [
            'normalized_compound', 'hydration_number', 'chebi_match', 'chebi_id',
            'chebi_original_name', 'similarity_score', 'match_confidence', 'matching_method'
        ]
        
        quality_columns = ['mapping_status', 'mapping_quality']
        
        # Reorder columns (include only those that exist)
        column_order = []
        for col_list in [primary_columns, chebi_columns, quality_columns]:
            for col in col_list:
                if col in df.columns:
                    column_order.append(col)
        
        # Add any remaining columns
        remaining_columns = [col for col in df.columns if col not in column_order]
        column_order.extend(remaining_columns)
        
        df_output = df.reindex(columns=column_order)
        
        # Sort by mapping quality and frequency
        df_output = df_output.sort_values([
            'mapping_quality', 'medium_id', 'original'
        ])
        
        # Save to TSV
        df_output.to_csv(self.output_file, sep='\t', index=False)
        
        # Generate summary statistics
        self._generate_summary_stats(df_output)
    
    def _generate_summary_stats(self, df: pd.DataFrame):
        """Generate and log summary statistics."""
        total_entries = len(df)
        
        # Mapping status counts
        status_counts = df['mapping_status'].value_counts()
        quality_counts = df['mapping_quality'].value_counts()
        
        # Calculate coverage
        mapped_entries = len(df[df['mapped'].notna() & (df['mapped'] != '')])
        chebi_entries = len(df[df['chebi_id'].notna() & (df['chebi_id'] != '')])
        
        logger.info(f"""
=== UNIFIED MAPPING SUMMARY ===
Output file: {self.output_file}
Total entries: {total_entries}

Mapping Coverage:
- Original KG mappings: {mapped_entries} entries
- ChEBI mappings: {chebi_entries} entries
- Overall coverage: {max(mapped_entries, chebi_entries)} / {total_entries} ({max(mapped_entries, chebi_entries)/total_entries*100:.1f}%)

Mapping Status Distribution:
{status_counts.to_string()}

Mapping Quality Distribution:
{quality_counts.to_string()}

Top 10 compounds by medium frequency:
""")
        
        # Show top compounds by frequency (count how many media they appear in)
        compound_frequency = df['original'].value_counts().head(10)
        for compound, count in compound_frequency.items():
            sample_row = df[df['original'] == compound].iloc[0]
            mapping_info = f"KG: {sample_row['mapped'][:20]}..." if pd.notna(sample_row['mapped']) and sample_row['mapped'] else "None"
            chebi_info = f"ChEBI: {sample_row.get('chebi_id', 'None')}"
            logger.info(f"  {compound} (in {count} media) - {mapping_info}, {chebi_info}")
    
    def run_merge(self):
        """
        Run the complete merging process.
        """
        logger.info("Starting compound mapping merge process...")
        
        # Load input files
        self.composition_df = self.load_composition_mappings()
        self.matches_df = self.load_unaccounted_matches()
        
        # Create unified mapping
        self.unified_df = self.create_unified_mapping()
        
        # Add quality statistics
        self.unified_df = self.add_mapping_statistics(self.unified_df)
        
        # Save results
        self.save_unified_mapping(self.unified_df)
        
        logger.info("Mapping merge process completed!")

def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(description='Merge composition KG mappings with ChEBI matches')
    parser.add_argument('--composition-file', 
                        default='composition_kg_mapping.tsv',
                        help='Path to composition KG mapping TSV file')
    parser.add_argument('--matches-file', 
                        default='unaccounted_compound_matches.tsv',
                        help='Path to unaccounted compound matches TSV file')
    parser.add_argument('--output', 
                        default='unified_compound_mappings.tsv',
                        help='Output TSV file for unified mappings')
    parser.add_argument('-v', '--verbose', 
                        action='store_true',
                        help='Verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Check if input files exist
    for file_path in [args.composition_file, args.matches_file]:
        if not Path(file_path).exists():
            logger.error(f"Input file not found: {file_path}")
            return 1
    
    # Initialize merger
    merger = CompoundMappingMerger(
        composition_file=args.composition_file,
        matches_file=args.matches_file,
        output_file=args.output
    )
    
    # Run merge process
    try:
        merger.run_merge()
        return 0
    except Exception as e:
        logger.error(f"Merge process failed: {e}")
        return 1

if __name__ == "__main__":
    exit(main())