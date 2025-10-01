#!/usr/bin/env python3
"""
Enhanced Comprehensive Media Composition Extractor

Extracts chemical compositions from all media file formats:
- DSMZ JSON files (BacDive/MediaDive structured data)
- JCM HTML files (structured tables)  
- PDF files (converted to text via MarkItDown)
- Other format files

This replaces extract_all_compositions.py with JCM HTML parsing capability.

Author: Claude Code
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set
import sys
import re
from markitdown import MarkItDown
from bs4 import BeautifulSoup

# Add current directory to path for JCM parser import
sys.path.append(str(Path(__file__).parent))

from parse_jcm_html import JCMHTMLParser


class EnhancedCompositionExtractor:
    """Enhanced extractor that handles all media file formats including JCM HTML."""
    
    def __init__(self):
        self.setup_logging()
        self.stats = {
            "total_files": 0,
            "dsmz_json_files": 0,
            "dsmz_pdf_files": 0,
            "jcm_html_files": 0,
            "ccap_pdf_files": 0,
            "atcc_pdf_files": 0,
            "cyanosite_html_files": 0,
            "other_files": 0,
            "successful_extractions": 0,
            "failed_extractions": 0,
            "total_ingredients": 0
        }
        
        # Initialize specialized parsers
        self.jcm_parser = JCMHTMLParser()
        self.markitdown = MarkItDown()
        
    def setup_logging(self):
        """Setup logging configuration."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('enhanced_composition_extraction.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def identify_media_file_type(self, file_path: Path) -> str:
        """Identify the type of media file."""
        filename = file_path.stem.lower()
        suffix = file_path.suffix.lower()
        
        if suffix == '.json':
            return 'dsmz_json'
        elif suffix == '.html' and filename.startswith('jcm_'):
            return 'jcm_html'
        elif suffix == '.html' and filename.startswith('cyanosite_'):
            return 'cyanosite_html'
        elif suffix == '.pdf' and filename.startswith('dsmz_'):
            return 'dsmz_pdf'
        elif suffix == '.pdf' and filename.startswith('ccap_'):
            return 'ccap_pdf'
        elif suffix == '.pdf' and filename.startswith('atcc_'):
            return 'atcc_pdf'
        elif suffix == '.pdf':
            return 'other_pdf'
        else:
            return 'other'
    
    def extract_from_dsmz_json(self, json_file: Path) -> Optional[Dict]:
        """Extract composition from DSMZ JSON file."""
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Extract medium ID from filename
            medium_id = json_file.stem.replace('_composition', '')
            
            # Handle BacDive/MediaDive JSON structure
            if isinstance(data, dict):
                composition = data.get('composition', [])
                medium_name = data.get('medium_name', f"DSMZ {medium_id}")
            elif isinstance(data, list):
                composition = data
                medium_name = f"DSMZ {medium_id}"
            else:
                self.logger.warning(f"Unknown JSON structure in {json_file}")
                return None
            
            media_data = {
                "medium_id": medium_id,
                "medium_name": medium_name,
                "source": "dsmz",
                "composition": composition,
                "preparation_instructions": data.get('preparation_instructions', '') if isinstance(data, dict) else ''
            }
            
            self.stats["total_ingredients"] += len(composition)
            return media_data
            
        except Exception as e:
            self.logger.error(f"Error extracting from DSMZ JSON {json_file}: {e}")
            return None
    
    def extract_from_pdf(self, pdf_file: Path) -> Optional[Dict]:
        """Extract composition from PDF file using MarkItDown."""
        try:
            self.logger.info(f"Converting PDF to text: {pdf_file.name}")
            
            # Convert PDF to text using MarkItDown
            result = self.markitdown.convert(str(pdf_file))
            
            if not result or not result.text_content:
                self.logger.warning(f"No text content extracted from {pdf_file.name}")
                return None
            
            # Extract medium ID and source from filename
            medium_id = pdf_file.stem
            source = self.get_source_from_filename(pdf_file)
            
            # Parse composition from text content
            composition = self.parse_composition_from_text(result.text_content)
            
            if not composition:
                self.logger.warning(f"No composition found in {pdf_file.name}")
                return None
            
            media_data = {
                "medium_id": medium_id,
                "medium_name": self.extract_medium_name_from_text(result.text_content, medium_id),
                "source": source,
                "composition": composition,
                "preparation_instructions": self.extract_preparation_instructions(result.text_content),
                "extraction_method": "pdf_text_parsing"
            }
            
            self.stats["total_ingredients"] += len(composition)
            return media_data
            
        except Exception as e:
            self.logger.error(f"Error extracting from PDF {pdf_file}: {e}")
            return None
    
    def extract_from_cyanosite_html(self, html_file: Path) -> Optional[Dict]:
        """Extract composition from Cyanosite HTML file."""
        try:
            with open(html_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            soup = BeautifulSoup(content, 'html.parser')
            medium_id = html_file.stem
            
            # Parse Cyanosite HTML structure (simpler than JCM)
            composition = self.parse_cyanosite_composition(soup)
            
            if not composition:
                self.logger.warning(f"No composition found in Cyanosite HTML {html_file.name}")
                return None
            
            media_data = {
                "medium_id": medium_id,
                "medium_name": self.extract_cyanosite_medium_name(soup, medium_id),
                "source": "cyanosite",
                "composition": composition,
                "preparation_instructions": "",
                "extraction_method": "cyanosite_html_parsing"
            }
            
            self.stats["total_ingredients"] += len(composition)
            return media_data
            
        except Exception as e:
            self.logger.error(f"Error extracting from Cyanosite HTML {html_file}: {e}")
            return None
    
    def extract_from_other_file(self, file_path: Path) -> Optional[Dict]:
        """Extract composition from other file types (placeholder)."""
        self.logger.info(f"Other file type extraction not implemented for {file_path}")
        return None
    
    def get_source_from_filename(self, file_path: Path) -> str:
        """Extract source from filename."""
        filename = file_path.stem.lower()
        if filename.startswith('dsmz_'):
            return 'dsmz'
        elif filename.startswith('ccap_'):
            return 'ccap'
        elif filename.startswith('atcc_'):
            return 'atcc'
        elif filename.startswith('jcm_'):
            return 'jcm'
        elif filename.startswith('cyanosite_'):
            return 'cyanosite'
        else:
            return 'unknown'
    
    def parse_composition_from_text(self, text_content: str) -> List[Dict]:
        """Parse chemical composition from PDF text content."""
        composition = []
        
        # Try different parsing strategies in order
        
        # 1. Standard tabular format (ingredients, then amounts, then units)
        tabular_composition = self.parse_tabular_format(text_content)
        if tabular_composition:
            composition.extend(tabular_composition)
        
        # 2. Reverse tabular format (amounts first, then ingredients)
        if not composition:
            reverse_composition = self.parse_reverse_tabular_format(text_content)
            if reverse_composition:
                composition.extend(reverse_composition)
        
        # 3. Multi-solution format (complex nested solutions)
        if not composition:
            multi_solution = self.parse_multi_solution_format(text_content)
            if multi_solution:
                composition.extend(multi_solution)
        
        # 4. Reference medium format (refers to another medium)
        if not composition:
            reference_composition = self.parse_reference_medium(text_content)
            if reference_composition:
                composition.extend(reference_composition)
        
        # 5. ATCC dotted line format (ingredient...amount+unit)
        if not composition:
            dotted_composition = self.parse_dotted_line_format(text_content)
            if dotted_composition:
                composition.extend(dotted_composition)
        
        # 6. Columnar format (ingredient amount unit on same line)
        if not composition:
            columnar_composition = self.parse_columnar_format(text_content)
            if columnar_composition:
                composition.extend(columnar_composition)
        
        # 7. Parenthetical amount format (ingredient (amount unit))
        if not composition:
            parenthetical_composition = self.parse_parenthetical_format(text_content)
            if parenthetical_composition:
                composition.extend(parenthetical_composition)
        
        # 8. Three-column separated layout (DSMZ format)
        if not composition:
            three_column = self.parse_three_column_layout(text_content)
            if three_column:
                composition.extend(three_column)
        
        # 9. Simple list format (CCAP SNA format)
        if not composition:
            simple_list = self.parse_simple_list_format(text_content)
            if simple_list:
                composition.extend(simple_list)
        
        # 10. Enhanced prose format (narrative text)
        if not composition:
            prose_format = self.parse_enhanced_prose_format(text_content)
            if prose_format:
                composition.extend(prose_format)
        
        # 11. Common patterns for chemical composition in scientific texts
        if not composition:
            patterns = [
                # Pattern 1: Chemical name followed by concentration and unit
                r'([A-Z][a-zA-Z0-9·\-\(\)]+(?:\s+[a-zA-Z0-9·\-\(\)]+)*)\s+([0-9]+(?:\.[0-9]+)?)\s*(g/L|g|mg/L|mg|mM|μM|M)\b',
                # Pattern 2: Table-like format in one line
                r'([A-Z][a-zA-Z0-9·\-\(\)]+(?:\s+[a-zA-Z0-9·\-\(\)]+)*)\s+([0-9]+(?:\.[0-9]+)?)\s+(g/L|g|mg/L|mg|mM|μM|M)',
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, text_content, re.MULTILINE | re.IGNORECASE)
                for match in matches:
                    if len(match) >= 2:
                        name = match[0].strip()
                        concentration = float(match[1])
                        unit = match[2] if len(match) > 2 else 'g/L'
                        
                        # Filter out obvious non-chemical names and avoid duplicates
                        if self.is_likely_chemical_name(name) and not any(c['name'] == name for c in composition):
                            composition.append({
                                "name": name,
                                "concentration": concentration,
                                "unit": unit,
                                "extraction_method": "pdf_text_pattern_matching"
                            })
        
        return composition[:50]  # Limit to avoid false positives
    
    def parse_tabular_format(self, text_content: str) -> List[Dict]:
        """Parse tabular format where ingredients, amounts, and units are in separate lines/columns."""
        composition = []
        lines = [line.strip() for line in text_content.split('\n') if line.strip()]
        
        # Find ingredient section - look for consecutive ingredient lines
        ingredient_start = -1
        ingredient_end = -1
        
        for i, line in enumerate(lines):
            # Skip title lines and empty lines
            if not line or line.lower().endswith('medium') or line.startswith('©') or 'adjust' in line.lower():
                continue
                
            # Check if this line looks like an ingredient
            if self.is_likely_chemical_name(line) and not re.match(r'^[0-9]', line):
                if ingredient_start == -1:
                    ingredient_start = i
                ingredient_end = i
            elif ingredient_start != -1 and re.match(r'^[0-9]', line):
                # We've hit numbers, stop collecting ingredients
                break
        
        if ingredient_start == -1:
            return composition
            
        # Collect ingredients
        ingredients = []
        for i in range(ingredient_start, ingredient_end + 1):
            line = lines[i]
            if self.is_likely_chemical_name(line) and not re.match(r'^[0-9]', line):
                ingredients.append(line)
        
        # Find amounts - look for numbers after ingredients
        amounts = []
        amount_start = ingredient_end + 1
        while amount_start < len(lines) and not re.match(r'^[0-9]', lines[amount_start]):
            amount_start += 1
            
        for i in range(amount_start, len(lines)):
            line = lines[i]
            if re.match(r'^[0-9]', line):
                try:
                    amount = float(line)
                    amounts.append(amount)
                except ValueError:
                    break
            else:
                break
        
        # Find units - look for unit labels after amounts
        units = []
        unit_start = amount_start + len(amounts)
        while unit_start < len(lines) and lines[unit_start] not in ['g', 'mg', 'ml', 'l', 'g/l', 'mg/l', 'mm', 'μm', 'm', 'mM']:
            unit_start += 1
            
        for i in range(unit_start, len(lines)):
            line = lines[i]
            if line.lower() in ['g', 'mg', 'ml', 'l', 'g/l', 'mg/l', 'mm', 'μm', 'm', 'mm', 'μl']:
                units.append(line.lower())
            elif line.startswith('©') or 'adjust' in line.lower():
                break
                
        # Match ingredients with amounts and units
        min_len = min(len(ingredients), len(amounts))
        for i in range(min_len):
            unit = units[i] if i < len(units) else 'g'
            composition.append({
                "name": ingredients[i],
                "concentration": amounts[i],
                "unit": unit,
                "extraction_method": "pdf_tabular_parsing"
            })
        
        return composition
    
    def parse_reverse_tabular_format(self, text_content: str) -> List[Dict]:
        """Parse reverse tabular format where amounts come before ingredients."""
        composition = []
        lines = [line.strip() for line in text_content.split('\n') if line.strip()]
        
        # Find sequences of decimal numbers (amounts)
        amounts = []
        units = []
        ingredients = []
        
        # Phase 1: Collect amounts (decimal numbers)
        amount_phase = True
        unit_phase = False
        ingredient_phase = False
        
        for line in lines:
            # Skip empty lines and copyright
            if not line or line.startswith('©') or 'reserved' in line.lower():
                continue
            
            # Phase 1: Collect decimal numbers as amounts
            if amount_phase:
                if re.match(r'^[0-9]+\.[0-9]+$', line):
                    amounts.append(float(line))
                elif re.match(r'^[0-9]+\s+(mM|M|%)', line):  # Special case: "20 mM"
                    match = re.match(r'^([0-9]+)\s+([a-zA-Z%]+)', line)
                    if match:
                        amounts.append(float(match.group(1)))
                        units.append(match.group(2))
                elif line.lower() in ['g', 'mg', 'ml', 'l']:
                    # Start of unit phase
                    amount_phase = False
                    unit_phase = True
                    units.append(line.lower())
                elif self.is_likely_chemical_name(line) and not re.match(r'^[0-9]', line):
                    # Jump directly to ingredient phase if we hit ingredient names
                    amount_phase = False
                    unit_phase = False
                    ingredient_phase = True
                    ingredients.append(line)
            
            # Phase 2: Collect units
            elif unit_phase:
                if line.lower() in ['g', 'mg', 'ml', 'l', 'mm', 'μm', 'm']:
                    units.append(line.lower())
                elif self.is_likely_chemical_name(line) and not re.match(r'^[0-9]', line):
                    # Switch to ingredient phase
                    unit_phase = False
                    ingredient_phase = True
                    ingredients.append(line)
            
            # Phase 3: Collect ingredients
            elif ingredient_phase:
                if self.is_likely_chemical_name(line) and not re.match(r'^[0-9]', line):
                    ingredients.append(line)
                elif line.lower().endswith('medium') or 'adjust' in line.lower():
                    break  # End of ingredients
        
        # Handle case where units weren't explicitly listed
        if not units and amounts:
            units = ['g'] * len(amounts)  # Default to grams
        
        # Match amounts, units, and ingredients
        min_len = min(len(amounts), len(ingredients))
        for i in range(min_len):
            unit = units[i] if i < len(units) else 'g'
            composition.append({
                "name": ingredients[i],
                "concentration": amounts[i],
                "unit": unit,
                "extraction_method": "pdf_reverse_tabular_parsing"
            })
        
        return composition
    
    def parse_multi_solution_format(self, text_content: str) -> List[Dict]:
        """Parse complex multi-solution formats with nested components."""
        composition = []
        lines = text_content.split('\n')
        
        current_solution = None
        in_solution = False
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Detect solution headers
            if ('solution' in line.lower() or 'salts' in line.lower()) and ':' in line:
                current_solution = line
                in_solution = True
                continue
            
            # Skip pH lines and other metadata
            if line.lower().startswith(('ph ', 'adjust ph', '©', 'distilled water')):
                continue
            
            # Look for ingredient lines in solutions
            if in_solution and self.is_likely_chemical_name(line):
                # Try to find concentration info on same line or nearby
                concentration = 1.0  # Default
                unit = "g"  # Default
                
                # Check for concentration patterns in the line
                conc_match = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*(g|mg|ml|mM|M|%)', line)
                if conc_match:
                    concentration = float(conc_match.group(1))
                    unit = conc_match.group(2)
                    # Clean ingredient name
                    ingredient_name = re.sub(r'\s*\([0-9]+(?:\.[0-9]+)?\s*[a-zA-Z%]+\)', '', line).strip()
                else:
                    ingredient_name = line
                
                composition.append({
                    "name": ingredient_name,
                    "concentration": concentration,
                    "unit": unit,
                    "extraction_method": "pdf_multi_solution_parsing",
                    "solution": current_solution
                })
        
        return composition
    
    def parse_reference_medium(self, text_content: str) -> List[Dict]:
        """Parse reference media that refer to other media."""
        composition = []
        
        # Look for reference patterns
        ref_patterns = [
            r'medium\s+(\d+)',
            r'see\s+medium\s+(\d+)',
            r'to\s+medium\s+(\d+)',
            r'from\s+medium\s+(\d+)'
        ]
        
        for pattern in ref_patterns:
            match = re.search(pattern, text_content.lower())
            if match:
                referenced_medium = match.group(1)
                # Create a placeholder composition indicating this is a reference
                composition.append({
                    "name": f"Reference to Medium {referenced_medium}",
                    "concentration": 1.0,
                    "unit": "reference",
                    "extraction_method": "pdf_reference_parsing",
                    "referenced_medium": referenced_medium
                })
                
                # Also try to extract any additional ingredients mentioned
                additional_ingredients = self.extract_additional_ingredients(text_content)
                composition.extend(additional_ingredients)
                break
        
        return composition
    
    def extract_additional_ingredients(self, text_content: str) -> List[Dict]:
        """Extract additional ingredients mentioned in reference media."""
        composition = []
        
        # Look for patterns like "add 5% blood", "supplemented with X"
        addition_patterns = [
            r'add\s+([0-9]+(?:\.[0-9]+)?%?)\s+([a-zA-Z\s]+)',
            r'supplemented\s+with\s+([0-9]+(?:\.[0-9]+)?%?)\s+([a-zA-Z\s]+)',
            r'plus\s+([0-9]+(?:\.[0-9]+)?%?)\s+([a-zA-Z\s]+)'
        ]
        
        for pattern in addition_patterns:
            matches = re.findall(pattern, text_content.lower())
            for match in matches:
                if len(match) >= 2:
                    amount_str = match[0].replace('%', '')
                    ingredient = match[1].strip()
                    
                    try:
                        amount = float(amount_str)
                        unit = "%" if "%" in match[0] else "g"
                        
                        if self.is_likely_chemical_name(ingredient):
                            composition.append({
                                "name": ingredient.title(),
                                "concentration": amount,
                                "unit": unit,
                                "extraction_method": "pdf_reference_addition_parsing"
                            })
                    except ValueError:
                        continue
        
        return composition
    
    def parse_dotted_line_format(self, text_content: str) -> List[Dict]:
        """Parse ATCC dotted line format where ingredients and amounts are separated by dots."""
        composition = []
        lines = text_content.split('\n')
        
        for line in lines:
            # Skip empty lines and metadata
            if not line.strip() or line.startswith('©') or 'ATCC Medium' in line:
                continue
            
            # Look for dotted line patterns
            # Pattern 1: ingredient………amount+unit (dots are actually … characters)
            if '…' in line:
                # Split on the dots
                parts = line.split('…')
                if len(parts) >= 2:
                    ingredient = parts[0].strip()
                    # Get the last part which should have amount+unit
                    amount_unit = parts[-1].strip()
                    
                    # Extract amount and unit
                    amount_match = re.match(r'([0-9]+(?:\.[0-9]+)?)\s*([a-zA-Z/]+)', amount_unit)
                    if amount_match and self.is_likely_chemical_name(ingredient):
                        amount = float(amount_match.group(1))
                        unit = amount_match.group(2)
                        
                        composition.append({
                            "name": ingredient,
                            "concentration": amount,
                            "unit": unit,
                            "extraction_method": "atcc_dotted_line_parsing"
                        })
                continue
            
            # Pattern 2: Check for special dot patterns (regular dots)
            if re.search(r'\.{3,}', line):
                dot_match = re.match(r'^([A-Za-z][^\.]+?)\.{3,}\s*([0-9]+(?:\.[0-9]+)?)\s*([a-zA-Z/]+)', line)
                if dot_match:
                    ingredient = dot_match.group(1).strip()
                    amount = float(dot_match.group(2))
                    unit = dot_match.group(3)
                    
                    if self.is_likely_chemical_name(ingredient):
                        composition.append({
                            "name": ingredient,
                            "concentration": amount,
                            "unit": unit,
                            "extraction_method": "atcc_dotted_line_parsing"
                        })
                continue
            
            # Pattern 3: ingredient with many spaces then amount+unit
            space_match = re.match(r'^([A-Za-z][^\d…\.]+?)\s{3,}([0-9]+(?:\.[0-9]+)?)\s*([a-zA-Z/]+)$', line.strip())
            if space_match:
                ingredient = space_match.group(1).strip()
                amount = float(space_match.group(2))
                unit = space_match.group(3)
                
                if self.is_likely_chemical_name(ingredient):
                    composition.append({
                        "name": ingredient,  
                        "concentration": amount,
                        "unit": unit,
                        "extraction_method": "atcc_spaced_parsing"
                    })
        
        return composition
    
    def parse_columnar_format(self, text_content: str) -> List[Dict]:
        """Parse columnar format where ingredient, amount, and unit are on the same line."""
        composition = []
        lines = text_content.split('\n')
        
        for line in lines:
            # Skip empty lines and metadata
            if not line.strip() or line.startswith('©') or 'adjust' in line.lower():
                continue
            
            # Pattern: ingredient name (multiple words) followed by amount and unit
            # Example: "Glucose            10.0     g"
            match = re.match(r'^([A-Za-z][A-Za-z0-9\s\-·\(\)]+?)\s{2,}([0-9]+(?:\.[0-9]+)?)\s+([a-zA-Z/]+)$', line)
            if match:
                ingredient = match.group(1).strip()
                amount = float(match.group(2))
                unit = match.group(3)
                
                if self.is_likely_chemical_name(ingredient):
                    composition.append({
                        "name": ingredient,
                        "concentration": amount,
                        "unit": unit,
                        "extraction_method": "columnar_format_parsing"
                    })
        
        return composition
    
    def parse_parenthetical_format(self, text_content: str) -> List[Dict]:
        """Parse format where amounts are in parentheses after ingredient names."""
        composition = []
        
        # Pattern: ingredient name (amount unit)
        # Examples: "NaCl (25.0 g)", "Glucose (10 g/L)"
        pattern = r'([A-Za-z][A-Za-z0-9\s\-·]+?)\s*\(([0-9]+(?:\.[0-9]+)?)\s*([a-zA-Z/]+)\)'
        
        matches = re.findall(pattern, text_content)
        for match in matches:
            ingredient = match[0].strip()
            amount = float(match[1])
            unit = match[2]
            
            if self.is_likely_chemical_name(ingredient):
                composition.append({
                    "name": ingredient,
                    "concentration": amount,
                    "unit": unit,
                    "extraction_method": "parenthetical_format_parsing"
                })
        
        return composition
    
    def parse_three_column_layout(self, text_content: str) -> List[Dict]:
        """Parse DSMZ three-column format: ingredients | amounts | units."""
        composition = []
        lines = [line.strip() for line in text_content.split('\n') if line.strip()]
        
        # Identify sections by analyzing line patterns
        ingredient_lines = []
        amount_lines = []
        unit_lines = []
        
        # Phase detection - look for transitions in line patterns
        current_phase = "unknown"
        
        for line in lines:
            # Skip headers and metadata
            if any(skip in line.lower() for skip in ['medium', '©', 'adjust', 'sterilize', 'autoclave']):
                continue
            
            # Detect ingredients (chemical names, not pure numbers)
            if self.is_likely_chemical_name(line) and not re.match(r'^[\d\.\s]+$', line):
                if current_phase != "ingredients":
                    current_phase = "ingredients"
                ingredient_lines.append(line)
            
            # Detect amounts (pure decimal numbers)
            elif re.match(r'^[\d\.]+$', line) and len(ingredient_lines) > 0:
                if current_phase != "amounts":
                    current_phase = "amounts"
                amount_lines.append(float(line))
            
            # Detect units
            elif line.lower() in ['g', 'mg', 'ml', 'l', 'mm', 'μl', 'μm'] and len(amount_lines) > 0:
                if current_phase != "units":
                    current_phase = "units"
                unit_lines.append(line.lower())
        
        # Match ingredients to amounts and units by position
        min_len = min(len(ingredient_lines), len(amount_lines))
        for i in range(min_len):
            unit = unit_lines[i] if i < len(unit_lines) else 'g'
            composition.append({
                "name": ingredient_lines[i],
                "concentration": amount_lines[i],
                "unit": unit,
                "extraction_method": "three_column_layout_parsing"
            })
        
        return composition
    
    def parse_simple_list_format(self, text_content: str) -> List[Dict]:
        """Parse simple CCAP format: ingredients list, 'per litre', amounts list."""
        composition = []
        
        # Clean text by replacing non-breaking spaces with regular spaces
        text_content = text_content.replace('\xa0', ' ')
        lines = [line.strip() for line in text_content.split('\n') if line.strip()]
        
        # Look for the pattern: ingredients, "per litre", amounts
        ingredients = []
        amounts_with_units = []
        found_per_litre = False
        collecting_amounts = False
        
        for line in lines:
            if not line:
                continue
            
            # Skip metadata lines
            if any(skip in line.lower() for skip in ['©', 'adjust', 'sterilize', 'preparation', 'ccap', 'tel:', 'fax:', 'email:', 'web:']):
                continue
            
            # Skip the title line
            if line.startswith('SNA') and 'Seawater' in line:
                continue
            
            # Skip single character lines (formatting artifacts)
            if len(line) == 1:
                continue
            
            # Detect "per litre" delimiter
            if 'per litre' in line.lower() or 'per liter' in line.lower():
                found_per_litre = True
                collecting_amounts = True
                continue
            
            # Collect ingredients before "per litre" 
            if not found_per_litre:
                # Skip "Medium" header
                if line.lower() == 'medium':
                    continue
                # Accept ingredient-like lines (not just chemical names)
                if len(line) > 3 and not re.match(r'^\d', line):
                    ingredients.append(line)
            
            # Collect amounts after "per litre"
            elif collecting_amounts and re.search(r'\d+\.?\d*\s*(g|mg|ml|l)', line):
                # Extract amount and unit
                match = re.search(r'(\d+\.?\d*)\s*(g|mg|ml|l)', line)
                if match:
                    amount = float(match.group(1))
                    unit = match.group(2)
                    amounts_with_units.append((amount, unit))
            # Stop collecting if we hit preparation instructions
            elif collecting_amounts and any(prep in line.lower() for prep in ['make up', 'steam', 'autoclave']):
                break
        
        # Match ingredients with amounts
        min_len = min(len(ingredients), len(amounts_with_units))
        for i in range(min_len):
            amount, unit = amounts_with_units[i]
            composition.append({
                "name": ingredients[i],
                "concentration": amount,
                "unit": unit,
                "extraction_method": "simple_list_format_parsing"
            })
        
        return composition
    
    def parse_enhanced_prose_format(self, text_content: str) -> List[Dict]:
        """Parse prose format with embedded concentrations."""
        composition = []
        
        # Enhanced patterns for prose-embedded concentrations
        patterns = [
            # Pattern 1: "supplemented with X g/l of compound"
            r'supplemented\s+with\s+([0-9]+(?:\.[0-9]+)?)\s*(g|mg|ml)/l\s+(?:of\s+)?([^,\.;]+?)(?:\s+and|\.|,|$)',
            # Pattern 2: "contains X g compound per liter"
            r'contains\s+([0-9]+(?:\.[0-9]+)?)\s*(g|mg|ml)\s+([^,\.;]+?)\s+per\s+(?:liter|litre)',
            # Pattern 3: "compound X g/L"
            r'([A-Z][^,\.;]*?)\s+([0-9]+(?:\.[0-9]+)?)\s*(g|mg|ml)/L',
            # Pattern 4: "X is added at Y mg/l"
            r'([A-Z][^,\.;]*?)\s+is\s+added\s+at\s+([0-9]+(?:\.[0-9]+)?)\s*(g|mg|ml)/l',
            # Pattern 5: "Brain heart infusion X g, compound Y mg"
            r'([A-Za-z][^,\.;]*?)\s+([0-9]+(?:\.[0-9]+)?)\s*(g|mg|ml)(?:\s*,|\s+and|\s*$)',
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text_content, re.IGNORECASE)
            for match in matches:
                if len(match.groups()) >= 3:
                    if pattern.startswith(r'([A-Z]') and not pattern.startswith(r'supplemented'):
                        # Patterns where compound comes first
                        compound = match.group(1).strip()
                        amount = float(match.group(2))
                        unit = match.group(3)
                    else:
                        # Patterns where amount comes first
                        amount = float(match.group(1))
                        unit = match.group(2)
                        compound = match.group(3).strip()
                    
                    # Clean compound name
                    compound = re.sub(r'\s+', ' ', compound).strip()
                    compound = compound.rstrip('.,;:')
                    
                    # Check if it's a valid chemical name
                    if self.is_likely_chemical_name(compound) and not any(c['name'] == compound for c in composition):
                        composition.append({
                            "name": compound,
                            "concentration": amount,
                            "unit": f"{unit}/L",
                            "extraction_method": "enhanced_prose_parsing"
                        })
        
        return composition
    
    def is_likely_chemical_name(self, name: str) -> bool:
        """Check if a string is likely a chemical name."""
        # Basic heuristics for chemical names
        chemical_indicators = [
            'Cl', 'SO4', 'PO4', 'NO3', 'CO3', 'HCO3', 'H2O', 'x', '·',
            'Na', 'K', 'Mg', 'Ca', 'Fe', 'Zn', 'Cu', 'Mn', 'NH4', 'NO2',
            'extract', 'agar', 'glucose', 'peptone', 'yeast', 'starch',
            'casitone', 'tryptone', 'beef', 'malt', 'sucrose', 'fructose',
            'lactose', 'maltose', 'glycerol', 'ethanol', 'acetate', 'citrate',
            'pyruvate', 'succinate', 'fumarate', 'malate', 'vitamin', 'biotin',
            'thiamine', 'nicotinic', 'folic', 'cobalamin', 'trace', 'solution'
        ]
        
        name_lower = name.lower()
        
        # Must be reasonable length
        if len(name) < 2 or len(name) > 100:
            return False
            
        # Skip obvious non-ingredients
        skip_words = ['medium', 'distilled water', 'adjust', '©', 'reserved', 'dsmz', 'sterilize']
        for skip in skip_words:
            if skip in name_lower:
                return False
        
        # Accept common media ingredients by name patterns
        common_ingredients = [
            'glucose', 'sucrose', 'fructose', 'lactose', 'maltose', 'starch', 'glycerol',
            'yeast extract', 'beef extract', 'malt extract', 'peptone', 'tryptone', 'casitone',
            'agar', 'gellan', 'carrageenan', 'vitamin', 'biotin', 'thiamine', 'trace'
        ]
        
        for ingredient in common_ingredients:
            if ingredient in name_lower:
                return True
        
        # Check for chemical patterns
        for indicator in chemical_indicators:
            if indicator.lower() in name_lower:
                return True
        
        # Check for chemical formula patterns (letters followed by numbers)
        if re.search(r'[A-Z][a-z]*[0-9]', name):
            return True
            
        # Check for salt patterns (e.g., "Na2SO4", "CaCl2")
        if re.search(r'^[A-Z][a-z]?[0-9]?[A-Z]', name):
            return True
            
        # If it starts with capital letter and contains some chemical-like patterns
        if name[0].isupper() and any(c.isupper() for c in name[1:]) and len(name) > 3:
            return True
            
        return False
    
    def extract_medium_name_from_text(self, text_content: str, default_id: str) -> str:
        """Extract medium name from text content."""
        # Look for common medium name patterns
        patterns = [
            r'Medium\s+([A-Z0-9][^\n\r]+)',
            r'MEDIUM\s+([A-Z0-9][^\n\r]+)',
            r'([A-Z][A-Z\s]+MEDIUM)',
            r'# ([^#\n\r]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text_content)
            if match:
                return match.group(1).strip()
        
        return f"Medium {default_id}"
    
    def extract_preparation_instructions(self, text_content: str) -> str:
        """Extract preparation instructions from text content."""
        # Look for instruction sections
        patterns = [
            r'(?:Preparation|PREPARATION|Instructions|INSTRUCTIONS):?\s*([^#]+?)(?:\n\s*\n|\n\s*#|$)',
            r'(?:Method|METHOD):?\s*([^#]+?)(?:\n\s*\n|\n\s*#|$)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text_content, re.DOTALL)
            if match:
                return match.group(1).strip()[:500]  # Limit length
        
        return ""
    
    def parse_cyanosite_composition(self, soup: BeautifulSoup) -> List[Dict]:
        """Parse composition from Cyanosite HTML."""
        composition = []
        
        # Look for tables or lists containing composition data
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            for row in rows[1:]:  # Skip header row
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    name = cells[0].get_text(strip=True)
                    concentration_text = cells[1].get_text(strip=True)
                    
                    # Parse concentration
                    conc_match = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*([a-zA-Z/]+)', concentration_text)
                    if conc_match and self.is_likely_chemical_name(name):
                        composition.append({
                            "name": name,
                            "concentration": float(conc_match.group(1)),
                            "unit": conc_match.group(2),
                            "extraction_method": "cyanosite_html_table"
                        })
        
        return composition
    
    def extract_cyanosite_medium_name(self, soup: BeautifulSoup, default_id: str) -> str:
        """Extract medium name from Cyanosite HTML."""
        # Look for title or heading
        for tag in ['h1', 'h2', 'title']:
            element = soup.find(tag)
            if element:
                return element.get_text(strip=True)
        
        return f"Cyanosite {default_id}"
    
    def process_media_file(self, file_path: Path) -> Optional[Dict]:
        """Process a single media file and extract composition."""
        self.stats["total_files"] += 1
        file_type = self.identify_media_file_type(file_path)
        
        self.logger.info(f"Processing {file_type} file: {file_path}")
        
        if file_type == 'dsmz_json':
            self.stats["dsmz_json_files"] += 1
            return self.extract_from_dsmz_json(file_path)
        elif file_type == 'jcm_html':
            self.stats["jcm_html_files"] += 1
            return self.jcm_parser.parse_jcm_html_file(file_path)
        elif file_type == 'cyanosite_html':
            self.stats["cyanosite_html_files"] += 1
            return self.extract_from_cyanosite_html(file_path)
        elif file_type == 'dsmz_pdf':
            self.stats["dsmz_pdf_files"] += 1
            return self.extract_from_pdf(file_path)
        elif file_type == 'ccap_pdf':
            self.stats["ccap_pdf_files"] += 1
            return self.extract_from_pdf(file_path)
        elif file_type == 'atcc_pdf':
            self.stats["atcc_pdf_files"] += 1
            return self.extract_from_pdf(file_path)
        elif file_type == 'other_pdf':
            self.stats["other_files"] += 1
            return self.extract_from_pdf(file_path)
        else:
            self.stats["other_files"] += 1
            return self.extract_from_other_file(file_path)
    
    def find_all_media_files(self, media_pdfs_dir: str) -> List[Path]:
        """Find all media files to process."""
        media_dir = Path(media_pdfs_dir)
        
        # Find all relevant media files
        files = []
        
        # DSMZ JSON files
        json_files = list(media_dir.glob("*_composition.json"))
        files.extend(json_files)
        
        # JCM HTML files  
        jcm_html_files = list(media_dir.glob("jcm_*.html"))
        files.extend(jcm_html_files)
        
        # Cyanosite HTML files
        cyanosite_html_files = list(media_dir.glob("cyanosite_*.html"))
        files.extend(cyanosite_html_files)
        
        # PDF files by source
        dsmz_pdf_files = list(media_dir.glob("dsmz_*.pdf"))
        ccap_pdf_files = list(media_dir.glob("ccap_*.pdf"))
        atcc_pdf_files = list(media_dir.glob("atcc_*.pdf"))
        other_pdf_files = [f for f in media_dir.glob("*.pdf") 
                          if not any(f.name.startswith(prefix) for prefix in ['dsmz_', 'ccap_', 'atcc_'])]
        
        pdf_files = dsmz_pdf_files + ccap_pdf_files + atcc_pdf_files + other_pdf_files
        files.extend(pdf_files)
        
        self.logger.info(f"Found {len(files)} total media files:")
        self.logger.info(f"  - DSMZ JSON: {len(json_files)}")
        self.logger.info(f"  - JCM HTML: {len(jcm_html_files)}")
        self.logger.info(f"  - Cyanosite HTML: {len(cyanosite_html_files)}")
        self.logger.info(f"  - DSMZ PDFs: {len(dsmz_pdf_files)}")
        self.logger.info(f"  - CCAP PDFs: {len(ccap_pdf_files)}")
        self.logger.info(f"  - ATCC PDFs: {len(atcc_pdf_files)}")
        self.logger.info(f"  - Other PDFs: {len(other_pdf_files)}")
        self.logger.info(f"  - Total PDFs: {len(pdf_files)}")
        
        return files
    
    def extract_all_compositions(self, media_pdfs_dir: str, output_dir: str) -> None:
        """Extract compositions from all media files."""
        self.logger.info("=== ENHANCED MEDIA COMPOSITION EXTRACTION ===")
        
        # Find all media files
        media_files = self.find_all_media_files(media_pdfs_dir)
        
        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Process each file
        successful_compositions = []
        failed_files = []
        
        for media_file in media_files:
            composition_data = self.process_media_file(media_file)
            
            if composition_data:
                # Save individual composition file
                output_file = output_path / f"{composition_data['medium_id']}_composition.json"
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(composition_data, f, indent=2, ensure_ascii=False)
                
                successful_compositions.append(composition_data)
                
                # Don't count "no_data" pages as failures
                if composition_data.get("no_data"):
                    self.stats.setdefault("no_data_pages", 0)
                    self.stats["no_data_pages"] += 1
                else:
                    self.stats["successful_extractions"] += 1
            else:
                self.stats["failed_extractions"] += 1
                failed_files.append(str(media_file))
        
        # Create comprehensive summary
        self.create_comprehensive_summary(output_path, successful_compositions)
        
        # Save failed files list
        self.save_failed_files_list(output_path, failed_files)
        
        # Log final statistics
        self.log_final_statistics()
    
    def create_comprehensive_summary(self, output_path: Path, compositions: List[Dict]) -> None:
        """Create a comprehensive summary of all extractions."""
        summary = {
            "extraction_statistics": self.stats,
            "total_media_extracted": len(compositions),
            "media_by_source": {},
            "ingredient_statistics": {
                "total_ingredients": self.stats["total_ingredients"],
                "avg_ingredients_per_medium": self.stats["total_ingredients"] / len(compositions) if compositions else 0
            },
            "most_common_ingredients": {},
            "extraction_method": "enhanced_multi_format"
        }
        
        # Analyze by source
        source_counts = {}
        ingredient_counts = {}
        
        for media in compositions:
            source = media.get("source", "unknown")
            source_counts[source] = source_counts.get(source, 0) + 1
            
            # Count ingredient occurrences
            for ingredient in media.get("composition", []):
                name = ingredient.get("name", "unknown")
                ingredient_counts[name] = ingredient_counts.get(name, 0) + 1
        
        summary["media_by_source"] = source_counts
        
        # Top 20 most common ingredients
        sorted_ingredients = sorted(ingredient_counts.items(), key=lambda x: x[1], reverse=True)
        summary["most_common_ingredients"] = dict(sorted_ingredients[:20])
        
        # Save comprehensive summary
        summary_file = output_path / "comprehensive_extraction_summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Comprehensive summary saved to {summary_file}")
    
    def save_failed_files_list(self, output_path: Path, failed_files: List[str]) -> None:
        """Save list of files that failed parsing."""
        if not failed_files:
            self.logger.info("No failed files to report!")
            return
        
        # Save as text file for easy viewing
        failed_files_txt = output_path / "failed_files.txt"
        with open(failed_files_txt, 'w', encoding='utf-8') as f:
            f.write(f"# Failed Media Files - {len(failed_files)} files\n")
            f.write(f"# Generated on: {self.get_timestamp()}\n\n")
            
            # Group by file type
            file_types = {}
            for file_path in failed_files:
                path = Path(file_path)
                file_type = self.identify_media_file_type(path)
                if file_type not in file_types:
                    file_types[file_type] = []
                file_types[file_type].append(file_path)
            
            for file_type, paths in file_types.items():
                f.write(f"## {file_type.upper()} FILES ({len(paths)} failed)\n")
                for path in sorted(paths):
                    f.write(f"{path}\n")
                f.write("\n")
        
        # Save as JSON for programmatic access
        failed_files_json = output_path / "failed_files.json"
        failed_data = {
            "extraction_date": self.get_timestamp(),
            "total_failed": len(failed_files),
            "failed_by_type": {},
            "failed_files": failed_files
        }
        
        # Group by type for JSON
        for file_path in failed_files:
            path = Path(file_path)
            file_type = self.identify_media_file_type(path)
            if file_type not in failed_data["failed_by_type"]:
                failed_data["failed_by_type"][file_type] = []
            failed_data["failed_by_type"][file_type].append(file_path)
        
        with open(failed_files_json, 'w', encoding='utf-8') as f:
            json.dump(failed_data, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Failed files list saved to {failed_files_txt}")
        self.logger.info(f"Failed files JSON saved to {failed_files_json}")
    
    def get_timestamp(self) -> str:
        """Get current timestamp for logging."""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def log_final_statistics(self) -> None:
        """Log final extraction statistics."""
        self.logger.info("=== ENHANCED EXTRACTION COMPLETED ===")
        self.logger.info(f"Total files processed: {self.stats['total_files']}")
        self.logger.info(f"  - DSMZ JSON: {self.stats['dsmz_json_files']}")
        self.logger.info(f"  - DSMZ PDF: {self.stats['dsmz_pdf_files']}")
        self.logger.info(f"  - JCM HTML: {self.stats['jcm_html_files']}")
        self.logger.info(f"  - CCAP PDF: {self.stats['ccap_pdf_files']}")
        self.logger.info(f"  - ATCC PDF: {self.stats['atcc_pdf_files']}")
        self.logger.info(f"  - Cyanosite HTML: {self.stats['cyanosite_html_files']}")
        self.logger.info(f"  - Other: {self.stats['other_files']}")
        
        total_pdfs = (self.stats['dsmz_pdf_files'] + self.stats['ccap_pdf_files'] + 
                     self.stats['atcc_pdf_files'])
        self.logger.info(f"Total PDFs processed: {total_pdfs}")
        
        self.logger.info(f"Successful extractions: {self.stats['successful_extractions']}")
        self.logger.info(f"Failed extractions: {self.stats['failed_extractions']}")
        self.logger.info(f"Total ingredients extracted: {self.stats['total_ingredients']}")
        
        success_rate = (self.stats['successful_extractions'] / self.stats['total_files']) * 100 if self.stats['total_files'] > 0 else 0
        self.logger.info(f"Success rate: {success_rate:.1f}%")


def main():
    """Main function to run enhanced composition extraction."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Enhanced comprehensive media composition extraction")
    parser.add_argument("--input-dir", default="media_pdfs",
                       help="Directory containing media files")
    parser.add_argument("--output-dir", default="media_compositions", 
                       help="Directory to save composition files")
    
    args = parser.parse_args()
    
    extractor = EnhancedCompositionExtractor()
    extractor.extract_all_compositions(args.input_dir, args.output_dir)


if __name__ == "__main__":
    main()