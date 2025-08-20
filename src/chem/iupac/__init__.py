"""
IUPAC Chemical Data Processing Module

This module provides tools for downloading and processing chemical data from IUPAC
and other authoritative sources to generate chemical_properties.tsv files for 
the MicroMediaParam pipeline.

Components:
- data_downloader.py: Download chemical data from IUPAC, NIST, ChEBI
- property_extractor.py: Extract pKa, solubility, molecular weight data
- tsv_generator.py: Generate chemical_properties.tsv in required format
- compound_mapper.py: Map compound names to standard identifiers
"""

__version__ = "1.0.0"
__author__ = "MicroMediaParam Project"

from .data_downloader import IUPACDataDownloader
from .property_extractor import ChemicalPropertyExtractor
from .tsv_generator import ChemicalPropertiesTSVGenerator
from .compound_mapper import CompoundMapper

__all__ = [
    'IUPACDataDownloader',
    'ChemicalPropertyExtractor', 
    'ChemicalPropertiesTSVGenerator',
    'CompoundMapper'
]