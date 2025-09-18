#!/usr/bin/env python3
"""
PubChem Chemical Data Processing Pipeline

Complete pipeline for downloading PubChem data and generating chemical_properties.tsv files.

Usage:
    python -m src.chem.pubchem.pipeline --from-mapping-file composition_kg_mapping.tsv
    python -m src.chem.pubchem.pipeline --download-compounds "sodium chloride,glucose,calcium carbonate"
    python -m src.chem.pubchem.pipeline --full-pipeline

Author: MicroMediaParam Project
"""

import asyncio
import argparse
import logging
import json
from pathlib import Path
from typing import List, Optional
import pandas as pd

from .data_downloader import PubChemDataDownloader
from .property_extractor import PubChemPropertyExtractor
from .tsv_generator import PubChemTSVGenerator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PubChemDataPipeline:
    """
    Complete pipeline for processing PubChem chemical data from download to TSV generation.
    """
    
    def __init__(self, 
                 data_dir: Path = Path("data/pubchem_processing"),
                 chemical_properties_file: Path = Path("chemical_properties.tsv")):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.chemical_properties_file = Path(chemical_properties_file)
        
        # Initialize components
        self.downloader = None  # Will be created in async context
        self.extractor = PubChemPropertyExtractor()
        self.tsv_generator = PubChemTSVGenerator()
        
        # File paths
        self.raw_data_file = self.data_dir / "pubchem_raw_data.json"
        self.processed_data_file = self.data_dir / "pubchem_processed_data.json"
        self.comparison_report_file = self.data_dir / "pubchem_comparison_report.json"
        
        # Error tracking and statistics
        self.stats = {
            'total_compounds': 0,
            'successful_downloads': 0,
            'failed_downloads': 0,
            'empty_results': 0,
            'processed_compounds': 0,
            'failed_processing': 0,
            'failed_compounds': [],
            'empty_compounds': [],
            'processing_errors': [],
            'cid_resolution_failures': [],
            'api_failures': []
        }
    
    def print_processing_statistics(self) -> None:
        """Print comprehensive processing statistics and error report."""
        print("\n" + "="*60)
        print("🧬 PubChem Chemical Data Processing Report")
        print("="*60)
        
        # Summary statistics
        print(f"\n📊 Summary Statistics:")
        print(f"   Total compounds requested:     {self.stats['total_compounds']:>6}")
        print(f"   Successful downloads:          {self.stats['successful_downloads']:>6}")
        print(f"   Failed downloads:              {self.stats['failed_downloads']:>6}")
        print(f"   Empty results (no CID found):  {self.stats['empty_results']:>6}")
        print(f"   Successfully processed:        {self.stats['processed_compounds']:>6}")
        print(f"   Processing failures:           {self.stats['failed_processing']:>6}")
        
        # Success rates
        if self.stats['total_compounds'] > 0:
            success_rate = (self.stats['successful_downloads'] / self.stats['total_compounds']) * 100
            processing_rate = (self.stats['processed_compounds'] / self.stats['total_compounds']) * 100
            print(f"\n📈 Success Rates:")
            print(f"   Download success rate:         {success_rate:>6.1f}%")
            print(f"   Overall processing rate:       {processing_rate:>6.1f}%")
        
        # Failed compounds details
        if self.stats['failed_compounds']:
            print(f"\n❌ Failed Downloads ({len(self.stats['failed_compounds'])} compounds):")
            for i, compound in enumerate(self.stats['failed_compounds'][:10], 1):
                print(f"   {i:>2}. {compound}")
            if len(self.stats['failed_compounds']) > 10:
                print(f"   ... and {len(self.stats['failed_compounds']) - 10} more")
        
        # Empty results details
        if self.stats['empty_compounds']:
            print(f"\n⚠️  No CID Found ({len(self.stats['empty_compounds'])} compounds):")
            for i, compound in enumerate(self.stats['empty_compounds'][:10], 1):
                print(f"   {i:>2}. {compound}")
            if len(self.stats['empty_compounds']) > 10:
                print(f"   ... and {len(self.stats['empty_compounds']) - 10} more")
        
        # CID resolution failures
        if self.stats['cid_resolution_failures']:
            print(f"\n🔍 CID Resolution Issues ({len(self.stats['cid_resolution_failures'])} compounds):")
            for i, compound in enumerate(self.stats['cid_resolution_failures'][:5], 1):
                print(f"   {i:>2}. {compound}")
            if len(self.stats['cid_resolution_failures']) > 5:
                print(f"   ... and {len(self.stats['cid_resolution_failures']) - 5} more")
        
        # API failures
        if self.stats['api_failures']:
            print(f"\n🌐 API Request Failures ({len(self.stats['api_failures'])} errors):")
            for i, error in enumerate(self.stats['api_failures'][:5], 1):
                print(f"   {i:>2}. {error}")
            if len(self.stats['api_failures']) > 5:
                print(f"   ... and {len(self.stats['api_failures']) - 5} more")
        
        # Processing errors details
        if self.stats['processing_errors']:
            print(f"\n🔧 Processing Errors ({len(self.stats['processing_errors'])} errors):")
            for i, error in enumerate(self.stats['processing_errors'][:5], 1):
                print(f"   {i:>2}. {error}")
            if len(self.stats['processing_errors']) > 5:
                print(f"   ... and {len(self.stats['processing_errors']) - 5} more")
        
        print("\n" + "="*60)
    
    async def download_chemical_data_robust(self, compound_names: List[str]) -> None:
        """
        Download chemical data with robust error handling and statistics tracking.
        
        Args:
            compound_names: List of compound names to download
        """
        self.stats['total_compounds'] = len(compound_names)
        logger.info(f"Starting robust PubChem data download for {len(compound_names)} compounds")
        
        async with PubChemDataDownloader(
            cache_dir=self.data_dir / "cache",
            bulk_data_dir=self.data_dir / "bulk"
        ) as downloader:
            
            all_compound_data = []
            
            # Build CID lookup index (this downloads bulk files if needed)
            try:
                logger.info("Building PubChem CID lookup index...")
                cid_index = downloader.build_cid_lookup_index()
                logger.info(f"CID lookup index ready with {len(cid_index):,} entries")
            except Exception as e:
                logger.error(f"Failed to build CID lookup index: {e}")
                self.stats['processing_errors'].append(f"CID index build failed: {str(e)}")
                return
            
            # Process compounds individually for better error tracking
            for i, compound_name in enumerate(compound_names, 1):
                if i % 50 == 0:
                    logger.info(f"Progress: {i}/{len(compound_names)} compounds processed")
                
                try:
                    # Download compound data
                    compound_data = await downloader.download_compound_data(compound_name, cid_index)
                    
                    if compound_data:
                        all_compound_data.append(compound_data)
                        self.stats['successful_downloads'] += 1
                        logger.debug(f"Downloaded data for: {compound_name} (CID: {compound_data.cid})")
                    else:
                        self.stats['empty_results'] += 1
                        self.stats['empty_compounds'].append(compound_name)
                        self.stats['cid_resolution_failures'].append(compound_name)
                        logger.debug(f"No CID found for: {compound_name}")
                
                except Exception as e:
                    self.stats['failed_downloads'] += 1
                    self.stats['failed_compounds'].append(compound_name)
                    error_msg = f"{compound_name}: {str(e)}"
                    self.stats['api_failures'].append(error_msg)
                    logger.warning(f"Download failed for {compound_name}: {e}")
                
                # Rate limiting
                await asyncio.sleep(0.1)
            
            # Save all collected data
            if all_compound_data:
                await downloader.save_compounds_data(all_compound_data, self.raw_data_file)
                logger.info(f"Saved data for {len(all_compound_data)} compounds to: {self.raw_data_file}")
            else:
                logger.warning("No chemical data was successfully downloaded from PubChem")
        
        logger.info(f"Robust PubChem data download completed")
    
    def process_chemical_data_robust(self) -> None:
        """Process raw chemical data with enhanced error tracking."""
        if not self.raw_data_file.exists():
            logger.error(f"Raw data file not found: {self.raw_data_file}")
            return
        
        logger.info("Processing raw PubChem data with error tracking...")
        
        try:
            # Process the raw data
            processed_compounds = self.extractor.process_raw_data_file(self.raw_data_file)
            
            self.stats['processed_compounds'] = len(processed_compounds)
            
            # Save processed data
            self.extractor.save_processed_data(processed_compounds, self.processed_data_file)
            
            logger.info(f"Successfully processed {len(processed_compounds)} compounds")
            
        except Exception as e:
            self.stats['failed_processing'] += 1
            error_msg = f"Data processing failed: {str(e)}"
            self.stats['processing_errors'].append(error_msg)
            logger.error(error_msg)
            raise
    
    def generate_chemical_properties_tsv(self, merge_with_existing: bool = True) -> None:
        """
        Generate chemical_properties.tsv file from processed data.
        
        Args:
            merge_with_existing: Whether to merge with existing TSV file
        """
        if not self.processed_data_file.exists():
            logger.error(f"Processed data file not found: {self.processed_data_file}")
            return
        
        logger.info("Generating chemical_properties.tsv from PubChem data...")
        
        # Generate TSV
        self.tsv_generator.generate_tsv_from_json(
            self.processed_data_file, 
            self.chemical_properties_file, 
            merge_with_existing
        )
        
        # Validate the generated TSV
        is_valid = self.tsv_generator.validate_tsv_format(self.chemical_properties_file)
        if is_valid:
            logger.info("Generated TSV file passed validation")
        else:
            logger.error("Generated TSV file failed validation")
        
        # Generate comparison report if existing database exists
        if merge_with_existing:
            self.generate_comparison_report()
        
        logger.info(f"Successfully generated chemical_properties.tsv: {self.chemical_properties_file}")
    
    def generate_comparison_report(self) -> None:
        """Generate a comparison report between PubChem and existing data."""
        try:
            # Create a temporary TSV with just PubChem data
            temp_pubchem_tsv = self.data_dir / "temp_pubchem_only.tsv"
            self.tsv_generator.generate_tsv_from_json(
                self.processed_data_file,
                temp_pubchem_tsv,
                merge_with_existing=False
            )
            
            # Compare with existing database
            comparison_stats = self.tsv_generator.compare_with_existing_database(
                temp_pubchem_tsv,
                self.chemical_properties_file
            )
            
            # Save comparison report
            with open(self.comparison_report_file, 'w') as f:
                json.dump(comparison_stats, f, indent=2)
            
            logger.info(f"Generated comparison report: {self.comparison_report_file}")
            
            # Clean up temp file
            if temp_pubchem_tsv.exists():
                temp_pubchem_tsv.unlink()
                
        except Exception as e:
            logger.warning(f"Failed to generate comparison report: {e}")
    
    async def process_compounds_from_mapping_file(self, mapping_file: Path) -> None:
        """
        Process all compounds from a mapping file with robust error handling.
        
        Args:
            mapping_file: Path to TSV mapping file with compound names
        """
        logger.info(f"Processing compounds from mapping file: {mapping_file}")
        
        # Extract unique compound names from mapping file
        try:
            df = pd.read_csv(mapping_file, sep='\t')
            if 'original' in df.columns:
                compound_names = df['original'].dropna().unique().tolist()
            elif 'compound_name' in df.columns:
                compound_names = df['compound_name'].dropna().unique().tolist()
            else:
                # Try to find the column with compound names
                text_columns = df.select_dtypes(include=['object']).columns
                if len(text_columns) > 0:
                    compound_names = df[text_columns[0]].dropna().unique().tolist()
                else:
                    raise ValueError("No suitable compound name column found")
            
            # Filter out compounds that are too complex or not chemicals
            filtered_compounds = []
            for name in compound_names:
                # Skip very short names, mixtures, and complex entries
                if len(name) > 2 and not any(skip in name.lower() for skip in [
                    'extract', 'peptone', 'mixture', 'medium', 'agar', 'broth'
                ]):
                    filtered_compounds.append(name.strip())
            
            logger.info(f"Found {len(compound_names)} total compounds, {len(filtered_compounds)} suitable for PubChem processing")
            
            # Download data with robust error handling
            await self.download_chemical_data_robust(filtered_compounds)
            
            # Process the downloaded data
            self.process_chemical_data_robust()
            
            # Generate updated TSV
            self.generate_chemical_properties_tsv(merge_with_existing=True)
            
            # Print comprehensive statistics
            self.print_processing_statistics()
            
        except Exception as e:
            logger.error(f"Failed to process mapping file {mapping_file}: {e}")
            raise
    
    async def run_full_pipeline(self, target_compounds: Optional[List[str]] = None) -> None:
        """
        Run the complete PubChem pipeline.
        
        Args:
            target_compounds: Optional list of specific compounds to process
        """
        if target_compounds is None:
            # Default test compounds
            target_compounds = [
                "sodium chloride", "potassium chloride", "glucose", "sucrose",
                "glycine", "alanine", "calcium carbonate", "magnesium sulfate",
                "tris", "hepes", "acetate", "phosphate"
            ]
        
        logger.info("Running complete PubChem pipeline...")
        
        # Download compounds
        await self.download_chemical_data_robust(target_compounds)
        
        # Process data
        self.process_chemical_data_robust()
        
        # Generate TSV
        self.generate_chemical_properties_tsv(merge_with_existing=True)
        
        # Print statistics
        self.print_processing_statistics()
        
        logger.info("Complete PubChem pipeline finished")

