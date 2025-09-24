#!/usr/bin/env python3
"""
Extract chemical compositions from downloaded PDF text files and HTML files.
Creates JSON composition files that can be processed by the KG mapping pipeline.
"""

import json
import logging
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from bs4 import BeautifulSoup

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class CompositionExtractor:
    """Extract chemical compositions from various media file formats."""
    
    def __init__(self):
        self.unit_patterns = {
            'g/L': r'(\d+(?:\.\d+)?)\s*g(?:/L|/l|/litre|/liter|\s+per\s+(?:L|l|litre|liter))',
            'mg/L': r'(\d+(?:\.\d+)?)\s*mg(?:/L|/l|/litre|/liter|\s+per\s+(?:L|l|litre|liter))',
            'ml/L': r'(\d+(?:\.\d+)?)\s*ml(?:/L|/l|/litre|/liter|\s+per\s+(?:L|l|litre|liter))',
            'mM': r'(\d+(?:\.\d+)?)\s*mM',
            'μM': r'(\d+(?:\.\d+)?)\s*[μu]M',
        }
        
        # Common chemical compound patterns
        self.compound_patterns = [
            # Basic salts and common compounds
            r'([A-Z][a-z]*(?:[A-Z][a-z]*)*(?:\([A-Z][a-z]*\)\d*)*(?:\.\d*H2O)?)',
            # Chemical names with spaces
            r'([A-Z][a-z]+(?:\s+[a-z]+)*)',
            # Specific patterns for common compounds
            r'(sodium chloride|potassium chloride|magnesium sulfate|calcium chloride)',
            r'(yeast extract|beef extract|peptone|tryptone)',
            r'(glucose|sucrose|lactose|fructose)',
        ]
    
    def extract_from_markdown(self, file_path: Path) -> Optional[Dict]:
        """Extract composition from markdown files (DSMZ, CCAP formats)."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract medium name from filename or content
            medium_name = self._extract_medium_name(file_path, content)
            
            # Parse different markdown formats
            compositions = []
            
            # DSMZ format - simple table with compound, amount, unit
            if 'dsmz' in str(file_path).lower():
                compositions = self._parse_dsmz_format(content)
            
            # CCAP format - more complex with stocks and final concentrations  
            elif 'ccap' in str(file_path).lower():
                compositions = self._parse_ccap_format(content)
            
            # Generic format parsing
            else:
                compositions = self._parse_generic_format(content)
            
            if compositions:
                return {
                    'medium_id': self._get_medium_id(file_path),
                    'medium_name': medium_name,
                    'source': self._get_source(file_path),
                    'composition': compositions
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")
            return None
    
    def extract_from_html(self, file_path: Path) -> Optional[Dict]:
        """Extract composition from HTML files (Cyanosite format)."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            soup = BeautifulSoup(content, 'html.parser')
            
            # Extract medium name from title or headers
            medium_name = self._extract_html_medium_name(soup)
            
            # Parse HTML tables for composition data
            compositions = self._parse_html_tables(soup)
            
            if compositions:
                return {
                    'medium_id': self._get_medium_id(file_path),
                    'medium_name': medium_name,
                    'source': self._get_source(file_path),
                    'composition': compositions
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")
            return None
    
    def _extract_medium_name(self, file_path: Path, content: str) -> str:
        """Extract medium name from file content or filename."""
        # Try to find medium name in content
        name_patterns = [
            r'^(.+?)\s*(?:Medium|MEDIUM)',
            r'(?:Medium|MEDIUM)\s*[:\-]?\s*(.+?)(?:\n|$)',
            r'^([A-Z][A-Z0-9]+(?:\s+[A-Z0-9]+)*)',
        ]
        
        for pattern in name_patterns:
            match = re.search(pattern, content, re.MULTILINE)
            if match:
                return match.group(1).strip()
        
        # Fallback to filename
        return file_path.stem.replace('_', ' ').title()
    
    def _extract_html_medium_name(self, soup: BeautifulSoup) -> str:
        """Extract medium name from HTML content."""
        # Try title tag
        title = soup.find('title')
        if title:
            return title.get_text().strip()
        
        # Try headers
        for header in soup.find_all(['h1', 'h2', 'h3']):
            text = header.get_text().strip()
            if 'medium' in text.lower():
                return text
        
        return "Unknown Medium"
    
    def _parse_dsmz_format(self, content: str) -> List[Dict]:
        """Parse DSMZ format markdown files."""
        compositions = []
        lines = content.split('\n')
        
        # Look for patterns like "Peptone 5.0 g"
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('©'):
                continue
            
            # Pattern: compound name followed by amount and unit
            match = re.search(r'^([A-Za-z][A-Za-z\s,\.\(\)]+?)\s+(\d+(?:\.\d+)?)\s*([a-zA-Z/]+)', line)
            if match:
                compound = match.group(1).strip()
                amount = float(match.group(2))
                unit = match.group(3).strip()
                
                compositions.append({
                    'name': compound,
                    'concentration': amount,
                    'unit': unit
                })
        
        return compositions
    
    def _parse_ccap_format(self, content: str) -> List[Dict]:
        """Parse CCAP format markdown files."""
        compositions = []
        
        # CCAP files have complex stock solutions - extract final concentrations
        # Look for patterns in final medium section
        medium_section = False
        for line in content.split('\n'):
            line = line.strip()
            
            if 'Medium' in line or 'per litre' in line:
                medium_section = True
                continue
            
            if medium_section and line:
                # Extract compound and concentration
                # Pattern: "compound amount unit"
                for compound_pattern in self.compound_patterns:
                    compound_match = re.search(compound_pattern, line, re.IGNORECASE)
                    if compound_match:
                        compound = compound_match.group(1)
                        
                        # Look for amount and unit
                        amount_match = re.search(r'(\d+(?:\.\d+)?)\s*([a-zA-Z/]+)', line)
                        if amount_match:
                            amount = float(amount_match.group(1))
                            unit = amount_match.group(2)
                            
                            compositions.append({
                                'name': compound,
                                'concentration': amount,
                                'unit': unit
                            })
                            break
        
        return compositions
    
    def _parse_generic_format(self, content: str) -> List[Dict]:
        """Parse generic format files."""
        compositions = []
        
        for line in content.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            # Look for compound name with amount and unit
            for unit_pattern in self.unit_patterns.values():
                amount_match = re.search(unit_pattern, line)
                if amount_match:
                    amount = float(amount_match.group(1))
                    
                    # Extract compound name (everything before the amount)
                    compound_part = line[:amount_match.start()].strip()
                    
                    for compound_pattern in self.compound_patterns:
                        compound_match = re.search(compound_pattern, compound_part)
                        if compound_match:
                            compound = compound_match.group(1).strip()
                            
                            # Determine unit from pattern
                            unit = 'g/L'  # Default
                            if 'mg' in line.lower():
                                unit = 'mg/L'
                            elif 'ml' in line.lower():
                                unit = 'ml/L'
                            elif 'mM' in line:
                                unit = 'mM'
                            elif 'μM' in line or 'uM' in line:
                                unit = 'μM'
                            
                            compositions.append({
                                'name': compound,
                                'concentration': amount,
                                'unit': unit
                            })
                            break
                    break
        
        return compositions
    
    def _parse_html_tables(self, soup: BeautifulSoup) -> List[Dict]:
        """Parse HTML tables for composition data."""
        compositions = []
        
        for table in soup.find_all('table'):
            for row in table.find_all('tr'):
                cells = row.find_all('td')
                if len(cells) >= 2:
                    compound = cells[0].get_text().strip()
                    amount_text = cells[1].get_text().strip()
                    
                    # Extract amount and unit
                    amount_match = re.search(r'(\d+(?:\.\d+)?)\s*([a-zA-Z/]+)', amount_text)
                    if amount_match and compound:
                        amount = float(amount_match.group(1))
                        unit = amount_match.group(2)
                        
                        compositions.append({
                            'name': compound,
                            'concentration': amount,
                            'unit': unit
                        })
        
        return compositions
    
    def _get_medium_id(self, file_path: Path) -> str:
        """Generate medium ID from filename."""
        return file_path.stem
    
    def _get_source(self, file_path: Path) -> str:
        """Determine source from filename."""
        filename = str(file_path).lower()
        if 'dsmz' in filename:
            return 'dsmz'
        elif 'ccap' in filename:
            return 'ccap'
        elif 'atcc' in filename:
            return 'atcc'
        elif 'jcm' in filename:
            return 'jcm'
        elif 'cyanosite' in filename:
            return 'cyanosite'
        else:
            return 'unknown'


def main():
    """Extract compositions from all downloaded files."""
    extractor = CompositionExtractor()
    
    # Directories
    media_texts_dir = Path("media_texts")
    media_pdfs_dir = Path("media_pdfs")
    output_dir = Path("media_compositions")
    output_dir.mkdir(exist_ok=True)
    
    extracted_count = 0
    failed_count = 0
    
    # Process markdown files
    logger.info(f"Processing markdown files from {media_texts_dir}")
    if media_texts_dir.exists():
        for md_file in media_texts_dir.glob("*.md"):
            composition = extractor.extract_from_markdown(md_file)
            if composition:
                # Save as JSON
                output_file = output_dir / f"{composition['medium_id']}_composition.json"
                with open(output_file, 'w') as f:
                    json.dump(composition, f, indent=2)
                extracted_count += 1
                if extracted_count % 100 == 0:
                    logger.info(f"Extracted {extracted_count} compositions so far...")
            else:
                failed_count += 1
    
    # Process HTML files
    logger.info(f"Processing HTML files from {media_pdfs_dir}")
    if media_pdfs_dir.exists():
        for html_file in media_pdfs_dir.glob("*.html"):
            composition = extractor.extract_from_html(html_file)
            if composition:
                # Save as JSON
                output_file = output_dir / f"{composition['medium_id']}_composition.json"
                with open(output_file, 'w') as f:
                    json.dump(composition, f, indent=2)
                extracted_count += 1
                if extracted_count % 100 == 0:
                    logger.info(f"Extracted {extracted_count} compositions so far...")
            else:
                failed_count += 1
    
    logger.info(f"Extraction complete. Successfully extracted {extracted_count} compositions, {failed_count} failed")
    
    # Create summary
    summary = {
        'total_extracted': extracted_count,
        'total_failed': failed_count,
        'sources_processed': {
            'markdown_files': len(list(media_texts_dir.glob("*.md"))) if media_texts_dir.exists() else 0,
            'html_files': len(list(media_pdfs_dir.glob("*.html"))) if media_pdfs_dir.exists() else 0
        }
    }
    
    with open(output_dir / "extraction_summary.json", 'w') as f:
        json.dump(summary, f, indent=2)
    
    return extracted_count


if __name__ == "__main__":
    sys.exit(0 if main() > 0 else 1)