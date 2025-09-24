#!/usr/bin/env python3
"""
Enhanced media extractor that cleanly separates ingredients from instructions.
Fixes procedure text contamination and extracts preparation instructions separately.
"""

import json
import logging
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from bs4 import BeautifulSoup

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class EnhancedMediaExtractor:
    """Enhanced extractor that cleanly separates ingredients from preparation instructions."""
    
    def __init__(self):
        # Clean chemical compound patterns (excluding procedure text)
        self.compound_patterns = [
            # Chemical formulas with hydrates (strict)
            r'\b([A-Z][a-z]?(?:\d*[A-Z][a-z]?\d*)*(?:\([A-Z][a-z]?\d*\)\d*)*(?:\s*x?\s*\d*\s*H2O)?)\b',
            # Named compounds (strict - must end with chemical indicators)
            r'\b([A-Z][a-z]+(?:\s+[a-z]+)*(?:\s+(?:chloride|sulfate|phosphate|nitrate|carbonate|bicarbonate|acetate|citrate|hydroxide|oxide|extract|peptone|acid|agar|solution)))\b',
        ]
        
        # Enhanced concentration patterns
        self.concentration_patterns = [
            (r'(\d+(?:\.\d+)?)\s*g/l\b', 'g/L'),
            (r'(\d+(?:\.\d+)?)\s*g/L\b', 'g/L'),
            (r'(\d+(?:\.\d+)?)\s*g\s*l-1\b', 'g/L'),
            (r'(\d+(?:\.\d+)?)\s*mg/l\b', 'mg/L'),
            (r'(\d+(?:\.\d+)?)\s*mg/L\b', 'mg/L'),
            (r'(\d+(?:\.\d+)?)\s*ml/l\b', 'ml/L'),
            (r'(\d+(?:\.\d+)?)\s*ml/L\b', 'ml/L'),
            (r'(\d+(?:\.\d+)?)\s*mM\b', 'mM'),
            (r'(\d+(?:\.\d+)?)\s*μM\b', 'μM'),
            (r'(\d+(?:\.\d+)?)\s*uM\b', 'μM'),
            (r'(\d+(?:\.\d+)?)\s*M\b(?![a-z])', 'M'),
        ]
        
        # Procedure text indicators (to exclude from ingredients)
        self.procedure_indicators = [
            'dissolve', 'add', 'mix', 'adjust', 'autoclave', 'sterilize', 'filter', 
            'prepare', 'supplement', 'replace', 'omit', 'incubate', 'inoculate',
            'pressurize', 'sparge', 'distribute', 'dispense', 'cool', 'heat',
            'bring to', 'make up to', 'final ph', 'final volume', 'upon autoclaving',
            'after inoculation', 'for dsm', 'note:', 'reference:', 'supplier:'
        ]
        
        # Known pure compounds
        self.known_compounds = {
            'nacl', 'kcl', 'cacl2', 'mgcl2', 'mgso4', 'k2hpo4', 'kh2po4', 'nh4cl',
            'na2co3', 'nahco3', 'na2so4', 'caso4', 'feso4', 'znso4', 'cuso4',
            'glucose', 'sucrose', 'lactose', 'fructose', 'mannitol', 'glycerol',
            'yeast extract', 'beef extract', 'peptone', 'tryptone', 'casein', 'agar',
            'biotin', 'thiamine', 'hepes', 'tris', 'edta', 'resazurin', 'cysteine'
        }
    
    def extract_media_data(self, file_path: Path) -> Optional[Dict]:
        """Extract both ingredients and preparation instructions."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Split content into sections
            ingredient_section, instruction_section = self._split_content_sections(content)
            
            # Extract ingredients (clean, no procedure contamination)
            ingredients = self._extract_clean_ingredients(ingredient_section)
            
            # Extract preparation instructions
            instructions = self._extract_preparation_instructions(instruction_section)
            
            if ingredients or instructions:
                return {
                    'medium_id': self._get_medium_id(file_path),
                    'medium_name': self._extract_medium_name(file_path, content),
                    'source': self._get_source(file_path),
                    'composition': ingredients,
                    'preparation_instructions': instructions,
                    'extraction_stats': {
                        'ingredients_found': len(ingredients),
                        'has_instructions': len(instructions) > 0,
                        'instruction_length': len(instructions)
                    }
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")
            return None
    
    def _split_content_sections(self, content: str) -> Tuple[str, str]:
        """Split content into ingredient section and instruction section."""
        lines = content.split('\n')
        
        ingredient_lines = []
        instruction_lines = []
        
        # More sophisticated section detection
        in_tabular_ingredients = False
        procedure_started = False
        
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            
            # Skip empty lines and headers
            if not line_stripped or any(skip in line_stripped.lower() for skip in ['©', 'page', 'dsmz - all rights reserved']):
                continue
            
            # Check if this is the start of a procedure section
            if (re.match(r'^\d+\.\s+(?:Dissolve|Add|Mix|Adjust|Autoclave|Sterilize|Prepare)', line_stripped, re.IGNORECASE) or
                line_stripped.lower().startswith('note:') or
                line_stripped.lower().startswith('reference:')):
                procedure_started = True
                instruction_lines.append(line_stripped)
                continue
            
            # If we've started procedures, everything goes to instructions
            if procedure_started:
                instruction_lines.append(line_stripped)
                continue
            
            # Look for DSMZ-style embedded ingredient lists in medium title lines
            if re.match(r'^\d+[a-z]*\.\s+[A-Z][A-Z\s]+MEDIUM', line_stripped, re.IGNORECASE):
                # This might contain embedded ingredients - extract them
                embedded_ingredients = self._extract_embedded_ingredients(line_stripped)
                if embedded_ingredients:
                    ingredient_lines.extend(embedded_ingredients)
                # Also add to instructions as context
                instruction_lines.append(line_stripped)
                continue
            
            # Detect tabular ingredient sections
            if self._looks_like_ingredient_line(line_stripped):
                in_tabular_ingredients = True
                ingredient_lines.append(line_stripped)
            elif re.match(r'^\d+\.?\d*$', line_stripped) and in_tabular_ingredients:
                # Numbers in tabular format
                ingredient_lines.append(line_stripped)
            elif line_stripped.lower() in ['g', 'mg', 'ml', 'mm', 'μm'] and in_tabular_ingredients:
                # Units in tabular format
                ingredient_lines.append(line_stripped)
            elif in_tabular_ingredients and any(marker in line_stripped.lower() for marker in ['final ph', 'final volume']):
                # End of tabular section
                in_tabular_ingredients = False
                instruction_lines.append(line_stripped)
            else:
                # Default to instructions for unclear lines
                instruction_lines.append(line_stripped)
        
        return '\n'.join(ingredient_lines), '\n'.join(instruction_lines)
    
    def _extract_embedded_ingredients(self, medium_title_line: str) -> List[str]:
        """Extract ingredients embedded in medium title lines (DSMZ format)."""
        ingredients = []
        
        # Look for patterns like "Yeast extract Peptone NaCl Agar Distilled water pH 7.0 3.0 5.0 5.0 15.0 1000.0 g g g g ml"
        # Split by common separators and identify compound-like terms
        
        # Remove the medium number and name prefix
        text = re.sub(r'^\d+[a-z]*\.\s+[A-Z][A-Z\s]+MEDIUM[^a-z]*', '', medium_title_line, flags=re.IGNORECASE)
        
        # Split into potential tokens
        tokens = text.split()
        
        current_compounds = []
        for token in tokens:
            # Stop at pH indicators or numeric sequences
            if token.lower() in ['ph', 'adjust'] or re.match(r'^\d+\.?\d*$', token):
                break
            
            # Check if token looks like a compound part
            if (len(token) >= 3 and 
                token[0].isupper() and 
                not any(bad in token.lower() for bad in ['medium', 'broth', 'agar']) and
                re.match(r'^[A-Za-z][A-Za-z\-]*$', token)):
                current_compounds.append(token)
            elif current_compounds:
                # End of compound sequence - save it
                compound_name = ' '.join(current_compounds)
                if self._is_pure_compound_name(compound_name):
                    ingredients.append(compound_name)
                current_compounds = []
        
        # Don't forget the last compound
        if current_compounds:
            compound_name = ' '.join(current_compounds)
            if self._is_pure_compound_name(compound_name):
                ingredients.append(compound_name)
        
        return ingredients
    
    def _looks_like_ingredient_line(self, line: str) -> bool:
        """Check if line looks like ingredient data (not procedure text)."""
        line_lower = line.lower()
        
        # Exclude procedure text
        if any(proc in line_lower for proc in self.procedure_indicators):
            return False
        
        # Include chemical formulas
        if re.match(r'^[A-Z][a-z]?(?:\d*[A-Z][a-z]?\d*)*', line):
            return True
        
        # Include known compound names
        if any(compound in line_lower for compound in self.known_compounds):
            return True
        
        # Include lines with chemical indicators
        chemical_indicators = ['chloride', 'sulfate', 'phosphate', 'extract', 'peptone', 'solution', 'acid']
        if any(indicator in line_lower for indicator in chemical_indicators):
            return True
        
        return False
    
    def _extract_clean_ingredients(self, ingredient_section: str) -> List[Dict]:
        """Extract ingredients without procedure text contamination."""
        ingredients = []
        
        # Strategy 1: Tabular format (DSMZ style)
        tabular_ingredients = self._extract_tabular_ingredients(ingredient_section)
        ingredients.extend(tabular_ingredients)
        
        # Strategy 2: Inline ingredients (compound + concentration on same line)
        inline_ingredients = self._extract_inline_ingredients(ingredient_section)
        ingredients.extend(inline_ingredients)
        
        # Strategy 3: Compound lists (names only)
        list_ingredients = self._extract_ingredient_lists(ingredient_section)
        ingredients.extend(list_ingredients)
        
        # Clean and deduplicate
        clean_ingredients = self._clean_and_deduplicate(ingredients)
        
        return clean_ingredients
    
    def _extract_tabular_ingredients(self, content: str) -> List[Dict]:
        """Extract from tabular format: compounds, then amounts, then units."""
        ingredients = []
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        
        # Parse sections
        compound_names = []
        amounts = []
        units = []
        
        current_section = 'compounds'
        
        for line in lines:
            if current_section == 'compounds':
                # Chemical compound names
                if self._is_pure_compound_name(line):
                    compound_names.append(line)
                # Switch to amounts when we hit pure numbers
                elif re.match(r'^\d+\.?\d*$', line):
                    current_section = 'amounts'
                    amounts.append(float(line))
            
            elif current_section == 'amounts':
                # Collect all numeric values
                if re.match(r'^\d+\.?\d*$', line):
                    amounts.append(float(line))
                # Switch to units when we hit unit indicators
                elif line.lower() in ['g', 'mg', 'ml', 'mm', 'μm', 'um']:
                    current_section = 'units'
                    units.append(line.lower())
            
            elif current_section == 'units':
                # Collect unit indicators
                if line.lower() in ['g', 'mg', 'ml', 'mm', 'μm', 'um']:
                    units.append(line.lower())
        
        # Match compounds with amounts and units
        min_length = min(len(compound_names), len(amounts))
        
        for i in range(min_length):
            compound = self._clean_compound_name(compound_names[i])
            amount = amounts[i]
            
            # Determine unit
            if i < len(units):
                unit = units[i]
                # Convert to concentration units
                if unit in ['g', 'mg', 'ml']:
                    unit = f"{unit}/L"
            else:
                unit = 'g/L'  # Default for DSMZ
            
            if amount > 0 and self._is_valid_ingredient_name(compound):
                ingredients.append({
                    'name': compound,
                    'concentration': amount,
                    'unit': unit,
                    'extraction_method': 'tabular'
                })
        
        return ingredients
    
    def _extract_inline_ingredients(self, content: str) -> List[Dict]:
        """Extract ingredients with concentrations on the same line."""
        ingredients = []
        
        for line in content.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            # Skip if line contains procedure indicators
            if any(proc in line.lower() for proc in self.procedure_indicators):
                continue
            
            # Look for concentration patterns
            for pattern, unit in self.concentration_patterns:
                matches = list(re.finditer(pattern, line, re.IGNORECASE))
                
                for match in matches:
                    amount = float(match.group(1))
                    
                    # Extract compound name before concentration
                    before_text = line[:match.start()].strip()
                    compound = self._extract_clean_compound_name(before_text)
                    
                    if compound and self._is_valid_ingredient_name(compound) and amount > 0:
                        ingredients.append({
                            'name': compound,
                            'concentration': amount,
                            'unit': unit,
                            'extraction_method': 'inline'
                        })
        
        return ingredients
    
    def _extract_ingredient_lists(self, content: str) -> List[Dict]:
        """Extract ingredient names from lists (even without concentrations)."""
        ingredients = []
        
        for line in content.split('\n'):
            line = line.strip()
            
            # Skip procedure text
            if any(proc in line.lower() for proc in self.procedure_indicators):
                continue
            
            # Skip numbers and units
            if re.match(r'^\d+\.?\d*$', line) or line.lower() in ['g', 'mg', 'ml']:
                continue
            
            if self._is_pure_compound_name(line):
                compound = self._clean_compound_name(line)
                if self._is_valid_ingredient_name(compound):
                    ingredients.append({
                        'name': compound,
                        'concentration': None,
                        'unit': None,
                        'extraction_method': 'list'
                    })
        
        return ingredients
    
    def _extract_preparation_instructions(self, instruction_section: str) -> str:
        """Extract and clean preparation instructions."""
        if not instruction_section.strip():
            return ""
        
        # Clean up instructions
        lines = []
        for line in instruction_section.split('\n'):
            line = line.strip()
            if line and not any(skip in line.lower() for skip in ['©', 'page', 'dsmz - all rights reserved']):
                lines.append(line)
        
        # Join into coherent instructions
        instructions = ' '.join(lines)
        
        # Clean up spacing and formatting
        instructions = re.sub(r'\s+', ' ', instructions)
        instructions = instructions.strip()
        
        return instructions
    
    def _is_pure_compound_name(self, text: str) -> bool:
        """Check if text is a pure compound name (no procedure contamination)."""
        if not text or len(text) < 2:
            return False
        
        text_lower = text.lower()
        
        # Exclude procedure text
        if any(proc in text_lower for proc in self.procedure_indicators):
            return False
        
        # Exclude obvious non-compounds
        exclusions = ['page', 'tel', 'fax', 'copyright', 'approved', 'reviewed', 'final']
        if any(excl in text_lower for excl in exclusions):
            return False
        
        # Include known compounds
        if any(compound in text_lower for compound in self.known_compounds):
            return True
        
        # Include chemical formulas
        if re.match(r'^[A-Z][a-z]?(?:\d*[A-Z][a-z]?\d*)*(?:\s*x?\s*\d*\s*H2O)?$', text):
            return True
        
        # Include chemical names with proper endings
        chemical_endings = ['chloride', 'sulfate', 'phosphate', 'nitrate', 'carbonate', 
                           'acetate', 'citrate', 'extract', 'peptone', 'acid', 'agar', 'solution']
        if any(text_lower.endswith(ending) for ending in chemical_endings):
            return True
        
        return False
    
    def _extract_clean_compound_name(self, text: str) -> Optional[str]:
        """Extract clean compound name from text."""
        if not text:
            return None
        
        # Clean the text
        text = text.strip()
        
        # Remove common prefixes
        text = re.sub(r'^\d+\.\s*', '', text)
        text = re.sub(r'^-\s*', '', text)
        
        # Look for compound patterns
        for pattern in self.compound_patterns:
            matches = list(re.finditer(pattern, text, re.IGNORECASE))
            if matches:
                # Take the longest match
                longest_match = max(matches, key=lambda m: len(m.group(1)))
                return self._clean_compound_name(longest_match.group(1))
        
        # Fallback: if it looks like a compound, use it
        if self._is_pure_compound_name(text):
            return self._clean_compound_name(text)
        
        return None
    
    def _clean_compound_name(self, name: str) -> str:
        """Clean and normalize compound names."""
        if not name:
            return ""
        
        # Handle hydrates
        name = re.sub(r'\s*x\s*(\d+)\s*H2O', r' \1-hydrate', name)
        name = re.sub(r'\s*\.\s*(\d+)\s*H2O', r' \1-hydrate', name)
        
        # Remove parenthetical brand info at end
        name = re.sub(r'\s*\([^)]*\)\s*$', '', name)
        
        # Clean spacing
        name = ' '.join(name.split())
        
        return name.strip()
    
    def _is_valid_ingredient_name(self, name: str) -> bool:
        """Validate that name is a genuine ingredient."""
        if not name or len(name) < 2:
            return False
        
        name_lower = name.lower()
        
        # Exclude procedure contamination
        if any(proc in name_lower for proc in self.procedure_indicators):
            return False
        
        # Exclude obvious junk
        junk_patterns = ['page', 'tel:', 'copyright', 'final', 'total', 'step']
        if any(junk in name_lower for junk in junk_patterns):
            return False
        
        # Accept known compounds
        if any(compound in name_lower for compound in self.known_compounds):
            return True
        
        # Accept chemical patterns
        if re.match(r'^[A-Z][a-z]?(?:\d*[A-Z][a-z]?\d*)*', name):
            return True
        
        # Accept chemical names
        chemical_indicators = ['chloride', 'sulfate', 'extract', 'peptone', 'acid', 'solution']
        if any(indicator in name_lower for indicator in chemical_indicators):
            return True
        
        return len(name) >= 3
    
    def _clean_and_deduplicate(self, ingredients: List[Dict]) -> List[Dict]:
        """Clean and remove duplicate ingredients."""
        seen = {}
        
        for ingredient in ingredients:
            name = ingredient['name'].lower().strip()
            
            if name in seen:
                # Keep version with concentration if available
                if ingredient.get('concentration') and not seen[name].get('concentration'):
                    seen[name] = ingredient
            else:
                seen[name] = ingredient
        
        # Return only ingredients with valid names
        return [ing for ing in seen.values() if self._is_valid_ingredient_name(ing['name'])]
    
    def _extract_medium_name(self, file_path: Path, content: str) -> str:
        """Extract medium name."""
        lines = content.split('\n')
        for line in lines[:3]:
            line = line.strip()
            if line and ':' in line and not line.lower().startswith('final'):
                return line
        
        return file_path.stem.replace('_', ' ').title()
    
    def _get_medium_id(self, file_path: Path) -> str:
        """Generate medium ID."""
        return file_path.stem
    
    def _get_source(self, file_path: Path) -> str:
        """Determine source."""
        filename = str(file_path).lower()
        if 'dsmz' in filename:
            return 'dsmz'
        elif 'ccap' in filename:
            return 'ccap'
        elif 'atcc' in filename:
            return 'atcc'
        elif 'jcm' in filename:
            return 'jcm'
        else:
            return 'unknown'


def main():
    """Test enhanced extraction on problematic files."""
    extractor = EnhancedMediaExtractor()
    
    # Test on files that had procedure contamination
    test_files = [
        'media_texts/dsmz_339.md',   # Had "Replace glucose with" contamination
        'media_texts/dsmz_1011c.md', # Good DSMZ tabular format
        'media_texts/dsmz_1737.md',  # Very low quality before
        'media_texts/dsmz_368.md'    # Failed extraction before
    ]
    
    for test_file in test_files:
        file_path = Path(test_file)
        if file_path.exists():
            print(f"\n=== Testing {file_path.name} ===")
            result = extractor.extract_media_data(file_path)
            
            if result:
                print(f"Medium: {result['medium_name']}")
                print(f"Ingredients found: {len(result['composition'])}")
                print(f"Has instructions: {result['extraction_stats']['has_instructions']}")
                print(f"Instruction length: {result['extraction_stats']['instruction_length']} chars")
                
                print(f"\nIngredients:")
                for i, comp in enumerate(result['composition'][:8]):
                    conc_str = f"{comp['concentration']} {comp['unit']}" if comp.get('concentration') else "no concentration"
                    method = comp.get('extraction_method', 'unknown')
                    print(f"  {i+1}. {comp['name']}: {conc_str} [{method}]")
                
                if len(result['composition']) > 8:
                    print(f"  ... and {len(result['composition']) - 8} more")
                
                if result['preparation_instructions']:
                    print(f"\nPreparation Instructions:")
                    instructions = result['preparation_instructions']
                    if len(instructions) > 200:
                        print(f"  {instructions[:200]}...")
                    else:
                        print(f"  {instructions}")
            else:
                print("No data extracted")


if __name__ == "__main__":
    main()