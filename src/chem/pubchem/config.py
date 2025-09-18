#!/usr/bin/env python3
"""
PubChem Pipeline Configuration

Configuration settings and constants for the PubChem chemical data processing pipeline.

Author: MicroMediaParam Project
"""

from pathlib import Path
from typing import Dict, List

# PubChem API endpoints
PUBCHEM_REST_API = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
PUBCHEM_POWER_USER_API = "https://pubchem.ncbi.nlm.nih.gov/rest/pug_view"

# FTP paths for bulk data downloads
PUBCHEM_FTP_BASE = "ftp.ncbi.nlm.nih.gov"
PUBCHEM_BULK_PATHS = {
    'iupac_names': '/pubchem/Compound/Extras/CID-IUPAC.gz',
    'smiles': '/pubchem/Compound/Extras/CID-SMILES.gz', 
    'synonyms_filtered': '/pubchem/Compound/Extras/CID-Synonym-filtered.gz',
    'synonyms_unfiltered': '/pubchem/Compound/Extras/CID-Synonym-unfiltered.gz',
    'sdf_files': '/pubchem/Compound/CURRENT-Full/SDF/'
}

# Rate limiting settings
API_RATE_LIMIT = 0.2  # seconds between API requests
BULK_DOWNLOAD_TIMEOUT = 3600  # seconds for bulk file downloads

# Property keys to retrieve from PubChem API
PUBCHEM_PROPERTY_KEYS = [
    'MolecularFormula', 'MolecularWeight', 'IsomericSMILES', 
    'IUPACName', 'InChI', 'InChIKey', 'HeavyAtomCount',
    'Charge', 'HBondDonorCount', 'HBondAcceptorCount',
    'RotatableBondCount', 'TPSA', 'XLogP', 'Complexity'
]

# Functional group pKa values for estimation
FUNCTIONAL_GROUP_PKA = {
    # Acids
    'carboxylic_acid': 4.75,
    'phenol': 10.0,
    'alcohol': 15.5,
    'thiol': 10.5,
    'sulfonic_acid': -3.0,
    
    # Bases
    'primary_amine': 10.8,
    'secondary_amine': 11.0,
    'tertiary_amine': 9.8,
    'imidazole': 6.0,
    'guanidine': 12.5,
    
    # Phosphates
    'phosphate_1': 2.15,
    'phosphate_2': 7.20,
    'phosphate_3': 12.35,
    
    # Common buffer compounds
    'tris': 8.07,
    'hepes': 7.55,
    'mes': 6.15,
    'mops': 7.20,
    'pipes': 6.80,
    'acetate': 4.76,
    'citrate_1': 3.13,
    'citrate_2': 4.76,
    'citrate_3': 6.40
}

# SMILES patterns for functional group detection
SMILES_FUNCTIONAL_GROUPS = {
    'carboxylic_acid': r'C\(=O\)O[H]?',
    'phenol': r'c[OH]',
    'alcohol': r'[CH][OH]',
    'primary_amine': r'[CH2]N[H2]?',
    'secondary_amine': r'[CH]N[H]?[CH]',
    'tertiary_amine': r'[N][CH3]{3}|[N]\([CH]\)',
    'phosphate': r'P\(=O\)\(O\)',
    'sulfonic_acid': r'S\(=O\)\(=O\)O',
    'thiol': r'[CH]SH',
    'imidazole': r'c1c[nH]cn1',
    'guanidine': r'NC\(=N\)N'
}

