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