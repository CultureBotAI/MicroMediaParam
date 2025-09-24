#!/usr/bin/env python3
"""
Run improved extraction on all files to replace the noisy extractions.
"""

import json
import logging
from pathlib import Path
from improved_composition_extractor import ImprovedCompositionExtractor

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_improved_extraction():
    """Run improved extraction on all files."""
    extractor = ImprovedCompositionExtractor()
    
    # Directories
    media_texts_dir = Path("media_texts")
    media_pdfs_dir = Path("media_pdfs")
    output_dir = Path("media_compositions_improved")
    output_dir.mkdir(exist_ok=True)
    
    extracted_count = 0
    failed_count = 0
    quality_stats = {'high': 0, 'medium': 0, 'low': 0}
    
    # Process markdown files
    logger.info(f"Processing markdown files from {media_texts_dir}")
    if media_texts_dir.exists():
        markdown_files = list(media_texts_dir.glob("*.md"))
        logger.info(f"Found {len(markdown_files)} markdown files")
        
        for i, md_file in enumerate(markdown_files):
            if i % 100 == 0:
                logger.info(f"Processed {i}/{len(markdown_files)} files...")
            
            composition = extractor.extract_from_markdown_improved(md_file)
            if composition and composition.get('composition'):
                # Assess quality
                num_compounds = len(composition['composition'])
                if num_compounds >= 5:
                    quality = 'high'
                elif num_compounds >= 2:
                    quality = 'medium'
                else:
                    quality = 'low'
                
                quality_stats[quality] += 1
                
                # Save as JSON
                output_file = output_dir / f"{composition['medium_id']}_composition.json"
                with open(output_file, 'w') as f:
                    json.dump(composition, f, indent=2)
                extracted_count += 1
            else:
                failed_count += 1
    
    # Process HTML files
    logger.info(f"Processing HTML files from {media_pdfs_dir}")
    if media_pdfs_dir.exists():
        html_files = list(media_pdfs_dir.glob("*.html"))
        logger.info(f"Found {len(html_files)} HTML files")
        
        for i, html_file in enumerate(html_files):
            if i % 50 == 0:
                logger.info(f"Processed {i}/{len(html_files)} HTML files...")
            
            composition = extractor.extract_from_html(html_file)
            if composition and composition.get('composition'):
                # Assess quality
                num_compounds = len(composition['composition'])
                if num_compounds >= 5:
                    quality = 'high'
                elif num_compounds >= 2:
                    quality = 'medium'
                else:
                    quality = 'low'
                
                quality_stats[quality] += 1
                
                # Save as JSON
                output_file = output_dir / f"{composition['medium_id']}_composition.json"
                with open(output_file, 'w') as f:
                    json.dump(composition, f, indent=2)
                extracted_count += 1
            else:
                failed_count += 1
    
    logger.info(f"Improved extraction complete!")
    logger.info(f"Successfully extracted {extracted_count} compositions, {failed_count} failed")
    logger.info(f"Quality distribution: High={quality_stats['high']}, Medium={quality_stats['medium']}, Low={quality_stats['low']}")
    
    # Calculate success rate improvement
    total_files = len(list(media_texts_dir.glob("*.md"))) + len(list(media_pdfs_dir.glob("*.html")))
    success_rate = (extracted_count / total_files) * 100 if total_files > 0 else 0
    
    logger.info(f"Overall success rate: {success_rate:.1f}% ({extracted_count}/{total_files})")
    
    # Create summary
    summary = {
        'total_extracted': extracted_count,
        'total_failed': failed_count,
        'total_files_processed': total_files,
        'success_rate_percent': success_rate,
        'quality_distribution': quality_stats,
        'high_quality_files': quality_stats['high'],
        'extraction_method': 'improved_format_specific_parser'
    }
    
    with open(output_dir / "improved_extraction_summary.json", 'w') as f:
        json.dump(summary, f, indent=2)
    
    return extracted_count, quality_stats

if __name__ == "__main__":
    run_improved_extraction()