#!/usr/bin/env python3
"""
IUPAC Chemical Data Processing Pipeline

Complete pipeline for downloading chemical data and generating chemical_properties.tsv files.

Usage:
    python -m src.chem.iupac.pipeline --update-chemical-properties
    python -m src.chem.iupac.pipeline --download-compounds "sodium chloride,glucose,calcium carbonate"
    python -m src.chem.iupac.pipeline --full-pipeline

Author: MicroMediaParam Project
"""

import asyncio
import argparse
import logging
from pathlib import Path
from typing import List, Optional

from .data_downloader import IUPACDataDownloader
from .property_extractor import ChemicalPropertyExtractor
from .tsv_generator import ChemicalPropertiesTSVGenerator
from .compound_mapper import CompoundMapper

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ChemicalDataPipeline:
    """
    Complete pipeline for processing chemical data from download to TSV generation.
    """
    
    def __init__(self, 
                 data_dir: Path = Path("data/chemical_processing"),
                 chemical_properties_file: Path = Path("chemical_properties.tsv")):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.chemical_properties_file = Path(chemical_properties_file)
        
        # Initialize components
        self.downloader = None  # Will be created in async context
        self.extractor = ChemicalPropertyExtractor()
        self.tsv_generator = ChemicalPropertiesTSVGenerator()
        self.mapper = CompoundMapper()
        
        # File paths
        self.raw_data_file = self.data_dir / "raw_chemical_data.json"
        self.processed_data_file = self.data_dir / "processed_chemical_data.json"
        self.mapping_report_file = self.data_dir / "compound_mapping_report.tsv"
        
        # Error tracking
        self.stats = {
            'total_compounds': 0,
            'successful_downloads': 0,
            'failed_downloads': 0,
            'empty_results': 0,
            'processed_compounds': 0,
            'failed_processing': 0,
            'failed_compounds': [],
            'empty_compounds': [],
            'processing_errors': []
        }
    
    async def download_chemical_data(self, compound_names: List[str]) -> None:
        """
        Download chemical data for specified compounds.
        
        Args:
            compound_names: List of compound names to download
        """
        logger.info(f"Starting chemical data download for {len(compound_names)} compounds")
        
        async with IUPACDataDownloader(self.data_dir / "sources") as downloader:
            # Download from all sources
            raw_data = await downloader.download_all_sources(compound_names)
            
            # Save raw data
            await downloader.save_raw_data(raw_data, "raw_chemical_data.json")
            
            # Move to expected location
            source_file = self.data_dir / "sources" / "raw_chemical_data.json"
            if source_file.exists():
                source_file.rename(self.raw_data_file)
        
        logger.info(f"Chemical data download completed: {self.raw_data_file}")
    
    def process_chemical_data(self) -> None:
        """Process raw chemical data into structured properties."""
        if not self.raw_data_file.exists():
            logger.error(f"Raw data file not found: {self.raw_data_file}")
            return
        
        logger.info("Processing raw chemical data...")
        
        # Extract and process properties
        processed_compounds = self.extractor.process_raw_data(self.raw_data_file)
        
        # Save processed data
        self.extractor.save_processed_data(processed_compounds, self.processed_data_file)
        
        logger.info(f"Processed {len(processed_compounds)} compounds")
    
    def generate_chemical_properties_tsv(self, merge_with_existing: bool = True) -> None:
        """
        Generate chemical_properties.tsv file.
        
        Args:
            merge_with_existing: Whether to merge with existing TSV file
        """
        if not self.processed_data_file.exists():
            logger.error(f"Processed data file not found: {self.processed_data_file}")
            return
        
        logger.info("Generating chemical_properties.tsv...")
        
        # Generate TSV from processed data
        self.tsv_generator.generate_tsv_from_json(
            self.processed_data_file,
            self.chemical_properties_file,
            merge_with_existing=merge_with_existing
        )
        
        # Validate the generated file
        is_valid = self.tsv_generator.validate_tsv_format(self.chemical_properties_file)
        if is_valid:
            logger.info(f"Successfully generated chemical_properties.tsv: {self.chemical_properties_file}")
        else:
            logger.error("Generated TSV file failed validation")
    
    def analyze_existing_compounds(self, mappings_files: List[Path]) -> List[str]:
        """
        Analyze existing compound mapping files to identify compounds for download.
        
        Args:
            mappings_files: List of compound mapping files
            
        Returns:
            List of standardized compound names for download
        """
        logger.info("Analyzing existing compound mappings...")
        
        # Create target compound list
        target_compounds = self.mapper.create_download_target_list(mappings_files)
        
        # Generate mapping report
        all_compounds = set()
        for mappings_file in mappings_files:
            if mappings_file.exists():
                compounds = self.mapper.extract_compounds_from_mappings_file(mappings_file)
                all_compounds.update(compounds)
        
        self.mapper.save_mapping_report(list(all_compounds), self.mapping_report_file)
        
        logger.info(f"Identified {len(target_compounds)} target compounds for download")
        return target_compounds
    
    async def run_full_pipeline(self, mappings_files: Optional[List[Path]] = None) -> None:
        """
        Run the complete chemical data processing pipeline.
        
        Args:
            mappings_files: Optional list of compound mapping files to analyze
        """
        logger.info("Starting full chemical data processing pipeline")
        
        # Default mapping files if not provided
        if mappings_files is None:
            mappings_files = [
                Path("high_confidence_compound_mappings_normalized_ingredient_enhanced_normalized.tsv"),
                Path("composition_kg_mapping.tsv"),
                Path("unaccounted_compound_matches.tsv")
            ]
        
        try:
            # Step 1: Analyze existing compounds
            target_compounds = self.analyze_existing_compounds(mappings_files)
            
            # Step 2: Download chemical data
            if target_compounds:
                await self.download_chemical_data(target_compounds)
            else:
                logger.warning("No target compounds identified for download")
                return
            
            # Step 3: Process raw data
            self.process_chemical_data()
            
            # Step 4: Generate TSV file
            self.generate_chemical_properties_tsv(merge_with_existing=True)
            
            logger.info("Full pipeline completed successfully")
            
        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            raise
    
    async def update_chemical_properties(self, additional_compounds: Optional[List[str]] = None) -> None:
        """
        Update chemical_properties.tsv with new compounds.
        
        Args:
            additional_compounds: Optional list of additional compounds to include
        """
        logger.info("Updating chemical_properties.tsv with new compounds")
        
        # Get compounds from existing mapping files
        mappings_files = [
            Path("high_confidence_compound_mappings_normalized_ingredient_enhanced_normalized.tsv"),
            Path("composition_kg_mapping.tsv")
        ]
        
        target_compounds = self.analyze_existing_compounds(mappings_files)
        
        # Add additional compounds if provided
        if additional_compounds:
            for compound in additional_compounds:
                standard_name = self.mapper.map_to_standard_name(compound)
                if standard_name:
                    target_compounds.append(standard_name)
        
        # Remove duplicates
        target_compounds = list(set(target_compounds))
        
        # Download and process
        await self.download_chemical_data(target_compounds)
        self.process_chemical_data()
        self.generate_chemical_properties_tsv(merge_with_existing=True)
        
        logger.info("Chemical properties update completed")
    
    def print_processing_statistics(self) -> None:
        """Print comprehensive processing statistics and error report."""
        print("\n" + "="*60)
        print("🧪 IUPAC Chemical Data Processing Report")
        print("="*60)
        
        # Summary statistics
        print(f"\n📊 Summary Statistics:")
        print(f"   Total compounds requested:     {self.stats['total_compounds']:>6}")
        print(f"   Successful downloads:          {self.stats['successful_downloads']:>6}")
        print(f"   Failed downloads:              {self.stats['failed_downloads']:>6}")
        print(f"   Empty results (no data found): {self.stats['empty_results']:>6}")
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
            print(f"\n⚠️  No Data Found ({len(self.stats['empty_compounds'])} compounds):")
            for i, compound in enumerate(self.stats['empty_compounds'][:10], 1):
                print(f"   {i:>2}. {compound}")
            if len(self.stats['empty_compounds']) > 10:
                print(f"   ... and {len(self.stats['empty_compounds']) - 10} more")
        
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
        logger.info(f"Starting robust chemical data download for {len(compound_names)} compounds")
        
        async with IUPACDataDownloader(self.data_dir / "sources") as downloader:
            all_raw_data = []
            
            for i, compound_name in enumerate(compound_names, 1):
                if i % 50 == 0:
                    logger.info(f"Progress: {i}/{len(compound_names)} compounds processed")
                
                try:
                    # Download from all sources for this compound
                    compound_data = await downloader.download_compound_data(compound_name)
                    
                    if compound_data:
                        # Check if we got meaningful data
                        has_data = any([
                            compound_data.get('molecular_weight'),
                            compound_data.get('formula'),
                            compound_data.get('cas_number'),
                            compound_data.get('chebi_id'),
                            compound_data.get('pubchem_cid')
                        ])
                        
                        if has_data:
                            all_raw_data.append(compound_data)
                            self.stats['successful_downloads'] += 1
                        else:
                            self.stats['empty_results'] += 1
                            self.stats['empty_compounds'].append(compound_name)
                            logger.debug(f"No meaningful data found for: {compound_name}")
                    else:
                        self.stats['empty_results'] += 1
                        self.stats['empty_compounds'].append(compound_name)
                        logger.debug(f"No data returned for: {compound_name}")
                
                except Exception as e:
                    self.stats['failed_downloads'] += 1
                    self.stats['failed_compounds'].append(compound_name)
                    error_msg = f"{compound_name}: {str(e)}"
                    self.stats['processing_errors'].append(error_msg)
                    logger.warning(f"Download failed for {compound_name}: {e}")
                
                # Rate limiting
                await asyncio.sleep(0.1)
            
            # Save all collected data
            if all_raw_data:
                await downloader.save_raw_data_list(all_raw_data, "raw_chemical_data.json")
                
                # Move to expected location
                source_file = self.data_dir / "sources" / "raw_chemical_data.json"
                if source_file.exists():
                    source_file.rename(self.raw_data_file)
                
                logger.info(f"Saved data for {len(all_raw_data)} compounds to: {self.raw_data_file}")
            else:
                logger.warning("No chemical data was successfully downloaded")
        
        logger.info(f"Robust chemical data download completed")
    
    async def process_compounds_from_mapping_file(self, mapping_file: Path) -> None:
        """
        Process all compounds from a mapping file with robust error handling.
        
        Args:
            mapping_file: Path to TSV mapping file with compound names
        """
        logger.info(f"Processing compounds from mapping file: {mapping_file}")
        
        # Extract unique compound names from mapping file
        import pandas as pd
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
                standard_name = self.mapper.map_to_standard_name(name)
                if standard_name and len(standard_name) > 2:  # Skip very short names
                    filtered_compounds.append(standard_name)
            
            logger.info(f"Found {len(compound_names)} total compounds, {len(filtered_compounds)} suitable for processing")
            
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
    
    def process_chemical_data_robust(self) -> None:
        """Process raw chemical data with enhanced error tracking."""
        if not self.raw_data_file.exists():
            logger.error(f"Raw data file not found: {self.raw_data_file}")
            return
        
        logger.info("Processing raw chemical data with error tracking...")
        
        try:
            # Check format and extract and process properties
            import json
            with open(self.raw_data_file, 'r') as f:
                raw_data = json.load(f)
            
            # Use appropriate processing method based on data format
            if isinstance(raw_data, list):
                processed_compounds = self.extractor.process_raw_data_list(self.raw_data_file)
            else:
                processed_compounds = self.extractor.process_raw_data(self.raw_data_file)
            
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

