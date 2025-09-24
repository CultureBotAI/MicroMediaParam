#!/usr/bin/env python3
"""
Extract compounds from composition_kg_mapping.tsv that are NOT mapped to CHEBI
(either unmapped or mapped to other databases like PubChem, CAS, etc.)
"""

import pandas as pd
import logging
from pathlib import Path
from typing import List, Dict, Set

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def analyze_mapping_coverage(df: pd.DataFrame) -> Dict:
    """Analyze the current mapping coverage by database type."""
    
    # Count total rows and compounds
    total_rows = len(df)
    total_compounds = df['original'].nunique()
    
    # Identify mapping types
    unmapped_mask = df['mapped'].isna() | (df['mapped'] == '') | (df['mapped'].str.strip() == '')
    chebi_mask = df['mapped'].str.startswith('CHEBI:', na=False)
    pubchem_mask = df['mapped'].str.startswith('PubChem:', na=False) 
    cas_mask = df['mapped'].str.startswith('CAS-RN:', na=False)
    other_mapped_mask = ~unmapped_mask & ~chebi_mask & ~pubchem_mask & ~cas_mask
    
    # Count by category
    unmapped_rows = unmapped_mask.sum()
    chebi_rows = chebi_mask.sum()
    pubchem_rows = pubchem_mask.sum()
    cas_rows = cas_mask.sum()
    other_mapped_rows = other_mapped_mask.sum()
    
    # Count unique compounds by category
    unmapped_compounds = df[unmapped_mask]['original'].nunique()
    chebi_compounds = df[chebi_mask]['original'].nunique()
    pubchem_compounds = df[pubchem_mask]['original'].nunique()
    cas_compounds = df[cas_mask]['original'].nunique()
    other_mapped_compounds = df[other_mapped_mask]['original'].nunique()
    
    # Get unique database types for "other" category
    other_dbs = set()
    if other_mapped_rows > 0:
        other_mapped_values = df[other_mapped_mask]['mapped'].dropna()
        for value in other_mapped_values:
            if ':' in value:
                db_prefix = value.split(':', 1)[0]
                other_dbs.add(db_prefix)
    
    return {
        'total': {
            'rows': total_rows,
            'compounds': total_compounds
        },
        'unmapped': {
            'rows': unmapped_rows,
            'compounds': unmapped_compounds,
            'percentage': (unmapped_rows / total_rows * 100) if total_rows > 0 else 0
        },
        'chebi': {
            'rows': chebi_rows,
            'compounds': chebi_compounds,
            'percentage': (chebi_rows / total_rows * 100) if total_rows > 0 else 0
        },
        'pubchem': {
            'rows': pubchem_rows,
            'compounds': pubchem_compounds,
            'percentage': (pubchem_rows / total_rows * 100) if total_rows > 0 else 0
        },
        'cas': {
            'rows': cas_rows,
            'compounds': cas_compounds,
            'percentage': (cas_rows / total_rows * 100) if total_rows > 0 else 0
        },
        'other': {
            'rows': other_mapped_rows,
            'compounds': other_mapped_compounds,
            'percentage': (other_mapped_rows / total_rows * 100) if total_rows > 0 else 0,
            'databases': sorted(other_dbs)
        }
    }

