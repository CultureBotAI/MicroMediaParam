#!/usr/bin/env python3
"""
Analyze lower quality and failure cases to ensure ALL ingredients are captured.
"""

import json
import re
from pathlib import Path
from collections import defaultdict
from improved_composition_extractor import ImprovedCompositionExtractor

def analyze_missing_ingredients():
    """Analyze files with low compound counts and failures to find missing ingredients."""
    
    improved_dir = Path("media_compositions_improved")
    text_dir = Path("media_texts")
    
    # Get all processed files and their quality
    processed_files = {}
    failed_files = set()
    
    # Load improved extractions
    for comp_file in improved_dir.glob("*_composition.json"):
        try:
            with open(comp_file, 'r') as f:
                data = json.load(f)
            
            medium_id = data['medium_id']
            num_compounds = len(data.get('composition', []))
            processed_files[medium_id] = {
                'compounds': num_compounds,
                'data': data
            }
        except Exception as e:
            print(f"Error reading {comp_file}: {e}")
    
    # Find all text files that weren't processed or had low quality
    all_text_files = list(text_dir.glob("*.md"))
    print(f"Found {len(all_text_files)} text files total")
    print(f"Successfully processed {len(processed_files)} files")
    
    # Identify different categories
    very_low_quality = []  # 0-2 compounds
    low_quality = []       # 3-4 compounds  
    failed_extractions = []
    
    for text_file in all_text_files:
        medium_id = text_file.stem
        
        if medium_id in processed_files:
            compounds = processed_files[medium_id]['compounds']
            if compounds <= 2:
                very_low_quality.append((text_file, compounds))
            elif compounds <= 4:
                low_quality.append((text_file, compounds))
        else:
            failed_extractions.append(text_file)
    
    print(f"\nCategory breakdown:")
    print(f"  Failed extractions: {len(failed_extractions)}")
    print(f"  Very low quality (≤2 compounds): {len(very_low_quality)}")
    print(f"  Low quality (3-4 compounds): {len(low_quality)}")
    
    # Analyze samples from each category
    extractor = ImprovedCompositionExtractor()
    
    def analyze_sample_files(file_list, category_name, max_samples=10):
        """Analyze sample files from a category to find missing patterns."""
        print(f"\n=== ANALYZING {category_name.upper()} ===")
        
        samples = file_list[:max_samples] if len(file_list) > max_samples else file_list
        
        for i, item in enumerate(samples):
            if isinstance(item, tuple):
                text_file, compound_count = item
                print(f"\n{i+1}. {text_file.name} (extracted {compound_count} compounds)")
            else:
                text_file = item
                print(f"\n{i+1}. {text_file.name} (failed extraction)")
            
            # Read original text
            try:
                with open(text_file, 'r') as f:
                    content = f.read()
                
                # Look for potential missing compounds
                lines = content.split('\n')
                
                print(f"   Original content analysis:")
                print(f"   - Total lines: {len(lines)}")
                
                # Look for chemical-like terms that might have been missed
                potential_compounds = []
                compound_indicators = [
                    r'\b[A-Z][a-z]*[A-Z][a-z0-9]*\b',  # Chemical formulas
                    r'\b\w+\s+(?:chloride|sulfate|phosphate|nitrate|carbonate|acetate|citrate)\b',
                    r'\b(?:sodium|potassium|calcium|magnesium|iron|zinc|copper)\s+\w+\b',
                    r'\b\w+\s+extract\b',
                    r'\b\w+\s+peptone\b',
                    r'\w+ose\b',  # sugars
                    r'\b\w+\s+acid\b'
                ]
                
                for line in lines[:50]:  # Check first 50 lines
                    line = line.strip()
                    if line and not re.match(r'^\d+\.', line):  # Skip procedure text
                        for pattern in compound_indicators:
                            matches = re.findall(pattern, line, re.IGNORECASE)
                            for match in matches:
                                if len(match) > 2 and match not in potential_compounds:
                                    potential_compounds.append(match)
                
                # Look for concentration patterns that might indicate missed compounds
                concentration_lines = []
                for line in lines:
                    if re.search(r'\d+\.?\d*\s*(?:g|mg|ml|mM|μM|M)(?:/L|/l)?\b', line):
                        concentration_lines.append(line.strip())
                
                print(f"   - Potential compounds found: {len(potential_compounds)}")
                if potential_compounds:
                    print(f"   - Examples: {potential_compounds[:5]}")
                
                print(f"   - Lines with concentrations: {len(concentration_lines)}")
                if concentration_lines:
                    print(f"   - Examples: {concentration_lines[:3]}")
                
                # Check what the extractor actually found
                if isinstance(item, tuple):
                    medium_id = text_file.stem
                    if medium_id in processed_files:
                        extracted = processed_files[medium_id]['data']['composition']
                        print(f"   - Actually extracted: {[c['name'] for c in extracted]}")
                
                # Identify potential format issues
                format_issues = []
                
                # Check for separated tabular format (DSMZ style)
                has_compound_section = False
                has_number_section = False
                has_unit_section = False
                
                for line in lines:
                    line = line.strip()
                    if re.match(r'^[A-Z][a-z]*', line) and len(line) > 2:
                        has_compound_section = True
                    elif re.match(r'^\d+\.?\d*$', line):
                        has_number_section = True
                    elif line in ['g', 'mg', 'ml', 'mM', 'μM']:
                        has_unit_section = True
                
                if has_compound_section and has_number_section and not has_unit_section:
                    format_issues.append("Missing unit section in tabular format")
                
                if not has_compound_section and has_number_section:
                    format_issues.append("Numbers without clear compound names")
                
                # Check for complex solution references
                if 'solution' in content.lower() and 'stock' in content.lower():
                    format_issues.append("Complex solution/stock format")
                
                if format_issues:
                    print(f"   - Format issues detected: {format_issues}")
                
            except Exception as e:
                print(f"   Error reading file: {e}")
    
    # Analyze each category
    analyze_sample_files(failed_extractions, "FAILED EXTRACTIONS", 5)
    analyze_sample_files(very_low_quality, "VERY LOW QUALITY", 5)
    analyze_sample_files(low_quality, "LOW QUALITY", 5)
    
    # Overall recommendations
    print(f"\n=== RECOMMENDATIONS ===")
    
    # Calculate what percentage might have missing ingredients
    total_problematic = len(failed_extractions) + len(very_low_quality) + len(low_quality)
    total_files = len(all_text_files)
    
    print(f"Problematic files: {total_problematic}/{total_files} ({total_problematic/total_files*100:.1f}%)")
    print(f"")
    print(f"Priority improvements needed:")
    print(f"1. Handle {len(failed_extractions)} completely failed extractions")
    print(f"2. Improve {len(very_low_quality)} very low quality extractions")
    print(f"3. Enhance {len(low_quality)} low quality extractions")
    
    return {
        'failed': len(failed_extractions),
        'very_low': len(very_low_quality),
        'low': len(low_quality),
        'total_problematic': total_problematic,
        'total_files': total_files
    }

if __name__ == "__main__":
    analyze_missing_ingredients()