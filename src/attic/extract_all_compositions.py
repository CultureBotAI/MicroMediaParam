#!/usr/bin/env python3
"""
Extract ALL compositions using the comprehensive ingredient extractor.
This replaces the original extraction to ensure complete ingredient capture.
"""

import json
import logging
from pathlib import Path
from enhanced_media_extractor import EnhancedMediaExtractor

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def extract_all_compositions():
    """Extract compositions with enhanced ingredient and instruction capture."""
    extractor = EnhancedMediaExtractor()
    
    # Directories
    media_texts_dir = Path("media_texts")
    output_dir = Path("media_compositions")
    output_dir.mkdir(exist_ok=True)
    
    extracted_count = 0
    failed_count = 0
    total_ingredients = 0
    
    # Process markdown files
    logger.info(f"Processing markdown files from {media_texts_dir}")
    if media_texts_dir.exists():
        markdown_files = list(media_texts_dir.glob("*.md"))
        logger.info(f"Found {len(markdown_files)} markdown files")
        
        for i, md_file in enumerate(markdown_files):
            if i % 100 == 0:
                logger.info(f"Processed {i}/{len(markdown_files)} files...")
            
            composition = extractor.extract_media_data(md_file)
            if composition and (composition.get('composition') or composition.get('preparation_instructions')):
                num_ingredients = len(composition.get('composition', []))
                total_ingredients += num_ingredients
                
                # Save as JSON with both ingredients and instructions
                output_data = {
                    'medium_id': composition['medium_id'],
                    'medium_name': composition['medium_name'],
                    'source': composition['source'],
                    'composition': composition.get('composition', []),
                    'preparation_instructions': composition.get('preparation_instructions', '')
                }
                
                output_file = output_dir / f"{composition['medium_id']}_composition.json"
                with open(output_file, 'w') as f:
                    json.dump(output_data, f, indent=2)
                extracted_count += 1
            else:
                failed_count += 1
    
    logger.info(f"Comprehensive extraction complete!")
    logger.info(f"Successfully extracted {extracted_count} compositions, {failed_count} failed")
    logger.info(f"Total ingredients captured: {total_ingredients}")
    logger.info(f"Average ingredients per composition: {total_ingredients/extracted_count:.1f}" if extracted_count > 0 else "No successful extractions")
    
    # Calculate success rate
    total_files = len(list(media_texts_dir.glob("*.md"))) if media_texts_dir.exists() else 0
    success_rate = (extracted_count / total_files) * 100 if total_files > 0 else 0
    
    logger.info(f"Overall success rate: {success_rate:.1f}% ({extracted_count}/{total_files})")
    
    # Create summary
    summary = {
        'total_extracted': extracted_count,
        'total_failed': failed_count,
        'total_files_processed': total_files,
        'success_rate_percent': success_rate,
        'total_ingredients': total_ingredients,
        'avg_ingredients_per_composition': total_ingredients / extracted_count if extracted_count > 0 else 0,
        'extraction_method': 'enhanced_clean_separation'
    }
    
    with open(output_dir / "comprehensive_extraction_summary.json", 'w') as f:
        json.dump(summary, f, indent=2)
    
    return extracted_count

if __name__ == "__main__":
    extract_all_compositions()