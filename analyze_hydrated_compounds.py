#!/usr/bin/env python3
"""
Analyze unmapped compounds containing hydration patterns in the composition mapping file.
"""

import pandas as pd
import re
from collections import defaultdict

def main():
    # Read the mapping file
    df = pd.read_csv('composition_kg_mapping_with_oak_chebi.tsv', sep='\t', dtype=str)
    
    # Define hydration patterns
    hydration_patterns = [
        (r'\.?\s*x?\s*\d*\s*H2O', 'x N H2O format'),  # .H2O, x H2O, x 2 H2O, etc.
        (r'\s+(mono|di|tri|tetra|penta|hexa|hepta|octa|nona|deca)hydrate', 'named hydrate'),
        (r'hydrate', 'general hydrate'),
        (r'•\s*\d*\s*H2O', 'bullet notation'),  # bullet point notation
        (r'·\s*\d*\s*H2O', 'middle dot notation'),  # middle dot notation
        (r'\.\s*\d*\s*H2O', 'dot notation'), # dot notation
        (r'\s+H2O', 'space H2O'),         # space H2O
        (r'·nH2O', 'generic n hydrate'),          # generic n hydrate
    ]
    
    # Find compounds with hydration patterns
    hydrated_compounds = []
    pattern_stats = defaultdict(int)
    
    for idx, row in df.iterrows():
        original = str(row.get('original', ''))
        mapped = str(row.get('mapped', ''))
        
        # Check if compound contains hydration patterns
        is_hydrated = False
        matched_patterns = []
        original_lower = original.lower()
        
        for pattern, pattern_name in hydration_patterns:
            if re.search(pattern, original_lower):
                is_hydrated = True
                matched_patterns.append(pattern_name)
                pattern_stats[pattern_name] += 1
        
        if is_hydrated:
            # Check if it's unmapped or not mapped to CHEBI
            is_unmapped = (
                pd.isna(mapped) or 
                mapped == '' or 
                mapped == 'nan' or
                not mapped.startswith('CHEBI:')
            )
            
            hydrated_compounds.append({
                'original': original,
                'mapped': mapped,
                'is_unmapped': is_unmapped,
                'medium_id': row.get('medium_id', ''),
                'patterns': matched_patterns
            })
    
    print("=== HYDRATED COMPOUNDS ANALYSIS ===")
    print(f'Total hydrated compounds found: {len(hydrated_compounds)}')
    
    # Count unmapped vs mapped
    unmapped_count = sum(1 for c in hydrated_compounds if c['is_unmapped'])
    mapped_count = len(hydrated_compounds) - unmapped_count
    
    print(f'Unmapped hydrated compounds: {unmapped_count}')
    print(f'Mapped hydrated compounds: {mapped_count}')
    print(f'Mapping success rate: {mapped_count/len(hydrated_compounds)*100:.1f}%')
    print()
    
    # Pattern statistics
    print("=== HYDRATION PATTERN STATISTICS ===")
    for pattern_name, count in sorted(pattern_stats.items(), key=lambda x: x[1], reverse=True):
        print(f'{pattern_name}: {count} compounds')
    print()
    
    # Show examples of unmapped hydrated compounds
    print("=== EXAMPLES OF UNMAPPED HYDRATED COMPOUNDS ===")
    unmapped_examples = [c for c in hydrated_compounds if c['is_unmapped']]
    
    # Group by pattern type
    unmapped_by_pattern = defaultdict(list)
    for example in unmapped_examples:
        for pattern in example['patterns']:
            unmapped_by_pattern[pattern].append(example)
    
    for pattern_name, examples in unmapped_by_pattern.items():
        print(f"\n{pattern_name.upper()} ({len(examples)} unmapped compounds):")
        for i, example in enumerate(examples[:10], 1):  # Show first 10 of each type
            print(f"  {i:2d}. {example['original']} (mapped to: {example['mapped']})")
        if len(examples) > 10:
            print(f"  ... and {len(examples)-10} more")
    
    print()
    print("=== EXAMPLES OF SUCCESSFULLY MAPPED HYDRATED COMPOUNDS ===")
    mapped_examples = [c for c in hydrated_compounds if not c['is_unmapped']][:15]
    for i, example in enumerate(mapped_examples, 1):
        print(f"{i:2d}. {example['original']} → {example['mapped']}")
    
    # Analysis of base compounds
    print("\n=== BASE COMPOUND ANALYSIS ===")
    print("Checking if base (non-hydrated) forms are mapped...")
    
    base_compounds = set()
    unmapped_hydrates = [c for c in hydrated_compounds if c['is_unmapped']]
    
    for compound in unmapped_hydrates[:20]:  # Check first 20
        original = compound['original']
        # Try to extract base compound name by removing hydration parts
        base_name = re.sub(r'\.?\s*x?\s*\d*\s*H2O', '', original, flags=re.IGNORECASE)
        base_name = re.sub(r'\s+(mono|di|tri|tetra|penta|hexa|hepta|octa|nona|deca)hydrate', '', base_name, flags=re.IGNORECASE)
        base_name = re.sub(r'hydrate', '', base_name, flags=re.IGNORECASE)
        base_name = re.sub(r'•\s*\d*\s*H2O', '', base_name, flags=re.IGNORECASE)
        base_name = re.sub(r'·\s*\d*\s*H2O', '', base_name, flags=re.IGNORECASE)
        base_name = base_name.strip()
        
        # Check if base compound exists in the mapping
        base_matches = df[df['original'].str.contains(re.escape(base_name), case=False, na=False)]
        base_chebi_matches = base_matches[base_matches['mapped'].str.startswith('CHEBI:', na=False)]
        
        if not base_chebi_matches.empty:
            print(f"✓ Base compound '{base_name}' (from '{original}') HAS ChEBI mapping:")
            for _, match in base_chebi_matches.head(2).iterrows():
                print(f"    {match['original']} → {match['mapped']}")
        else:
            print(f"✗ Base compound '{base_name}' (from '{original}') has no ChEBI mapping")
    
    # Summary recommendations
    print("\n=== RECOMMENDATIONS FOR IMPROVING HYDRATION NORMALIZATION ===")
    
    total_unmapped = len(unmapped_examples)
    if total_unmapped > 0:
        print(f"1. {total_unmapped} hydrated compounds remain unmapped ({total_unmapped/len(hydrated_compounds)*100:.1f}%)")
        
        # Most common unmapped patterns
        most_common_pattern = max(unmapped_by_pattern.items(), key=lambda x: len(x[1]))
        print(f"2. Most common unmapped pattern: '{most_common_pattern[0]}' with {len(most_common_pattern[1])} compounds")
        
        print("3. Current hydration patterns being handled:")
        current_patterns = [
            r'\.?\s*x?\s*\d*\s*H2O',  # From normalize_hydration_forms.py line 78
            r'\s+(mono|di|tri|tetra|penta|hexa|hepta|octa|nona|deca)hydrate',
            r'hydrate', r'dihydrate', r'trihydrate', etc.
        ]
        for pattern in current_patterns[:5]:
            print(f"   - {pattern}")
        
        print("4. Missing patterns that should be added:")
        missing_patterns = ['•', '·', '.nH2O', 'bullet/dot notations']
        for pattern in missing_patterns:
            print(f"   - {pattern}")
            
        print("5. Suggested improvements:")
        print("   - Enhance normalize_hydration_forms.py to handle bullet/dot notations")
        print("   - Add more comprehensive regex patterns for hydrate detection")
        print("   - Implement base compound lookup for unmapped hydrates")
        print("   - Consider fuzzy matching between hydrated and anhydrous forms")
    else:
        print("Excellent! All hydrated compounds are successfully mapped.")

if __name__ == "__main__":
    main()