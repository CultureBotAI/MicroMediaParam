#!/usr/bin/env python3
"""
Download METPO sheet from Google Drive and annotate labels with ChEBI terms using OAK.

This script:
1. Downloads the METPO spreadsheet from Google Drive as CSV
2. Extracts the label column 
3. Uses OAK to annotate labels against ChEBI ontology
4. Saves results as TSV with ChEBI annotations

Usage:
    python download_and_annotate_metpo.py
"""

import pandas as pd
import requests
import subprocess
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse, parse_qs

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('metpo_annotation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class METPOAnnotator:
    """Download METPO sheet and annotate with ChEBI terms."""
    
    def __init__(self, output_dir: str = "metpo_data"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # File paths
        self.csv_file = self.output_dir / "metpo_sheet.csv"
        self.labels_file = self.output_dir / "metpo_labels.txt"
        self.annotations_file = self.output_dir / "metpo_chebi_annotations.tsv"
        self.final_output = self.output_dir / "metpo_annotated_labels.tsv"
        
    def extract_sheet_id_and_gid(self, url: str) -> tuple[str, str]:
        """Extract spreadsheet ID and sheet GID from Google Sheets URL."""
        # Extract spreadsheet ID (between /d/ and /edit)
        if '/d/' in url:
            sheet_id = url.split('/d/')[1].split('/')[0]
        else:
            raise ValueError("Invalid Google Sheets URL format")
            
        # Extract GID from URL fragment
        gid = "0"  # default
        if '#gid=' in url:
            gid = url.split('#gid=')[1].split('&')[0]
        elif 'gid=' in url:
            parsed = urlparse(url)
            query_params = parse_qs(parsed.query)
            if 'gid' in query_params:
                gid = query_params['gid'][0]
        
        return sheet_id, gid
    
    def download_sheet_as_csv(self, sheets_url: str) -> None:
        """Download Google Sheet as CSV."""
        logger.info(f"Downloading METPO sheet from: {sheets_url}")
        
        try:
            # Extract sheet ID and GID
            sheet_id, gid = self.extract_sheet_id_and_gid(sheets_url)
            logger.info(f"Extracted sheet_id: {sheet_id}, gid: {gid}")
            
            # Construct CSV export URL
            csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
            
            # Download the CSV
            response = requests.get(csv_url, timeout=30)
            response.raise_for_status()
            
            # Save to file
            with open(self.csv_file, 'wb') as f:
                f.write(response.content)
                
            logger.info(f"Successfully downloaded sheet to: {self.csv_file}")
            
        except Exception as e:
            logger.error(f"Failed to download sheet: {e}")
            raise
    
    def extract_labels(self) -> List[str]:
        """Extract unique labels from the downloaded CSV."""
        logger.info("Extracting labels from METPO sheet...")
        
        try:
            # Read CSV
            df = pd.read_csv(self.csv_file)
            logger.info(f"Loaded CSV with {len(df)} rows and columns: {list(df.columns)}")
            
            # Look for label column (case insensitive)
            label_col = None
            for col in df.columns:
                if col.lower() in ['label', 'labels', 'compound', 'compound_name', 'name']:
                    label_col = col
                    break
            
            if label_col is None:
                # If no obvious label column, show available columns
                logger.error(f"No label column found. Available columns: {list(df.columns)}")
                raise ValueError("Could not find label column in CSV")
            
            logger.info(f"Using column '{label_col}' as label column")
            
            # Extract unique non-empty labels
            labels = df[label_col].dropna().astype(str).str.strip()
            labels = labels[labels != ''].unique().tolist()
            
            logger.info(f"Extracted {len(labels)} unique labels")
            
            # Save labels to file for OAK processing
            with open(self.labels_file, 'w') as f:
                for label in labels:
                    f.write(f"{label}\n")
            
            return labels
            
        except Exception as e:
            logger.error(f"Failed to extract labels: {e}")
            raise
    
    def annotate_with_oak_chebi(self, labels: List[str]) -> None:
        """Use OAK to annotate labels against ChEBI ontology."""
        logger.info("Annotating labels with ChEBI terms using OAK...")
        
        try:
            # Check if runoak is available
            result = subprocess.run(['runoak', '--help'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                raise RuntimeError("OAK (runoak) is not available. Please install: pip install oaklib")
            
            logger.info("OAK is available, starting annotation...")
            
            # Run OAK annotate command
            # Using sqlite:obo:chebi as the ChEBI source
            cmd = [
                'runoak',
                '-i', 'sqlite:obo:chebi',
                'annotate',
                '--text-file', str(self.labels_file),
                '--output', str(self.annotations_file),
                '--output-type', 'tsv'
            ]
            
            logger.info(f"Running command: {' '.join(cmd)}")
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode != 0:
                logger.error(f"OAK command failed with return code {result.returncode}")
                logger.error(f"STDOUT: {result.stdout}")
                logger.error(f"STDERR: {result.stderr}")
                
                # Try alternative ChEBI source
                logger.info("Trying alternative ChEBI source...")
                cmd[2] = 'pronto:obo:chebi'
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                
                if result.returncode != 0:
                    raise RuntimeError(f"OAK annotation failed: {result.stderr}")
            
            logger.info(f"OAK annotation completed successfully")
            logger.info(f"Annotations saved to: {self.annotations_file}")
            
        except subprocess.TimeoutExpired:
            logger.error("OAK annotation timed out after 5 minutes")
            raise
        except Exception as e:
            logger.error(f"Failed to annotate with OAK: {e}")
            raise
    
    def merge_annotations_with_labels(self, labels: List[str]) -> None:
        """Merge OAK annotations back with original labels."""
        logger.info("Merging annotations with original labels...")
        
        try:
            # Read OAK annotations
            if not self.annotations_file.exists():
                logger.warning("No annotations file found, creating empty annotations")
                annotations_df = pd.DataFrame(columns=['text', 'label_id', 'label', 'score'])
            else:
                annotations_df = pd.read_csv(self.annotations_file, sep='\t')
                logger.info(f"Loaded {len(annotations_df)} annotations")
            
            # Create DataFrame with all original labels
            labels_df = pd.DataFrame({'original_label': labels})
            
            # Merge with annotations (left join to keep all labels)
            if not annotations_df.empty and 'text' in annotations_df.columns:
                merged_df = labels_df.merge(
                    annotations_df, 
                    left_on='original_label', 
                    right_on='text', 
                    how='left'
                )
            else:
                # If no annotations, create empty columns
                merged_df = labels_df.copy()
                merged_df['text'] = merged_df['original_label']
                merged_df['label_id'] = None
                merged_df['label'] = None
                merged_df['score'] = None
            
            # Reorder columns
            column_order = ['original_label', 'text', 'label_id', 'label', 'score']
            existing_cols = [col for col in column_order if col in merged_df.columns]
            merged_df = merged_df[existing_cols]
            
            # Add summary statistics
            total_labels = len(labels)
            annotated_labels = merged_df['label_id'].notna().sum() if 'label_id' in merged_df.columns else 0
            annotation_rate = (annotated_labels / total_labels * 100) if total_labels > 0 else 0
            
            logger.info(f"Annotation summary:")
            logger.info(f"  Total labels: {total_labels}")
            logger.info(f"  Annotated labels: {annotated_labels}")
            logger.info(f"  Annotation rate: {annotation_rate:.1f}%")
            
            # Save final results
            merged_df.to_csv(self.final_output, sep='\t', index=False)
            logger.info(f"Final annotated results saved to: {self.final_output}")
            
        except Exception as e:
            logger.error(f"Failed to merge annotations: {e}")
            raise
    
    def run_complete_pipeline(self, sheets_url: str) -> None:
        """Run the complete pipeline from download to annotation."""
        logger.info("Starting METPO annotation pipeline...")
        
        try:
            # Step 1: Download sheet
            self.download_sheet_as_csv(sheets_url)
            
            # Step 2: Extract labels
            labels = self.extract_labels()
            
            # Step 3: Annotate with OAK
            self.annotate_with_oak_chebi(labels)
            
            # Step 4: Merge results
            self.merge_annotations_with_labels(labels)
            
            logger.info("METPO annotation pipeline completed successfully!")
            logger.info(f"Results available in: {self.output_dir}")
            
        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            raise

def main():
    """Main function to run the METPO annotation pipeline."""
    # METPO Google Sheets URL
    metpo_url = "https://docs.google.com/spreadsheets/d/1_Lr-9_5QHi8QLvRyTZFSciUhzGKD4DbUObyTpJ16_RU/edit?gid=355012485#gid=355012485"
    
    # Create annotator and run pipeline
    annotator = METPOAnnotator()
    annotator.run_complete_pipeline(metpo_url)

if __name__ == "__main__":
    main()