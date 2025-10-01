#!/usr/bin/env python3
"""
Create a comprehensive media summary TSV table with one row per medium.

This script aggregates data from:
1. media_properties/*.json files - pH, salinity, ionic strength calculations
2. high_confidence_compound_mappings.tsv - compound mapping statistics

Creates a single TSV file with one row per medium containing all computed
properties and mapping quality metrics.

Usage:
    python create_media_summary.py [--properties-dir DIR] [--mappings-file FILE] [--output FILE]
"""

import pandas as pd
import numpy as np
import json
import logging
from pathlib import Path
import argparse
import re
from typing import Dict, List, Optional, Tuple

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('create_media_summary.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class MediaSummarizer:
    """
    Create comprehensive media summary from properties and mapping data.
    """
    
    def __init__(self, 
                 properties_dir: str = "media_properties",
                 mappings_file: str = "high_confidence_compound_mappings.tsv",
                 output_file: str = "media_summary.tsv"):
        
        self.properties_dir = Path(properties_dir)
        self.mappings_file = mappings_file
        self.output_file = output_file
        
        # Storage for loaded data
        self.properties_data = {}
        self.mappings_df = None
        
    def load_media_properties(self) -> Dict[str, Dict]:
        """Load all media properties JSON files."""
        logger.info(f"Loading media properties from {self.properties_dir}")
        
        properties_data = {}
        json_files = list(self.properties_dir.glob("*_composition_properties.json"))
        
        logger.info(f"Found {len(json_files)} properties files")
        
        for json_file in json_files:
            try:
                # Extract medium ID from filename
                match = re.search(r'medium_([^_]+)_composition_properties\.json', json_file.name)
                if not match:
                    logger.warning(f"Could not extract medium ID from {json_file.name}")
                    continue
                    
                medium_id = match.group(1)
                
                # Load JSON data
                with open(json_file, 'r') as f:
                    data = json.load(f)
                    
                properties_data[medium_id] = data
                
            except Exception as e:
                logger.warning(f"Error loading {json_file}: {e}")
                continue
                
        logger.info(f"Successfully loaded {len(properties_data)} media properties")
        return properties_data
        
    def load_compound_mappings(self) -> pd.DataFrame:
        """Load high-confidence compound mappings."""
        logger.info(f"Loading compound mappings from {self.mappings_file}")
        
        try:
            df = pd.read_csv(self.mappings_file, sep='\t', dtype=str, low_memory=False)
            
            # Convert numeric columns
            numeric_cols = ['value', 'mmol_l', 'hydration_number', 'similarity_score']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                    
            logger.info(f"Loaded {len(df)} mapping entries covering {df['medium_id'].nunique()} media")
            return df
            
        except Exception as e:
            logger.error(f"Error loading mappings: {e}")
            raise
            
    def calculate_mapping_stats(self, medium_id: str) -> Dict:
        """Calculate mapping statistics for a specific medium."""
        
        if self.mappings_df is None:
            return {}
            
        # Filter mappings for this medium
        medium_mappings = self.mappings_df[self.mappings_df['medium_id'] == medium_id]
        
        if len(medium_mappings) == 0:
            return {
                'total_compounds': 0,
                'mapped_compounds': 0,
                'unmapped_compounds': 0,
                'mapping_rate': 0.0,
                'chebi_matches': 0,
                'very_high_confidence': 0,
                'high_confidence': 0,
                'excellent_quality': 0,
                'very_good_quality': 0,
                'good_quality': 0
            }
            
        total_compounds = len(medium_mappings)
        
        # Count mapping status
        mapped_compounds = len(medium_mappings[
            medium_mappings['mapped'].notna() & (medium_mappings['mapped'] != '')
        ])
        
        unmapped_compounds = total_compounds - mapped_compounds
        mapping_rate = (mapped_compounds / total_compounds * 100) if total_compounds > 0 else 0
        
        # Count ChEBI matches
        chebi_matches = len(medium_mappings[
            medium_mappings['chebi_match'].notna() & (medium_mappings['chebi_match'] != '')
        ])
        
        # Count confidence levels
        very_high_confidence = len(medium_mappings[medium_mappings['match_confidence'] == 'very_high'])
        high_confidence = len(medium_mappings[medium_mappings['match_confidence'] == 'high'])
        
        # Count quality levels
        excellent_quality = len(medium_mappings[medium_mappings['mapping_quality'] == 'excellent'])
        very_good_quality = len(medium_mappings[medium_mappings['mapping_quality'] == 'very_good'])
        good_quality = len(medium_mappings[medium_mappings['mapping_quality'] == 'good'])
        
        return {
            'total_compounds': total_compounds,
            'mapped_compounds': mapped_compounds,
            'unmapped_compounds': unmapped_compounds,
            'mapping_rate': round(mapping_rate, 1),
            'chebi_matches': chebi_matches,
            'very_high_confidence': very_high_confidence,
            'high_confidence': high_confidence,
            'excellent_quality': excellent_quality,
            'very_good_quality': very_good_quality,
            'good_quality': good_quality
        }
        
    def create_summary_row(self, medium_id: str, properties: Dict) -> Dict:
        """Create a summary row for a single medium."""
        
        row = {'medium_id': medium_id}
        
        # Extract pH properties
        ph_data = properties.get('ph', {})
        row.update({
            'ph_value': ph_data.get('value'),
            'ph_uncertainty': ph_data.get('uncertainty'),
            'ph_range_min': ph_data.get('range', [None, None])[0],
            'ph_range_max': ph_data.get('range', [None, None])[1],
            'ph_confidence': ph_data.get('confidence')
        })
        
        # Extract salinity properties
        salinity_data = properties.get('salinity', {})
        row.update({
            'salinity_percent_nacl': salinity_data.get('percent_nacl'),
            'salinity_uncertainty': salinity_data.get('uncertainty'),
            'salinity_range_min': salinity_data.get('range', [None, None])[0],
            'salinity_range_max': salinity_data.get('range', [None, None])[1],
            'salinity_confidence': salinity_data.get('confidence')
        })
        
        # Extract ionic strength
        ionic_strength_data = properties.get('ionic_strength', {})
        row.update({
            'ionic_strength_value': ionic_strength_data.get('value'),
            'ionic_strength_unit': ionic_strength_data.get('unit')
        })
        
        # Extract total dissolved solids
        tds_data = properties.get('total_dissolved_solids', {})
        row.update({
            'total_dissolved_solids_value': tds_data.get('value'),
            'total_dissolved_solids_unit': tds_data.get('unit')
        })
        
        # Extract analysis quality
        quality_data = properties.get('analysis_quality', {})
        row.update({
            'compounds_recognized': quality_data.get('compounds_recognized'),
            'compounds_estimated': quality_data.get('compounds_estimated'),
            'compounds_unaccounted': quality_data.get('compounds_unaccounted'),
            'total_coverage_rate': quality_data.get('total_coverage_rate'),
            'recognition_rate': quality_data.get('recognition_rate'),
            'estimation_rate': quality_data.get('estimation_rate'),
            'calculation_method': quality_data.get('calculation_method')
        })
        
        # Extract compound counts
        compound_details = properties.get('compound_details', {})
        row.update({
            'recognized_compounds_count': len(compound_details.get('recognized_compounds', [])),
            'estimated_compounds_count': len(compound_details.get('estimated_compounds', [])),
            'unaccounted_compounds_count': len(compound_details.get('unaccounted_compounds', []))
        })
        
        # Add compound lists (as semicolon-separated strings)
        row.update({
            'recognized_compounds_list': '; '.join(compound_details.get('recognized_compounds', [])),
            'estimated_compounds_list': '; '.join(compound_details.get('estimated_compounds', [])),
            'unaccounted_compounds_list': '; '.join(compound_details.get('unaccounted_compounds', []))
        })
        
        # Add notes count and content
        notes = properties.get('notes', [])
        row.update({
            'notes_count': len(notes),
            'notes_content': '; '.join(notes)
        })
        
        # Add mapping statistics
        mapping_stats = self.calculate_mapping_stats(medium_id)
        row.update(mapping_stats)
        
        return row
        
    def create_media_summary(self) -> pd.DataFrame:
        """Create comprehensive media summary DataFrame."""
        logger.info("Creating comprehensive media summary...")
        
        # Load data
        self.properties_data = self.load_media_properties()
        self.mappings_df = self.load_compound_mappings()
        
        # Create summary rows
        summary_rows = []
        
        for medium_id, properties in self.properties_data.items():
            try:
                row = self.create_summary_row(medium_id, properties)
                summary_rows.append(row)
            except Exception as e:
                logger.warning(f"Error creating summary for medium {medium_id}: {e}")
                continue
                
        # Create DataFrame
        summary_df = pd.DataFrame(summary_rows)

        # Check if any data was collected
        if len(summary_df) == 0:
            logger.warning("No summary data collected - creating empty summary with headers")
            # Create empty DataFrame with expected columns
            summary_df = pd.DataFrame(columns=['medium_id'])
            return summary_df

        # Sort by medium_id (numerically where possible)
        def sort_key(x):
            try:
                return (0, int(x))  # Numeric IDs first
            except ValueError:
                return (1, x)  # Non-numeric IDs second

        summary_df['sort_key'] = summary_df['medium_id'].apply(sort_key)
        summary_df = summary_df.sort_values('sort_key').drop('sort_key', axis=1)
        
        logger.info(f"Created summary for {len(summary_df)} media")
        
        return summary_df
        
    def save_summary(self, df: pd.DataFrame) -> None:
        """Save summary DataFrame to TSV file."""
        logger.info(f"Saving media summary to {self.output_file}")
        
        try:
            df.to_csv(self.output_file, sep='\t', index=False, na_rep='')
            logger.info(f"Successfully saved summary for {len(df)} media")
            
        except Exception as e:
            logger.error(f"Error saving summary: {e}")
            raise
            
    def analyze_summary(self, df: pd.DataFrame) -> None:
        """Analyze and report summary statistics."""
        logger.info("\n=== MEDIA SUMMARY ANALYSIS ===")

        total_media = len(df)
        logger.info(f"Total media: {total_media}")

        # Skip analysis if DataFrame is empty
        if total_media == 0:
            logger.warning("No media data to analyze")
            return

        # pH analysis
        ph_available = df['ph_value'].notna().sum()
        logger.info(f"Media with pH data: {ph_available} ({ph_available/total_media*100:.1f}%)")
        
        if ph_available > 0:
            ph_mean = df['ph_value'].mean()
            ph_std = df['ph_value'].std()
            ph_min = df['ph_value'].min()
            ph_max = df['ph_value'].max()
            logger.info(f"  pH range: {ph_min:.2f} - {ph_max:.2f} (mean: {ph_mean:.2f} ± {ph_std:.2f})")
            
        # Salinity analysis
        salinity_available = df['salinity_percent_nacl'].notna().sum()
        logger.info(f"Media with salinity data: {salinity_available} ({salinity_available/total_media*100:.1f}%)")
        
        if salinity_available > 0:
            sal_mean = df['salinity_percent_nacl'].mean()
            sal_std = df['salinity_percent_nacl'].std()
            sal_min = df['salinity_percent_nacl'].min()
            sal_max = df['salinity_percent_nacl'].max()
            logger.info(f"  Salinity range: {sal_min:.3f} - {sal_max:.3f}% NaCl (mean: {sal_mean:.3f} ± {sal_std:.3f}%)")
            
        # Mapping analysis
        total_compounds = df['total_compounds'].sum()
        mapped_compounds = df['mapped_compounds'].sum()
        chebi_matches = df['chebi_matches'].sum()
        
        if total_compounds > 0:
            overall_mapping_rate = mapped_compounds / total_compounds * 100
            chebi_rate = chebi_matches / total_compounds * 100
            
            logger.info(f"Overall compound mapping:")
            logger.info(f"  Total compounds: {total_compounds}")
            logger.info(f"  Mapped compounds: {mapped_compounds} ({overall_mapping_rate:.1f}%)")
            logger.info(f"  ChEBI matches: {chebi_matches} ({chebi_rate:.1f}%)")
            
        # Confidence analysis
        very_high_total = df['very_high_confidence'].sum()
        high_total = df['high_confidence'].sum()
        
        logger.info(f"Confidence distribution:")
        logger.info(f"  Very high confidence: {very_high_total}")
        logger.info(f"  High confidence: {high_total}")
        
        # Top media by compound count
        top_media = df.nlargest(10, 'total_compounds')[['medium_id', 'total_compounds', 'mapping_rate']]
        logger.info(f"\nTop 10 media by compound count:")
        for _, row in top_media.iterrows():
            logger.info(f"  Medium {row['medium_id']}: {row['total_compounds']} compounds ({row['mapping_rate']:.1f}% mapped)")
            
    def run_summarization(self) -> None:
        """Run the complete summarization process."""
        logger.info("Starting media summarization process...")
        
        # Create summary
        summary_df = self.create_media_summary()
        
        # Analyze results
        self.analyze_summary(summary_df)
        
        # Save summary
        self.save_summary(summary_df)
        
        logger.info("Media summarization completed!")

def main():
    """Main function to run the summarization process."""
    parser = argparse.ArgumentParser(
        description="Create comprehensive media summary TSV from properties and mappings"
    )
    parser.add_argument(
        '--properties-dir', 
        default='media_properties',
        help='Directory containing media properties JSON files (default: media_properties)'
    )
    parser.add_argument(
        '--mappings-file',
        default='high_confidence_compound_mappings.tsv', 
        help='High-confidence mappings file (default: high_confidence_compound_mappings.tsv)'
    )
    parser.add_argument(
        '--output',
        default='media_summary.tsv',
        help='Output summary file (default: media_summary.tsv)'
    )
    
    args = parser.parse_args()
    
    # Create and run summarizer
    summarizer = MediaSummarizer(
        properties_dir=args.properties_dir,
        mappings_file=args.mappings_file,
        output_file=args.output
    )
    
    summarizer.run_summarization()

if __name__ == "__main__":
    main()