async def main():
    """Main command-line interface for the PubChem pipeline."""
    parser = argparse.ArgumentParser(
        description="PubChem Chemical Data Processing Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process compounds from mapping file
  python -m src.chem.pubchem.pipeline --from-mapping-file composition_kg_mapping.tsv
  
  # Download data for specific compounds
  python -m src.chem.pubchem.pipeline --download-compounds "sodium chloride,glucose,calcium carbonate"
  
  # Run full pipeline with default compounds
  python -m src.chem.pubchem.pipeline --full-pipeline
  
  # Process only (skip download)
  python -m src.chem.pubchem.pipeline --process-only
        """
    )
    
    parser.add_argument(
        "--from-mapping-file",
        type=str,
        help="Process compounds from a TSV mapping file (e.g., composition_kg_mapping.tsv)"
    )
    
    parser.add_argument(
        "--download-compounds",
        type=str,
        help="Comma-separated list of compound names to download"
    )
    
    parser.add_argument(
        "--full-pipeline",
        action="store_true",
        help="Run complete pipeline with default compound set"
    )
    
    parser.add_argument(
        "--process-only",
        action="store_true",
        help="Process existing raw data without downloading"
    )
    
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data/pubchem_processing",
        help="Directory for intermediate data files"
    )
    
    parser.add_argument(
        "--output-file",
        type=str,
        default="chemical_properties.tsv",
        help="Output chemical properties TSV file"
    )
    
    args = parser.parse_args()
    
    # Create pipeline
    pipeline = PubChemDataPipeline(
        data_dir=Path(args.data_dir),
        chemical_properties_file=Path(args.output_file)
    )
    
    try:
        if args.from_mapping_file:
            mapping_file = Path(args.from_mapping_file)
            if not mapping_file.exists():
                logger.error(f"Mapping file not found: {mapping_file}")
                return
            await pipeline.process_compounds_from_mapping_file(mapping_file)
            
        elif args.download_compounds:
            compounds = [c.strip() for c in args.download_compounds.split(',')]
            await pipeline.download_chemical_data_robust(compounds)
            pipeline.process_chemical_data_robust()
            pipeline.generate_chemical_properties_tsv()
            pipeline.print_processing_statistics()
            
        elif args.full_pipeline:
            await pipeline.run_full_pipeline()
            
        elif args.process_only:
            pipeline.process_chemical_data_robust()
            pipeline.generate_chemical_properties_tsv()
            
        else:
            parser.print_help()
            
    except KeyboardInterrupt:
        logger.info("Pipeline interrupted by user")
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())