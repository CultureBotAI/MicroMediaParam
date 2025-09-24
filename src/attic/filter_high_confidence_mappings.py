#!/usr/bin/env python3
"""
Filter unified compound mappings to include only high and very high confidence entries.

This script takes the unified_compound_mappings.tsv file and filters it to only include
entries with match_confidence of 'high' or 'very_high', creating a high-confidence
subset for more reliable downstream analysis.

Usage:
    python filter_high_confidence_mappings.py [--input FILE] [--output FILE]
"""

import pandas as pd
import numpy as np
import logging
from pathlib import Path
import argparse

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('filter_high_confidence_mappings.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class HighConfidenceFilter:
    """
    Filter unified compound mappings to only include high and very high confidence matches.
    """
    
    def __init__(self, input_file: str = "unified_compound_mappings.tsv", 
                 output_file: str = "high_confidence_compound_mappings.tsv",
                 low_confidence_file: str = "low_confidence_compound_mappings.tsv"):
        
        self.input_file = input_file
        self.output_file = output_file
        self.low_confidence_file = low_confidence_file
        
    def load_unified_mappings(self) -> pd.DataFrame:
        """Load the unified compound mappings file."""
        logger.info(f"Loading unified mappings from {self.input_file}")
        
        try:
            df = pd.read_csv(self.input_file, sep='\t', dtype=str, low_memory=False)
            logger.info(f"Loaded {len(df)} total mapping entries")
            
            # Convert numeric columns back to appropriate types
            numeric_cols = ['value', 'mmol_l', 'hydration_number', 'similarity_score']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                    
            return df
            
        except Exception as e:
            logger.error(f"Error loading unified mappings: {e}")
            raise
    
    def filter_high_confidence(self, df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Filter mappings to only include high and very high confidence entries.
        
        Filtering criteria:
        1. Include entries with match_confidence = 'high' or 'very_high'
        2. Include entries with original mappings but no ChEBI matches (mapping_status = 'original_only')
        3. Exclude entries with match_confidence = 'medium', 'low', or 'no_match'
        4. Exclude unmapped entries (mapping_status = 'unmapped')
        
        Args:
            df: Input DataFrame with unified mappings
            
        Returns:
            Tuple of (high-confidence DataFrame, low-confidence DataFrame)
        """
        logger.info("Filtering for high and very high confidence mappings...")
        
        # Create filter conditions
        conditions = []
        
        # Include entries with high or very_high match_confidence
        high_confidence_condition = df['match_confidence'].isin(['high', 'very_high'])
        
        # Include entries with original mappings but no ChEBI matches 
        # (these are trusted from the original KG mapping process)
        original_only_condition = df['mapping_status'] == 'original_only'
        
        # Exclude unmapped entries
        not_unmapped_condition = df['mapping_status'] != 'unmapped'
        
        # Combine conditions: (high confidence ChEBI matches) OR (original mappings only)
        # AND not unmapped
        final_condition = ((high_confidence_condition | original_only_condition) & 
                          not_unmapped_condition)
        
        high_confidence_df = df[final_condition].copy()
        low_confidence_df = df[~final_condition].copy()
        
        logger.info(f"Filtered to {len(high_confidence_df)} high-confidence entries "
                   f"({len(high_confidence_df)/len(df)*100:.1f}% of total)")
        logger.info(f"Low-confidence entries: {len(low_confidence_df)} "
                   f"({len(low_confidence_df)/len(df)*100:.1f}% of total)")
        
        return high_confidence_df, low_confidence_df
    
    def analyze_filtered_results(self, original_df: pd.DataFrame, 
                               high_confidence_df: pd.DataFrame,
                               low_confidence_df: pd.DataFrame) -> None:
        """Analyze and report filtering results."""
        logger.info("\n=== FILTERING ANALYSIS ===")
        
        # Overall statistics
        total_original = len(original_df)
        total_high = len(high_confidence_df)
        total_low = len(low_confidence_df)
        retention_rate = total_high / total_original * 100
        
        logger.info(f"Original entries: {total_original}")
        logger.info(f"High-confidence entries: {total_high}")
        logger.info(f"Low-confidence entries: {total_low}")
        logger.info(f"High-confidence retention rate: {retention_rate:.1f}%")
        
        # Confidence distribution in high-confidence data
        if 'match_confidence' in high_confidence_df.columns:
            conf_dist_high = high_confidence_df['match_confidence'].value_counts().fillna(0)
            logger.info(f"\nHigh-confidence data - Confidence distribution:")
            for conf, count in conf_dist_high.items():
                logger.info(f"  {conf}: {count} entries")
        
        # Confidence distribution in low-confidence data
        if 'match_confidence' in low_confidence_df.columns:
            conf_dist_low = low_confidence_df['match_confidence'].value_counts().fillna(0)
            logger.info(f"\nLow-confidence data - Confidence distribution:")
            for conf, count in conf_dist_low.items():
                logger.info(f"  {conf}: {count} entries")
        
        # Mapping status distribution
        if 'mapping_status' in high_confidence_df.columns:
            status_dist = high_confidence_df['mapping_status'].value_counts()
            logger.info(f"\nHigh-confidence data - Mapping status distribution:")
            for status, count in status_dist.items():
                logger.info(f"  {status}: {count} entries")
                
        if 'mapping_status' in low_confidence_df.columns:
            status_dist_low = low_confidence_df['mapping_status'].value_counts()
            logger.info(f"\nLow-confidence data - Mapping status distribution:")
            for status, count in status_dist_low.items():
                logger.info(f"  {status}: {count} entries")
        
        # Coverage by media
        unique_media_original = original_df['medium_id'].nunique() if 'medium_id' in original_df.columns else 0
        unique_media_high = high_confidence_df['medium_id'].nunique() if 'medium_id' in high_confidence_df.columns else 0
        unique_media_low = low_confidence_df['medium_id'].nunique() if 'medium_id' in low_confidence_df.columns else 0
        
        logger.info(f"\nMedia coverage:")
        logger.info(f"  Original: {unique_media_original} media")
        logger.info(f"  High-confidence: {unique_media_high} media")
        logger.info(f"  Low-confidence: {unique_media_low} media")
        
        # Unique compounds
        unique_compounds_original = original_df['original'].nunique() if 'original' in original_df.columns else 0
        unique_compounds_high = high_confidence_df['original'].nunique() if 'original' in high_confidence_df.columns else 0
        unique_compounds_low = low_confidence_df['original'].nunique() if 'original' in low_confidence_df.columns else 0
        
        logger.info(f"\nUnique compounds:")
        logger.info(f"  Original: {unique_compounds_original} compounds")
        logger.info(f"  High-confidence: {unique_compounds_high} compounds")
        logger.info(f"  Low-confidence: {unique_compounds_low} compounds")
        logger.info(f"  High-confidence retention: {unique_compounds_high/unique_compounds_original*100:.1f}%")
    
    def save_filtered_mappings(self, high_df: pd.DataFrame, low_df: pd.DataFrame) -> None:
        """Save both high-confidence and low-confidence mappings to separate files."""
        
        # Save high-confidence mappings
        logger.info(f"Saving high-confidence mappings to {self.output_file}")
        try:
            high_df.to_csv(self.output_file, sep='\t', index=False, na_rep='')
            logger.info(f"Successfully saved {len(high_df)} high-confidence mappings")
        except Exception as e:
            logger.error(f"Error saving high-confidence mappings: {e}")
            raise
            
        # Save low-confidence mappings
        logger.info(f"Saving low-confidence mappings to {self.low_confidence_file}")
        try:
            low_df.to_csv(self.low_confidence_file, sep='\t', index=False, na_rep='')
            logger.info(f"Successfully saved {len(low_df)} low-confidence mappings")
        except Exception as e:
            logger.error(f"Error saving low-confidence mappings: {e}")
            raise
    
    def run_filtering(self) -> None:
        """Run the complete filtering process."""
        logger.info("Starting high-confidence mapping filter process...")
        
        # Load data
        original_df = self.load_unified_mappings()
        
        # Apply filtering
        high_confidence_df, low_confidence_df = self.filter_high_confidence(original_df)
        
        # Analyze results
        self.analyze_filtered_results(original_df, high_confidence_df, low_confidence_df)
        
        # Save filtered results
        self.save_filtered_mappings(high_confidence_df, low_confidence_df)
        
        logger.info("High-confidence filtering process completed!")

def main():
    """Main function to run the filtering process."""
    parser = argparse.ArgumentParser(
        description="Filter unified compound mappings for high and very high confidence entries"
    )
    parser.add_argument(
        '--input', 
        default='unified_compound_mappings.tsv',
        help='Input unified mappings file (default: unified_compound_mappings.tsv)'
    )
    parser.add_argument(
        '--output',
        default='high_confidence_compound_mappings.tsv', 
        help='Output high-confidence mappings file (default: high_confidence_compound_mappings.tsv)'
    )
    parser.add_argument(
        '--low-confidence-output',
        default='low_confidence_compound_mappings.tsv',
        help='Output low-confidence mappings file (default: low_confidence_compound_mappings.tsv)'
    )
    
    args = parser.parse_args()
    
    # Create and run filter
    filter_processor = HighConfidenceFilter(
        input_file=args.input,
        output_file=args.output,
        low_confidence_file=args.low_confidence_output
    )
    
    filter_processor.run_filtering()

if __name__ == "__main__":
    main()