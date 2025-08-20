#!/usr/bin/env python3
"""
Configuration for IUPAC Chemical Data Processing

Contains settings, API endpoints, and compound lists for chemical data processing.

Author: MicroMediaParam Project
"""

from pathlib import Path
from typing import Dict, List

# File paths
DEFAULT_DATA_DIR = Path("data/chemical_processing")
DEFAULT_OUTPUT_FILE = Path("chemical_properties.tsv")

# API endpoints and settings
API_CONFIG = {
    'pubchem': {
        'base_url': 'https://pubchem.ncbi.nlm.nih.gov/rest/pug',
        'rate_limit': 0.5,  # seconds between requests
        'timeout': 30,      # request timeout in seconds
    },
    'chebi': {
        'base_url': 'https://www.ebi.ac.uk/chebi',
        'rate_limit': 1.0,
        'timeout': 30,
    },
    'nist': {
        'base_url': 'https://webbook.nist.gov/chemistry',
        'rate_limit': 1.0,
        'timeout': 30,
    }
}

# Priority compounds for media analysis
PRIORITY_COMPOUNDS = [
    # Essential inorganic salts
    "sodium chloride",
    "potassium chloride", 
    "magnesium chloride",
    "calcium chloride",
    "ammonium chloride",
    
    # Sulfates
    "sodium sulfate",
    "magnesium sulfate",
    "iron sulfate",
    "zinc sulfate",
    "copper sulfate",
    "manganese sulfate",
    
    # Carbonates and bicarbonates
    "calcium carbonate",
    "sodium bicarbonate",
    "sodium carbonate",
    
    # Phosphates
    "potassium phosphate",
    "sodium phosphate",
    
    # Trace elements
    "boric acid",
    "zinc chloride",
    "iron chloride",
    "nickel chloride",
    "cobalt chloride",
    "copper chloride",
    
    # Carbon sources
    "glucose",
    "sucrose",
    "fructose",
    "lactose",
    "maltose",
    
    # Organic salts
    "sodium acetate",
    "sodium pyruvate",
    "sodium citrate",
    "sodium lactate",
    
    # Amino acids
    "glycine",
    "alanine",
    "cysteine",
    "glutamine",
    "asparagine",
    
    # Buffers
    "tris",
    "hepes",
    "mes",
    "mops",
    "pipes",
    
    # Vitamins and growth factors
    "thiamine",
    "riboflavin",
    "nicotinic acid",
    "pyridoxine",
    "biotin",
    "folic acid",
    "cobalamin"
]

# Default mapping files to analyze
DEFAULT_MAPPING_FILES = [
    "high_confidence_compound_mappings_normalized_ingredient_enhanced_normalized.tsv",
    "composition_kg_mapping.tsv",
    "unaccounted_compound_matches.tsv",
    "unified_compound_mappings.tsv"
]

# Chemical property estimation parameters
PROPERTY_ESTIMATION = {
    'default_activity_coefficient': 1.0,
    'default_solubility_g_per_L': 100.0,
    'default_molecular_weight': 100.0,
    
    # Solubility categories (g/L)
    'solubility_categories': {
        'insoluble': 0.01,
        'slightly_soluble': 1.0,
        'moderately_soluble': 100.0,
        'soluble': 500.0,
        'highly_soluble': 1000.0
    },
    
    # Activity coefficient adjustments for complex compounds
    'activity_coefficients': {
        'complex_mixtures': 0.7,    # peptone, yeast extract
        'large_molecules': 0.8,     # proteins, polymers
        'ionic_compounds': 1.0,     # simple salts
        'neutral_molecules': 1.0    # sugars, amino acids
    }
}

# Validation parameters
VALIDATION = {
    'min_molecular_weight': 10.0,
    'max_molecular_weight': 10000.0,
    'min_solubility': 0.0001,
    'max_solubility': 10000.0,
    'max_pka_value': 20.0,
    'min_pka_value': -10.0
}

# Logging configuration
LOGGING_CONFIG = {
    'level': 'INFO',
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'file': 'chemical_data_processing.log'
}

def get_config() -> Dict:
    """Get complete configuration dictionary."""
    return {
        'api': API_CONFIG,
        'priority_compounds': PRIORITY_COMPOUNDS,
        'default_mapping_files': DEFAULT_MAPPING_FILES,
        'property_estimation': PROPERTY_ESTIMATION,
        'validation': VALIDATION,
        'logging': LOGGING_CONFIG,
        'paths': {
            'data_dir': DEFAULT_DATA_DIR,
            'output_file': DEFAULT_OUTPUT_FILE
        }
    }