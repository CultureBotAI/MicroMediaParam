#!/usr/bin/env python3
"""
Memory-Optimized PubChem Data Downloader

This patch modifies the PubChem data downloader to handle large CID index files
without loading them entirely into memory.

Key optimizations:
1. Stream-based processing for large JSON files
2. SQLite database for efficient lookups
3. Lazy loading of compound data
"""

import json
import sqlite3
import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

def convert_json_to_sqlite(json_file: Path, db_file: Path, batch_size: int = 10000):
    """
    Convert large JSON CID index to SQLite database for memory-efficient access.
    
    Args:
        json_file: Path to large JSON file
        db_file: Path to output SQLite database
        batch_size: Number of entries to process at once
    """
    logger.info(f"Converting {json_file} to SQLite database...")
    
    # Create SQLite database
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    # Create table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cid_lookup (
            compound_name TEXT PRIMARY KEY,
            cid INTEGER NOT NULL
        )
    """)
    
    # Create index for faster lookups
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_compound_name 
        ON cid_lookup(compound_name)
    """)
    
    # Stream-process JSON file
    logger.info("Stream-processing JSON file...")
    
    # Read JSON file in chunks
    with open(json_file, 'r') as f:
        # Skip opening bracket
        char = f.read(1)
        while char and char != '{':
            char = f.read(1)
        
        batch = []
        buffer = ""
        brace_count = 0
        in_string = False
        escape_next = False
        entry_count = 0
        
        while True:
            char = f.read(1)
            if not char:
                break
                
            buffer += char
            
            # Track string boundaries
            if not escape_next:
                if char == '"':
                    in_string = not in_string
                elif char == '\\':
                    escape_next = True
            else:
                escape_next = False
            
            # Track braces outside strings
            if not in_string:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    
                    # Complete entry found
                    if brace_count == 0 and buffer.strip().endswith('}'):
                        # Parse entry
                        entry_str = buffer.strip()
                        if entry_str.endswith(','):
                            entry_str = entry_str[:-1]
                        
                        try:
                            # Extract key-value pair
                            if ':' in entry_str:
                                key_part = entry_str.split(':', 1)[0].strip().strip('"')
                                value_part = entry_str.split(':', 1)[1].strip().rstrip('}')
                                
                                if key_part and value_part:
                                    try:
                                        cid = int(value_part)
                                        batch.append((key_part.lower(), cid))
                                        entry_count += 1
                                        
                                        if entry_count % 100000 == 0:
                                            logger.info(f"Processed {entry_count:,} entries")
                                    except ValueError:
                                        pass
                        except Exception as e:
                            logger.debug(f"Skip entry: {e}")
                        
                        buffer = ""
                        
                        # Insert batch
                        if len(batch) >= batch_size:
                            cursor.executemany(
                                "INSERT OR REPLACE INTO cid_lookup (compound_name, cid) VALUES (?, ?)",
                                batch
                            )
                            conn.commit()
                            batch = []
        
        # Insert remaining batch
        if batch:
            cursor.executemany(
                "INSERT OR REPLACE INTO cid_lookup (compound_name, cid) VALUES (?, ?)",
                batch
            )
            conn.commit()
    
    logger.info(f"Conversion complete. Total entries: {entry_count:,}")
    
    # Optimize database
    cursor.execute("VACUUM")
    conn.close()
    
    return db_file

def create_memory_efficient_lookup(cache_dir: Path) -> Optional[Path]:
    """
    Create or use existing SQLite database for CID lookups.
    
    Args:
        cache_dir: Cache directory path
        
    Returns:
        Path to SQLite database or None if not available
    """
    json_file = cache_dir / "cid_lookup_index.json"
    db_file = cache_dir / "cid_lookup_index.db"
    
    # If SQLite database already exists, use it
    if db_file.exists():
        logger.info(f"Using existing SQLite CID lookup: {db_file}")
        return db_file
    
    # If JSON file exists, convert it
    if json_file.exists():
        logger.info("Converting JSON CID index to SQLite for memory efficiency...")
        return convert_json_to_sqlite(json_file, db_file)
    
    logger.warning("No CID lookup index available")
    return None

class MemoryEfficientCIDLookup:
    """Memory-efficient CID lookup using SQLite database."""
    
    def __init__(self, db_file: Path):
        self.db_file = db_file
        self.conn = None
        
    def __enter__(self):
        self.conn = sqlite3.connect(self.db_file)
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.close()
            
    def lookup(self, compound_name: str) -> Optional[int]:
        """Look up CID for a compound name."""
        cursor = self.conn.cursor()
        result = cursor.execute(
            "SELECT cid FROM cid_lookup WHERE compound_name = ? LIMIT 1",
            (compound_name.lower(),)
        ).fetchone()
        return result[0] if result else None
    
    def batch_lookup(self, compound_names: list) -> Dict[str, int]:
        """Batch lookup CIDs for multiple compounds."""
        cursor = self.conn.cursor()
        placeholders = ','.join(['?' for _ in compound_names])
        query = f"SELECT compound_name, cid FROM cid_lookup WHERE compound_name IN ({placeholders})"
        
        results = cursor.execute(query, [name.lower() for name in compound_names]).fetchall()
        return {name: cid for name, cid in results}

def patch_pubchem_downloader():
    """
    Create a patched version of PubChem data downloader that uses SQLite.
    """
    patch_code = '''
# Memory-efficient patch for PubChemDataDownloader
# Add this to src/chem/pubchem/data_downloader.py

def build_cid_lookup_index_efficient(self, force_rebuild: bool = False) -> Dict[str, str]:
    """
    Memory-efficient version using SQLite database.
    """
    from optimize_pubchem_memory import create_memory_efficient_lookup, MemoryEfficientCIDLookup
    
    db_file = create_memory_efficient_lookup(self.cache_dir)
    if not db_file:
        # Fall back to building from scratch if needed
        return self._build_cid_lookup_from_api()
    
    # For immediate use, load only requested compounds
    if hasattr(self, '_target_compounds'):
        with MemoryEfficientCIDLookup(db_file) as lookup:
            return lookup.batch_lookup(self._target_compounds)
    
    # Return empty dict for now, will use on-demand lookup
    return {}
'''
    
    logger.info("Patch code generated. Apply to PubChem downloader for memory efficiency.")
    print(patch_code)

def main():
    """Main function to set up memory-efficient PubChem processing."""
    cache_dir = Path("data/pubchem_processing/cache")
    
    if cache_dir.exists():
        db_file = create_memory_efficient_lookup(cache_dir)
        if db_file:
            logger.info(f"✓ SQLite database ready: {db_file}")
            logger.info("PubChem processing can now handle large datasets efficiently")
        else:
            logger.warning("Could not create SQLite database")
    else:
        logger.error(f"Cache directory not found: {cache_dir}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()