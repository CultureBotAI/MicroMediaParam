#!/usr/bin/env python3
"""
JCM HTML Media Parser

Parses JCM (Japan Collection of Microorganisms) HTML files to extract
chemical compositions from structured table data.

JCM HTML files contain well-structured composition tables with:
- Chemical compound names (with HTML subscripts/superscripts)
- Concentrations (in various units: g, ml, mM, mg, etc.)
- Preparation instructions and pH information
- Cross-references to other media solutions

Author: Claude Code
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from bs4 import BeautifulSoup, NavigableString
import html


class JCMHTMLParser:
    """Parser for JCM HTML media files."""
    
    def __init__(self):
        self.setup_logging()
        self.stats = {
            "total_files": 0,
            "successful_parses": 0,
            "failed_parses": 0,
            "total_ingredients": 0,
            "media_with_solutions": 0
        }
    
    def setup_logging(self):
        """Setup logging configuration."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('jcm_html_parsing.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def clean_html_text(self, element) -> str:
        """Clean HTML text, converting subscripts/superscripts and entities."""
        if not element:
            return ""
        
        # Get all text including from child elements
        text = element.get_text(separator="", strip=True)
        
        # Handle HTML entities
        text = html.unescape(text)
        
        # Clean up multiple spaces
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def parse_concentration_and_unit(self, conc_cell, unit_cell) -> Tuple[Optional[float], Optional[str]]:
        """Parse concentration and unit from table cells."""
        try:
            # Extract concentration
            conc_text = self.clean_html_text(conc_cell)
            if not conc_text or conc_text.isspace():
                return None, None
            
            # Remove extra whitespace and extract numeric value
            conc_match = re.search(r'(\d+(?:\.\d+)?)', conc_text)
            concentration = float(conc_match.group(1)) if conc_match else None
            
            # Extract unit
            unit_text = self.clean_html_text(unit_cell) if unit_cell else None
            unit = unit_text.strip() if unit_text else None
            
            return concentration, unit
            
        except (ValueError, AttributeError) as e:
            self.logger.debug(f"Error parsing concentration/unit: {e}")
            return None, None
    
    def extract_medium_info(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Extract medium ID and name from HTML."""
        medium_info = {}
        
        # Extract medium number from search text
        search_text = soup.find(text=re.compile(r"Search for medium no\. = \[(\d+)\]"))
        if search_text:
            medium_id_match = re.search(r"\[(\d+)\]", search_text)
            if medium_id_match:
                medium_info["medium_id"] = f"jcm_{medium_id_match.group(1)}"
        
        # Extract medium name from bold font
        name_element = soup.find("font", size="3")
        if name_element:
            name_text = self.clean_html_text(name_element)
            # Remove medium number and extra spaces
            name_cleaned = re.sub(r'^\d+\s+', '', name_text)
            medium_info["medium_name"] = name_cleaned
        
        return medium_info
    
    def extract_preparation_instructions(self, soup: BeautifulSoup) -> str:
        """Extract preparation instructions from HTML."""
        instructions = []
        
        # Find text after tables but before HR or copyright
        table = soup.find("table", {"border": True})
        if table:
            # Get text after the last table
            tables = soup.find_all("table", {"border": True})
            last_table = tables[-1] if tables else table
            
            current = last_table.next_sibling
            while current and current.name != "hr":
                if isinstance(current, NavigableString):
                    text = str(current).strip()
                    if text:
                        instructions.append(text)
                elif current.name in ["br", "p"]:
                    # Continue to next
                    pass
                elif current.get_text(strip=True):
                    instructions.append(current.get_text(strip=True))
                current = current.next_sibling
        
        return " ".join(instructions)
    
    def parse_composition_table(self, table) -> List[Dict[str, any]]:
        """Parse a composition table and extract ingredients."""
        composition = []
        
        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) >= 3:  # Name, concentration, unit
                name_cell = cells[0]
                conc_cell = cells[1] 
                unit_cell = cells[2]
                
                # Extract ingredient name
                ingredient_name = self.clean_html_text(name_cell)
                if not ingredient_name or ingredient_name == "Distilled water":
                    continue
                
                # Extract concentration and unit
                concentration, unit = self.parse_concentration_and_unit(conc_cell, unit_cell)
                
                # Check for solution references
                solution_ref = None
                link = name_cell.find("a")
                if link and "jcm_grmd" in str(link.get("href", "")):
                    ref_match = re.search(r"GRMD=(\d+)", str(link.get("href", "")))
                    if ref_match:
                        solution_ref = f"jcm_{ref_match.group(1)}"
                
                ingredient_data = {
                    "name": ingredient_name,
                    "concentration": concentration,
                    "unit": unit,
                    "extraction_method": "jcm_table"
                }
                
                if solution_ref:
                    ingredient_data["solution_reference"] = solution_ref
                
                composition.append(ingredient_data)
                self.stats["total_ingredients"] += 1
        
        return composition
    
    def parse_jcm_html_file(self, html_file_path: Path) -> Optional[Dict[str, any]]:
        """Parse a single JCM HTML file."""
        try:
            self.logger.info(f"Parsing JCM HTML file: {html_file_path}")
            
            with open(html_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check if this is an empty/no-data page
            if "Nothing found" in content or "No data" in content:
                self.logger.info(f"Empty media page (no data available): {html_file_path}")
                medium_id = f"jcm_{html_file_path.stem.replace('jcm_', '')}"
                return {
                    "medium_id": medium_id,
                    "medium_name": f"JCM {medium_id.replace('jcm_', '')} (No Data)",
                    "source": "jcm",
                    "composition": [],
                    "preparation_instructions": "",
                    "no_data": True
                }
            
            soup = BeautifulSoup(content, 'html.parser')
            
            # Extract medium information
            medium_info = self.extract_medium_info(soup)
            if not medium_info.get("medium_id"):
                self.logger.warning(f"Could not extract medium ID from {html_file_path}")
                return None
            
            # Find all composition tables
            tables = soup.find_all("table", {"border": True})
            if not tables:
                self.logger.warning(f"No composition tables found in {html_file_path}")
                return None
            
            # Parse main composition table
            composition = []
            for table in tables:
                table_composition = self.parse_composition_table(table)
                composition.extend(table_composition)
            
            # Extract preparation instructions
            preparation_instructions = self.extract_preparation_instructions(soup)
            
            # Check for solution references
            has_solutions = any(ing.get("solution_reference") for ing in composition)
            if has_solutions:
                self.stats["media_with_solutions"] += 1
            
            media_data = {
                "medium_id": medium_info["medium_id"],
                "medium_name": medium_info.get("medium_name", "Unknown JCM Medium"),
                "source": "jcm",
                "composition": composition,
                "preparation_instructions": preparation_instructions
            }
            
            self.stats["successful_parses"] += 1
            self.logger.info(f"Successfully parsed {medium_info['medium_id']} with {len(composition)} ingredients")
            
            return media_data
            
        except Exception as e:
            self.stats["failed_parses"] += 1
            self.logger.error(f"Error parsing {html_file_path}: {e}")
            return None
    
    def parse_all_jcm_files(self, input_dir: str, output_dir: str) -> None:
        """Parse all JCM HTML files in a directory."""
        input_path = Path(input_dir)
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Find all JCM HTML files
        jcm_files = list(input_path.glob("jcm_*.html"))
        self.logger.info(f"Found {len(jcm_files)} JCM HTML files to process")
        
        successful_compositions = []
        
        for html_file in jcm_files:
            self.stats["total_files"] += 1
            
            composition_data = self.parse_jcm_html_file(html_file)
            if composition_data:
                # Save individual composition file
                output_file = output_path / f"{composition_data['medium_id']}_composition.json"
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(composition_data, f, indent=2, ensure_ascii=False)
                
                successful_compositions.append(composition_data)
        
        # Create summary report
        self.create_summary_report(output_path, successful_compositions)
        
        self.logger.info(f"JCM HTML parsing completed:")
        self.logger.info(f"  Total files: {self.stats['total_files']}")
        self.logger.info(f"  Successful: {self.stats['successful_parses']}")
        self.logger.info(f"  Failed: {self.stats['failed_parses']}")
        self.logger.info(f"  Total ingredients: {self.stats['total_ingredients']}")
        self.logger.info(f"  Media with solution refs: {self.stats['media_with_solutions']}")
    
    def create_summary_report(self, output_path: Path, compositions: List[Dict]) -> None:
        """Create a summary report of the parsing results."""
        summary = {
            "parsing_statistics": self.stats,
            "total_media_parsed": len(compositions),
            "media_by_ingredient_count": {},
            "most_common_ingredients": {},
            "media_with_solutions": []
        }
        
        # Analyze ingredient counts
        ingredient_counts = {}
        for media in compositions:
            ingredient_count = len(media["composition"])
            summary["media_by_ingredient_count"][str(ingredient_count)] = \
                summary["media_by_ingredient_count"].get(str(ingredient_count), 0) + 1
            
            # Count ingredient occurrences
            for ingredient in media["composition"]:
                name = ingredient["name"]
                ingredient_counts[name] = ingredient_counts.get(name, 0) + 1
                
            # Track media with solution references
            if any(ing.get("solution_reference") for ing in media["composition"]):
                summary["media_with_solutions"].append(media["medium_id"])
        
        # Top 20 most common ingredients
        sorted_ingredients = sorted(ingredient_counts.items(), key=lambda x: x[1], reverse=True)
        summary["most_common_ingredients"] = dict(sorted_ingredients[:20])
        
        # Save summary
        summary_file = output_path / "jcm_parsing_summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Summary report saved to {summary_file}")


def main():
    """Main function to run JCM HTML parsing."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Parse JCM HTML media files")
    parser.add_argument("--input-dir", default="media_pdfs", 
                       help="Directory containing JCM HTML files")
    parser.add_argument("--output-dir", default="media_compositions", 
                       help="Directory to save composition JSON files")
    
    args = parser.parse_args()
    
    jcm_parser = JCMHTMLParser()
    jcm_parser.parse_all_jcm_files(args.input_dir, args.output_dir)


if __name__ == "__main__":
    main()