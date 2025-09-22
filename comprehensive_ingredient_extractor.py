#!/usr/bin/env python3
"""
Comprehensive ingredient extractor that ensures ALL ingredients are captured.
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


class ComprehensiveIngredientExtractor:
    """Extract ALL ingredients using multiple complementary strategies."""
    
    def __init__(self):
        # Comprehensive chemical compound patterns
        self.compound_patterns = [
            # Chemical formulas with hydrates
            r'\b([A-Z][a-z]?(?:\d*[A-Z][a-z]?\d*)*(?:\([A-Z][a-z]?\d*\)\d*)*(?:\s*x?\s*\d*\s*H2O)?)\b',
            # Named compounds with concentrations nearby
            r'\b([A-Z][a-z]+(?:\s+[a-z]+)*(?:\s+(?:chloride|sulfate|phosphate|nitrate|carbonate|bicarbonate|acetate|citrate|hydroxide|oxide|extract|peptone|acid)))\b',
            # Commercial/branded compounds
            r'\b([A-Z][a-z]+(?:\s+[a-z]+)*\s*\([^)]+\))\b',
            # Simple compound names near concentrations
            r'\b([A-Z][a-z]+(?:\s+[a-z]+){0,2})\s+(?=\d+\.?\d*\s*(?:g|mg|ml|mM|μM|M))',
        ]
        
        # Enhanced concentration patterns
        self.concentration_patterns = [
            (r'(\d+(?:\.\d+)?)\s*g/l', 'g/L'),
            (r'(\d+(?:\.\d+)?)\s*g/L', 'g/L'),
            (r'(\d+(?:\.\d+)?)\s*g\s*l-1', 'g/L'),
            (r'(\d+(?:\.\d+)?)\s*mg/l', 'mg/L'),
            (r'(\d+(?:\.\d+)?)\s*mg/L', 'mg/L'),
            (r'(\d+(?:\.\d+)?)\s*ml/l', 'ml/L'),
            (r'(\d+(?:\.\d+)?)\s*ml/L', 'ml/L'),
            (r'(\d+(?:\.\d+)?)\s*mM', 'mM'),
            (r'(\d+(?:\.\d+)?)\s*μM', 'μM'),
            (r'(\d+(?:\.\d+)?)\s*uM', 'μM'),
            (r'(\d+(?:\.\d+)?)\s*M(?!\w)', 'M'),
            (r'(\d+(?:\.\d+)?)\s*g', 'g'),
            (r'(\d+(?:\.\d+)?)\s*mg', 'mg'),
            (r'(\d+(?:\.\d+)?)\s*ml', 'ml'),
        ]
        
        # Known media compounds for validation
        self.known_compounds = {
            'nacl', 'kcl', 'cacl2', 'mgcl2', 'mgso4', 'k2hpo4', 'kh2po4', 'nh4cl',
            'na2co3', 'nahco3', 'glucose', 'sucrose', 'lactose', 'fructose', 'mannitol',
            'yeast extract', 'beef extract', 'peptone', 'tryptone', 'casein', 'agar',
            'biotin', 'thiamine', 'hepes', 'tris', 'edta', 'resazurin', 'cysteine',
            'sodium chloride', 'potassium chloride', 'calcium chloride', 'magnesium chloride',
            'magnesium sulfate', 'sodium carbonate', 'sodium bicarbonate'
        }
    
    def extract_all_ingredients(self, file_path: Path) -> Optional[Dict]:
        """Extract ALL ingredients using multiple strategies."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Use multiple extraction strategies
            all_ingredients = []
            
            # Strategy 1: Tabular format extraction (DSMZ style)
            tabular_ingredients = self._extract_tabular_format(content)
            all_ingredients.extend(tabular_ingredients)
            
            # Strategy 2: Inline concentration extraction
            inline_ingredients = self._extract_inline_concentrations(content)
            all_ingredients.extend(inline_ingredients)
            
            # Strategy 3: Compound list extraction (no concentrations)
            list_ingredients = self._extract_compound_lists(content)
            all_ingredients.extend(list_ingredients)
            
            # Strategy 4: Procedure text mining
            procedure_ingredients = self._extract_from_procedures(content)
            all_ingredients.extend(procedure_ingredients)
            
            # Strategy 5: Solution/stock references
            solution_ingredients = self._extract_solution_references(content)
            all_ingredients.extend(solution_ingredients)
            
            # Deduplicate and validate
            unique_ingredients = self._deduplicate_ingredients(all_ingredients)
            validated_ingredients = self._validate_all_ingredients(unique_ingredients)
            
            if validated_ingredients:
                return {
                    'medium_id': self._get_medium_id(file_path),
                    'medium_name': self._extract_medium_name(file_path, content),
                    'source': self._get_source(file_path),
                    'composition': validated_ingredients,
                    'extraction_strategies_used': self._count_strategies_used(all_ingredients)
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")
            return None
    
    def _extract_tabular_format(self, content: str) -> List[Dict]:
        """Extract from separated tabular format (compounds, amounts, units)."""
        ingredients = []
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        
        # Find compound section, amount section, unit section
        compound_lines = []
        amount_lines = []
        unit_lines = []
        
        current_section = 'compounds'
        
        for line in lines:
            # Stop at procedure text
            if re.match(r'^\d+\.\s', line) or 'dissolve' in line.lower() or 'add' in line.lower():
                break
            
            # Skip headers and metadata
            if any(skip in line.lower() for skip in ['final ph', 'final volume', 'page', '©']):
                continue
            
            if current_section == 'compounds':
                # Chemical compound names
                if self._looks_like_compound_name(line):
                    compound_lines.append(line)
                # Switch to amounts when we hit numbers
                elif re.match(r'^\d+\.?\d*$', line):
                    current_section = 'amounts'
                    amount_lines.append(float(line))
            
            elif current_section == 'amounts':
                # Numeric values
                if re.match(r'^\d+\.?\d*$', line):
                    amount_lines.append(float(line))
                # Switch to units when we hit unit indicators
                elif line.lower() in ['g', 'mg', 'ml', 'mm', 'μm', 'um']:
                    current_section = 'units'
                    unit_lines.append(line)
            
            elif current_section == 'units':
                # Unit indicators
                if line.lower() in ['g', 'mg', 'ml', 'mm', 'μm', 'um', 'g/l', 'mg/l', 'ml/l']:
                    unit_lines.append(line)
        
        # Match compounds with amounts and units
        min_length = min(len(compound_lines), len(amount_lines))
        
        for i in range(min_length):
            compound = self._clean_compound_name(compound_lines[i])
            amount = amount_lines[i]
            
            # Determine unit
            if i < len(unit_lines):
                unit = unit_lines[i]
                if unit.lower() in ['g', 'mg', 'ml']:
                    unit = f"{unit}/L"  # Convert to concentration
            else:
                unit = 'g/L'  # Default assumption
            
            if amount > 0:
                ingredients.append({
                    'name': compound,
                    'concentration': amount,
                    'unit': unit,
                    'strategy': 'tabular'
                })
        
        return ingredients
    
    def _extract_inline_concentrations(self, content: str) -> List[Dict]:
        """Extract compounds with concentrations on the same line."""
        ingredients = []
        
        for line in content.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            # Look for concentration patterns
            for pattern, unit in self.concentration_patterns:
                matches = list(re.finditer(pattern, line, re.IGNORECASE))
                
                for match in matches:
                    amount = float(match.group(1))
                    
                    # Look backwards for compound name
                    before_text = line[:match.start()]
                    
                    # Extract compound name using various strategies
                    compound = self._extract_compound_before_concentration(before_text)
                    
                    if compound and amount > 0:
                        ingredients.append({
                            'name': compound,
                            'concentration': amount,
                            'unit': unit,
                            'strategy': 'inline'
                        })
        
        return ingredients
    
    def _extract_compound_lists(self, content: str) -> List[Dict]:
        """Extract compound lists even without explicit concentrations."""
        ingredients = []
        lines = content.split('\n')
        
        # Look for sections that list compounds
        in_compound_section = False
        
        for line in lines:
            line = line.strip()
            
            # Detect compound list sections
            if any(marker in line.lower() for marker in ['composition', 'ingredients', 'components', 'medium']):
                in_compound_section = True
                continue
            
            # Stop at procedure sections
            if re.match(r'^\d+\.\s', line) or any(stop in line.lower() for stop in ['dissolve', 'autoclave', 'adjust ph']):
                in_compound_section = False
            
            if in_compound_section and self._looks_like_compound_name(line):
                compound = self._clean_compound_name(line)
                if compound:
                    ingredients.append({
                        'name': compound,
                        'concentration': None,
                        'unit': None,
                        'strategy': 'compound_list'
                    })
        
        return ingredients
    
    def _extract_from_procedures(self, content: str) -> List[Dict]:
        """Extract ingredients mentioned in procedure text."""
        ingredients = []
        
        # Common procedure patterns that mention ingredients
        procedure_patterns = [
            r'add\s+(\d+\.?\d*)\s*([a-zA-Z/]+)\s+([^.]+?)(?:\.|,|;)',
            r'supplement.*?with\s+(\d+\.?\d*)\s*([a-zA-Z/]+)\s+([^.]+?)(?:\.|,|;)',
            r'dissolve\s+(\d+\.?\d*)\s*([a-zA-Z/]+)\s+([^.]+?)(?:\.|,|;)',
            r'(\d+\.?\d*)\s*([a-zA-Z/]+)\s+([^.]+?)\s+(?:added|dissolved|supplemented)',
        ]
        
        for pattern in procedure_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            
            for match in matches:
                amount = float(match.group(1))
                unit = match.group(2)
                compound_text = match.group(3).strip()
                
                # Clean compound name
                compound = self._clean_compound_name(compound_text)
                
                if compound and amount > 0:
                    ingredients.append({
                        'name': compound,
                        'concentration': amount,
                        'unit': unit,
                        'strategy': 'procedure'
                    })
        
        return ingredients
    
    def _extract_solution_references(self, content: str) -> List[Dict]:
        """Extract ingredients from solution/stock references."""
        ingredients = []
        
        # Look for solution definitions
        solution_patterns = [
            r'solution\s+[A-Z]:\s*([^.]+)',
            r'stock\s+solution\s*\d*:\s*([^.]+)',
            r'([^.]+)\s+solution\s+\(([^)]+)\)',
        ]
        
        for pattern in solution_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            
            for match in matches:
                solution_text = match.group(1).strip()
                
                # Extract compounds from solution description
                solution_compounds = self._parse_solution_description(solution_text)
                
                for compound in solution_compounds:
                    ingredients.append({
                        'name': compound['name'],
                        'concentration': compound.get('concentration'),
                        'unit': compound.get('unit'),
                        'strategy': 'solution'
                    })
        
        return ingredients
    
    def _parse_solution_description(self, text: str) -> List[Dict]:
        """Parse compound description from solution text."""
        compounds = []
        
        # Look for compound patterns in solution description
        for pattern in self.compound_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            
            for match in matches:
                compound_name = match.group(1).strip()
                
                if self._looks_like_compound_name(compound_name):
                    compounds.append({
                        'name': self._clean_compound_name(compound_name),
                        'concentration': None,
                        'unit': None
                    })
        
        return compounds
    
    def _extract_compound_before_concentration(self, text: str) -> Optional[str]:
        """Extract compound name before a concentration."""
        # Remove common prefixes and clean up
        text = text.strip()
        
        # Look for compound patterns
        for pattern in self.compound_patterns:
            matches = list(re.finditer(pattern, text, re.IGNORECASE))
            
            if matches:
                # Take the last match (closest to concentration)
                compound = matches[-1].group(1).strip()
                
                if self._looks_like_compound_name(compound):
                    return self._clean_compound_name(compound)
        
        # Fallback: take last few words that look chemical
        words = text.split()
        if words:
            # Try combinations of last words
            for length in range(min(3, len(words)), 0, -1):
                potential_compound = ' '.join(words[-length:])
                
                if self._looks_like_compound_name(potential_compound):
                    return self._clean_compound_name(potential_compound)
        
        return None
    
    def _looks_like_compound_name(self, text: str) -> bool:
        """Check if text looks like a chemical compound name."""
        if not text or len(text) < 2:
            return False
        
        text_lower = text.lower()
        
        # Exclude obvious non-compounds
        exclusions = [
            'page', 'tel', 'fax', 'email', 'www', 'copyright', 'dsmz', 'approved',
            'reviewed', 'created', 'revision', 'autoclave', 'sterilize', 'dissolve',
            'final', 'volume', 'adjust', 'prepare', 'add', 'mix', 'solution a',
            'solution b', 'solution c', 'solution d', 'solution e'
        ]
        
        if any(excl in text_lower for excl in exclusions):
            return False
        
        # Must start with capital or known chemical indicator
        if not (text[0].isupper() or any(ind in text_lower for ind in ['ph', 'h2o', 'co2'])):
            return False
        
        # Positive indicators
        if any(ind in text_lower for ind in self.known_compounds):
            return True
        
        # Chemical patterns
        if re.match(r'^[A-Z][a-z]?(?:\d*[A-Z][a-z]?\d*)*', text):
            return True
        
        # Common chemical endings
        chemical_endings = ['chloride', 'sulfate', 'phosphate', 'nitrate', 'carbonate', 
                           'acetate', 'citrate', 'extract', 'peptone', 'acid', 'ose']
        
        if any(text_lower.endswith(ending) for ending in chemical_endings):
            return True
        
        return len(text) >= 3 and text.isalpha()
    
    def _clean_compound_name(self, name: str) -> str:
        """Clean and normalize compound names."""
        if not name:
            return ""
        
        # Remove common prefixes/suffixes
        name = re.sub(r'^\d+\.\s*', '', name)  # Remove numbering
        name = re.sub(r'\s*\([^)]*\)\s*$', '', name)  # Remove parenthetical info at end
        name = re.sub(r'^\s*-\s*', '', name)  # Remove leading dash
        
        # Handle hydrates properly
        name = re.sub(r'\s*x\s*(\d+)\s*H2O', r' \1-hydrate', name)
        name = re.sub(r'\s*\.\s*(\d+)\s*H2O', r' \1-hydrate', name)
        
        # Clean up spacing
        name = ' '.join(name.split())
        
        return name.strip()
    
    def _deduplicate_ingredients(self, ingredients: List[Dict]) -> List[Dict]:
        """Remove duplicate ingredients, keeping the best version."""
        seen = {}
        
        for ingredient in ingredients:
            name = ingredient['name'].lower().strip()
            
            if name in seen:
                # Keep the version with concentration if available
                if ingredient.get('concentration') and not seen[name].get('concentration'):
                    seen[name] = ingredient
            else:
                seen[name] = ingredient
        
        return list(seen.values())
    
    def _validate_all_ingredients(self, ingredients: List[Dict]) -> List[Dict]:
        """Validate ingredients with lenient criteria to capture everything."""
        validated = []
        
        for ingredient in ingredients:
            name = ingredient.get('name', '').strip()
            concentration = ingredient.get('concentration')
            unit = ingredient.get('unit')
            
            # Very lenient validation - only exclude obvious junk
            if not name or len(name) < 2:
                continue
            
            # Exclude obvious non-chemical text
            if any(bad in name.lower() for bad in ['page', 'copyright', 'tel:', 'fax:']):
                continue
            
            # Include everything else, even without concentrations
            validated.append({
                'name': name,
                'concentration': concentration if concentration else 0.0,
                'unit': unit if unit else 'unknown'
            })
        
        return validated
    
    def _count_strategies_used(self, ingredients: List[Dict]) -> Dict[str, int]:
        """Count how many ingredients came from each extraction strategy."""
        strategy_counts = {}
        
        for ingredient in ingredients:
            strategy = ingredient.get('strategy', 'unknown')
            strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1
        
        return strategy_counts
    
    def _extract_medium_name(self, file_path: Path, content: str) -> str:
        """Extract medium name."""
        lines = content.split('\n')
        for line in lines[:5]:
            line = line.strip()
            if line and ':' in line:
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
    """Test comprehensive extraction on problematic files."""
    extractor = ComprehensiveIngredientExtractor()
    
    # Test on previously failed files
    test_files = [
        'media_texts/dsmz_1626.md',
        'media_texts/dsmz_368.md',
        'media_texts/dsmz_1737.md',
        'media_texts/dsmz_339.md'
    ]
    
    for test_file in test_files:
        file_path = Path(test_file)
        if file_path.exists():
            print(f"\n=== Testing {file_path.name} ===")
            result = extractor.extract_all_ingredients(file_path)
            
            if result:
                print(f"Medium: {result['medium_name']}")
                print(f"Total ingredients: {len(result['composition'])}")
                print(f"Strategies used: {result['extraction_strategies_used']}")
                
                # Show first 10 ingredients
                for i, comp in enumerate(result['composition'][:10]):
                    conc_str = f"{comp['concentration']} {comp['unit']}" if comp['concentration'] else "no concentration"
                    print(f"  {i+1}. {comp['name']}: {conc_str}")
                
                if len(result['composition']) > 10:
                    print(f"  ... and {len(result['composition']) - 10} more")
            else:
                print("Still no ingredients extracted")


if __name__ == "__main__":
    main()