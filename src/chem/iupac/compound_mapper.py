#!/usr/bin/env python3
"""
Compound Mapper

Maps compound names from media compositions to standardized chemical names
for data downloading and processing.

Author: MicroMediaParam Project
"""

import re
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
import pandas as pd
from fuzzywuzzy import fuzz, process

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CompoundMapper:
    """
    Map compound names from media compositions to standardized chemical names.
    
    Handles:
    - Name normalization and standardization
    - Hydration state removal
    - Synonym mapping
    - Fuzzy matching for name variants
    """
    
    def __init__(self):
        self.name_mappings = self._build_name_mappings()
        self.hydration_patterns = self._build_hydration_patterns()
        self.synonym_database = self._build_synonym_database()
        self.exclusion_patterns = self._build_exclusion_patterns()
    
    def _build_name_mappings(self) -> Dict[str, str]:
        """Build mapping of common name variations to standard names."""
        return {
            # Inorganic salts - standard names
            'nacl': 'sodium chloride',
            'sodium chloride': 'sodium chloride',
            'table salt': 'sodium chloride',
            'kcl': 'potassium chloride', 
            'potassium chloride': 'potassium chloride',
            'mgcl2': 'magnesium chloride',
            'magnesium chloride': 'magnesium chloride',
            'cacl2': 'calcium chloride',
            'calcium chloride': 'calcium chloride',
            'nh4cl': 'ammonium chloride',
            'ammonium chloride': 'ammonium chloride',
            
            # Sulfates
            'na2so4': 'sodium sulfate',
            'sodium sulfate': 'sodium sulfate',
            'mgso4': 'magnesium sulfate',
            'magnesium sulfate': 'magnesium sulfate',
            'feso4': 'iron sulfate',
            'iron sulfate': 'iron sulfate',
            'ferrous sulfate': 'iron sulfate',
            'znso4': 'zinc sulfate',
            'zinc sulfate': 'zinc sulfate',
            'cuso4': 'copper sulfate',
            'copper sulfate': 'copper sulfate',
            'cupric sulfate': 'copper sulfate',
            'mnso4': 'manganese sulfate',
            'manganese sulfate': 'manganese sulfate',
            
            # Carbonates
            'caco3': 'calcium carbonate',
            'calcium carbonate': 'calcium carbonate',
            'nahco3': 'sodium bicarbonate',
            'sodium bicarbonate': 'sodium bicarbonate',
            'sodium hydrogen carbonate': 'sodium bicarbonate',
            'na2co3': 'sodium carbonate',
            'sodium carbonate': 'sodium carbonate',
            
            # Phosphates
            'k2hpo4': 'potassium phosphate',
            'dipotassium phosphate': 'potassium phosphate',
            'potassium phosphate dibasic': 'potassium phosphate',
            'kh2po4': 'potassium phosphate',
            'monopotassium phosphate': 'potassium phosphate',
            'potassium phosphate monobasic': 'potassium phosphate',
            'na2hpo4': 'sodium phosphate',
            'disodium phosphate': 'sodium phosphate',
            'nah2po4': 'sodium phosphate',
            'sodium dihydrogen phosphate': 'sodium phosphate',
            
            # Trace elements
            'h3bo3': 'boric acid',
            'boric acid': 'boric acid',
            'zncl2': 'zinc chloride',
            'zinc chloride': 'zinc chloride',
            'fecl2': 'iron chloride',
            'fecl3': 'iron chloride',
            'iron chloride': 'iron chloride',
            'ferric chloride': 'iron chloride',
            'ferrous chloride': 'iron chloride',
            'nicl2': 'nickel chloride',
            'nickel chloride': 'nickel chloride',
            'cocl2': 'cobalt chloride',
            'cobalt chloride': 'cobalt chloride',
            'cucl2': 'copper chloride',
            'copper chloride': 'copper chloride',
            'cupric chloride': 'copper chloride',
            
            # Carbon sources
            'glucose': 'glucose',
            'd-glucose': 'glucose',
            'dextrose': 'glucose',
            'sucrose': 'sucrose',
            'fructose': 'fructose',
            'd-fructose': 'fructose',
            'lactose': 'lactose',
            'maltose': 'maltose',
            
            # Organic salts
            'sodium acetate': 'sodium acetate',
            'na acetate': 'sodium acetate',
            'na-acetate': 'sodium acetate',
            'sodium pyruvate': 'sodium pyruvate',
            'sodium citrate': 'sodium citrate',
            'sodium lactate': 'sodium lactate',
            
            # Amino acids
            'glycine': 'glycine',
            'l-glycine': 'glycine',
            'alanine': 'alanine',
            'l-alanine': 'alanine',
            'cysteine': 'cysteine',
            'l-cysteine': 'cysteine',
            'glutamine': 'glutamine',
            'l-glutamine': 'glutamine',
            'asparagine': 'asparagine',
            'l-asparagine': 'asparagine',
            
            # Buffers
            'tris': 'tris',
            'tris buffer': 'tris',
            'tris-hcl': 'tris',
            'hepes': 'hepes',
            'hepes buffer': 'hepes',
            'mes': 'mes',
            'mops': 'mops',
            'pipes': 'pipes',
            
            # Vitamins
            'thiamine': 'thiamine',
            'vitamin b1': 'thiamine',
            'thiamine hcl': 'thiamine',
            'riboflavin': 'riboflavin',
            'vitamin b2': 'riboflavin',
            'nicotinic acid': 'nicotinic acid',
            'niacin': 'nicotinic acid',
            'vitamin b3': 'nicotinic acid',
            'pyridoxine': 'pyridoxine',
            'vitamin b6': 'pyridoxine',
            'biotin': 'biotin',
            'vitamin b7': 'biotin',
            'folic acid': 'folic acid',
            'vitamin b9': 'folic acid',
            'cobalamin': 'cobalamin',
            'vitamin b12': 'cobalamin',
        }
    
    def _build_hydration_patterns(self) -> List[str]:
        """Build patterns for removing hydration states."""
        return [
            r'\s*[·•]\s*\d+\s*h2o',      # · 2 H2O
            r'\s*\.\s*\d+\s*h2o',        # . 2 H2O  
            r'\s*x\s*\d+\s*h2o',         # x 2 H2O
            r'\s*\*\s*\d+\s*h2o',        # * 2 H2O
            r'\s+\d+\s*h2o',             # space 2 H2O
            r'\s*\(\d+\s*h2o\)',         # (2 H2O)
            r'\s*hydrate',               # hydrate
            r'\s*monohydrate',           # monohydrate
            r'\s*dihydrate',             # dihydrate
            r'\s*trihydrate',            # trihydrate
            r'\s*heptahydrate',          # heptahydrate
        ]
    
    def _build_synonym_database(self) -> Dict[str, Set[str]]:
        """Build database of known synonyms for chemical compounds."""
        return {
            'sodium chloride': {
                'nacl', 'table salt', 'halite', 'rock salt', 'sea salt'
            },
            'glucose': {
                'd-glucose', 'dextrose', 'grape sugar', 'blood sugar'
            },
            'calcium carbonate': {
                'caco3', 'limestone', 'chalk', 'calcite', 'aragonite'
            },
            'iron sulfate': {
                'feso4', 'ferrous sulfate', 'iron(ii) sulfate', 'green vitriol'
            },
            'copper sulfate': {
                'cuso4', 'cupric sulfate', 'copper(ii) sulfate', 'blue vitriol'
            },
            'tris': {
                'tris buffer', 'tris-hcl', 'tham', 'trizma'
            },
            'thiamine': {
                'vitamin b1', 'thiamine hcl', 'thiamine hydrochloride', 'aneurine'
            }
        }
    
    def _build_exclusion_patterns(self) -> List[str]:
        """Build patterns for compound names to exclude (complex mixtures)."""
        return [
            r'.*peptone.*',
            r'.*extract.*',
            r'.*broth.*',
            r'.*medium.*',
            r'.*agar.*',
            r'.*blood.*',
            r'.*serum.*',
            r'.*casein.*',
            r'.*gelatin.*',
            r'.*tryptone.*',
            r'.*yeast.*',
            r'.*beef.*',
            r'.*meat.*',
            r'distilled water',
            r'deionized water',
            r'tap water'
        ]
    
    def normalize_compound_name(self, name: str) -> str:
        """
        Normalize compound name by removing variations and hydration states.
        
        Args:
            name: Original compound name
            
        Returns:
            Normalized compound name
        """
        if not name or not isinstance(name, str):
            return ""
        
        # Convert to lowercase and strip whitespace
        normalized = name.lower().strip()
        
        # Remove common prefixes/suffixes
        normalized = re.sub(r'^[dl]-', '', normalized)  # Remove D-/L- stereochemistry
        normalized = re.sub(r'^[+-]-', '', normalized)  # Remove +/- indicators
        normalized = re.sub(r'\s*\([^)]*grade[^)]*\)', '', normalized)  # Remove grade info
        normalized = re.sub(r'\s*\([^)]*purity[^)]*\)', '', normalized)  # Remove purity info
        
        # Remove hydration states
        for pattern in self.hydration_patterns:
            normalized = re.sub(pattern, '', normalized, flags=re.IGNORECASE)
        
        # Clean up extra whitespace
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        return normalized
    
    def is_excluded_compound(self, name: str) -> bool:
        """
        Check if compound should be excluded (complex mixture).
        
        Args:
            name: Compound name to check
            
        Returns:
            True if compound should be excluded
        """
        name_lower = name.lower()
        
        for pattern in self.exclusion_patterns:
            if re.match(pattern, name_lower):
                return True
        
        return False
    
    def map_to_standard_name(self, name: str) -> Optional[str]:
        """
        Map compound name to standard chemical name.
        
        Args:
            name: Original compound name
            
        Returns:
            Standard chemical name or None if not mappable
        """
        if self.is_excluded_compound(name):
            return None
        
        normalized = self.normalize_compound_name(name)
        if not normalized:
            return None
        
        # Direct mapping lookup
        if normalized in self.name_mappings:
            return self.name_mappings[normalized]
        
        # Check synonym database
        for standard_name, synonyms in self.synonym_database.items():
            if normalized in synonyms:
                return standard_name
        
        # Fuzzy matching against known compounds
        known_compounds = list(self.name_mappings.keys())
        match = process.extractOne(normalized, known_compounds, scorer=fuzz.ratio)
        
        if match and match[1] >= 85:  # High similarity threshold
            return self.name_mappings[match[0]]
        
        # Return normalized name if no mapping found but not excluded
        return normalized
    
    def extract_compounds_from_mappings_file(self, mappings_file: Path) -> Set[str]:
        """
        Extract unique compound names from existing compound mappings file.
        
        Args:
            mappings_file: Path to compound mappings TSV file
            
        Returns:
            Set of unique compound names
        """
        compounds = set()
        
        try:
            df = pd.read_csv(mappings_file, sep='\t')
            
            # Extract from compound_name column
            if 'compound_name' in df.columns:
                compounds.update(df['compound_name'].dropna().str.strip())
            
            # Extract from original_compound column if it exists
            if 'original_compound' in df.columns:
                compounds.update(df['original_compound'].dropna().str.strip())
            
            logger.info(f"Extracted {len(compounds)} unique compounds from {mappings_file}")
            
        except Exception as e:
            logger.error(f"Error reading mappings file {mappings_file}: {e}")
        
        return compounds
    
    def create_download_target_list(self, 
                                  mappings_files: List[Path],
                                  additional_compounds: Optional[List[str]] = None) -> List[str]:
        """
        Create prioritized list of compounds for downloading chemical data.
        
        Args:
            mappings_files: List of compound mapping files to analyze
            additional_compounds: Additional compounds to include
            
        Returns:
            Prioritized list of standard compound names for downloading
        """
        all_compounds = set()
        
        # Extract compounds from mapping files
        for mappings_file in mappings_files:
            if mappings_file.exists():
                compounds = self.extract_compounds_from_mappings_file(mappings_file)
                all_compounds.update(compounds)
        
        # Add additional compounds
        if additional_compounds:
            all_compounds.update(additional_compounds)
        
        # Map to standard names and filter
        standard_compounds = set()
        unmappable_compounds = []
        
        for compound in all_compounds:
            standard_name = self.map_to_standard_name(compound)
            if standard_name:
                standard_compounds.add(standard_name)
            else:
                unmappable_compounds.append(compound)
        
        # Log statistics
        logger.info(f"Total compounds found: {len(all_compounds)}")
        logger.info(f"Mappable compounds: {len(standard_compounds)}")
        logger.info(f"Unmappable compounds: {len(unmappable_compounds)}")
        
        if unmappable_compounds:
            logger.debug(f"Unmappable compounds: {unmappable_compounds[:10]}...")  # Show first 10
        
        # Return sorted list
        return sorted(list(standard_compounds))
    
    def save_mapping_report(self, 
                          compounds: List[str],
                          output_file: Path) -> None:
        """
        Save compound mapping report showing original → standard name mappings.
        
        Args:
            compounds: List of original compound names
            output_file: Output file for mapping report
        """
        mapping_data = []
        
        for compound in compounds:
            standard_name = self.map_to_standard_name(compound)
            normalized = self.normalize_compound_name(compound)
            excluded = self.is_excluded_compound(compound)
            
            mapping_data.append({
                'original_name': compound,
                'normalized_name': normalized,
                'standard_name': standard_name or 'UNMAPPABLE',
                'excluded': excluded,
                'mappable': standard_name is not None
            })
        
        # Create DataFrame and save
        df = pd.DataFrame(mapping_data)
        df.to_csv(output_file, sep='\t', index=False)
        
        # Print summary
        total = len(df)
        mappable = df['mappable'].sum()
        excluded = df['excluded'].sum()
        
        logger.info(f"Mapping report saved to {output_file}")
        logger.info(f"Total: {total}, Mappable: {mappable} ({mappable/total*100:.1f}%), Excluded: {excluded}")

def main():
    """Test the compound mapper."""
    mapper = CompoundMapper()
    
    # Test compound mapping
    test_compounds = [
        "NaCl", "Glucose", "CaCl2 x 2 H2O", "D-glucose", 
        "Peptone", "Yeast extract", "Tris-HCl buffer",
        "FeSO4 x 7 H2O", "L-glycine", "Sodium acetate"
    ]
    
    print("Testing compound mapping:")
    for compound in test_compounds:
        standard_name = mapper.map_to_standard_name(compound)
        excluded = mapper.is_excluded_compound(compound)
        print(f"{compound:20} → {standard_name or 'UNMAPPABLE':20} (excluded: {excluded})")

if __name__ == "__main__":
    main()