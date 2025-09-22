#!/usr/bin/env python3
"""
PubChem Memory Workaround

Temporary workaround to bypass the 14GB CID index for testing with 5 compounds.
This creates a minimal index file with just the test compounds.
"""

import json
import shutil
from pathlib import Path

def create_minimal_cid_index():
    """Create a minimal CID index for the 5 test compounds."""
    
    # Known CIDs for test compounds (from PubChem)
    test_compounds_cids = {
        "glucose": "5793",
        "d-glucose": "5793",
        "dextrose": "5793",
        "sodium chloride": "5234",
        "salt": "5234", 
        "nacl": "5234",
        "glycine": "750",
        "aminoacetic acid": "750",
        "citric acid": "311",
        "2-hydroxypropane-1,2,3-tricarboxylic acid": "311",
        "potassium phosphate": "516951",
        "tripotassium phosphate": "62657",
        "potassium dihydrogen phosphate": "516951",
        "kh2po4": "516951",
        "k3po4": "62657"
    }
    
    # Paths
    large_index = Path("data/pubchem_processing/cache/cid_lookup_index.json")
    minimal_index = Path("data/pubchem_processing/cache/cid_lookup_index_minimal.json")
    
    # Backup large index if it exists
    if large_index.exists() and not Path(str(large_index) + ".large").exists():
        shutil.move(str(large_index), str(large_index) + ".large")
        print(f"Backed up large index to: {large_index}.large")
    
    # Create minimal index
    with open(minimal_index, 'w') as f:
        json.dump(test_compounds_cids, f, indent=2)
    
    # Replace the original with minimal version
    if minimal_index.exists():
        shutil.copy(str(minimal_index), str(large_index))
        print(f"Created minimal CID index with {len(test_compounds_cids)} entries")
        
    return large_index

def restore_large_index():
    """Restore the large CID index when needed."""
    large_index = Path("data/pubchem_processing/cache/cid_lookup_index.json")
    backup_index = Path(str(large_index) + ".large")
    
    if backup_index.exists():
        shutil.move(str(backup_index), str(large_index))
        print("Restored large CID index")
    else:
        print("No large index backup found")

if __name__ == "__main__":
    # Create minimal index for testing
    create_minimal_cid_index()
    print("\nTo restore the large index later, run:")
    print("python pubchem_memory_workaround.py --restore")
    
    import sys
    if "--restore" in sys.argv:
        restore_large_index()