#!/usr/bin/env python3

import json
import pandas as pd
from pathlib import Path
from src.scripts.compute_media_properties import MediaPropertiesCalculator

def process_all_media():
    """Process all sample media and create summary."""
    calculator = MediaPropertiesCalculator()
    results = []
    
    # Find all sample medium JSON files
    media_files = list(Path("media_pdfs").glob("medium_*_composition.json"))
    
    for media_file in media_files:
        print(f"Processing {media_file.name}...")
        
        with open(media_file, 'r') as f:
            medium_data = json.load(f)
        
        # Extract composition array
        composition = medium_data.get('composition', [])
        
        # Convert format
        formatted_composition = []
        for comp in composition:
            formatted_composition.append({
                'compound': comp['name'],
                'g_l': float(comp['concentration']) if comp['unit'] == 'g/L' else 0
            })
        
        # Calculate properties
        props = calculator.analyze_composition(formatted_composition)
        
        # Compile results
        result = {
            'medium_id': medium_data.get('medium_id', media_file.stem),
            'medium_name': medium_data.get('name', 'Unknown'),
            'description': medium_data.get('description', ''),
            'ph': props['ph']['value'],
            'ph_confidence': props['ph']['confidence'],
            'salinity_percent': props['salinity']['percent_nacl'],
            'salinity_confidence': props['salinity']['confidence'],
            'ionic_strength': props['ionic_strength']['value'],
            'total_dissolved_solids': props['total_dissolved_solids']['value'],
            'compounds_recognized': props['analysis_quality']['recognition_rate'],
            'compounds_estimated': props['analysis_quality']['estimation_rate'],
            'total_coverage': props['analysis_quality']['total_coverage_rate']
        }
        
        results.append(result)
    
    # Create summary DataFrame
    df = pd.DataFrame(results)
    
    # Save results
    df.to_csv('media_summary.csv', index=False)
    
    # Create JSON summary
    with open('media_summary.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nProcessed {len(results)} media compositions")
    print(f"Results saved to media_summary.csv and media_summary.json")
    
    # Print summary statistics
    print("\n=== SUMMARY STATISTICS ===")
    print(f"pH range: {df['ph'].min():.2f} - {df['ph'].max():.2f}")
    print(f"Average pH: {df['ph'].mean():.2f}")
    print(f"Salinity range: {df['salinity_percent'].min():.3f}% - {df['salinity_percent'].max():.3f}%")
    print(f"Average salinity: {df['salinity_percent'].mean():.3f}%")
    print(f"Ionic strength range: {df['ionic_strength'].min():.3f} - {df['ionic_strength'].max():.3f} M")
    print(f"Average compound coverage: {df['total_coverage'].mean():.1f}%")
    
    return results

if __name__ == "__main__":
    process_all_media()