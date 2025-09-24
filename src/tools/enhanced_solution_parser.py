#!/usr/bin/env python3
"""
Enhanced parser for DSMZ solution PDFs with improved chemical component extraction.
"""

import re
import json
import logging
from pathlib import Path
from typing import List, Dict, Tuple, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EnhancedSolutionParser:
    def __init__(self):
        self.chemical_patterns = self.compile_chemical_patterns()
        self.solution_name_patterns = self.compile_name_patterns()
        self.concentration_patterns = self.compile_concentration_patterns()
    
    def compile_chemical_patterns(self) -> List[Tuple[str, str]]:
        """Compile patterns for recognizing chemical compounds."""
        
        patterns = [
            # Standard chemical formulas
            (r'\b([A-Z][a-z]?(?:[A-Z][a-z]?)*(?:\d+)*(?:\s*[·\.\-]\s*\d*H2O)?)\s+([0-9.,]+)\s*(g|mg|μg|ml|µl|l|M|mM|µM|%)\b', 'formula_concentration'),
            
            # Chemical names with hydrates
            (r'\b([A-Za-z\s\-\(\)]+(?:\s+(?:monohydrate|dihydrate|trihydrate|tetrahydrate|pentahydrate|hexahydrate|heptahydrate|octahydrate|nonahydrate|decahydrate|\d+\-?hydrate|x\s*H2O|·\s*\d*H2O))?)\s+([0-9.,]+)\s*(g|mg|μg|ml|µl|l|M|mM|µM|%)', 'name_concentration'),
            
            # Common chemical compound names
            (r'\b(sodium\s+[a-z]+|potassium\s+[a-z]+|calcium\s+[a-z]+|magnesium\s+[a-z]+|iron\s+[a-z]+|copper\s+[a-z]+|zinc\s+[a-z]+|manganese\s+[a-z]+)\s+([0-9.,]+)\s*(g|mg|μg|ml|µl|l|M|mM|µM|%)', 'compound_name'),
            
            # EDTA and special compounds
            (r'\b(EDTA|Na2EDTA|sodium\s+EDTA|disodium\s+EDTA|ethylenediaminetetraacetic\s+acid)\s+([0-9.,]+)\s*(g|mg|μg|ml|µl|l|M|mM|µM|%)', 'special_compound'),
            
            # Vitamin compounds
            (r'\b(vitamin\s+[A-K]\d*|thiamine|riboflavin|niacin|pantothenic\s+acid|pyridoxine|biotin|folic\s+acid|cobalamin|ascorbic\s+acid)\s+([0-9.,]+)\s*(g|mg|μg|ml|µl|l|M|mM|µM|%)', 'vitamin'),
            
            # Acids and bases
            (r'\b([a-z]+ic\s+acid|[a-z]+\s+acid|sodium\s+hydroxide|potassium\s+hydroxide|NaOH|KOH)\s+([0-9.,]+)\s*(g|mg|μg|ml|µl|l|M|mM|µM|%)', 'acid_base'),
        ]
        
        return [(re.compile(pattern, re.IGNORECASE), pattern_type) for pattern, pattern_type in patterns]
    
    def compile_name_patterns(self) -> List[re.Pattern]:
        """Compile patterns for extracting solution names."""
        
        patterns = [
            r'"([^"]*solution[^"]*)"',
            r'([A-Za-z\s\-\']+solution)',
            r'Solution\s*:\s*([^\n]+)',
            r'Name\s*:\s*([^\n]+)',
            r'^([A-Z][A-Za-z\s\-\']+solution)\s*$'
        ]
        
        return [re.compile(pattern, re.IGNORECASE | re.MULTILINE) for pattern in patterns]
    
    def compile_concentration_patterns(self) -> List[re.Pattern]:
        """Compile patterns for extracting concentration information."""
        
        patterns = [
            # Dissolve X g of Y in Z ml water
            r'dissolve\s+([0-9.,]+)\s*(g|mg|μg)\s+(?:of\s+)?([^,\n]+?)(?:\s+in\s+([0-9.,]+)\s*(ml|l))?',
            
            # Add X g Y
            r'add\s+([0-9.,]+)\s*(g|mg|μg|ml|l)\s+([^,\n]+)',
            
            # X g/l Y or Y X g/l
            r'([0-9.,]+)\s*(g|mg|μg)\s*/\s*l\s+([^,\n]+)|([^,\n]+)\s+([0-9.,]+)\s*(g|mg|μg)\s*/\s*l',
            
            # Per liter concentrations
            r'([^,\n]+?)\s*:\s*([0-9.,]+)\s*(g|mg|μg|ml|l)\s*/\s*l',
        ]
        
        return [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
    
    def extract_solution_name(self, content: str) -> str:
        """Extract solution name with improved pattern matching."""
        
        # Try JSON-like patterns first (common in DSMZ)
        json_pattern = re.search(r'"([^"]*solution[^"]*)"', content, re.IGNORECASE)
        if json_pattern:
            name = json_pattern.group(1).strip()
            if len(name) > 5:  # Reasonable length
                return name
        
        # Try other patterns
        for pattern in self.solution_name_patterns:
            match = pattern.search(content)
            if match:
                name = match.group(1).strip()
                if len(name) > 5 and not any(unwanted in name.lower() for unwanted in ['page', 'table', 'figure']):
                    return name
        
        return "Unknown Solution"
    
    def clean_chemical_name(self, name: str) -> str:
        """Clean and standardize chemical names."""
        
        # Remove unwanted text
        name = re.sub(r'\b(dissolve|add|mix|in|water|solution|stock)\b', '', name, flags=re.IGNORECASE)
        name = re.sub(r'[^\w\s\-\(\)·\.]', ' ', name)  # Keep chemical symbols
        name = re.sub(r'\s+', ' ', name)  # Normalize spaces
        name = name.strip()
        
        # Skip if too short or contains unwanted patterns
        if (len(name) < 3 or 
            any(word in name.lower() for word in ['table', 'page', 'figure', 'step', 'then', 'final', 'total', 'per', 'about', 'approximately'])):
            return None
        
        # Standardize chemical names
        name_standardizations = {
            'sodium edta': 'Na2EDTA',
            'disodium edta': 'Na2EDTA',
            'ferrous sulfate': 'FeSO4',
            'ferric sulfate': 'Fe2(SO4)3',
            'copper sulfate': 'CuSO4',
            'zinc sulfate': 'ZnSO4',
            'manganese sulfate': 'MnSO4',
            'magnesium sulfate': 'MgSO4',
            'calcium chloride': 'CaCl2',
            'sodium chloride': 'NaCl',
            'potassium chloride': 'KCl',
            'sodium hydroxide': 'NaOH',
            'potassium hydroxide': 'KOH',
        }
        
        name_lower = name.lower()
        for standard_name, formula in name_standardizations.items():
            if standard_name in name_lower:
                return formula
        
        return name
    
    def parse_solution_text(self, text_path: Path) -> Optional[Dict]:
        """Parse solution text with enhanced chemical extraction."""
        
        solution_id = text_path.stem.replace('solution_', '')
        
        try:
            with open(text_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract solution name
            solution_name = self.extract_solution_name(content)
            
            # Extract chemical components
            components = self.extract_chemical_components(content)
            
            # If no components found with advanced patterns, try simple extraction
            if not components:
                components = self.extract_simple_components(content)
            
            composition_data = {
                'solution_id': solution_id,
                'solution_name': solution_name,
                'composition': components,
                'source': 'dsmz_solution_pdf_enhanced',
                'url': f"https://mediadive.dsmz.de/rest/solution/{solution_id}/pdf"
            }
            
            return composition_data
            
        except Exception as e:
            logger.error(f"Failed to parse solution {solution_id}: {e}")
            return None
    
    def extract_chemical_components(self, content: str) -> List[Dict]:
        """Extract chemical components using compiled patterns."""
        
        components = []
        
        for pattern, pattern_type in self.chemical_patterns:
            matches = pattern.findall(content)
            
            for match in matches:
                if pattern_type == 'formula_concentration':
                    compound, concentration, unit = match
                elif pattern_type in ['name_concentration', 'compound_name', 'special_compound', 'vitamin', 'acid_base']:
                    compound, concentration, unit = match
                else:
                    continue
                
                # Clean compound name
                clean_name = self.clean_chemical_name(compound)
                if not clean_name:
                    continue
                
                # Parse concentration
                try:
                    conc_value = float(concentration.replace(',', '.'))
                except ValueError:
                    conc_value = 0.0
                
                components.append({
                    'name': clean_name,
                    'concentration': conc_value,
                    'unit': unit,
                    'extraction_method': pattern_type,
                    'original_text': f"{compound} {concentration} {unit}"
                })
        
        # Deduplicate
        return self.deduplicate_components(components)
    
    def extract_simple_components(self, content: str) -> List[Dict]:
        """Simple fallback extraction for solutions with complex formatting."""
        
        components = []
        
        # Look for obvious chemical patterns in parentheses or bullets
        simple_patterns = [
            r'[•\-\*]\s*([A-Z][A-Za-z0-9\s\-·\.]+)\s*\n',  # Bullet points
            r'\(([A-Z][A-Za-z0-9\s\-·\.]+)\)',  # Parentheses
            r'^([A-Z][A-Za-z0-9\s\-·\.]{3,30})$',  # Simple lines
        ]
        
        for pattern in simple_patterns:
            matches = re.finditer(pattern, content, re.MULTILINE)
            
            for match in matches:
                compound = match.group(1).strip()
                clean_name = self.clean_chemical_name(compound)
                
                if clean_name and len(clean_name) > 2:
                    components.append({
                        'name': clean_name,
                        'concentration': 0.0,  # Unknown concentration
                        'unit': 'unknown',
                        'extraction_method': 'simple_pattern',
                        'original_text': compound
                    })
        
        return self.deduplicate_components(components)
    
    def deduplicate_components(self, components: List[Dict]) -> List[Dict]:
        """Remove duplicate components, keeping the one with the best information."""
        
        seen = {}
        unique_components = []
        
        for comp in components:
            key = comp['name'].lower().replace(' ', '')
            
            if key not in seen:
                seen[key] = True
                unique_components.append(comp)
            else:
                # Keep the one with concentration if available
                existing_idx = -1
                for i, existing in enumerate(unique_components):
                    if existing['name'].lower().replace(' ', '') == key:
                        existing_idx = i
                        break
                
                if (existing_idx >= 0 and 
                    comp['concentration'] > 0 and 
                    unique_components[existing_idx]['concentration'] == 0):
                    unique_components[existing_idx] = comp
        
        return unique_components

def reprocess_solution_compositions():
    """Reprocess all solution compositions with enhanced parser."""
    
    parser = EnhancedSolutionParser()
    text_dir = Path("solution_texts")
    composition_dir = Path("solution_compositions_enhanced")
    composition_dir.mkdir(exist_ok=True)
    
    if not text_dir.exists():
        logger.error("solution_texts directory not found")
        return
    
    text_files = list(text_dir.glob("solution_*.md"))
    logger.info(f"Reprocessing {len(text_files)} solution texts with enhanced parser...")
    
    results = {}
    total_components = 0
    
    for text_file in text_files:
        composition_data = parser.parse_solution_text(text_file)
        
        if composition_data:
            solution_id = composition_data['solution_id']
            num_components = len(composition_data['composition'])
            total_components += num_components
            
            # Save enhanced composition
            output_file = composition_dir / f"solution_{solution_id}_composition.json"
            with open(output_file, 'w') as f:
                json.dump(composition_data, f, indent=2)
            
            results[solution_id] = composition_data
            logger.info(f"✓ Solution {solution_id}: {composition_data['solution_name']} ({num_components} components)")
        else:
            logger.warning(f"✗ Failed to parse solution from {text_file}")
    
    # Summary
    logger.info(f"\n=== ENHANCED PARSING SUMMARY ===")
    logger.info(f"Solutions processed: {len(results)}")
    logger.info(f"Total components extracted: {total_components}")
    
    if results:
        avg_components = total_components / len(results)
        logger.info(f"Average components per solution: {avg_components:.1f}")
        
        # Show improved results
        improved_solutions = [(sol_id, data) for sol_id, data in results.items() if len(data['composition']) > 0]
        logger.info(f"Solutions with components: {len(improved_solutions)}")
        
        for sol_id, data in improved_solutions[:10]:
            logger.info(f"  Solution {sol_id}: {data['solution_name']} → {len(data['composition'])} components")
    
    return results

if __name__ == "__main__":
    reprocess_solution_compositions()