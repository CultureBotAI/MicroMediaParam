#!/usr/bin/env python3
"""
Complete workflow for DSMZ solution expansion: download, parse, and integrate into chemical mapping.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add current directory to path for imports
sys.path.append(str(Path(__file__).parent))

from download_dsmz_solutions import DSMZSolutionDownloader
from enhanced_solution_parser import EnhancedSolutionParser, reprocess_solution_compositions
from expand_solution_mappings import SolutionExpander

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def complete_solution_expansion_workflow(
    mapping_file: str,
    output_file: str,
    force_redownload: bool = False,
    force_reparse: bool = False
):
    """Complete workflow for solution expansion."""
    
    logger.info("=== COMPLETE DSMZ SOLUTION EXPANSION WORKFLOW ===")
    
    # Step 1: Download solution PDFs
    if force_redownload or not Path("solution_pdfs").exists():
        logger.info("\n--- STEP 1: DOWNLOADING SOLUTION PDFs ---")
        
        # Extract solution IDs from mapping file
        extract_solution_ids_from_mapping(mapping_file, "solution_ids_to_process.txt")
        
        with open("solution_ids_to_process.txt", 'r') as f:
            solution_ids = [line.strip() for line in f if line.strip()]
        
        downloader = DSMZSolutionDownloader()
        results = await downloader.download_all_solutions(solution_ids)
        logger.info(f"Downloaded and processed {len(results)} solutions")
    else:
        logger.info("Skipping download step (files exist)")
    
    # Step 2: Enhanced parsing
    if force_reparse or not Path("solution_compositions_enhanced").exists():
        logger.info("\n--- STEP 2: ENHANCED SOLUTION PARSING ---")
        enhanced_results = reprocess_solution_compositions()
        logger.info(f"Enhanced parsing extracted components from {len(enhanced_results)} solutions")
    else:
        logger.info("Skipping enhanced parsing (files exist)")
    
    # Step 3: Expand solution mappings
    logger.info("\n--- STEP 3: EXPANDING SOLUTION MAPPINGS ---")
    expander = SolutionExpander("solution_compositions_enhanced")
    expander.create_expansion_report("dsmz_solution_expansion_report.json")
    
    final_df = expander.expand_mapping_data(mapping_file, output_file)
    
    # Step 4: Analysis and summary
    logger.info("\n--- STEP 4: FINAL ANALYSIS ---")
    analyze_expansion_results(mapping_file, output_file)
    
    logger.info("\n=== WORKFLOW COMPLETE ===")
    return final_df

def extract_solution_ids_from_mapping(mapping_file: str, output_file: str):
    """Extract unique solution IDs from the mapping file."""
    
    import pandas as pd
    
    df = pd.read_csv(mapping_file, sep='\t')
    solution_entries = df[df['mapped'].str.startswith('solution:', na=False)]
    
    if len(solution_entries) == 0:
        logger.warning("No solution entries found in mapping file")
        with open(output_file, 'w') as f:
            pass
        return
    
    unique_solutions = solution_entries['mapped'].unique()
    solution_ids = [sol.replace('solution:', '') for sol in unique_solutions]
    solution_ids.sort(key=int)
    
    with open(output_file, 'w') as f:
        for solution_id in solution_ids:
            f.write(f"{solution_id}\n")
    
    logger.info(f"Extracted {len(solution_ids)} unique solution IDs to {output_file}")

def analyze_expansion_results(original_file: str, expanded_file: str):
    """Analyze the results of solution expansion."""
    
    import pandas as pd
    
    # Load both datasets
    original_df = pd.read_csv(original_file, sep='\t')
    expanded_df = pd.read_csv(expanded_file, sep='\t')
    
    # Solution analysis
    original_solutions = original_df[original_df['mapped'].str.startswith('solution:', na=False)]
    expanded_solutions = expanded_df[expanded_df['source'] == 'solution_expansion']
    
    # Chemical analysis
    original_chemicals = original_df[~original_df['mapped'].str.startswith('solution:', na=False)]
    final_chemicals = expanded_df[expanded_df['source'] != 'solution_expansion']
    
    logger.info(f"EXPANSION ANALYSIS:")
    logger.info(f"  Original dataset: {len(original_df):,} entries")
    logger.info(f"    - Solution entries: {len(original_solutions):,}")
    logger.info(f"    - Chemical entries: {len(original_chemicals):,}")
    
    logger.info(f"  Expanded dataset: {len(expanded_df):,} entries")
    logger.info(f"    - Expanded solution components: {len(expanded_solutions):,}")
    logger.info(f"    - Original chemical entries: {len(final_chemicals):,}")
    
    logger.info(f"  Net change: {len(expanded_df) - len(original_df):+,} entries")
    
    # Component analysis
    if len(expanded_solutions) > 0:
        unique_expanded_solutions = expanded_solutions['medium_id'].nunique()
        avg_components_per_medium = len(expanded_solutions) / unique_expanded_solutions
        logger.info(f"  Solutions with expanded components: {unique_expanded_solutions}")
        logger.info(f"  Average components per expanded solution: {avg_components_per_medium:.1f}")
        
        # Show examples
        logger.info(f"  Example expansions:")
        solution_examples = expanded_solutions.groupby('medium_id').size().sort_values(ascending=False).head(5)
        for medium_id, count in solution_examples.items():
            original_name = expanded_solutions[expanded_solutions['medium_id'] == medium_id]['original'].iloc[0]
            logger.info(f"    {medium_id}: {original_name} → {count} components")

async def main():
    """Main entry point."""
    
    import argparse
    
    parser = argparse.ArgumentParser(description="Complete DSMZ solution expansion workflow")
    parser.add_argument("--input", required=True, help="Input mapping TSV file")
    parser.add_argument("--output", required=True, help="Output expanded mapping TSV file")
    parser.add_argument("--force-redownload", action="store_true", help="Force re-download of PDFs")
    parser.add_argument("--force-reparse", action="store_true", help="Force re-parsing of solutions")
    
    args = parser.parse_args()
    
    await complete_solution_expansion_workflow(
        args.input,
        args.output,
        args.force_redownload,
        args.force_reparse
    )

if __name__ == "__main__":
    asyncio.run(main())