async def main():
    """Main command-line interface for the chemical data pipeline."""
    parser = argparse.ArgumentParser(
        description="IUPAC Chemical Data Processing Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Update chemical_properties.tsv with compounds from existing mappings
  python -m src.chem.iupac.pipeline --update-chemical-properties
  
  # Download data for specific compounds
  python -m src.chem.iupac.pipeline --download-compounds "sodium chloride,glucose,calcium carbonate"
  
  # Run full pipeline
  python -m src.chem.iupac.pipeline --full-pipeline
  
  # Process existing raw data
  python -m src.chem.iupac.pipeline --process-only
        """
    )
    
    parser.add_argument(
        "--update-chemical-properties",
        action="store_true",
        help="Update chemical_properties.tsv with compounds from existing mappings"
    )
    
    parser.add_argument(
        "--download-compounds",
        type=str,
        help="Comma-separated list of compounds to download data for"
    )
    
    parser.add_argument(
        "--full-pipeline",
        action="store_true",
        help="Run complete pipeline from analysis to TSV generation"
    )
    
    parser.add_argument(
        "--process-only",
        action="store_true",
        help="Process existing raw data without downloading"
    )
    
    parser.add_argument(
        "--from-mapping-file",
        type=str,
        help="Process compounds from a TSV mapping file (e.g., composition_kg_mapping.tsv)"
    )
    
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data/chemical_processing",
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
    pipeline = ChemicalDataPipeline(
        data_dir=Path(args.data_dir),
        chemical_properties_file=Path(args.output_file)
    )
    
    try:
        if args.update_chemical_properties:
            await pipeline.update_chemical_properties()
            
        elif args.download_compounds:
            compounds = [c.strip() for c in args.download_compounds.split(',')]
            await pipeline.download_chemical_data(compounds)
            pipeline.process_chemical_data()
            pipeline.generate_chemical_properties_tsv()
            
        elif args.from_mapping_file:
            mapping_file = Path(args.from_mapping_file)
            if not mapping_file.exists():
                logger.error(f"Mapping file not found: {mapping_file}")
                return
            await pipeline.process_compounds_from_mapping_file(mapping_file)
            
        elif args.full_pipeline:
            await pipeline.run_full_pipeline()
            
        elif args.process_only:
            pipeline.process_chemical_data()
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