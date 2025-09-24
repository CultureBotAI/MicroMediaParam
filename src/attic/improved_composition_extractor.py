#!/usr/bin/env python3
"""
Improved composition extractor with format-specific parsing and better chemical recognition.
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


class ImprovedCompositionExtractor:
    """Improved extractor with format-specific parsing and chemical validation."""
    
    def __init__(self):
        # Known chemical databases for validation
        self.known_chemicals = self._load_chemical_database()
        
        # Chemical name patterns (improved)
        self.chemical_patterns = [
            # Salts with proper chemical endings
            r'\b([A-Z][a-z]*(?:\s+[a-z]+)*(?:\s+(?:chloride|sulfate|phosphate|nitrate|carbonate|bicarbonate|acetate|citrate|hydroxide|oxide)))\b',
            # Chemical compounds with formulas
            r'\b([A-Z][a-z]*(?:[A-Z][a-z]*)*(?:\([IV|V|VI|II|III]*\))?(?:\s*\d*[A-Z][a-z]*\d*)*)\b',
            # Common media components
            r'\b(peptone|tryptone|yeast extract|beef extract|casein|glucose|sucrose|lactose|agar|gellan|agarose)\b',
            # Elements and simple compounds
            r'\b([A-Z][a-z]?(?:[A-Z][a-z]?\d*)*)\b(?=\s+\d+\.?\d*\s*(?:g|mg|μg|ml|μl|mM|μM|M))'
        ]
        
        # Units and concentration patterns
        self.concentration_patterns = {
            'g/L': r'(\d+(?:\.\d+)?)\s*g(?:/L|/l|/litre|/liter|\s+per\s+(?:L|l|litre|liter))',
            'mg/L': r'(\d+(?:\.\d+)?)\s*mg(?:/L|/l|/litre|/liter|\s+per\s+(?:L|l|litre|liter))',
            'ml/L': r'(\d+(?:\.\d+)?)\s*ml(?:/L|/l|/litre|/liter|\s+per\s+(?:L|l|litre|liter))',
            'mM': r'(\d+(?:\.\d+)?)\s*mM\b',
            'μM': r'(\d+(?:\.\d+)?)\s*[μu]M\b',
            'M': r'(\d+(?:\.\d+)?)\s*M\b(?!g|l|[a-z])',
            'g': r'(\d+(?:\.\d+)?)\s*g\b(?!/)',
            'mg': r'(\d+(?:\.\d+)?)\s*mg\b(?!/)',
            'ml': r'(\d+(?:\.\d+)?)\s*ml\b(?!/)',
        }
        
        # Noise patterns to filter out
        self.noise_patterns = [
            r'\b(?:page|tel|fax|email|www|copyright|ltd|inc|gmbh|reviewed|created|approved|revision)\b',
            r'\b(?:autoclave|sterilize|adjust|filter|add|mix|dissolve|distribute|prepare)\b',
            r'\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b',
            r'\b(?:and|or|to|of|for|with|from|under|into|upon|before|after|during)\b',
            r'\b(?:solution|medium|tube|vial|atmosphere|gas|mixture|temperature)\b',
            r'\bpH\s+\d+',
            r'\d+\s*°C',
            r'\d+\s*psi',
            r'^\s*[a-z]\s*$',  # single letters
            r'^\s*\d+\s*$',    # standalone numbers
        ]
    
    def _load_chemical_database(self) -> Set[str]:
        """Load known chemical names for validation."""
        # Basic chemical database - can be expanded
        chemicals = {
            # Common salts
            'sodium chloride', 'potassium chloride', 'calcium chloride', 'magnesium chloride',
            'sodium sulfate', 'potassium sulfate', 'calcium sulfate', 'magnesium sulfate',
            'sodium phosphate', 'potassium phosphate', 'calcium phosphate',
            'sodium carbonate', 'potassium carbonate', 'calcium carbonate',
            'sodium bicarbonate', 'potassium bicarbonate',
            'sodium nitrate', 'potassium nitrate', 'calcium nitrate',
            'sodium acetate', 'potassium acetate', 'calcium acetate',
            'ferric chloride', 'ferrous sulfate', 'ferric citrate',
            'ammonium chloride', 'ammonium sulfate', 'ammonium nitrate',
            
            # Media components
            'peptone', 'tryptone', 'casitone', 'yeast extract', 'beef extract',
            'malt extract', 'corn steep liquor', 'soy peptone',
            'glucose', 'sucrose', 'lactose', 'fructose', 'maltose', 'mannitol',
            'glycerol', 'agar', 'gellan gum', 'agarose',
            
            # Vitamins and cofactors
            'biotin', 'thiamine', 'riboflavin', 'niacin', 'pyridoxine',
            'cyanocobalamin', 'folic acid', 'pantothenic acid',
            
            # Other compounds
            'hepes', 'tris', 'edta', 'dithionite', 'cysteine',
            'ascorbic acid', 'citric acid', 'acetic acid'
        }
        
        # Add variations (with/without spaces, different cases)
        expanded = set()
        for chem in chemicals:
            expanded.add(chem.lower())
            expanded.add(chem.replace(' ', ''))
            expanded.add(chem.title())
        
        return expanded
    
    def extract_from_markdown_improved(self, file_path: Path) -> Optional[Dict]:
        """Improved extraction from markdown files with format-specific parsing."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            source = self._get_source(file_path)
            
            # Use format-specific parsing
            if source == 'dsmz':
                compositions = self._parse_dsmz_improved(content)
            elif source == 'ccap':
                compositions = self._parse_ccap_improved(content)
            else:
                compositions = self._parse_generic_improved(content)
            
            # Filter and validate compositions
            validated_compositions = self._validate_compositions(compositions)
            
            if validated_compositions:
                return {
                    'medium_id': self._get_medium_id(file_path),
                    'medium_name': self._extract_medium_name_improved(file_path, content),
                    'source': source,
                    'composition': validated_compositions
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
            
            # Validate compositions
            validated_compositions = self._validate_compositions(compositions)
            
            if validated_compositions:
                return {
                    'medium_id': self._get_medium_id(file_path),
                    'medium_name': medium_name,
                    'source': self._get_source(file_path),
                    'composition': validated_compositions
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")
            return None
    
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
    
    def _parse_dsmz_improved(self, content: str) -> List[Dict]:
        """Improved DSMZ format parsing."""
        compositions = []
        lines = content.split('\n')
        
        # Parse the main tabular format (compounds, amounts, units in separate sections)
        table_compositions = self._extract_dsmz_tabular_format(lines)
        compositions.extend(table_compositions)
        
        # Look for supplement information (most reliable)
        supplement_compositions = self._extract_dsmz_supplements(content)
        compositions.extend(supplement_compositions)
        
        # Look for direct compound mentions with concentrations
        direct_compositions = self._extract_direct_compounds(content)
        compositions.extend(direct_compositions)
        
        return compositions
    
    def _extract_dsmz_tabular_format(self, lines: List[str]) -> List[Dict]:
        """Parse DSMZ tabular format: compounds, then amounts, then units."""
        compositions = []
        
        # Find the main composition section (before procedure text)
        compound_lines = []
        amount_lines = []
        unit_lines = []
        
        # State tracking
        collecting_compounds = True
        collecting_amounts = False
        collecting_units = False
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Skip empty lines and headers
            if not line or 'Final pH:' in line or 'Final volume:' in line:
                continue
            
            # Stop at procedure text (starts with numbers like "1. Dissolve")
            if re.match(r'^\d+\.\s', line):
                break
            
            # Stop at copyright/page info
            if any(marker in line for marker in ['©', 'Page', 'DSMZ - All rights reserved']):
                break
            
            # Detect sections based on content patterns
            if collecting_compounds:
                # Check if this looks like a compound name
                if self._looks_like_dsmz_compound(line):
                    compound_lines.append(line)
                # If we hit a numeric line, switch to amounts
                elif re.match(r'^\d+\.?\d*$', line):
                    collecting_compounds = False
                    collecting_amounts = True
                    amount_lines.append(float(line))
            
            elif collecting_amounts:
                # Collect numeric values
                if re.match(r'^\d+\.?\d*$', line):
                    amount_lines.append(float(line))
                # If we hit a unit line, switch to units
                elif line in ['g', 'mg', 'ml', 'mM', 'μM', 'M']:
                    collecting_amounts = False
                    collecting_units = True
                    unit_lines.append(line)
            
            elif collecting_units:
                # Collect unit values
                if line in ['g', 'mg', 'ml', 'mM', 'μM', 'M', 'g/l', 'mg/l', 'ml/l']:
                    unit_lines.append(line)
        
        
        # Match compounds with amounts and units
        min_length = min(len(compound_lines), len(amount_lines))
        
        for i in range(min_length):
            compound = compound_lines[i]
            amount = amount_lines[i]
            
            # Determine unit (default to g/L if not enough units specified)
            if i < len(unit_lines):
                unit = unit_lines[i]
                # Convert single letter units to concentration units
                if unit == 'g':
                    unit = 'g/L'
                elif unit == 'mg':
                    unit = 'mg/L'
                elif unit == 'ml':
                    unit = 'ml/L'
            else:
                unit = 'g/L'  # Default for DSMZ format
            
            # Clean and validate compound name
            clean_compound = self._clean_dsmz_compound_name(compound)
            
            if self._is_valid_chemical_name(clean_compound) and amount > 0:
                compositions.append({
                    'name': clean_compound,
                    'concentration': amount,
                    'unit': unit
                })
        
        return compositions
    
    def _looks_like_dsmz_compound(self, line: str) -> bool:
        """Check if line looks like a DSMZ compound name."""
        # Should not be a pure number
        if re.match(r'^\d+\.?\d*$', line):
            return False
        
        # Should not be a pure unit
        if line in ['g', 'mg', 'ml', 'mM', 'μM', 'M']:
            return False
        
        # Should start with capital letter or known chemical
        if not re.match(r'^[A-Z]', line):
            return False
        
        # Should not be procedure text
        if re.match(r'^\d+\.\s', line):
            return False
        
        # Should look like a chemical compound
        chemical_indicators = [
            'Cl', 'SO4', 'PO4', 'NO3', 'CO3', 'HCO3', 'CH3COO', 'C6H12O6',
            'extract', 'solution', 'acid', 'hydroxide', 'oxide', 'sulfate',
            'chloride', 'phosphate', 'nitrate', 'carbonate', 'acetate', 'water'
        ]
        
        # More lenient for DSMZ - if it has capital letters and looks chemical, accept it
        if any(indicator in line for indicator in chemical_indicators):
            return True
        
        # Accept compound formulas like NaCl, K2HPO4, etc.
        if re.match(r'^[A-Z][a-z]?[A-Z0-9()x\s\-]+', line):
            return True
        
        return len(line) > 2 and not line.isdigit()
    
    def _clean_dsmz_compound_name(self, compound: str) -> str:
        """Clean DSMZ compound names."""
        # Handle hydrates
        compound = re.sub(r'\s*x\s*(\d+)\s*H2O', r' \1-hydrate', compound)
        compound = re.sub(r'\s*\.\s*(\d+)\s*H2O', r' \1-hydrate', compound)
        
        # Handle chemical formulas in parentheses
        compound = re.sub(r'\(([IV|V|VI|II|III]+)\)', r'(\1)', compound)
        
        # Clean up spacing
        compound = ' '.join(compound.split())
        
        return compound.strip()
    
    def _extract_dsmz_supplements(self, content: str) -> List[Dict]:
        """Extract supplement information from DSMZ format."""
        compositions = []
        
        # Pattern for supplement lines like "Supplement medium with 1.00 g/l yeast extract"
        supplement_pattern = r'Supplement.*?with\s+(\d+(?:\.\d+)?)\s*([a-zA-Z/]+)\s+([^.]+)'
        
        for match in re.finditer(supplement_pattern, content, re.IGNORECASE):
            amount = float(match.group(1))
            unit = match.group(2)
            compound_text = match.group(3).strip()
            
            # Clean compound name
            compound = re.sub(r'\s+added.*$', '', compound_text)
            compound = re.sub(r'\s+from.*$', '', compound)
            compound = compound.strip()
            
            if self._is_valid_chemical_name(compound):
                compositions.append({
                    'name': compound,
                    'concentration': amount,
                    'unit': unit
                })
        
        return compositions
    
    def _extract_dsmz_tables(self, content: str) -> List[Dict]:
        """Extract compounds from DSMZ tabular sections."""
        compositions = []
        lines = content.split('\n')
        
        # Look for solution sections with compound lists
        in_solution = False
        solution_compounds = []
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Detect solution headers
            if re.match(r'^Solution [A-Z]', line):
                in_solution = True
                solution_compounds = []
                continue
            
            # End of solution when we hit empty line or another section
            if in_solution and (not line or re.match(r'^\d+\.\s', line) or re.match(r'^Solution [A-Z]', line)):
                # Process collected compounds
                compositions.extend(self._process_solution_compounds(solution_compounds, lines, i))
                in_solution = False
                solution_compounds = []
            
            # Collect compound names in solution
            if in_solution and line and not re.match(r'^\d+\.?\d*$', line) and not re.match(r'^[a-z]+$', line):
                # Check if it looks like a chemical compound
                if self._looks_like_chemical_compound(line):
                    solution_compounds.append(line)
        
        return compositions
    
    def _process_solution_compounds(self, compounds: List[str], all_lines: List[str], start_idx: int) -> List[Dict]:
        """Process compounds found in a solution section with their amounts."""
        compositions = []
        
        # Look ahead for amounts and units
        amount_lines = []
        unit_lines = []
        
        for i in range(start_idx, min(start_idx + 20, len(all_lines))):
            line = all_lines[i].strip()
            
            # Collect numeric values
            if re.match(r'^\d+\.?\d*$', line):
                amount_lines.append(float(line))
            
            # Collect unit lines
            elif line in ['g', 'mg', 'ml', 'g/l', 'mg/l', 'ml/l', 'mM', 'μM']:
                unit_lines.append(line)
        
        # Match compounds with amounts and units
        for i, compound in enumerate(compounds):
            if i < len(amount_lines):
                amount = amount_lines[i]
                unit = unit_lines[i] if i < len(unit_lines) else 'g/L'
                
                compositions.append({
                    'name': compound,
                    'concentration': amount,
                    'unit': unit
                })
        
        return compositions
    
    def _extract_direct_compounds(self, content: str) -> List[Dict]:
        """Extract compounds with directly attached concentrations."""
        compositions = []
        
        # Pattern for compound concentration unit on same line
        for pattern_name, pattern in self.concentration_patterns.items():
            for match in re.finditer(pattern, content):
                amount = float(match.group(1))
                
                # Look backwards for compound name
                start_pos = max(0, match.start() - 100)
                before_text = content[start_pos:match.start()]
                
                # Extract potential compound name
                words = before_text.split()
                if words:
                    # Take last few words as potential compound name
                    for length in range(min(4, len(words)), 0, -1):
                        potential_compound = ' '.join(words[-length:])
                        if self._is_valid_chemical_name(potential_compound):
                            compositions.append({
                                'name': potential_compound,
                                'concentration': amount,
                                'unit': pattern_name
                            })
                            break
        
        return compositions
    
    def _parse_ccap_improved(self, content: str) -> List[Dict]:
        """Improved CCAP format parsing."""
        compositions = []
        
        # CCAP files often have stock solutions and final concentrations
        # Focus on final medium composition section
        
        lines = content.split('\n')
        in_medium_section = False
        
        for line in lines:
            line = line.strip()
            
            # Look for medium composition markers
            if any(marker in line.lower() for marker in ['medium', 'final', 'per litre', 'per liter']):
                in_medium_section = True
                continue
            
            if in_medium_section and line:
                # Try to extract compound and concentration from line
                comp = self._extract_compound_from_line(line)
                if comp:
                    compositions.append(comp)
        
        return compositions
    
    def _extract_compound_from_line(self, line: str) -> Optional[Dict]:
        """Extract compound name and concentration from a single line."""
        # Try each concentration pattern
        for unit, pattern in self.concentration_patterns.items():
            match = re.search(pattern, line)
            if match:
                amount = float(match.group(1))
                
                # Extract compound name (everything before the amount)
                compound_part = line[:match.start()].strip()
                
                # Clean up compound name
                compound = self._clean_compound_name(compound_part)
                
                if self._is_valid_chemical_name(compound):
                    return {
                        'name': compound,
                        'concentration': amount,
                        'unit': unit
                    }
        
        return None
    
    def _parse_generic_improved(self, content: str) -> List[Dict]:
        """Improved generic format parsing."""
        compositions = []
        
        # Try line-by-line extraction
        for line in content.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            comp = self._extract_compound_from_line(line)
            if comp:
                compositions.append(comp)
        
        return compositions
    
    def _clean_compound_name(self, name: str) -> str:
        """Clean and normalize compound names."""
        # Remove common prefixes/suffixes
        name = re.sub(r'^(stock\s+|solution\s+)', '', name, flags=re.IGNORECASE)
        name = re.sub(r'\s+(stock|solution)$', '', name, flags=re.IGNORECASE)
        
        # Remove numbers at start/end that aren't part of chemical name
        name = re.sub(r'^\d+\.\s*', '', name)
        name = re.sub(r'\s*\(\d+\)$', '', name)
        
        # Clean up spacing
        name = ' '.join(name.split())
        
        return name.strip()
    
    def _is_valid_chemical_name(self, name: str) -> bool:
        """Validate if a name looks like a chemical compound."""
        if not name or len(name) < 2:
            return False
        
        name_lower = name.lower()
        
        # Check against noise patterns (but be more lenient)
        strict_noise_patterns = [
            r'\b(?:page|tel|fax|email|www|copyright|ltd|inc|gmbh|reviewed|created|approved|revision)\b',
            r'\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b',
            r'^\s*[a-z]\s*$',  # single letters only
        ]
        
        for noise_pattern in strict_noise_patterns:
            if re.search(noise_pattern, name_lower):
                return False
        
        # Check against known chemicals
        if name_lower in self.known_chemicals:
            return True
        
        # Chemical formula patterns (like NaCl, K2HPO4, CaCl2, etc.)
        if re.match(r'^[A-Z][a-z]?(?:\d*[A-Z][a-z]?\d*)*(?:\s*\d*-?hydrate)?$', name):
            return True
        
        # Chemical formulas with parentheses (like Fe(NH4)2(SO4)2)
        if re.match(r'^[A-Z][a-z]?(?:\([A-Z][a-z]?\d*\)\d*)*(?:[A-Z][a-z]?\d*)*(?:\s*\d*-?hydrate)?$', name):
            return True
        
        # Pattern-based validation for common chemical names
        chemical_indicators = [
            'acid', 'chloride', 'sulfate', 'phosphate', 'nitrate', 'carbonate',
            'bicarbonate', 'acetate', 'citrate', 'hydroxide', 'oxide',
            'sodium', 'potassium', 'calcium', 'magnesium', 'iron', 'zinc',
            'copper', 'manganese', 'cobalt', 'nickel', 'ammonium',
            'glucose', 'sucrose', 'lactose', 'peptone', 'extract', 'agar',
            'water', 'solution', 'pyruvate', 'lactate', 'dithionite', 'vitamin'
        ]
        
        if any(indicator in name_lower for indicator in chemical_indicators):
            return True
        
        # Accept compound names that start with capital and contain chemical elements
        common_elements = ['Na', 'K', 'Ca', 'Mg', 'Fe', 'Cl', 'S', 'P', 'N', 'C', 'H', 'O']
        if any(element in name for element in common_elements):
            return True
        
        # Check if it follows chemical naming patterns
        if re.match(r'^[A-Z][a-z]*(?:\s+[a-z]+)*$', name):
            return True
        
        return False
    
    def _looks_like_chemical_compound(self, text: str) -> bool:
        """Check if text looks like a chemical compound name."""
        if not text or len(text) < 2:
            return False
        
        # Must start with capital letter or common chemical prefix
        if not re.match(r'^[A-Z]', text):
            return False
        
        # Should not be obviously non-chemical
        non_chemical_patterns = [
            r'^\d+$',  # just numbers
            r'^[A-Z]$',  # single letters
            r'Solution',
            r'Medium',
            r'Page',
            r'Tel:',
            r'Fax:',
        ]
        
        for pattern in non_chemical_patterns:
            if re.match(pattern, text):
                return False
        
        return True
    
    def _validate_compositions(self, compositions: List[Dict]) -> List[Dict]:
        """Validate and filter compositions."""
        validated = []
        
        for comp in compositions:
            name = comp.get('name', '').strip()
            concentration = comp.get('concentration', 0)
            unit = comp.get('unit', '')
            
            # Basic validation
            if not name or not isinstance(concentration, (int, float)) or concentration <= 0:
                continue
            
            # Chemical name validation
            if not self._is_valid_chemical_name(name):
                continue
            
            # Reasonable concentration range
            if concentration > 1000:  # unreasonably high
                continue
            
            # Valid units
            valid_units = ['g/L', 'mg/L', 'ml/L', 'mM', 'μM', 'M', 'g', 'mg', 'ml']
            if unit not in valid_units:
                continue
            
            validated.append(comp)
        
        return validated
    
    def _extract_medium_name_improved(self, file_path: Path, content: str) -> str:
        """Improved medium name extraction."""
        # Try to find medium name in first few lines
        lines = content.split('\n')
        for line in lines[:5]:
            line = line.strip()
            if line and not re.match(r'^\d', line):
                # Clean up the name
                name = re.sub(r'^\d+[a-z]*:', '', line).strip()
                if name:
                    return name
        
        # Fallback to filename
        return file_path.stem.replace('_', ' ').title()
    
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
    """Test improved extraction on a sample of files."""
    extractor = ImprovedCompositionExtractor()
    
    # Test on multiple files to verify improvements
    test_files = [
        'media_texts/dsmz_1011c.md',
        'media_texts/dsmz_195c.md',
        'media_texts/ccap_BG11.md'
    ]
    
    total_extracted = 0
    
    for test_file in test_files:
        file_path = Path(test_file)
        if file_path.exists():
            print(f"\n=== Testing {file_path.name} ===")
            result = extractor.extract_from_markdown_improved(file_path)
            if result:
                print(f"Medium: {result['medium_name']}")
                print(f"Compounds found: {len(result['composition'])}")
                total_extracted += len(result['composition'])
                for comp in result['composition'][:5]:  # Show first 5
                    print(f"  - {comp['name']}: {comp['concentration']} {comp['unit']}")
                if len(result['composition']) > 5:
                    print(f"  ... and {len(result['composition']) - 5} more")
            else:
                print("No valid compositions extracted")
    
    print(f"\nTotal compounds extracted: {total_extracted}")


if __name__ == "__main__":
    main()