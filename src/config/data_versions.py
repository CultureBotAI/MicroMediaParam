#!/usr/bin/env python3
"""
Data version configuration for deterministic pipeline runs.

This file pins the exact versions of external data dependencies used
for compound mapping. All scripts should reference these constants
to ensure reproducibility.

To update versions:
1. Download new data files
2. Verify checksums with: md5 <filepath>
3. Update the constants below
4. Update DATA_MANIFEST.tsv with new checksums
"""

from pathlib import Path

# ChEBI ontology version
# Source: https://ftp.ebi.ac.uk/pub/databases/chebi/ontology/chebi.owl
CHEBI_VERSION = "246"
CHEBI_DATE = "2025-11-20"
CHEBI_OWL_MD5 = "b7cfd4df772f4acd785e178abe4bf4c8"
CHEBI_JSON_MD5 = "9bcbe207c2245e208e6cdfec21c9d681"

# ChEBI nodes file (KG-Microbe transform output)
CHEBI_NODES_FILE = Path(
    "/Users/marcin/Documents/VIMSS/ontology/KG-Hub/KG-Microbe/"
    "kg-microbe/data/transformed/ontologies/chebi_nodes.tsv"
)
CHEBI_NODES_MD5 = "5a4ded6d84737f877135d802a51f8959"

# Merged KG nodes file (for composition mapping)
MERGED_KG_NODES_FILE = Path(
    "/Users/marcin/Documents/VIMSS/ontology/KG-Hub/KG-Microbe/"
    "kg-microbe/data/merged/20250222/merged-kg_nodes.tsv"
)

# Cache files
OLS_CACHE_FILE = Path("data/cache/ols_multi_ontology_cache.tsv")
OLS_CACHE_MD5 = "ac19c134748e341c60b2a92fbf7bf9af"

PUBCHEM_CACHE_FILE = Path("data/cache/pubchem_lookup_cache.tsv")
PUBCHEM_CACHE_MD5 = "8b7c519341f6084a5dd712672bb33c01"

PUBCHEM_NAME_CACHE_FILE = Path("data/cache/pubchem_name_cache.tsv")
PUBCHEM_NAME_CACHE_MD5 = "19f303e392467f56405680e3b51f351e"


def verify_data_versions() -> bool:
    """
    Verify that data files match expected checksums.

    Returns:
        True if all files match, False otherwise
    """
    import hashlib

    files_to_check = [
        (CHEBI_NODES_FILE, CHEBI_NODES_MD5),
        (OLS_CACHE_FILE, OLS_CACHE_MD5),
        (PUBCHEM_CACHE_FILE, PUBCHEM_CACHE_MD5),
    ]

    all_valid = True
    for filepath, expected_md5 in files_to_check:
        if not filepath.exists():
            print(f"WARNING: Missing file: {filepath}")
            all_valid = False
            continue

        actual_md5 = hashlib.md5(filepath.read_bytes()).hexdigest()
        if actual_md5 != expected_md5:
            print(f"WARNING: MD5 mismatch for {filepath}")
            print(f"  Expected: {expected_md5}")
            print(f"  Actual:   {actual_md5}")
            all_valid = False

    return all_valid


if __name__ == "__main__":
    print(f"ChEBI Version: {CHEBI_VERSION} ({CHEBI_DATE})")
    print(f"ChEBI Nodes: {CHEBI_NODES_FILE}")
    print(f"Merged KG: {MERGED_KG_NODES_FILE}")
    print()

    if verify_data_versions():
        print("All data files verified successfully")
    else:
        print("Some data files have changed or are missing")
