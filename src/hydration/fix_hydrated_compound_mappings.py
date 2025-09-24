#!/usr/bin/env python3
"""
Fix hydrated compound mappings that are incorrectly mapped to ingredient codes
instead of proper CHEBI identifiers.

This script specifically addresses compounds like "MnCl2 x 4 H2O" that are
mapped to "ingredient:2003" instead of proper CHEBI IDs.
"""

import pandas as pd
import logging
from pathlib import Path
from typing import Dict, List, Set
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HydratedCompoundMapper:
    """Fix hydrated compounds mapped to ingredient codes."""
    
    def __init__(self):
        # Manual mappings for known ingredient codes to proper CHEBI IDs
        self.ingredient_to_chebi = {
            'ingredient:2003': 'CHEBI:7773',  # MnCl2 x 4 H2O -> MnCl2 (manganese dichloride)
            # Add more as discovered
        }
        
        # Base compound patterns for hydrate normalization
        self.hydration_patterns = [
            r'\s*[x•·]\s*\d*\s*h2o\s*$',     # x H2O, • H2O, · H2O, x 4 H2O
            r'\s*\.\s*\d*\s*h2o\s*$',        # .H2O, .4H2O
            r'\s*\d*\s*h2o\s*$',             # 4H2O, H2O
            r'\s*(mono|di|tri|tetra|penta|hexa|hepta|octa|nona|deca)hydrate\s*$',
        ]
        
        # Known base compound mappings (base compound -> CHEBI ID)
        self.base_compound_chebi = {
            'MnCl2': 'CHEBI:7773',   # manganese dichloride
            'MnCl₂': 'CHEBI:7773',   # alternative notation
            'MgCl2': 'CHEBI:6636',   # already mapped correctly
            'CaCl2': 'CHEBI:3312',   # already mapped correctly
            'FeCl2': 'CHEBI:24458',  # already mapped correctly
            'ZnSO4': 'CHEBI:35176',  # already mapped correctly
            'CuSO4': 'CHEBI:23414',  # already mapped correctly
            'FeSO4': 'CHEBI:75836',  # already mapped correctly
        }

    def normalize_hydrated_compound(self, compound: str) -> str:
        """Extract base compound name from hydrated form."""
        compound_lower = compound.lower().strip()
        
        # Try each hydration pattern
        for pattern in self.hydration_patterns:
            match = re.search(pattern, compound_lower)
            if match:
                # Remove the hydration part
                base_compound = compound[:match.start()].strip()
                return base_compound
        
        # If no hydration pattern found, return original
        return compound

    def identify_problematic_mappings(self, df: pd.DataFrame) -> pd.DataFrame:
        """Find hydrated compounds mapped to ingredient codes."""
        
        # Find compounds containing H2O or hydrate patterns
        hydrated_mask = df['original'].str.contains(
            r'[Hh]2[Oo]|hydrate', 
            regex=True, 
            na=False
        )
        
        # Find compounds mapped to ingredient codes
        ingredient_mask = df['mapped'].str.startswith('ingredient:', na=False)
        
        # Combine both conditions
        problematic = df[hydrated_mask & ingredient_mask].copy()
        
        return problematic

    def fix_compound_mappings(self, df: pd.DataFrame) -> pd.DataFrame:
        """Fix hydrated compound mappings."""
        
        logger.info("🔧 Fixing hydrated compound mappings...")
        
        updated_df = df.copy()
        fixes_applied = 0
        
        for ingredient_code, chebi_id in self.ingredient_to_chebi.items():
            # Find all rows with this ingredient code
            mask = updated_df['mapped'] == ingredient_code
            matching_rows = updated_df[mask]
            
            if len(matching_rows) > 0:
                # Log the compounds being fixed
                compounds = matching_rows['original'].unique()
                logger.info(f"Fixing {len(matching_rows)} rows with {ingredient_code}:")
                for compound in compounds:
                    count = len(matching_rows[matching_rows['original'] == compound])
                    logger.info(f"  {compound} ({count} occurrences) → {chebi_id}")
                
                # Apply the fix
                updated_df.loc[mask, 'mapped'] = chebi_id
                fixes_applied += len(matching_rows)
        
        logger.info(f"Applied fixes to {fixes_applied} rows")
        return updated_df

    def analyze_remaining_hydrated_issues(self, df: pd.DataFrame) -> None:
        """Analyze remaining hydrated compounds that need attention."""
        
        logger.info("🔍 Analyzing remaining hydrated compound issues...")
        
        # Find hydrated compounds not mapped to CHEBI
        hydrated_mask = df['original'].str.contains(
            r'[Hh]2[Oo]|hydrate', 
            regex=True, 
            na=False
        )
        
        non_chebi_mask = ~df['mapped'].str.startswith('CHEBI:', na=False)
        
        remaining_issues = df[hydrated_mask & non_chebi_mask]
        
        if len(remaining_issues) > 0:
            logger.warning(f"Found {len(remaining_issues)} hydrated compounds still not mapped to CHEBI:")
            
            # Group by compound and mapping type
            compound_summary = remaining_issues.groupby(['original', 'mapped']).size().reset_index(name='count')
            
            for _, row in compound_summary.iterrows():
                compound = row['original']
                mapping = row['mapped'] if pd.notna(row['mapped']) else 'UNMAPPED'
                count = row['count']
                
                # Try to extract base compound
                base_compound = self.normalize_hydrated_compound(compound)
                
                logger.warning(f"  {compound} → {mapping} ({count} rows)")
                if base_compound != compound:
                    logger.warning(f"    Base compound: {base_compound}")
        else:
            logger.info("✅ No remaining hydrated compounds with mapping issues")

    def suggest_oak_candidates(self, df: pd.DataFrame) -> List[str]:
        """Suggest hydrated compounds for OAK annotation."""
        
        # Find hydrated compounds that are unmapped or mapped to non-CHEBI
        hydrated_mask = df['original'].str.contains(
            r'[Hh]2[Oo]|hydrate', 
            regex=True, 
            na=False
        )
        
        non_chebi_mask = ~df['mapped'].str.startswith('CHEBI:', na=False)
        
        candidates = df[hydrated_mask & non_chebi_mask]['original'].unique()
        
        # Extract base compounds
        base_compounds = []
        for compound in candidates:
            base_compound = self.normalize_hydrated_compound(compound)
            if base_compound not in base_compounds:
                base_compounds.append(base_compound)
        
        return list(candidates) + base_compounds

