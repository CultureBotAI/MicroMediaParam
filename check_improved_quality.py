#!/usr/bin/env python3

import json
from pathlib import Path
from collections import defaultdict

def check_improved_quality():
    """Quick quality check on improved extractions."""
    
    improved_dir = Path("media_compositions_improved")
    files = list(improved_dir.glob("*_composition.json"))
    
    print(f"Checking {len(files)} improved extractions...")
    
    # Stats
    total_compounds = 0
    quality_stats = defaultdict(int)
    source_stats = defaultdict(lambda: {'files': 0, 'compounds': 0})
    
    # Sample good extractions
    good_examples = []
    
    for file_path in files:
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            source = data.get('source', 'unknown')
            composition = data.get('composition', [])
            num_compounds = len(composition)
            
            total_compounds += num_compounds
            source_stats[source]['files'] += 1
            source_stats[source]['compounds'] += num_compounds
            
            # Quality assessment
            if num_compounds >= 10:
                quality_stats['high'] += 1
                if len(good_examples) < 3:
                    good_examples.append((file_path.name, data))
            elif num_compounds >= 5:
                quality_stats['medium'] += 1
            elif num_compounds >= 2:
                quality_stats['low'] += 1
            else:
                quality_stats['very_low'] += 1
        
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
    
    print(f"\n=== IMPROVED EXTRACTION QUALITY ===")
    print(f"Total files: {len(files)}")
    print(f"Total compounds: {total_compounds}")
    print(f"Average compounds per file: {total_compounds/len(files):.1f}")
    
    print(f"\nQuality Distribution:")
    for quality, count in quality_stats.items():
        print(f"  {quality}: {count} files ({count/len(files)*100:.1f}%)")
    
    print(f"\nBy Source:")
    for source, stats in source_stats.items():
        avg_compounds = stats['compounds'] / stats['files'] if stats['files'] > 0 else 0
        print(f"  {source}: {stats['files']} files, avg {avg_compounds:.1f} compounds/file")
    
    print(f"\nExample High-Quality Extractions:")
    for filename, data in good_examples:
        print(f"  {filename}: {data['medium_name']}")
        print(f"    Source: {data['source']}, Compounds: {len(data['composition'])}")
        for comp in data['composition'][:3]:
            print(f"      - {comp['name']}: {comp['concentration']} {comp['unit']}")
        print()

if __name__ == "__main__":
    check_improved_quality()