def extract_non_chebi_compounds(mapping_file: Path) -> None:
    """Extract compounds that need CHEBI mapping."""
    
    print("🔍 Extracting Non-CHEBI Compounds for OAK/Fuzzy Mapping")
    print("=" * 55)
    
    if not mapping_file.exists():
        print(f"❌ Mapping file not found: {mapping_file}")
        return
    
    # Load mapping data
    print(f"📊 Loading mapping data from: {mapping_file}")
    df = pd.read_csv(mapping_file, sep='\t')
    
    # Analyze current coverage
    coverage = analyze_mapping_coverage(df)
    
    print(f"\n📈 Current Mapping Coverage Analysis:")
    print(f"   Total rows: {coverage['total']['rows']:,}")
    print(f"   Total unique compounds: {coverage['total']['compounds']:,}")
    print()
    print(f"   📋 Breakdown by database:")
    print(f"   ✅ CHEBI mapped: {coverage['chebi']['rows']:,} rows ({coverage['chebi']['percentage']:.1f}%) | {coverage['chebi']['compounds']} compounds")
    print(f"   🧪 PubChem mapped: {coverage['pubchem']['rows']:,} rows ({coverage['pubchem']['percentage']:.1f}%) | {coverage['pubchem']['compounds']} compounds")
    print(f"   🏷️  CAS-RN mapped: {coverage['cas']['rows']:,} rows ({coverage['cas']['percentage']:.1f}%) | {coverage['cas']['compounds']} compounds")
    
    if coverage['other']['rows'] > 0:
        print(f"   📦 Other databases: {coverage['other']['rows']:,} rows ({coverage['other']['percentage']:.1f}%) | {coverage['other']['compounds']} compounds")
        print(f"      Databases: {', '.join(coverage['other']['databases'])}")
    
    print(f"   ❌ Unmapped: {coverage['unmapped']['rows']:,} rows ({coverage['unmapped']['percentage']:.1f}%) | {coverage['unmapped']['compounds']} compounds")
    
    # Identify compounds that need CHEBI mapping
    # These are compounds that are either unmapped OR mapped to non-CHEBI databases
    needs_chebi_mask = ~df['mapped'].str.startswith('CHEBI:', na=False)
    needs_chebi_df = df[needs_chebi_mask].copy()
    
    # Get unique compounds that need CHEBI mapping
    compounds_needing_chebi = needs_chebi_df['original'].unique()
    
    print(f"\n🎯 Compounds Needing CHEBI Mapping:")
    print(f"   Total rows needing CHEBI: {len(needs_chebi_df):,}")
    print(f"   Unique compounds needing CHEBI: {len(compounds_needing_chebi):,}")
    print(f"   Percentage of total compounds: {len(compounds_needing_chebi)/coverage['total']['compounds']*100:.1f}%")
    
    # Show sample compounds
    print(f"\n🔍 Sample compounds needing CHEBI mapping:")
    for i, compound in enumerate(compounds_needing_chebi[:15], 1):
        # Check current mapping status
        compound_rows = df[df['original'] == compound]
        current_mapping = compound_rows['mapped'].iloc[0] if not compound_rows['mapped'].isna().all() else "UNMAPPED"
        row_count = len(compound_rows)
        print(f"   {i:2d}. {compound} [{current_mapping}] ({row_count} rows)")
    
    if len(compounds_needing_chebi) > 15:
        print(f"   ... and {len(compounds_needing_chebi) - 15} more compounds")
    
    # Filter out single letter compounds and other problematic entries
    print(f"\n🔧 Filtering compounds for OAK processing...")
    
    filtered_compounds = []
    excluded_compounds = []
    
    for compound in compounds_needing_chebi:
        # Skip single letter compounds
        if len(compound.strip()) <= 1:
            excluded_compounds.append(f"{compound} (single letter)")
            continue
            
        # Skip very short compounds that are likely elements or abbreviations
        if len(compound.strip()) <= 2 and compound.strip().isupper():
            excluded_compounds.append(f"{compound} (likely element/abbreviation)")
            continue
            
        # Skip compounds with only numbers and basic punctuation
        if not any(c.isalpha() for c in compound):
            excluded_compounds.append(f"{compound} (no letters)")
            continue
            
        filtered_compounds.append(compound)
    
    print(f"   Original compounds: {len(compounds_needing_chebi)}")
    print(f"   Filtered compounds: {len(filtered_compounds)}")
    print(f"   Excluded compounds: {len(excluded_compounds)}")
    
    if excluded_compounds:
        print(f"   Sample excluded: {excluded_compounds[:5]}")
    
    # Save compounds list for OAK/fuzzy processing
    compounds_file = Path("compounds_for_chebi_mapping.txt")
    print(f"\n💾 Saving filtered compound list to: {compounds_file}")
    
    with open(compounds_file, 'w') as f:
        for compound in sorted(filtered_compounds):
            f.write(f"{compound}\n")
    
    # Save detailed mapping data for these compounds
    details_file = Path("non_chebi_mapping_details.tsv")
    print(f"💾 Saving detailed mapping data to: {details_file}")
    
    needs_chebi_df.to_csv(details_file, sep='\t', index=False)
    
    # Create summary by current mapping type for compounds needing CHEBI
    print(f"\n📊 Breakdown of compounds needing CHEBI mapping:")
    
    summary_df = needs_chebi_df.groupby(['original', 'mapped']).size().reset_index(name='row_count')
    
    # Group by mapping type
    unmapped_compounds_df = summary_df[summary_df['mapped'].isna() | (summary_df['mapped'] == '')]
    pubchem_compounds_df = summary_df[summary_df['mapped'].str.startswith('PubChem:', na=False)]
    cas_compounds_df = summary_df[summary_df['mapped'].str.startswith('CAS-RN:', na=False)]
    other_compounds_df = summary_df[~summary_df['mapped'].isna() & 
                                   ~(summary_df['mapped'] == '') &
                                   ~summary_df['mapped'].str.startswith('PubChem:', na=False) &
                                   ~summary_df['mapped'].str.startswith('CAS-RN:', na=False)]
    
    print(f"   🚫 Completely unmapped: {len(unmapped_compounds_df)} compounds")
    print(f"   🧪 Currently PubChem-mapped: {len(pubchem_compounds_df)} compounds")  
    print(f"   🏷️  Currently CAS-RN-mapped: {len(cas_compounds_df)} compounds")
    print(f"   📦 Currently other-database-mapped: {len(other_compounds_df)} compounds")
    
    print(f"\n✅ Files created for OAK/fuzzy processing:")
    print(f"   📄 {compounds_file} - List of {len(filtered_compounds)} filtered compounds")
    print(f"   📊 {details_file} - Full mapping details ({len(needs_chebi_df):,} rows)")
    
    print(f"\n🚀 Next steps:")
    print(f"   1. Run Makefile target:")
    print(f"      make oak-chebi-mapping")
    print(f"   2. Or use OAK annotate directly:")
    print(f"      runoak -i sqlite:obo:chebi annotate --text-file {compounds_file} --output-type json --lexical-index-file data/chebi_lexical_index.db")
    print(f"   3. Or use the CHEBI fuzzy matcher:")
    print(f"      python chebi_fuzzy_matcher.py {compounds_file}")

def main():
    """Main function."""
    mapping_file = Path("composition_kg_mapping.tsv")
    extract_non_chebi_compounds(mapping_file)

if __name__ == "__main__":
    main()