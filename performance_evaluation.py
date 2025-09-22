#!/usr/bin/env python3
"""
Performance evaluation of the enhanced ingredient extraction system.
Compares before/after and provides comprehensive metrics.
"""

import json
import random
from pathlib import Path
from collections import defaultdict
from enhanced_media_extractor import EnhancedMediaExtractor

def run_performance_evaluation():
    """Run comprehensive performance evaluation on enhanced extraction."""
    
    print("🧪 ENHANCED INGREDIENT EXTRACTION PERFORMANCE EVALUATION")
    print("=" * 70)
    
    extractor = EnhancedMediaExtractor()
    
    # Test on a representative sample
    text_dir = Path("media_texts")
    all_files = list(text_dir.glob("*.md"))
    
    # Take a stratified sample
    sample_size = min(200, len(all_files))  # Test on 200 files for comprehensive eval
    sample_files = random.sample(all_files, sample_size)
    
    print(f"📊 Testing on {sample_size} randomly selected files from {len(all_files)} total")
    
    # Performance metrics
    results = {
        'total_files': sample_size,
        'successful_extractions': 0,
        'failed_extractions': 0,
        'total_ingredients': 0,
        'total_instructions': 0,
        'files_with_instructions': 0,
        'by_source': defaultdict(lambda: {'files': 0, 'ingredients': 0, 'avg_ingredients': 0}),
        'by_quality': defaultdict(int),
        'extraction_methods': defaultdict(int),
        'sample_results': []
    }
    
    print(f"\n⚡ Processing files...")
    
    for i, file_path in enumerate(sample_files):
        if i % 50 == 0:
            print(f"   Processed {i}/{sample_size} files...")
        
        try:
            result = extractor.extract_media_data(file_path)
            
            if result and (result.get('composition') or result.get('preparation_instructions')):
                results['successful_extractions'] += 1
                
                # Count ingredients
                ingredients = result.get('composition', [])
                num_ingredients = len(ingredients)
                results['total_ingredients'] += num_ingredients
                
                # Count instructions
                instructions = result.get('preparation_instructions', '')
                if instructions:
                    results['files_with_instructions'] += 1
                    results['total_instructions'] += len(instructions)
                
                # Source statistics
                source = result.get('source', 'unknown')
                results['by_source'][source]['files'] += 1
                results['by_source'][source]['ingredients'] += num_ingredients
                
                # Quality assessment
                if num_ingredients >= 10:
                    results['by_quality']['high'] += 1
                elif num_ingredients >= 5:
                    results['by_quality']['medium'] += 1
                elif num_ingredients >= 2:
                    results['by_quality']['low'] += 1
                else:
                    results['by_quality']['very_low'] += 1
                
                # Extraction method statistics
                for ingredient in ingredients:
                    method = ingredient.get('extraction_method', 'unknown')
                    results['extraction_methods'][method] += 1
                
                # Save good examples
                if len(results['sample_results']) < 5 and num_ingredients >= 5:
                    results['sample_results'].append({
                        'file': file_path.name,
                        'medium_name': result.get('medium_name', ''),
                        'source': source,
                        'ingredients': num_ingredients,
                        'has_instructions': bool(instructions),
                        'instruction_length': len(instructions)
                    })
            
            else:
                results['failed_extractions'] += 1
                
        except Exception as e:
            print(f"   Error processing {file_path}: {e}")
            results['failed_extractions'] += 1
    
    # Calculate derived metrics
    success_rate = (results['successful_extractions'] / results['total_files']) * 100
    avg_ingredients = results['total_ingredients'] / results['successful_extractions'] if results['successful_extractions'] > 0 else 0
    avg_instructions = results['total_instructions'] / results['files_with_instructions'] if results['files_with_instructions'] > 0 else 0
    
    # Calculate source averages
    for source_data in results['by_source'].values():
        if source_data['files'] > 0:
            source_data['avg_ingredients'] = source_data['ingredients'] / source_data['files']
    
    print(f"\n✅ Processing complete!")
    
    # Display results
    print(f"\n📈 OVERALL PERFORMANCE METRICS")
    print(f"   Total files tested: {results['total_files']}")
    print(f"   Successful extractions: {results['successful_extractions']} ({success_rate:.1f}%)")
    print(f"   Failed extractions: {results['failed_extractions']} ({100-success_rate:.1f}%)")
    print(f"   Total ingredients extracted: {results['total_ingredients']}")
    print(f"   Average ingredients per file: {avg_ingredients:.1f}")
    print(f"   Files with preparation instructions: {results['files_with_instructions']} ({results['files_with_instructions']/results['total_files']*100:.1f}%)")
    print(f"   Average instruction length: {avg_instructions:.0f} characters")
    
    print(f"\n🎯 QUALITY DISTRIBUTION")
    total_successful = results['successful_extractions']
    for quality, count in results['by_quality'].items():
        percentage = (count / total_successful) * 100 if total_successful > 0 else 0
        
        if quality == 'high':
            quality_desc = "High (≥10 ingredients)"
        elif quality == 'medium':
            quality_desc = "Medium (5-9 ingredients)"
        elif quality == 'low':
            quality_desc = "Low (2-4 ingredients)"
        else:
            quality_desc = "Very Low (0-1 ingredients)"
            
        print(f"   {quality_desc}: {count} files ({percentage:.1f}%)")
    
    print(f"\n🏷️ BY SOURCE")
    for source, stats in results['by_source'].items():
        print(f"   {source.upper()}: {stats['files']} files, avg {stats['avg_ingredients']:.1f} ingredients/file")
    
    print(f"\n⚙️ EXTRACTION METHODS")
    total_ingredients = sum(results['extraction_methods'].values())
    for method, count in results['extraction_methods'].items():
        percentage = (count / total_ingredients) * 100 if total_ingredients > 0 else 0
        print(f"   {method}: {count} ingredients ({percentage:.1f}%)")
    
    print(f"\n🌟 SAMPLE HIGH-QUALITY EXTRACTIONS")
    for i, sample in enumerate(results['sample_results'], 1):
        print(f"   {i}. {sample['file']}")
        print(f"      Medium: {sample['medium_name']}")
        print(f"      Source: {sample['source']}, Ingredients: {sample['ingredients']}")
        print(f"      Has instructions: {sample['has_instructions']} ({sample['instruction_length']} chars)")
    
    # Compare with previous results (if available)
    print(f"\n📊 COMPARISON WITH PREVIOUS EXTRACTION")
    try:
        # Load previous results if available
        previous_dir = Path("media_compositions_improved")
        if previous_dir.exists():
            previous_files = list(previous_dir.glob("*_composition.json"))
            previous_total_ingredients = 0
            previous_files_processed = 0
            
            for prev_file in previous_files:
                try:
                    with open(prev_file, 'r') as f:
                        data = json.load(f)
                    previous_total_ingredients += len(data.get('composition', []))
                    previous_files_processed += 1
                except:
                    pass
            
            if previous_files_processed > 0:
                prev_avg = previous_total_ingredients / previous_files_processed
                improvement = ((avg_ingredients - prev_avg) / prev_avg) * 100 if prev_avg > 0 else 0
                
                print(f"   Previous extraction: {prev_avg:.1f} avg ingredients/file")
                print(f"   Enhanced extraction: {avg_ingredients:.1f} avg ingredients/file")
                print(f"   Improvement: {improvement:+.1f}%")
                
                if improvement > 0:
                    print(f"   🎉 Enhanced extraction is {improvement:.1f}% better!")
                else:
                    print(f"   ⚠️ Enhanced extraction shows {abs(improvement):.1f}% change")
    
    except Exception as e:
        print(f"   Could not compare with previous results: {e}")
    
    print(f"\n💾 SUMMARY STATISTICS")
    print(f"   Success Rate: {success_rate:.1f}%")
    print(f"   Ingredient Capture: {avg_ingredients:.1f} ingredients/file")
    print(f"   Instruction Capture: {results['files_with_instructions']/results['total_files']*100:.1f}% of files")
    print(f"   High Quality Files: {results['by_quality']['high']/total_successful*100:.1f}% (≥10 ingredients)" if total_successful > 0 else "   High Quality Files: 0%")
    
    # Save detailed results
    detailed_results = {
        'evaluation_summary': {
            'sample_size': sample_size,
            'success_rate_percent': success_rate,
            'avg_ingredients_per_file': avg_ingredients,
            'avg_instruction_length': avg_instructions,
            'files_with_instructions_percent': (results['files_with_instructions']/results['total_files']*100)
        },
        'quality_distribution': dict(results['by_quality']),
        'source_performance': dict(results['by_source']),
        'extraction_methods': dict(results['extraction_methods']),
        'sample_results': results['sample_results']
    }
    
    with open('enhanced_extraction_performance.json', 'w') as f:
        json.dump(detailed_results, f, indent=2)
    
    print(f"\n📁 Detailed results saved to: enhanced_extraction_performance.json")
    
    return detailed_results

if __name__ == "__main__":
    run_performance_evaluation()