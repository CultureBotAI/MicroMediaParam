#!/usr/bin/env python3

import json
from src.scripts.compute_media_properties import MediaPropertiesCalculator

# Load medium 1 composition
with open('media_pdfs/medium_1_composition.json', 'r') as f:
    medium_data = json.load(f)

# Extract composition array
composition = medium_data['composition']

# Convert format to what the script expects
formatted_composition = []
for comp in composition:
    formatted_composition.append({
        'compound': comp['name'],
        'g_l': float(comp['concentration']) if comp['unit'] == 'g/L' else 0
    })

# Calculate properties
calculator = MediaPropertiesCalculator()
results = calculator.analyze_composition(formatted_composition)

print(json.dumps(results, indent=2))