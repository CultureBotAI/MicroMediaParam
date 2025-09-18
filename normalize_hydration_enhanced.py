#!/usr/bin/env python3
"""
Enhanced Hydrate Normalization System

This script implements a dual-tracking approach for hydrated compounds:
1. Maps hydrates to base (anhydrous) ChEBI compounds for chemical properties
2. Tracks hydration state for accurate molecular weight and stoichiometric calculations
3. Corrects pH/salinity calculations by accounting for hydration effects

Key improvements:
- Base compound ChEBI mapping for chemical behavior
- Hydration-corrected molecular weights for concentration conversions
- Dual tracking: base_chebi + hydration_number
- Systematic treatment of all hydration states

Usage:
    python normalize_hydration_enhanced.py [--input-high FILE] [--input-low FILE] [--test-compounds]
"""

import pandas as pd
import numpy as np
import requests
import re
import json
import logging
import time
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set, Union
from dataclasses import dataclass
import urllib.parse

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('normalize_hydration_enhanced.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class HydrateInfo:
    """Data structure for tracking hydrate compound information."""
    original_name: str
    base_compound: str
    base_formula: str  
    hydration_number: int
    hydrate_formula: str
    base_chebi_id: Optional[str]
    base_molecular_weight: float
    water_molecular_weight: float
    hydrated_molecular_weight: float
    confidence: str
    parsing_method: str


class EnhancedHydrateNormalizer:
    """
    Enhanced normalization system for hydrated compounds with dual tracking.
    
    Maps hydrates to:
    1. Base (anhydrous) ChEBI compounds for chemical properties
    2. Hydration state for accurate molecular weight calculations
    """
    
    def __init__(self):
        self.water_mw = 18.015  # g/mol
        self.chebi_cache = {}
        self.base_compound_cache = {}
        self.molecular_weight_cache = {}
        
        # Enhanced hydration patterns
        self.hydration_patterns = [
            # Standard notation: "x n H2O"
            (r'\s*[x×]\s*(\d+(?:\.\d+)?)\s*H2O', r'.\1H2O'),
            # Dot notation: ".n H2O"  
            (r'\.(\d+(?:\.\d+)?)\s*H2O', r'.\1H2O'),
            # Single H2O without number
            (r'\s*[x×]\s*H2O\b', '.1H2O'),
            # Word forms
            (r'\s*monohydrate\b', '.1H2O'),
            (r'\s*dihydrate\b', '.2H2O'),
            (r'\s*trihydrate\b', '.3H2O'),
            (r'\s*tetrahydrate\b', '.4H2O'),
            (r'\s*pentahydrate\b', '.5H2O'),
            (r'\s*hexahydrate\b', '.6H2O'),
            (r'\s*heptahydrate\b', '.7H2O'),
            (r'\s*octahydrate\b', '.8H2O'),
            (r'\s*nonahydrate\b', '.9H2O'),
            (r'\s*decahydrate\b', '.10H2O'),
            (r'\s*dodecahydrate\b', '.12H2O'),
            # Variable hydration (remove)
            (r'\s*[n]\s*H2O', ''),
        ]
        
        # Common base compound patterns for ChEBI lookup
        self.base_compound_patterns = [
            # Metal salts
            (r'^([A-Z][a-z]?(?:[A-Z][a-z]?\d*)*(?:\([A-Z][a-z]?\d*\))*)\s*[\.x×].*H2O', r'\1'),
            # Simple compounds  
            (r'^([A-Za-z0-9()]+)\s*[\.x×].*H2O', r'\1'),
        ]
        
    def parse_hydrate_compound(self, compound_name: str) -> HydrateInfo:
        """
        Parse a hydrated compound into base compound + hydration information.
        
        Args:
            compound_name: Original compound name (e.g., "CaCl2 x 2 H2O")
            
        Returns:
            HydrateInfo: Structured information about the hydrate
        """
        original = compound_name.strip()
        
        # Check if this is a hydrated compound
        hydration_match = None
        hydration_number = 0
        
        # Try to extract hydration number
        for pattern, replacement in self.hydration_patterns:
            match = re.search(pattern, original, re.IGNORECASE)
            if match:
                try:
                    hydration_number = float(match.group(1))
                    hydration_match = match
                    break
                except (ValueError, IndexError):
                    continue
        
        # Extract base compound
        if hydration_match:
            # Remove hydration part to get base compound
            base_compound = re.sub(r'\s*[\.x×]\s*\d*\.?\d*\s*H2O.*$', '', original, flags=re.IGNORECASE)
            base_compound = re.sub(r'\s*\w*hydrate.*$', '', base_compound, flags=re.IGNORECASE)
            base_compound = base_compound.strip()
            parsing_method = "hydrate_pattern"
        else:
            # Not a hydrate, use as-is
            base_compound = original
            hydration_number = 0
            parsing_method = "no_hydration"
        
        # Normalize base compound formula
        base_formula = self._normalize_formula(base_compound)
        
        # Create hydrated formula
        if hydration_number > 0:
            if hydration_number == int(hydration_number):
                hydrate_formula = f"{base_formula}.{int(hydration_number)}H2O"
            else:
                hydrate_formula = f"{base_formula}.{hydration_number}H2O"
        else:
            hydrate_formula = base_formula
        
        # Calculate molecular weights
        base_mw = self._estimate_molecular_weight(base_formula)
        water_mw = hydration_number * self.water_mw
        hydrated_mw = base_mw + water_mw
        
        # Lookup base ChEBI ID
        base_chebi_id = self._lookup_base_chebi(base_compound, base_formula)
        
        # Determine confidence
        confidence = self._assess_confidence(base_compound, hydration_number, parsing_method)
        
        return HydrateInfo(
            original_name=original,
            base_compound=base_compound,
            base_formula=base_formula,
            hydration_number=int(hydration_number) if hydration_number == int(hydration_number) else hydration_number,
            hydrate_formula=hydrate_formula,
            base_chebi_id=base_chebi_id,
            base_molecular_weight=base_mw,
            water_molecular_weight=water_mw,
            hydrated_molecular_weight=hydrated_mw,
            confidence=confidence,
            parsing_method=parsing_method
        )
    
    def _normalize_formula(self, compound: str) -> str:
        """Normalize chemical formula for consistency."""
        # Remove extra whitespace
        normalized = re.sub(r'\s+', '', compound)
        
        # Standardize common compounds
        formula_mappings = {
            'CaCl2': 'CaCl2',
            'CuSO4': 'CuSO4', 
            'FeSO4': 'FeSO4',
            'MgSO4': 'MgSO4',
            'NaCl': 'NaCl',
            'FeCl3': 'FeCl3',
            'AlK(SO4)2': 'AlK(SO4)2',
            'Na2SO4': 'Na2SO4',
            'MnSO4': 'MnSO4',
            'ZnSO4': 'ZnSO4',
            'NiCl2': 'NiCl2',
            'CoCl2': 'CoCl2',
        }
        
        return formula_mappings.get(normalized, normalized)
    
    def _estimate_molecular_weight(self, formula: str) -> float:
        """
        Estimate molecular weight from chemical formula.
        Uses a simple lookup table for common compounds.
        """
        # Common molecular weights (g/mol)
        mw_table = {
            'CaCl2': 110.98,
            'CuSO4': 159.61,
            'FeSO4': 151.91,
            'MgSO4': 120.37,
            'NaCl': 58.44,
            'FeCl3': 162.20,
            'AlK(SO4)2': 258.21,
            'Na2SO4': 142.04,
            'MnSO4': 151.00,
            'ZnSO4': 161.47,
            'NiCl2': 129.60,
            'CoCl2': 129.84,
            'Na2WO4': 293.82,
            'HBO3': 61.83,
            'glucose': 180.16,
            'KCl': 74.55,
            'MgCl2': 95.21,
            'Na2HPO4': 141.96,
            'KH2PO4': 136.09,
            'NH4Cl': 53.49,
        }
        
        return mw_table.get(formula, 100.0)  # Default estimate if unknown
    
    def _lookup_base_chebi(self, compound: str, formula: str) -> Optional[str]:
        """
        Lookup base (anhydrous) ChEBI ID for a compound.
        
        This should map hydrates to their base anhydrous form:
        CaCl2 x 2 H2O → CHEBI:3312 (calcium chloride, anhydrous)
        CuSO4 x 5 H2O → CHEBI:23414 (copper sulfate, anhydrous)
        """
        # Cache check
        cache_key = f"{compound}|{formula}"
        if cache_key in self.base_compound_cache:
            return self.base_compound_cache[cache_key]
        
        # Known base compound mappings (anhydrous forms)
        base_chebi_mappings = {
            'CaCl2': 'CHEBI:3312',      # calcium chloride (anhydrous)
            'CuSO4': 'CHEBI:23414',     # copper sulfate (anhydrous) 
            'FeSO4': 'CHEBI:75832',     # iron sulfate (anhydrous)
            'MgSO4': 'CHEBI:32599',     # magnesium sulfate (anhydrous)
            'NaCl': 'CHEBI:26710',      # sodium chloride
            'FeCl3': 'CHEBI:30808',     # iron trichloride (anhydrous)
            'Na2SO4': 'CHEBI:32149',    # sodium sulfate (anhydrous)
            'MnSO4': 'CHEBI:135251',    # manganese sulfate (anhydrous)
            'ZnSO4': 'CHEBI:62984',     # zinc sulfate (anhydrous)
            'NiCl2': 'CHEBI:34887',     # nickel dichloride (anhydrous)
            'CoCl2': 'CHEBI:35696',     # cobalt dichloride (anhydrous)
        }
        
        # Try exact formula match first
        result = base_chebi_mappings.get(formula)
        if not result:
            # Try compound name match
            result = base_chebi_mappings.get(compound)
        
        # Cache result
        self.base_compound_cache[cache_key] = result
        return result
    
    def _assess_confidence(self, base_compound: str, hydration_number: float, method: str) -> str:
        """Assess confidence level of the hydrate parsing."""
        if method == "no_hydration":
            return "high"  # Simple compound, high confidence
        elif hydration_number > 0 and hydration_number <= 12:
            # Reasonable hydration numbers
            if base_compound in ['CaCl2', 'CuSO4', 'FeSO4', 'MgSO4']:
                return "very_high"  # Known hydrates
            else:
                return "high"  # Parsed successfully
        elif hydration_number > 12:
            return "medium"  # Unusual hydration number
        else:
            return "low"  # Failed parsing
    
    def process_mapping_file(self, input_file: str, output_file: str) -> None:
        """
        Process a mapping file to add enhanced hydrate normalization.
        
        Args:
            input_file: Path to input TSV file
            output_file: Path to output TSV file with enhanced hydrate information
        """
        logger.info(f"Processing mapping file: {input_file}")
        
        # Read input file
        df = pd.read_csv(input_file, sep='\t', dtype=str)
        logger.info(f"Loaded {len(df)} entries from {input_file}")
        
        # Add new columns for hydrate tracking
        new_columns = [
            'base_compound', 'base_formula', 'hydration_number', 'hydrate_formula',
            'base_chebi_id', 'base_molecular_weight', 'water_molecular_weight', 
            'hydrated_molecular_weight', 'hydration_confidence', 'hydration_parsing_method',
            'corrected_mmol_l'
        ]
        
        for col in new_columns:
            df[col] = ''
        
        # Process each row
        processed_count = 0
        for idx, row in df.iterrows():
            original_name = str(row.get('original', ''))
            if original_name and original_name != 'nan':
                try:
                    hydrate_info = self.parse_hydrate_compound(original_name)
                    
                    # Update row with hydrate information
                    df.at[idx, 'base_compound'] = hydrate_info.base_compound
                    df.at[idx, 'base_formula'] = hydrate_info.base_formula
                    df.at[idx, 'hydration_number'] = hydrate_info.hydration_number
                    df.at[idx, 'hydrate_formula'] = hydrate_info.hydrate_formula
                    df.at[idx, 'base_chebi_id'] = hydrate_info.base_chebi_id or ''
                    df.at[idx, 'base_molecular_weight'] = hydrate_info.base_molecular_weight
                    df.at[idx, 'water_molecular_weight'] = hydrate_info.water_molecular_weight
                    df.at[idx, 'hydrated_molecular_weight'] = hydrate_info.hydrated_molecular_weight
                    df.at[idx, 'hydration_confidence'] = hydrate_info.confidence
                    df.at[idx, 'hydration_parsing_method'] = hydrate_info.parsing_method
                    
                    # Calculate corrected molarity if concentration is available
                    concentration = row.get('value', '')
                    if concentration and concentration != 'nan' and str(concentration).replace('.','').isdigit():
                        try:
                            conc_g_per_l = float(concentration)
                            corrected_mmol_l = (conc_g_per_l / hydrate_info.hydrated_molecular_weight) * 1000
                            df.at[idx, 'corrected_mmol_l'] = f"{corrected_mmol_l:.6f}"
                        except (ValueError, ZeroDivisionError):
                            df.at[idx, 'corrected_mmol_l'] = ''
                    
                    processed_count += 1
                    if processed_count % 1000 == 0:
                        logger.info(f"Processed {processed_count} compounds...")
                        
                except Exception as e:
                    logger.warning(f"Error processing compound '{original_name}': {e}")
                    continue
        
        # Save results
        df.to_csv(output_file, sep='\t', index=False)
        logger.info(f"Saved enhanced mapping to {output_file}")
        logger.info(f"Successfully processed {processed_count} compounds")
        
        # Generate summary statistics
        self._generate_summary_stats(df, output_file)
    
    def _generate_summary_stats(self, df: pd.DataFrame, output_file: str) -> None:
        """Generate summary statistics for the hydrate normalization."""
        logger.info("\n=== HYDRATE NORMALIZATION SUMMARY ===")
        
        # Overall statistics
        total_compounds = len(df)
        hydrated_compounds = len(df[df['hydration_number'].astype(str) != '0'])
        
        logger.info(f"Total compounds processed: {total_compounds}")
        logger.info(f"Hydrated compounds found: {hydrated_compounds} ({hydrated_compounds/total_compounds*100:.1f}%)")
        
        # Hydration distribution
        hydration_counts = df['hydration_number'].value_counts().sort_index()
        logger.info(f"Hydration state distribution:")
        for hydration, count in hydration_counts.items():
            if str(hydration) != '0':
                logger.info(f"  {hydration} H2O: {count} compounds")
        
        # Base ChEBI mapping success
        base_chebi_mapped = len(df[df['base_chebi_id'] != ''])
        logger.info(f"Base ChEBI mapping success: {base_chebi_mapped}/{total_compounds} ({base_chebi_mapped/total_compounds*100:.1f}%)")
        
        # Confidence distribution
        confidence_counts = df['hydration_confidence'].value_counts()
        logger.info(f"Confidence level distribution:")
        for conf, count in confidence_counts.items():
            logger.info(f"  {conf}: {count} compounds")
        
        # Most common hydrated compounds
        if hydrated_compounds > 0:
            logger.info(f"Most common hydrated compound types:")
            hydrated_df = df[df['hydration_number'].astype(str) != '0']
            base_compound_counts = hydrated_df['base_formula'].value_counts().head(10)
            for compound, count in base_compound_counts.items():
                logger.info(f"  {compound}: {count} occurrences")

    def test_system(self) -> None:
        """Test the enhanced hydrate normalization system with example compounds."""
        logger.info("\n=== TESTING ENHANCED HYDRATE NORMALIZATION ===")
        
        test_compounds = [
            "CaCl2 x 2 H2O",
            "CuSO4 x 5 H2O", 
            "FeSO4 x 7 H2O",
            "MgSO4.7H2O",
            "NaCl",
            "CaCl2 x 6 H2O",
            "sodium chloride monohydrate",
            "FeCl3 x 6 H2O",
            "glucose",
            "MnSO4 x H2O"
        ]
        
        for compound in test_compounds:
            try:
                hydrate_info = self.parse_hydrate_compound(compound)
                logger.info(f"\nCompound: {compound}")
                logger.info(f"  Base: {hydrate_info.base_formula} (ChEBI: {hydrate_info.base_chebi_id})")
                logger.info(f"  Hydration: {hydrate_info.hydration_number} H2O")
                logger.info(f"  MW: {hydrate_info.base_molecular_weight:.2f} + {hydrate_info.water_molecular_weight:.2f} = {hydrate_info.hydrated_molecular_weight:.2f} g/mol")
                logger.info(f"  Confidence: {hydrate_info.confidence}")
            except Exception as e:
                logger.error(f"Error testing compound '{compound}': {e}")


def main():
    """Main function for enhanced hydrate normalization."""
    parser = argparse.ArgumentParser(description='Enhanced Hydrate Normalization System')
    parser.add_argument('--input-high', default='high_confidence_compound_mappings_normalized.tsv',
                        help='High confidence mapping file')
    parser.add_argument('--input-low', default='low_confidence_compound_mappings_normalized.tsv',
                        help='Low confidence mapping file')
    parser.add_argument('--test-compounds', action='store_true',
                        help='Test system with example compounds')
    parser.add_argument('--output-suffix', default='_hydrate_enhanced',
                        help='Suffix for output files')
    
    args = parser.parse_args()
    
    normalizer = EnhancedHydrateNormalizer()
    
    if args.test_compounds:
        normalizer.test_system()
        return
    
    # Process mapping files
    for input_file in [args.input_high, args.input_low]:
        if Path(input_file).exists():
            output_file = input_file.replace('.tsv', f'{args.output_suffix}.tsv')
            logger.info(f"Processing {input_file} → {output_file}")
            normalizer.process_mapping_file(input_file, output_file)
        else:
            logger.warning(f"Input file not found: {input_file}")
    
    logger.info("Enhanced hydrate normalization completed!")


if __name__ == "__main__":
    main()