def main():
    """Main function."""
    
    print("🔧 Fixing Hydrated Compound Mappings")
    print("=" * 40)
    
    # Input and output files
    input_file = Path("composition_kg_mapping_with_oak_chebi.tsv")
    output_file = Path("composition_kg_mapping_hydration_fixed.tsv")
    
    if not input_file.exists():
        logger.error(f"Input file not found: {input_file}")
        return
    
    # Load data
    logger.info(f"📊 Loading data from: {input_file}")
    df = pd.read_csv(input_file, sep='\t')
    logger.info(f"Loaded {len(df):,} mapping entries")
    
    # Initialize fixer
    mapper = HydratedCompoundMapper()
    
    # Identify problematic mappings
    logger.info("🔍 Identifying problematic hydrated compound mappings...")
    problematic = mapper.identify_problematic_mappings(df)
    
    if len(problematic) > 0:
        logger.info(f"Found {len(problematic)} problematic mappings:")
        compound_summary = problematic.groupby(['original', 'mapped']).size().reset_index(name='count')
        for _, row in compound_summary.iterrows():
            logger.info(f"  {row['original']} → {row['mapped']} ({row['count']} occurrences)")
    else:
        logger.info("No hydrated compounds mapped to ingredient codes found")
    
    # Apply fixes
    fixed_df = mapper.fix_compound_mappings(df)
    
    # Analyze remaining issues
    mapper.analyze_remaining_hydrated_issues(fixed_df)
    
    # Calculate improvement
    original_chebi = (df['mapped'].str.startswith('CHEBI:', na=False)).sum()
    fixed_chebi = (fixed_df['mapped'].str.startswith('CHEBI:', na=False)).sum()
    
    logger.info(f"📈 Mapping improvement:")
    logger.info(f"  CHEBI mappings: {original_chebi} → {fixed_chebi} (+{fixed_chebi - original_chebi})")
    logger.info(f"  CHEBI coverage: {original_chebi/len(df)*100:.2f}% → {fixed_chebi/len(df)*100:.2f}%")
    
    # Suggest OAK candidates
    oak_candidates = mapper.suggest_oak_candidates(fixed_df)
    if oak_candidates:
        logger.info(f"💡 Suggested compounds for OAK annotation: {len(oak_candidates)}")
        oak_file = Path("hydrated_compounds_for_oak.txt")
        with open(oak_file, 'w') as f:
            for compound in sorted(set(oak_candidates)):
                f.write(f"{compound}\n")
        logger.info(f"Saved candidates to: {oak_file}")
    
    # Save fixed mapping
    logger.info(f"💾 Saving fixed mapping to: {output_file}")
    fixed_df.to_csv(output_file, sep='\t', index=False)
    
    logger.info("✅ Hydrated compound mapping fixes completed!")
    
    print(f"\n🚀 Next steps:")
    print(f"  1. Review the fixed mapping: {output_file}")
    print(f"  2. If satisfied, replace the original:")
    print(f"     mv {output_file} {input_file}")
    if oak_candidates:
        print(f"  3. Run OAK annotation on remaining candidates:")
        print(f"     runoak -i sqlite:obo:chebi annotate --text-file hydrated_compounds_for_oak.txt --output hydrated_oak_annotations.json")

if __name__ == "__main__":
    main()