# Atomic masses for molecular weight calculation
ATOMIC_MASSES = {
    'H': 1.008, 'He': 4.003, 'Li': 6.941, 'Be': 9.012, 'B': 10.811,
    'C': 12.011, 'N': 14.007, 'O': 15.999, 'F': 18.998, 'Ne': 20.180,
    'Na': 22.990, 'Mg': 24.305, 'Al': 26.982, 'Si': 28.086, 'P': 30.974,
    'S': 32.065, 'Cl': 35.453, 'Ar': 39.948, 'K': 39.098, 'Ca': 40.078,
    'Sc': 44.956, 'Ti': 47.867, 'V': 50.942, 'Cr': 51.996, 'Mn': 54.938,
    'Fe': 55.845, 'Co': 58.933, 'Ni': 58.693, 'Cu': 63.546, 'Zn': 65.38,
    'Ga': 69.723, 'Ge': 72.64, 'As': 74.922, 'Se': 78.96, 'Br': 79.904,
    'Kr': 83.798, 'Rb': 85.468, 'Sr': 87.62, 'Y': 88.906, 'Zr': 91.224,
    'Nb': 92.906, 'Mo': 95.96, 'Tc': 98.0, 'Ru': 101.07, 'Rh': 102.906,
    'Pd': 106.42, 'Ag': 107.868, 'Cd': 112.411, 'In': 114.818, 'Sn': 118.710,
    'Sb': 121.760, 'Te': 127.60, 'I': 126.90, 'Xe': 131.293
}

# Common ion charges for ionic compounds
COMMON_ION_CHARGES = {
    # Cations
    'Na': {'Na+': 1},
    'K': {'K+': 1},
    'Li': {'Li+': 1},
    'Cs': {'Cs+': 1},
    'Rb': {'Rb+': 1},
    'Ca': {'Ca2+': 2},
    'Mg': {'Mg2+': 2},
    'Sr': {'Sr2+': 2},
    'Ba': {'Ba2+': 2},
    'Al': {'Al3+': 3},
    'Fe': {'Fe2+': 2, 'Fe3+': 3},
    'Cu': {'Cu+': 1, 'Cu2+': 2},
    'Zn': {'Zn2+': 2},
    'Mn': {'Mn2+': 2, 'Mn3+': 3},
    'Co': {'Co2+': 2, 'Co3+': 3},
    'Ni': {'Ni2+': 2},
    'Pb': {'Pb2+': 2},
    'Sn': {'Sn2+': 2, 'Sn4+': 4},
    
    # Anions
    'Cl': {'Cl-': -1},
    'Br': {'Br-': -1},
    'I': {'I-': -1},
    'F': {'F-': -1},
    'O': {'O2-': -2},
    'S': {'S2-': -2}
}

# Polyatomic ion charges
POLYATOMIC_ION_CHARGES = {
    'SO4': {'SO42-': -2},
    'SO3': {'SO32-': -2},
    'PO4': {'PO43-': -3},
    'HPO4': {'HPO42-': -2},
    'H2PO4': {'H2PO4-': -1},
    'CO3': {'CO32-': -2},
    'HCO3': {'HCO3-': -1},
    'NO3': {'NO3-': -1},
    'NO2': {'NO2-': -1},
    'ClO4': {'ClO4-': -1},
    'ClO3': {'ClO3-': -1},
    'ClO2': {'ClO2-': -1},
    'ClO': {'ClO-': -1},
    'OH': {'OH-': -1},
    'CN': {'CN-': -1},
    'SCN': {'SCN-': -1},
    'MnO4': {'MnO4-': -1},
    'CrO4': {'CrO42-': -2},
    'Cr2O7': {'Cr2O72-': -2}
}

