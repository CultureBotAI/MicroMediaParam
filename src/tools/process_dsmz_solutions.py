#!/usr/bin/env python3
"""
Complete workflow to process DSMZ solutions: download PDFs, extract compositions, and expand mapping data.
"""

import asyncio
import logging
import argparse
import sys
from pathlib import Path

# Add current directory to path for imports
sys.path.append(str(Path(__file__).parent))

from download_dsmz_solutions import DSMZSolutionDownloader
from expand_solution_mappings import SolutionExpander

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    parser = argparse.ArgumentParser(description="Complete DSMZ solution processing workflow")
    parser.add_argument("--mapping-file", required=True, help="Input mapping TSV file")
    parser.add_argument("--output-file", required=True, help="Output mapping TSV file with expanded solutions")
    parser.add_argument("--solution-ids-file", default="solution_ids_to_process.txt", help="File with solution IDs")
    parser.add_argument("--skip-download", action="store_true", help="Skip download step if compositions exist")
    parser.add_argument("--report", action="store_true", help="Generate detailed report")
    
    args = parser.parse_args()
    
    logger.info("=== DSMZ SOLUTION PROCESSING WORKFLOW ===")
    
    # Step 1: Extract solution IDs from mapping file if not provided
    if not Path(args.solution_ids_file).exists():
        logger.info("Extracting solution IDs from mapping file...")
        extract_solution_ids_from_mapping(args.mapping_file, args.solution_ids_file)
    
    # Load solution IDs
    with open(args.solution_ids_file, 'r') as f:
        solution_ids = [line.strip() for line in f if line.strip()]
    
    logger.info(f"Processing {len(solution_ids)} DSMZ solutions")
    
    # Step 2: Download and process solution PDFs
    if not args.skip_download:
        logger.info("\n=== STEP 1: DOWNLOADING DSMZ SOLUTION PDFs ===")
        downloader = DSMZSolutionDownloader()
        results = await downloader.download_all_solutions(solution_ids)
        logger.info(f"Successfully processed {len(results)} solutions")
    else:
        logger.info("Skipping download step...")
    
    # Step 3: Expand solution mappings
    logger.info("\n=== STEP 2: EXPANDING SOLUTION MAPPINGS ===")
    expander = SolutionExpander("solution_compositions")
    
    if args.report:
        logger.info("Generating expansion report...")
        expander.create_expansion_report("dsmz_solution_expansion_report.json")
    
    # Expand the mappings
    expanded_df = expander.expand_mapping_data(args.mapping_file, args.output_file)
    
    logger.info("\n=== WORKFLOW COMPLETE ===")
    logger.info(f"Original mapping file: {args.mapping_file}")
    logger.info(f"Expanded mapping file: {args.output_file}")
    
    if args.report:
        logger.info("Detailed report: dsmz_solution_expansion_report.json")

def extract_solution_ids_from_mapping(mapping_file: str, output_file: str):
    """Extract unique solution IDs from the mapping file."""
    
    import pandas as pd
    
    df = pd.read_csv(mapping_file, sep='\t')
    solution_entries = df[df['mapped'].str.startswith('solution:', na=False)]
    
    if len(solution_entries) == 0:
        logger.warning("No solution entries found in mapping file")
        with open(output_file, 'w') as f:
            pass  # Create empty file
        return
    
    # Extract unique solution IDs
    unique_solutions = solution_entries['mapped'].unique()
    solution_ids = [sol.replace('solution:', '') for sol in unique_solutions]
    solution_ids.sort(key=int)  # Sort numerically
    
    with open(output_file, 'w') as f:
        for solution_id in solution_ids:
            f.write(f"{solution_id}\n")
    
    logger.info(f"Extracted {len(solution_ids)} unique solution IDs to {output_file}")

if __name__ == "__main__":
    asyncio.run(main())