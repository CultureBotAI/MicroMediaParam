#!/usr/bin/env python3
"""
Enhanced Compound Mapper for Unmapped Compounds

This script identifies and maps unmapped compounds using:
1. Chemical formula patterns (KH2PO4 → potassium dihydrogen phosphate)
2. Hydrate variations (·6H2O, x H2O, xH2O)
3. Common compound name variations (Na-acetate → sodium acetate)
4. Known chemical abbreviations
"""

import pandas as pd
import re
import logging
from pathlib import Path
from typing import Dict, Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('enhance_unmapped_compounds.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class UnmappedCompoundEnhancer:
    """Enhance mappings for previously unmapped compounds."""

    def __init__(self):
        # Chemical formula to ChEBI mappings
        self.formula_mappings = {
            'KH2PO4': 'CHEBI:63036',  # potassium dihydrogen phosphate
            'K2HPO4': 'CHEBI:32588',  # dipotassium hydrogen phosphate
            'NH4Cl': 'CHEBI:31206',   # ammonium chloride
            'Na2HPO4': 'CHEBI:32149', # disodium hydrogen phosphate
            'NaH2PO4': 'CHEBI:37585', # sodium dihydrogen phosphate
            'MgSO4': 'CHEBI:32599',   # magnesium sulfate
            'CaCl2': 'CHEBI:3312',    # calcium chloride
            'FeCl2': 'CHEBI:30812',   # iron(II) chloride
            'FeCl3': 'CHEBI:30808',   # iron(III) chloride
            'CoCl2': 'CHEBI:35701',   # cobalt(II) chloride
            'CuSO4': 'CHEBI:23414',   # copper(II) sulfate
            'ZnSO4': 'CHEBI:35176',   # zinc sulfate
            'MnSO4': 'CHEBI:75896',   # manganese(II) sulfate
            'MnCl2': 'CHEBI:34342',   # manganese(II) chloride
            'NiCl2': 'CHEBI:34887',   # nickel(II) chloride
            'H3BO3': 'CHEBI:33118',   # boric acid
            'Na2S': 'CHEBI:33183',    # sodium sulfide
            'Na2CO3': 'CHEBI:29377',  # sodium carbonate
            'NaHCO3': 'CHEBI:32139',  # sodium bicarbonate / sodium hydrogen carbonate
            'K2SO4': 'CHEBI:32036',   # potassium sulfate
        }

        # Common name variations to ChEBI mappings
        self.name_mappings = {
            'na-acetate': 'CHEBI:32954',           # sodium acetate
            'sodium-acetate': 'CHEBI:32954',
            'na acetate': 'CHEBI:32954',
            'na-pyruvate': 'CHEBI:140345',         # sodium pyruvate
            'sodium-pyruvate': 'CHEBI:140345',
            'na pyruvate': 'CHEBI:140345',
            'na-lactate': 'CHEBI:32398',           # sodium lactate
            'sodium-lactate': 'CHEBI:32398',
            'na-formate': 'CHEBI:62955',           # sodium formate
            'sodium-formate': 'CHEBI:62955',
            'thiamine-hcl': 'CHEBI:532454',        # thiamine hydrochloride
            'thiamin-hcl': 'CHEBI:532454',
            'thiamine hcl': 'CHEBI:532454',
            'l-cysteine hcl': 'CHEBI:17561',       # L-cysteine hydrochloride
            'l-cysteine·hcl': 'CHEBI:17561',
            'l-cysteine·hcl·h2o': 'CHEBI:17561',   # L-cysteine hydrochloride hydrate
            'cysteine hcl': 'CHEBI:17561',
            'soluble starch': 'CHEBI:28017',       # starch
            'yeast extract': 'CAS-RN:8013-01-2',   # yeast extract (use CAS-RN)
            'tryptone': 'ingredient:tryptone',      # complex ingredient
            'trypticase peptone': 'ingredient:trypticase_peptone',
            'bacto peptone': 'ingredient:bacto_peptone',
            'phytone peptone': 'ingredient:phytone_peptone',
            'casamino acids': 'ingredient:casamino_acids',
            'casitone': 'ingredient:casitone',
            'meat peptone': 'ingredient:meat_peptone',
            'edta·2na': 'CHEBI:64734',             # EDTA disodium salt
            'edta-2na': 'CHEBI:64734',
        }

        # Hydrate patterns - will map to base compound
        self.hydrate_patterns = [
            (r'·(\d+)H2O', ''),           # CoCl2·6H2O → CoCl2
            (r'\s+x\s+(\d+)\s*H2O', ''),  # L-Cysteine HCl x H2O → L-Cysteine HCl
            (r'\s+xH2O', ''),              # MnSO4·xH2O → MnSO4
            (r'\s+x\s+H2O', ''),           # variations
        ]

        self.stats = {
            'formula_matches': 0,
            'name_matches': 0,
            'hydrate_resolved': 0,
            'still_unmapped': 0
        }

    def normalize_compound_name(self, name: str) -> str:
        """Normalize compound name for matching."""
        if pd.isna(name) or name == "":
            return ""

        normalized = name.strip().lower()
        # Remove brand names in parentheses for first pass
        normalized_no_brand = re.sub(r'\s*\([^)]*\)', '', normalized)
        return normalized_no_brand

    def extract_base_formula(self, compound: str) -> Optional[str]:
        """Extract base chemical formula from compound name."""
        # Try to find chemical formula pattern
        formula_match = re.search(r'\b([A-Z][a-z]?\d*)+\b', compound)
        if formula_match:
            return formula_match.group(0)
        return None

    def map_compound(self, compound: str) -> Optional[str]:
        """
        Try to map an unmapped compound using various strategies.

        Returns ChEBI ID, CAS-RN, or ingredient code if successful, None otherwise.
        """
        if pd.isna(compound) or compound.strip() == "":
            return None

        original = compound
        normalized = self.normalize_compound_name(compound)

        # Strategy 1: Direct formula match
        # Extract potential formula (handle hydrates first)
        base_compound = compound
        for pattern, replacement in self.hydrate_patterns:
            if re.search(pattern, compound):
                base_compound = re.sub(pattern, replacement, compound).strip()
                logger.debug(f"Hydrate detected: {compound} → {base_compound}")
                break

        # Check if base compound (after stripping hydrate) is a known formula
        if base_compound in self.formula_mappings:
            self.stats['formula_matches'] += 1
            logger.info(f"Formula match: {compound} → {self.formula_mappings[base_compound]}")
            return self.formula_mappings[base_compound]

        # Strategy 2: Name variation match
        if normalized in self.name_mappings:
            self.stats['name_matches'] += 1
            logger.info(f"Name match: {compound} → {self.name_mappings[normalized]}")
            return self.name_mappings[normalized]

        # Strategy 3: Strip hydrate and check name mappings again
        if base_compound != compound:
            base_normalized = self.normalize_compound_name(base_compound)
            if base_normalized in self.name_mappings:
                self.stats['hydrate_resolved'] += 1
                logger.info(f"Hydrate resolved: {compound} → {self.name_mappings[base_normalized]}")
                return self.name_mappings[base_normalized]

            # Check if base is a formula
            if base_compound in self.formula_mappings:
                self.stats['hydrate_resolved'] += 1
                logger.info(f"Hydrate formula resolved: {compound} → {self.formula_mappings[base_compound]}")
                return self.formula_mappings[base_compound]

        return None

    def enhance_mapping_file(self, input_file: str, output_file: str):
        """
        Read mapping TSV, enhance unmapped compounds, and write results.
        """
        logger.info(f"Reading mapping file: {input_file}")
        df = pd.read_csv(input_file, sep='\t')

        logger.info(f"Loaded {len(df)} rows")

        # Count unmapped before
        unmapped_before = df['mapped'].isna() | (df['mapped'] == '')
        count_before = unmapped_before.sum()
        logger.info(f"Unmapped compounds before enhancement: {count_before}")

        # Enhance unmapped compounds
        enhanced_count = 0
        for idx, row in df.iterrows():
            if pd.isna(row['mapped']) or row['mapped'] == '':
                compound = row['original']
                new_mapping = self.map_compound(compound)
                if new_mapping:
                    df.at[idx, 'mapped'] = new_mapping
                    enhanced_count += 1

        # Count unmapped after
        unmapped_after = df['mapped'].isna() | (df['mapped'] == '')
        count_after = unmapped_after.sum()

        # Save enhanced mapping
        logger.info(f"Writing enhanced mapping to: {output_file}")
        df.to_csv(output_file, sep='\t', index=False)

        # Report statistics
        logger.info("\n" + "="*60)
        logger.info("ENHANCEMENT SUMMARY")
        logger.info("="*60)
        logger.info(f"Total rows: {len(df)}")
        logger.info(f"Unmapped before: {count_before}")
        logger.info(f"Newly mapped: {enhanced_count}")
        logger.info(f"Unmapped after: {count_after}")
        logger.info(f"Improvement: {enhanced_count / count_before * 100:.2f}%")
        logger.info("\nBreakdown:")
        logger.info(f"  Formula matches: {self.stats['formula_matches']}")
        logger.info(f"  Name matches: {self.stats['name_matches']}")
        logger.info(f"  Hydrate resolved: {self.stats['hydrate_resolved']}")
        logger.info("="*60)

        # Show top remaining unmapped
        logger.info("\nTop 20 remaining unmapped compounds:")
        remaining_unmapped = df[df['mapped'].isna() | (df['mapped'] == '')]['original']
        top_unmapped = remaining_unmapped.value_counts().head(20)
        for compound, count in top_unmapped.items():
            logger.info(f"  {compound}: {count} occurrences")


def main():
    enhancer = UnmappedCompoundEnhancer()

    input_file = "composition_kg_mapping.tsv"
    output_file = "composition_kg_mapping_enhanced.tsv"

    if not Path(input_file).exists():
        logger.error(f"Input file not found: {input_file}")
        return 1

    enhancer.enhance_mapping_file(input_file, output_file)
    logger.info(f"\nEnhanced mapping saved to: {output_file}")

    return 0


if __name__ == "__main__":
    exit(main())