# Compound name normalization patterns
NAME_NORMALIZATION_PATTERNS = [
    # Remove hydration states - comprehensive patterns
    (r'\s*[x×]\s*\d*\s*[Hh]2[Oo]\s*$', ''),       # x H2O, x 2 H2O at end
    (r'\s*[x×]\s+[Hh]2[Oo]\s*$', ''),             # x h2o (space separated) at end
    (r'\s*[·•]\s*\d*\s*[Hh]2[Oo]\s*$', ''),       # · H2O, · 2 H2O at end
    (r'\s*\.\s*\d*\s*[Hh]2[Oo]\s*$', ''),         # . H2O, . 2 H2O at end
    (r'\s*\*\s*\d*\s*[Hh]2[Oo]\s*$', ''),         # * H2O, * 2 H2O at end
    (r'\s+\d*\s*[Hh]2[Oo]\s*$', ''),              # space 2 H2O at end
    (r'\s*\(\d*\s*[Hh]2[Oo]\)\s*$', ''),          # (H2O), (2 H2O) at end
    (r'\s*\+\s*\d*\s*[Hh]2[Oo]\s*$', ''),         # + H2O, + 2 H2O at end
    (r'\s*·\s*n\s*[Hh]2[Oo]\s*$', ''),            # · n H2O at end
    (r'\s*[x×]\s*n\s*[Hh]2[Oo]\s*$', ''),         # x n H2O at end
    
    # Named hydrates (full word boundaries)
    (r'\s*\bhydrate\b\s*$', ''),
    (r'\s*\bmonohydrate\b\s*$', ''),
    (r'\s*\bdihydrate\b\s*$', ''),
    (r'\s*\btrihydrate\b\s*$', ''),
    (r'\s*\btetrahydrate\b\s*$', ''),
    (r'\s*\bpentahydrate\b\s*$', ''),
    (r'\s*\bhexahydrate\b\s*$', ''),
    (r'\s*\bheptahydrate\b\s*$', ''),
    (r'\s*\boctahydrate\b\s*$', ''),
    (r'\s*\bnonahydrate\b\s*$', ''),
    (r'\s*\bdecahydrate\b\s*$', ''),
    
    # Clean up artifacts from hydration removal
    (r'\s*\+\s*$', ''),              # Remove trailing +
    (r'\s*×\s*$', ''),               # Remove trailing ×
    (r'\s*·\s*n\s*$', ''),           # Remove trailing · n
    (r'\s*x\s*n?\s*$', ''),          # Remove trailing x or x n
    (r'\s*\bmon[oa]?\s*$', ''),      # Remove trailing mono/mona
    (r'\s*\btri?\s*$', ''),          # Remove trailing tri
    
    # Remove stereochemistry
    (r'\(R\)', ''),
    (r'\(S\)', ''),
    (r'\([RS]\)', ''),
    (r'\(±\)', ''),
    (r'\([dD][lL]\)', ''),
    (r'\([lL]\)', ''),
    (r'\([dD]\)', ''),
    (r'[dD]-', ''),
    (r'[lL]-', ''),
    (r'[dD]\+', ''),
    (r'[lL]\+', ''),
    
    # Remove pH indicators and other descriptors
    (r'\s*pH\s*\d+\.?\d*', ''),
    (r'\s*anhydrous\s*', ''),
    (r'\s*pure\s*', ''),
    (r'\s*reagent\s*grade\s*', ''),
    (r'\s*analytical\s*grade\s*', ''),
    (r'\s*technical\s*grade\s*', ''),
    
    # Normalize spacing and punctuation
    (r'\s+', ' '),
    (r'^[- ]+', ''),
    (r'[- ]+$', ''),
]

# Compounds to exclude from processing (too complex or not chemical compounds)
EXCLUDED_COMPOUNDS = {
    'peptone', 'tryptone', 'casitone', 'proteose peptone',
    'yeast extract', 'malt extract', 'beef extract',
    'agar', 'agarose', 'gellan gum',
    'nutrient broth', 'luria broth', 'lb medium',
    'blood', 'serum', 'plasma',
    'vitamin mix', 'trace element', 'micronutrient',
    'mineral mix', 'salt mix',
    'undefined', 'complex', 'mixture'
}

