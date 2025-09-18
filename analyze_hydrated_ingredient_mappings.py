#!/usr/bin/env python3
"""
Analyze hydrated compounds in composition_kg_mapping_with_oak_chebi.tsv
that are mapped to ingredient codes instead of CHEBI IDs.

This script finds compounds containing:
- "H2O" (hydrated compounds)
- "hydrate" patterns
- Other hydration patterns

That are mapped to "ingredient:" codes instead of CHEBI IDs.
"""

import csv
import re
from collections import defaultdict

def analyze_hydrated_ingredient_mappings():
    """Analyze the mapping file for hydrated compounds mapped to ingredient codes."""
    
    filename = "composition_kg_mapping_with_oak_chebi.tsv"
    
    # Patterns to identify hydrated compounds
    hydration_patterns = [
        r'H2O',               # Direct H2O notation
        r'x\s*\d+\s*H2O',     # x N H2O format
        r'hydrate',           # Contains "hydrate"
        r'monohydrate',       # Contains "monohydrate"
        r'dihydrate',         # Contains "dihydrate"
        r'trihydrate',        # Contains "trihydrate" 
        r'tetrahydrate',      # Contains "tetrahydrate"
        r'pentahydrate',      # Contains "pentahydrate"
        r'hexahydrate',       # Contains "hexahydrate"
        r'heptahydrate',      # Contains "heptahydrate"
        r'octahydrate',       # Contains "octahydrate"
        r'nonahydrate',       # Contains "nonahydrate"
        r'decahydrate',       # Contains "decahydrate"
        r'dodecahydrate',     # Contains "dodecahydrate"
    ]
    
    # Combine patterns
    hydration_regex = re.compile('|'.join(hydration_patterns), re.IGNORECASE)
    
    # Storage for results
    hydrated_ingredient_mappings = []
    hydrated_chebi_mappings = []
    all_ingredient_mappings = []
    
    # Compound counts
    compound_counts = defaultdict(int)
    ingredient_compound_counts = defaultdict(int)
    
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter='\t')
            
            for row in reader:
                original = row.get('original', '')
                mapped = row.get('mapped', '')
                
                # Check if compound is hydrated
                is_hydrated = bool(hydration_regex.search(original))
                
                if is_hydrated:
                    compound_counts[original] += 1
                    
                    if mapped.startswith('ingredient:'):
                        hydrated_ingredient_mappings.append({
                            'medium_id': row.get('medium_id', ''),
                            'original': original,
                            'mapped': mapped,
                            'value': row.get('value', ''),
                            'concentration': row.get('concentration', ''),
                            'unit': row.get('unit', ''),
                        })
                        ingredient_compound_counts[original] += 1
                    elif mapped.startswith('CHEBI:'):
                        hydrated_chebi_mappings.append({
                            'original': original,
                            'mapped': mapped,
                        })
                
                # Count all ingredient mappings for context
                if mapped.startswith('ingredient:'):
                    all_ingredient_mappings.append({
                        'original': original,
                        'mapped': mapped,
                        'is_hydrated': is_hydrated
                    })
    
    except FileNotFoundError:
        print(f"Error: File '{filename}' not found.")
        return
    except Exception as e:
        print(f"Error reading file: {e}")
        return
    
    # Print analysis results
    print("=== HYDRATED COMPOUNDS MAPPED TO INGREDIENT CODES ===\n")
    
    print(f"Total unique hydrated compounds found: {len(compound_counts)}")
    print(f"Hydrated compounds mapped to ingredient codes: {len(ingredient_compound_counts)}")
    print(f"Total occurrences of hydrated compounds mapped to ingredient codes: {len(hydrated_ingredient_mappings)}")
    print()
    
    # Group by compound name
    print("=== HYDRATED COMPOUNDS → INGREDIENT MAPPINGS ===\n")
    compound_mappings = defaultdict(lambda: {'count': 0, 'ingredient_codes': set(), 'examples': []})
    
    for entry in hydrated_ingredient_mappings:
        compound = entry['original']
        ingredient_code = entry['mapped']
        compound_mappings[compound]['count'] += 1
        compound_mappings[compound]['ingredient_codes'].add(ingredient_code)
        if len(compound_mappings[compound]['examples']) < 3:  # Keep up to 3 examples
            compound_mappings[compound]['examples'].append(
                f"Medium {entry['medium_id']}: {entry['value']} {entry['unit']}"
            )
    
    # Sort by count (descending)
    sorted_compounds = sorted(compound_mappings.items(), key=lambda x: x[1]['count'], reverse=True)
    
    for compound, data in sorted_compounds:
        ingredient_codes_str = ', '.join(sorted(data['ingredient_codes']))
        print(f"'{compound}' → {ingredient_codes_str}")
        print(f"  Occurrences: {data['count']}")
        print(f"  Examples:")
        for example in data['examples']:
            print(f"    - {example}")
        print()
    
    # Show some hydrated compounds that ARE properly mapped to CHEBI
    print("=== EXAMPLES OF HYDRATED COMPOUNDS PROPERLY MAPPED TO CHEBI ===\n")
    chebi_examples = defaultdict(set)
    for entry in hydrated_chebi_mappings[:20]:  # Show first 20
        chebi_examples[entry['original']].add(entry['mapped'])
    
    for i, (compound, chebi_ids) in enumerate(chebi_examples.items()):
        if i >= 10:  # Limit to 10 examples
            break
        chebi_str = ', '.join(sorted(chebi_ids))
        print(f"'{compound}' → {chebi_str}")
    
    print(f"\n... and {len(chebi_examples) - 10} more hydrated compounds properly mapped to CHEBI")
    
    # Summary statistics
    print("\n=== SUMMARY STATISTICS ===\n")
    total_mappings = len(all_ingredient_mappings)
    hydrated_ingredient_mappings_count = len(hydrated_ingredient_mappings)
    
    print(f"Total entries mapped to ingredient codes: {total_mappings}")
    print(f"Of these, hydrated compounds: {hydrated_ingredient_mappings_count} ({hydrated_ingredient_mappings_count/total_mappings*100:.1f}%)")
    print(f"Unique hydrated compounds mapped to ingredient codes: {len(ingredient_compound_counts)}")
    print()
    
    # Check for other hydration patterns
    print("=== HYDRATION PATTERNS FOUND ===\n")
    pattern_counts = defaultdict(int)
    for compound in compound_counts.keys():
        for pattern in hydration_patterns:
            if re.search(pattern, compound, re.IGNORECASE):
                pattern_counts[pattern] += 1
    
    for pattern, count in sorted(pattern_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"'{pattern}': {count} compounds")
    
    # Show specific ingredient codes
    print("\n=== INGREDIENT CODES USED FOR HYDRATED COMPOUNDS ===\n")
    ingredient_code_usage = defaultdict(int)
    for entry in hydrated_ingredient_mappings:
        ingredient_code_usage[entry['mapped']] += 1
    
    for code, count in sorted(ingredient_code_usage.items(), key=lambda x: x[1], reverse=True):
        print(f"{code}: {count} occurrences")

if __name__ == "__main__":
    analyze_hydrated_ingredient_mappings()