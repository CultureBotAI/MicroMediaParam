#!/usr/bin/env python3
"""
Analyze the quality of extracted compositions to identify patterns in noise and successful extractions.
"""

import json
import re
from pathlib import Path
from collections import defaultdict, Counter
import random

def analyze_extraction_quality():
    """Analyze extraction quality across a representative sample."""
    
    # Load all extracted compositions
    composition_files = list(Path("media_compositions").glob("*_composition.json"))
    print(f"Found {len(composition_files)} composition files")
    
    # Sample analysis on 100 random files for comprehensive understanding
    sample_size = min(100, len(composition_files))
    sample_files = random.sample(composition_files, sample_size)
    
    # Analysis metrics
    source_stats = defaultdict(lambda: {'total': 0, 'empty': 0, 'valid_compounds': 0, 'noise_compounds': 0})
    compound_patterns = Counter()
    noise_patterns = Counter()
    unit_patterns = Counter()
    
    valid_chemical_indicators = [
        'acid', 'chloride', 'sulfate', 'phosphate', 'nitrate', 'sodium', 'potassium', 
        'calcium', 'magnesium', 'iron', 'glucose', 'peptone', 'extract', 'agar',
        'carbonate', 'bicarbonate', 'hydroxide', 'oxide', 'citrate', 'acetate'
    ]
    
    noise_indicators = [
        'page', 'tel', 'fax', 'email', 'www', 'copyright', 'ltd', 'inc', 'gmbh',
        'reviewed', 'created', 'approved', 'revision', 'autoclave', 'sterilize',
        'nov', 'jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'dec',
        'due', 'for', 'make', 'add', 'mix', 'adjust', 'filter'
    ]
    
    detailed_results = []
    
    for i, comp_file in enumerate(sample_files):
        print(f"Analyzing {i+1}/{sample_size}: {comp_file.name}")
        
        try:
            with open(comp_file, 'r') as f:
                data = json.load(f)
            
            source = data.get('source', 'unknown')
            medium_name = data.get('medium_name', '')
            composition = data.get('composition', [])
            
            source_stats[source]['total'] += 1
            
            if not composition:
                source_stats[source]['empty'] += 1
                continue
            
            # Analyze each compound
            file_analysis = {
                'file': comp_file.name,
                'source': source,
                'medium_name': medium_name,
                'total_compounds': len(composition),
                'valid_compounds': 0,
                'noise_compounds': 0,
                'compounds': []
            }
            
            for comp in composition:
                name = comp.get('name', '').lower().strip()
                concentration = comp.get('concentration', 0)
                unit = comp.get('unit', '')
                
                if not name:
                    continue
                
                # Classify compound
                is_valid = any(indicator in name for indicator in valid_chemical_indicators)
                is_noise = any(indicator in name for indicator in noise_indicators)
                
                # Additional validation
                if len(name) < 3 or name in ['g', 'ml', 'l', 'per', 'to', 'of', 'and', 'or']:
                    is_noise = True
                    is_valid = False
                
                # Check for reasonable concentration values
                has_valid_concentration = isinstance(concentration, (int, float)) and 0 < concentration < 1000
                
                compound_analysis = {
                    'name': name,
                    'concentration': concentration,
                    'unit': unit,
                    'is_valid': is_valid,
                    'is_noise': is_noise,
                    'has_valid_concentration': has_valid_concentration
                }
                
                file_analysis['compounds'].append(compound_analysis)
                
                if is_valid and has_valid_concentration:
                    source_stats[source]['valid_compounds'] += 1
                    file_analysis['valid_compounds'] += 1
                    compound_patterns[name] += 1
                elif is_noise or not has_valid_concentration:
                    source_stats[source]['noise_compounds'] += 1
                    file_analysis['noise_compounds'] += 1
                    noise_patterns[name] += 1
                
                unit_patterns[unit] += 1
            
            detailed_results.append(file_analysis)
            
        except Exception as e:
            print(f"Error analyzing {comp_file}: {e}")
    
    # Print analysis results
    print("\n" + "="*60)
    print("EXTRACTION QUALITY ANALYSIS")
    print("="*60)
    
    print(f"\nAnalyzed {len(detailed_results)} files from {sample_size} sample")
    
    print(f"\n📊 BY SOURCE:")
    for source, stats in source_stats.items():
        total = stats['total']
        empty = stats['empty']
        valid = stats['valid_compounds']
        noise = stats['noise_compounds']
        if total > 0:
            print(f"  {source.upper()}: {total} files")
            print(f"    Empty: {empty} ({empty/total*100:.1f}%)")
            print(f"    Valid compounds: {valid}")
            print(f"    Noise compounds: {noise}")
            if valid + noise > 0:
                print(f"    Quality ratio: {valid/(valid+noise)*100:.1f}% valid")
    
    print(f"\n🧪 TOP VALID COMPOUNDS:")
    for compound, count in compound_patterns.most_common(15):
        print(f"  {compound}: {count}")
    
    print(f"\n🗑️ TOP NOISE PATTERNS:")
    for noise, count in noise_patterns.most_common(15):
        print(f"  {noise}: {count}")
    
    print(f"\n📏 UNIT PATTERNS:")
    for unit, count in unit_patterns.most_common(10):
        print(f"  '{unit}': {count}")
    
    # Find files with high quality extraction
    high_quality_files = []
    for result in detailed_results:
        if result['total_compounds'] > 0:
            quality_ratio = result['valid_compounds'] / result['total_compounds']
            if quality_ratio > 0.7 and result['valid_compounds'] >= 3:
                high_quality_files.append((result['file'], quality_ratio, result['valid_compounds']))
    
    high_quality_files.sort(key=lambda x: x[1], reverse=True)
    
    print(f"\n✅ HIGH QUALITY EXTRACTIONS ({len(high_quality_files)} files):")
    for filename, ratio, valid_count in high_quality_files[:10]:
        print(f"  {filename}: {ratio*100:.1f}% quality, {valid_count} valid compounds")
    
    # Save detailed analysis
    with open('extraction_quality_analysis.json', 'w') as f:
        json.dump({
            'summary': dict(source_stats),
            'sample_size': sample_size,
            'high_quality_files': high_quality_files,
            'detailed_results': detailed_results[:20]  # Save first 20 for review
        }, f, indent=2)
    
    print(f"\n💾 Detailed analysis saved to extraction_quality_analysis.json")
    
    # Recommendations
    print(f"\n💡 RECOMMENDATIONS:")
    total_valid = sum(stats['valid_compounds'] for stats in source_stats.values())
    total_noise = sum(stats['noise_compounds'] for stats in source_stats.values())
    
    if total_valid > 0:
        print(f"  • Focus on {len(high_quality_files)} high-quality files first")
        print(f"  • Overall valid/noise ratio: {total_valid/(total_valid+total_noise)*100:.1f}%")
        
        # Source-specific recommendations
        best_sources = [(source, stats['valid_compounds']/(stats['valid_compounds']+stats['noise_compounds'])) 
                       for source, stats in source_stats.items() 
                       if stats['valid_compounds'] + stats['noise_compounds'] > 0]
        best_sources.sort(key=lambda x: x[1], reverse=True)
        
        if best_sources:
            print(f"  • Best source format: {best_sources[0][0]} ({best_sources[0][1]*100:.1f}% quality)")
            print(f"  • Consider processing {best_sources[0][0]} files first")
    
    return detailed_results

if __name__ == "__main__":
    analyze_extraction_quality()