# High priority compounds for microbial media
PRIORITY_COMPOUNDS = [
    # Inorganic salts
    'sodium chloride', 'potassium chloride', 'magnesium chloride',
    'calcium chloride', 'ammonium chloride', 'sodium sulfate',
    'magnesium sulfate', 'calcium carbonate', 'sodium bicarbonate',
    'sodium carbonate', 'potassium phosphate', 'sodium phosphate',
    
    # Trace elements
    'iron sulfate', 'zinc sulfate', 'copper sulfate', 'manganese sulfate',
    'iron chloride', 'zinc chloride', 'nickel chloride', 'cobalt chloride',
    'copper chloride', 'boric acid', 'sodium molybdate',
    
    # Carbon sources
    'glucose', 'sucrose', 'fructose', 'lactose', 'maltose',
    'sodium acetate', 'sodium pyruvate', 'sodium citrate',
    'sodium succinate', 'sodium fumarate', 'sodium malate',
    
    # Nitrogen sources
    'ammonium sulfate', 'sodium nitrate', 'potassium nitrate',
    'urea', 'glycine', 'alanine', 'glutamine', 'asparagine',
    
    # Buffers
    'tris', 'hepes', 'mes', 'mops', 'pipes', 'bis-tris',
    'tricine', 'bicine', 'tes', 'epps',
    
    # Growth factors
    'thiamine', 'riboflavin', 'nicotinic acid', 'biotin',
    'folic acid', 'pyridoxine', 'cobalamin', 'pantothenic acid'
]

# Default directories
DEFAULT_DATA_DIR = Path("data/pubchem_processing")
DEFAULT_CACHE_DIR = Path("data/pubchem_cache")
DEFAULT_BULK_DIR = Path("data/pubchem_bulk")
DEFAULT_OUTPUT_FILE = Path("chemical_properties.tsv")

# File naming conventions
RAW_DATA_FILENAME = "pubchem_raw_data.json"
PROCESSED_DATA_FILENAME = "pubchem_processed_data.json"
COMPARISON_REPORT_FILENAME = "pubchem_comparison_report.json"
CID_INDEX_FILENAME = "cid_lookup_index.json"

# Processing settings
MAX_COMPOUND_NAME_LENGTH = 200
MIN_COMPOUND_NAME_LENGTH = 2
MAX_CHARGE_STATE = 3
MIN_CHARGE_STATE = -3
MAX_PKA_VALUE = 14
MIN_PKA_VALUE = -3
MAX_SOLUBILITY = 10000  # g/L
MIN_SOLUBILITY = 0.0001  # g/L

# Quality control thresholds
MIN_MOLECULAR_WEIGHT = 10.0
MAX_MOLECULAR_WEIGHT = 2000.0
MIN_HEAVY_ATOM_COUNT = 1
MAX_HEAVY_ATOM_COUNT = 100

# Logging configuration
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_LEVEL = 'INFO'

def get_default_config() -> Dict:
    """Get default configuration dictionary."""
    return {
        'api': {
            'rest_endpoint': PUBCHEM_REST_API,
            'power_user_endpoint': PUBCHEM_POWER_USER_API,
            'rate_limit': API_RATE_LIMIT,
            'timeout': 60
        },
        'ftp': {
            'base_url': PUBCHEM_FTP_BASE,
            'paths': PUBCHEM_BULK_PATHS,
            'timeout': BULK_DOWNLOAD_TIMEOUT
        },
        'processing': {
            'property_keys': PUBCHEM_PROPERTY_KEYS,
            'functional_group_pka': FUNCTIONAL_GROUP_PKA,
            'smiles_patterns': SMILES_FUNCTIONAL_GROUPS,
            'name_normalization': NAME_NORMALIZATION_PATTERNS,
            'excluded_compounds': EXCLUDED_COMPOUNDS,
            'priority_compounds': PRIORITY_COMPOUNDS
        },
        'paths': {
            'data_dir': DEFAULT_DATA_DIR,
            'cache_dir': DEFAULT_CACHE_DIR,
            'bulk_dir': DEFAULT_BULK_DIR,
            'output_file': DEFAULT_OUTPUT_FILE
        },
        'quality_control': {
            'min_molecular_weight': MIN_MOLECULAR_WEIGHT,
            'max_molecular_weight': MAX_MOLECULAR_WEIGHT,
            'min_heavy_atoms': MIN_HEAVY_ATOM_COUNT,
            'max_heavy_atoms': MAX_HEAVY_ATOM_COUNT,
            'max_compound_name_length': MAX_COMPOUND_NAME_LENGTH,
            'min_compound_name_length': MIN_COMPOUND_NAME_LENGTH
        }
    }