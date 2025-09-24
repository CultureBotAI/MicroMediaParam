#!/usr/bin/env python3
"""
Download DSMZ solution PDFs and extract their chemical compositions.
"""

import asyncio
import aiohttp
import aiofiles
import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional
import markitdown

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DSMZSolutionDownloader:
    def __init__(self):
        self.base_url = "https://mediadive.dsmz.de/rest/solution"
        self.pdf_dir = Path("solution_pdfs")
        self.text_dir = Path("solution_texts")
        self.composition_dir = Path("solution_compositions")
        self.markitdown = markitdown.MarkItDown()
        
        # Create directories
        for dir_path in [self.pdf_dir, self.text_dir, self.composition_dir]:
            dir_path.mkdir(exist_ok=True)
    
    async def download_solution_pdf(self, session: aiohttp.ClientSession, solution_id: str) -> Optional[Path]:
        """Download a single solution PDF from DSMZ."""
        
        pdf_url = f"{self.base_url}/{solution_id}/pdf"
        pdf_path = self.pdf_dir / f"solution_{solution_id}.pdf"
        
        if pdf_path.exists():
            logger.info(f"Solution {solution_id}: PDF already exists")
            return pdf_path
        
        try:
            logger.info(f"Downloading solution {solution_id} PDF...")
            async with session.get(pdf_url) as response:
                if response.status == 200:
                    content = await response.read()
                    async with aiofiles.open(pdf_path, 'wb') as f:
                        await f.write(content)
                    logger.info(f"✓ Downloaded solution {solution_id} PDF ({len(content)} bytes)")
                    return pdf_path
                else:
                    logger.warning(f"✗ Solution {solution_id}: HTTP {response.status}")
                    return None
                    
        except Exception as e:
            logger.error(f"✗ Solution {solution_id}: {e}")
            return None
    
    def convert_pdf_to_text(self, pdf_path: Path) -> Optional[Path]:
        """Convert solution PDF to markdown text."""
        
        solution_id = pdf_path.stem.replace('solution_', '')
        text_path = self.text_dir / f"solution_{solution_id}.md"
        
        if text_path.exists():
            logger.info(f"Solution {solution_id}: Text already exists")
            return text_path
        
        try:
            logger.info(f"Converting solution {solution_id} PDF to text...")
            result = self.markitdown.convert(str(pdf_path))
            
            with open(text_path, 'w', encoding='utf-8') as f:
                f.write(result.text_content)
            
            logger.info(f"✓ Converted solution {solution_id} to text")
            return text_path
            
        except Exception as e:
            logger.error(f"✗ Solution {solution_id} conversion failed: {e}")
            return None
    
    def extract_composition(self, text_path: Path) -> Optional[Dict]:
        """Extract chemical composition from solution text."""
        
        solution_id = text_path.stem.replace('solution_', '')
        
        try:
            with open(text_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            composition_data = {
                'solution_id': solution_id,
                'solution_name': self.extract_solution_name(content),
                'composition': self.parse_chemical_components(content),
                'source': 'dsmz_solution_pdf',
                'url': f"{self.base_url}/{solution_id}/pdf"
            }
            
            composition_path = self.composition_dir / f"solution_{solution_id}_composition.json"
            with open(composition_path, 'w') as f:
                json.dump(composition_data, f, indent=2)
            
            logger.info(f"✓ Extracted composition for solution {solution_id}: {len(composition_data['composition'])} components")
            return composition_data
            
        except Exception as e:
            logger.error(f"✗ Solution {solution_id} composition extraction failed: {e}")
            return None
    
    def extract_solution_name(self, content: str) -> str:
        """Extract solution name from text content."""
        
        # Look for solution name patterns
        name_patterns = [
            r'# (.+?solution)\n',
            r'## (.+?solution)\n',
            r'\*\*(.+?solution)\*\*',
            r'Solution:?\s*(.+?)\n',
            r'Name:?\s*(.+?)\n'
        ]
        
        for pattern in name_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                if len(name) > 5:  # Reasonable name length
                    return name
        
        return "Unknown Solution"
    
    def parse_chemical_components(self, content: str) -> List[Dict]:
        """Parse chemical components from solution text."""
        
        components = []
        
        # Common patterns for chemical composition tables
        composition_patterns = [
            # Table format with concentration and units
            r'(\w+(?:\s+\w+)*)\s+([0-9.,]+)\s*(g|mg|μg|ml|l|%|M|mM|µM)\s*/?\s*(l|L)?',
            # Bullet point format
            r'[•\-\*]\s*([A-Za-z0-9\-\s,()]+)\s+([0-9.,]+)\s*(g|mg|μg|ml|l|%|M|mM|µM)',
            # Simple colon format
            r'([A-Za-z0-9\-\s,()]+):\s+([0-9.,]+)\s*(g|mg|μg|ml|l|%|M|mM|µM)'
        ]
        
        for pattern in composition_patterns:
            matches = re.finditer(pattern, content, re.MULTILINE | re.IGNORECASE)
            
            for match in matches:
                component_name = match.group(1).strip()
                concentration = match.group(2).strip()
                unit = match.group(3).strip()
                
                # Clean up component name
                component_name = re.sub(r'[^\w\s\-().,]', '', component_name)
                component_name = component_name.strip()
                
                # Skip if too short or contains unwanted patterns
                if (len(component_name) < 3 or 
                    any(word in component_name.lower() for word in ['table', 'page', 'solution', 'medium', 'per', 'total'])):
                    continue
                
                # Parse concentration
                try:
                    conc_value = float(concentration.replace(',', '.'))
                except ValueError:
                    conc_value = 0.0
                
                components.append({
                    'name': component_name,
                    'concentration': conc_value,
                    'unit': unit,
                    'original_text': match.group(0)
                })
        
        # Deduplicate components
        seen_components = {}
        unique_components = []
        
        for comp in components:
            key = comp['name'].lower()
            if key not in seen_components:
                seen_components[key] = True
                unique_components.append(comp)
        
        return unique_components
    
    async def download_all_solutions(self, solution_ids: List[str]) -> Dict[str, Dict]:
        """Download and process all solution PDFs."""
        
        results = {}
        
        async with aiohttp.ClientSession() as session:
            # Download PDFs
            download_tasks = [
                self.download_solution_pdf(session, solution_id) 
                for solution_id in solution_ids
            ]
            
            pdf_paths = await asyncio.gather(*download_tasks, return_exceptions=True)
            
            # Process successful downloads
            for solution_id, pdf_path in zip(solution_ids, pdf_paths):
                if isinstance(pdf_path, Path) and pdf_path.exists():
                    # Convert to text
                    text_path = self.convert_pdf_to_text(pdf_path)
                    
                    if text_path:
                        # Extract composition
                        composition = self.extract_composition(text_path)
                        if composition:
                            results[solution_id] = composition
                
        return results

async def main():
    """Main function to download and process DSMZ solutions."""
    
    # Load solution IDs from file
    solution_ids_file = Path("solution_ids_to_process.txt")
    
    if not solution_ids_file.exists():
        logger.error("solution_ids_to_process.txt not found. Please create it with solution IDs.")
        return
    
    with open(solution_ids_file, 'r') as f:
        solution_ids = [line.strip() for line in f if line.strip()]
    
    logger.info(f"Processing {len(solution_ids)} DSMZ solutions...")
    
    downloader = DSMZSolutionDownloader()
    results = await downloader.download_all_solutions(solution_ids)
    
    # Summary
    logger.info(f"\n=== PROCESSING SUMMARY ===")
    logger.info(f"Total solutions requested: {len(solution_ids)}")
    logger.info(f"Successfully processed: {len(results)}")
    logger.info(f"Failed: {len(solution_ids) - len(results)}")
    
    # Show composition statistics
    total_components = sum(len(result['composition']) for result in results.values())
    logger.info(f"Total chemical components extracted: {total_components}")
    
    if results:
        avg_components = total_components / len(results)
        logger.info(f"Average components per solution: {avg_components:.1f}")
        
        # Show examples
        logger.info(f"\nExample solutions processed:")
        for solution_id, data in list(results.items())[:5]:
            logger.info(f"  Solution {solution_id}: {data['solution_name']} ({len(data['composition'])} components)")

if __name__ == "__main__":
    asyncio.run(main())