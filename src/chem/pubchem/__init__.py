#!/usr/bin/env python3
"""
PubChem Chemical Data Processing Module

A comprehensive pipeline for downloading, processing, and standardizing
chemical property data from PubChem for use in the MicroMediaParam project.

Key Features:
- Bulk FTP downloads for comprehensive coverage
- REST API integration for specific queries  
- Focus on ionization, solubility, and molecular properties
- Robust error handling and statistics reporting
- Compatible with chemical_properties.tsv format

Author: MicroMediaParam Project
"""

from .data_downloader import PubChemDataDownloader, PubChemCompoundData
from .property_extractor import PubChemPropertyExtractor, ProcessedChemicalProperties
from .tsv_generator import PubChemTSVGenerator
from .pipeline import PubChemDataPipeline
from .config import (
    PUBCHEM_REST_API, PUBCHEM_POWER_USER_API, 
    FUNCTIONAL_GROUP_PKA, PRIORITY_COMPOUNDS,
    get_default_config
)

__version__ = "1.0.0"
__author__ = "MicroMediaParam Project"

__all__ = [
    # Main classes
    "PubChemDataDownloader",
    "PubChemPropertyExtractor", 
    "PubChemTSVGenerator",
    "PubChemDataPipeline",
    
    # Data structures
    "PubChemCompoundData",
    "ProcessedChemicalProperties",
    
    # Configuration
    "PUBCHEM_REST_API",
    "PUBCHEM_POWER_USER_API",
    "FUNCTIONAL_GROUP_PKA",
    "PRIORITY_COMPOUNDS",
    "get_default_config",
]