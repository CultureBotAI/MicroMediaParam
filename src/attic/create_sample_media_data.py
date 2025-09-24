#!/usr/bin/env python3
"""
Create sample media composition data for testing the pipeline.

This creates realistic sample data based on common microbial growth media.
"""

import json
import os
from pathlib import Path

def create_sample_media_compositions():
    """Create sample JSON composition files for testing."""
    
    # Create media_pdfs directory if it doesn't exist
    media_dir = Path("media_pdfs")
    media_dir.mkdir(exist_ok=True)
    
    # Sample media compositions based on real microbial growth media
    sample_media = [
        {
            "medium_id": "1",
            "name": "LB Medium (Luria-Bertani)",
            "description": "Standard rich medium for bacterial culture",
            "composition": [
                {
                    "name": "tryptone",
                    "concentration": "10.0",
                    "unit": "g/L",
                    "role": "nitrogen source"
                },
                {
                    "name": "yeast extract",
                    "concentration": "5.0",
                    "unit": "g/L",
                    "role": "vitamin source"
                },
                {
                    "name": "sodium chloride",
                    "concentration": "10.0",
                    "unit": "g/L",
                    "role": "osmotic balance"
                }
            ],
            "pH": "7.0",
            "temperature": "37"
        },
        {
            "medium_id": "2", 
            "name": "M9 Minimal Medium",
            "description": "Defined minimal medium for E. coli",
            "composition": [
                {
                    "name": "glucose",
                    "concentration": "4.0",
                    "unit": "g/L",
                    "role": "carbon source"
                },
                {
                    "name": "sodium phosphate dibasic",
                    "concentration": "6.78",
                    "unit": "g/L",
                    "role": "buffer"
                },
                {
                    "name": "potassium phosphate monobasic",
                    "concentration": "3.0",
                    "unit": "g/L",
                    "role": "buffer"
                },
                {
                    "name": "sodium chloride",
                    "concentration": "0.5",
                    "unit": "g/L",
                    "role": "osmotic balance"
                },
                {
                    "name": "ammonium chloride",
                    "concentration": "1.0",
                    "unit": "g/L",
                    "role": "nitrogen source"
                },
                {
                    "name": "magnesium sulfate",
                    "concentration": "0.493",
                    "unit": "g/L",
                    "role": "cofactor"
                },
                {
                    "name": "calcium chloride",
                    "concentration": "0.011",
                    "unit": "g/L",
                    "role": "cofactor"
                }
            ],
            "pH": "7.4",
            "temperature": "37"
        },
        {
            "medium_id": "3",
            "name": "TSB (Tryptic Soy Broth)",
            "description": "General purpose medium for cultivation of bacteria",
            "composition": [
                {
                    "name": "tryptone",
                    "concentration": "17.0",
                    "unit": "g/L",
                    "role": "nitrogen source"
                },
                {
                    "name": "soy peptone",
                    "concentration": "3.0",
                    "unit": "g/L",
                    "role": "nitrogen source"
                },
                {
                    "name": "sodium chloride",
                    "concentration": "5.0",
                    "unit": "g/L",
                    "role": "osmotic balance"
                },
                {
                    "name": "dipotassium hydrogen phosphate",
                    "concentration": "2.5",
                    "unit": "g/L",
                    "role": "buffer"
                },
                {
                    "name": "glucose",
                    "concentration": "2.5",
                    "unit": "g/L",
                    "role": "carbon source"
                }
            ],
            "pH": "7.3",
            "temperature": "37"
        },
        {
            "medium_id": "4",
            "name": "Marine Broth 2216",
            "description": "Medium for cultivation of marine bacteria",
            "composition": [
                {
                    "name": "peptone",
                    "concentration": "5.0",
                    "unit": "g/L",
                    "role": "nitrogen source"
                },
                {
                    "name": "yeast extract",
                    "concentration": "1.0",
                    "unit": "g/L",
                    "role": "vitamin source"
                },
                {
                    "name": "ferric citrate",
                    "concentration": "0.1",
                    "unit": "g/L",
                    "role": "iron source"
                },
                {
                    "name": "sodium chloride",
                    "concentration": "19.45",
                    "unit": "g/L",
                    "role": "osmotic balance"
                },
                {
                    "name": "magnesium chloride",
                    "concentration": "5.9",
                    "unit": "g/L",
                    "role": "mineral"
                },
                {
                    "name": "magnesium sulfate",
                    "concentration": "3.24",
                    "unit": "g/L",
                    "role": "mineral"
                },
                {
                    "name": "calcium chloride",
                    "concentration": "1.8",
                    "unit": "g/L",
                    "role": "mineral"
                },
                {
                    "name": "potassium chloride",
                    "concentration": "0.55",
                    "unit": "g/L",
                    "role": "mineral"
                },
                {
                    "name": "sodium bicarbonate",
                    "concentration": "0.16",
                    "unit": "g/L",
                    "role": "buffer"
                }
            ],
            "pH": "7.6",
            "temperature": "25"
        },
        {
            "medium_id": "5",
            "name": "Nutrient Broth",
            "description": "Basic medium for cultivation of non-fastidious organisms",
            "composition": [
                {
                    "name": "peptone",
                    "concentration": "5.0",
                    "unit": "g/L",
                    "role": "nitrogen source"
                },
                {
                    "name": "beef extract",
                    "concentration": "3.0",
                    "unit": "g/L",
                    "role": "nitrogen/vitamin source"
                },
                {
                    "name": "sodium chloride",
                    "concentration": "8.0",
                    "unit": "g/L",
                    "role": "osmotic balance",
                    "optional": "false"
                }
            ],
            "pH": "7.4",
            "temperature": "37"
        }
    ]
    
    # Write sample JSON files
    for i, medium in enumerate(sample_media, 1):
        filename = f"medium_{i}_composition.json"
        filepath = media_dir / filename
        with open(filepath, 'w') as f:
            json.dump(medium, f, indent=2)
        print(f"Created: {filepath}")
    
    print(f"\n✓ Created {len(sample_media)} sample media composition files in {media_dir}")
    
    # Also create a sample PDF file marker
    sample_pdf = media_dir / "medium_pdf.pdf"
    if not sample_pdf.exists():
        sample_pdf.touch()
        print(f"Created: {sample_pdf}")

if __name__ == "__main__":
    create_sample_media_compositions()