#!/usr/bin/env python3
"""
Merge Multiple Unmapped Ingredient Sources.

Merges unmapped ingredient files from multiple sources into a single
non-redundant global file with source annotations.

Deduplication priority: formula > id > name (case-insensitive)
Conflict handling: Keep both entries with source annotations

Input formats supported:
- Simple 2-column TSV: id<tab>name
- Full pipeline format with 'original' column

Usage:
    python -m src.mapping.merge_unmapped_sources \\
        --inputs file1.tsv file2.tsv file3.tsv \\
        --output merged_unmapped_ingredients.tsv \\
        --source-names "local" "kg-microbe" "upstream"
"""

import argparse
import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class IngredientEntry:
    """Represents a single ingredient entry from any source."""
    id: str
    name: str
    formula: Optional[str] = None
    source: str = ""
    original_row: Optional[dict] = field(default_factory=dict)

    def get_dedup_keys(self) -> Tuple[Optional[str], str, str]:
        """
        Return deduplication keys in priority order.

        Returns:
            Tuple of (formula_key, id_key, name_key)
        """
        # Formula key (normalized)
        formula_key = None
        if self.formula:
            formula_key = self._normalize_formula(self.formula)

        # ID key (normalized)
        id_key = self._normalize_id(self.id)

        # Name key (normalized)
        name_key = self._normalize_name(self.name)

        return (formula_key, id_key, name_key)

    @staticmethod
    def _normalize_formula(formula: str) -> str:
        """Normalize chemical formula for matching."""
        if not formula:
            return ""
        # Remove spaces, lowercase, sort components
        formula = formula.strip().lower()
        # Remove common separators
        formula = re.sub(r'[\s\.\·×x]+', '', formula)
        return formula

    @staticmethod
    def _normalize_id(id_str: str) -> str:
        """Normalize ID for matching."""
        if not id_str:
            return ""
        # Extract numeric part if prefixed
        match = re.search(r':(\d+)$', id_str)
        if match:
            return match.group(1)
        return id_str.strip().lower()

    @staticmethod
    def _normalize_name(name: str) -> str:
        """Normalize name for matching."""
        if not name:
            return ""
        # Lowercase, remove extra whitespace
        name = name.strip().lower()
        name = ' '.join(name.split())
        # Remove common prefixes like '--'
        name = re.sub(r'^-+', '', name)
        return name


class UnmappedSourceMerger:
    """Merges multiple unmapped ingredient sources."""

    def __init__(self):
        self.entries: List[IngredientEntry] = []
        self.sources: Set[str] = set()

        # Deduplication indexes
        self.by_formula: Dict[str, List[IngredientEntry]] = defaultdict(list)
        self.by_id: Dict[str, List[IngredientEntry]] = defaultdict(list)
        self.by_name: Dict[str, List[IngredientEntry]] = defaultdict(list)

    def load_simple_tsv(self, filepath: str, source_name: str) -> int:
        """
        Load simple 2-column TSV (id, name).

        Args:
            filepath: Path to TSV file
            source_name: Source identifier for annotations

        Returns:
            Number of entries loaded
        """
        logger.info(f"Loading {filepath} as simple TSV (source: {source_name})")

        count = 0
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                parts = line.split('\t')
                if len(parts) >= 2:
                    entry_id = parts[0].strip()
                    entry_name = parts[1].strip() if parts[1] else ""
                else:
                    entry_id = parts[0].strip()
                    entry_name = ""

                # Skip entries with no name
                if not entry_name:
                    continue

                # Check if name looks like a formula
                formula = None
                if self._looks_like_formula(entry_name):
                    formula = entry_name

                entry = IngredientEntry(
                    id=entry_id,
                    name=entry_name,
                    formula=formula,
                    source=source_name,
                    original_row={'id': entry_id, 'name': entry_name}
                )

                self._add_entry(entry)
                count += 1

        self.sources.add(source_name)
        logger.info(f"Loaded {count} entries from {source_name}")
        return count

    def load_pipeline_tsv(self, filepath: str, source_name: str) -> int:
        """
        Load full pipeline TSV format with 'original' column.

        Args:
            filepath: Path to TSV file
            source_name: Source identifier for annotations

        Returns:
            Number of entries loaded
        """
        logger.info(f"Loading {filepath} as pipeline TSV (source: {source_name})")

        df = pd.read_csv(filepath, sep='\t', low_memory=False)

        count = 0
        for _, row in df.iterrows():
            # Try different column names for the compound name
            name = None
            for col in ['original', 'name', 'compound_name']:
                if col in df.columns and pd.notna(row.get(col)):
                    name = str(row[col]).strip()
                    if name:
                        break

            if not name:
                continue

            # Try to get ID
            entry_id = ""
            for col in ['medium_id', 'id', 'original_id']:
                if col in df.columns and pd.notna(row.get(col)):
                    entry_id = str(row[col]).strip()
                    if entry_id:
                        break

            # Check for formula
            formula = None
            for col in ['chebi_formula', 'formula', 'base_formula']:
                if col in df.columns and pd.notna(row.get(col)):
                    formula = str(row[col]).strip()
                    if formula:
                        break

            if not formula and self._looks_like_formula(name):
                formula = name

            entry = IngredientEntry(
                id=entry_id,
                name=name,
                formula=formula,
                source=source_name,
                original_row=row.to_dict()
            )

            self._add_entry(entry)
            count += 1

        self.sources.add(source_name)
        logger.info(f"Loaded {count} entries from {source_name}")
        return count

    def _looks_like_formula(self, text: str) -> bool:
        """Check if text looks like a chemical formula."""
        if not text:
            return False
        # Contains element-like patterns (e.g., Na, Cl, SO4, H2O)
        formula_patterns = [
            r'[A-Z][a-z]?\d*',  # Element with optional count
            r'H2O',
            r'SO4',
            r'PO4',
            r'NO3',
            r'\d+\s*H2O',  # Hydrates
        ]
        for pattern in formula_patterns:
            if re.search(pattern, text):
                # Also check it doesn't look like a regular word
                if not re.match(r'^[A-Za-z]+$', text):
                    return True
        return False

    def _add_entry(self, entry: IngredientEntry):
        """Add entry to internal storage and indexes."""
        self.entries.append(entry)

        formula_key, id_key, name_key = entry.get_dedup_keys()

        if formula_key:
            self.by_formula[formula_key].append(entry)
        if id_key:
            self.by_id[id_key].append(entry)
        if name_key:
            self.by_name[name_key].append(entry)

    def merge(self) -> pd.DataFrame:
        """
        Merge all entries with deduplication.

        Deduplication priority: formula > id > name
        Keeps all entries but marks duplicates with source annotations.

        Returns:
            DataFrame with merged, annotated entries
        """
        logger.info("Merging entries with deduplication...")

        # Track which entries we've processed
        processed: Set[int] = set()

        # Result rows
        results = []

        # Statistics
        stats = {
            'total_entries': len(self.entries),
            'unique_by_formula': 0,
            'unique_by_id': 0,
            'unique_by_name': 0,
            'duplicates_found': 0,
            'conflicts': 0,
        }

        # Process in dedup priority order
        for idx, entry in enumerate(self.entries):
            if idx in processed:
                continue

            formula_key, id_key, name_key = entry.get_dedup_keys()

            # Find all matching entries
            matches: List[Tuple[int, IngredientEntry, str]] = []
            match_reason = ""

            # Check formula matches first
            if formula_key and formula_key in self.by_formula:
                for match_entry in self.by_formula[formula_key]:
                    match_idx = self.entries.index(match_entry)
                    if match_idx not in processed:
                        matches.append((match_idx, match_entry, 'formula'))
                if len(matches) > 1:
                    match_reason = 'formula'
                    stats['unique_by_formula'] += 1

            # Check ID matches if no formula match
            if not matches and id_key and id_key in self.by_id:
                for match_entry in self.by_id[id_key]:
                    match_idx = self.entries.index(match_entry)
                    if match_idx not in processed:
                        matches.append((match_idx, match_entry, 'id'))
                if len(matches) > 1:
                    match_reason = 'id'
                    stats['unique_by_id'] += 1

            # Check name matches if no formula or ID match
            if not matches and name_key and name_key in self.by_name:
                for match_entry in self.by_name[name_key]:
                    match_idx = self.entries.index(match_entry)
                    if match_idx not in processed:
                        matches.append((match_idx, match_entry, 'name'))
                if len(matches) > 1:
                    match_reason = 'name'
                    stats['unique_by_name'] += 1

            # If no matches found, just add current entry
            if not matches:
                matches = [(idx, entry, 'unique')]

            # Process matches - keep all with source annotations
            sources_seen = set()
            for match_idx, match_entry, reason in matches:
                processed.add(match_idx)

                # Create result row
                row = {
                    'id': match_entry.id,
                    'name': match_entry.name,
                    'formula': match_entry.formula or '',
                    'source': match_entry.source,
                    'dedup_key': match_reason if match_reason else 'unique',
                    'is_duplicate': len(matches) > 1,
                }

                # Track sources for conflict detection
                sources_seen.add(match_entry.source)

                results.append(row)

            # Track duplicates and conflicts
            if len(matches) > 1:
                stats['duplicates_found'] += len(matches) - 1
                if len(sources_seen) > 1:
                    stats['conflicts'] += 1

        # Create DataFrame
        df = pd.DataFrame(results)

        # Sort by name for readability
        if not df.empty:
            df = df.sort_values(['name', 'source']).reset_index(drop=True)

        # Log statistics
        logger.info(f"""
Merge Statistics:
  Total entries loaded:     {stats['total_entries']}
  Unique by formula:        {stats['unique_by_formula']}
  Unique by ID:             {stats['unique_by_id']}
  Unique by name:           {stats['unique_by_name']}
  Duplicates found:         {stats['duplicates_found']}
  Cross-source conflicts:   {stats['conflicts']}
  Final entry count:        {len(df)}
        """)

        return df

    def save(self, df: pd.DataFrame, output_path: str):
        """Save merged results to TSV."""
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        df.to_csv(output_file, sep='\t', index=False)
        logger.info(f"Saved {len(df)} entries to {output_path}")


def detect_format(filepath: str) -> str:
    """
    Detect whether file is simple 2-column or full pipeline format.

    Returns:
        'simple' or 'pipeline'
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        first_line = f.readline().strip()

    # Check for pipeline format headers
    pipeline_headers = ['medium_id', 'original', 'mapped', 'chebi_label']
    for header in pipeline_headers:
        if header in first_line.lower():
            return 'pipeline'

    # Check column count
    parts = first_line.split('\t')
    if len(parts) <= 3:
        return 'simple'

    return 'pipeline'


def main():
    parser = argparse.ArgumentParser(
        description="Merge multiple unmapped ingredient sources",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--inputs', '-i',
        nargs='+',
        required=True,
        help='Input TSV files to merge'
    )
    parser.add_argument(
        '--source-names', '-s',
        nargs='+',
        help='Source names for each input file (same order as inputs)'
    )
    parser.add_argument(
        '--output', '-o',
        required=True,
        help='Output merged TSV file'
    )
    parser.add_argument(
        '--auto-detect-format',
        action='store_true',
        default=True,
        help='Auto-detect input file formats (default: True)'
    )

    args = parser.parse_args()

    # Validate inputs
    if args.source_names and len(args.source_names) != len(args.inputs):
        parser.error("Number of source names must match number of input files")

    # Default source names from filenames
    if not args.source_names:
        args.source_names = [Path(f).stem for f in args.inputs]

    # Create merger
    merger = UnmappedSourceMerger()

    # Load each input file
    for filepath, source_name in zip(args.inputs, args.source_names):
        if not Path(filepath).exists():
            logger.warning(f"File not found, skipping: {filepath}")
            continue

        # Detect format
        fmt = detect_format(filepath)
        logger.info(f"Detected format '{fmt}' for {filepath}")

        if fmt == 'simple':
            merger.load_simple_tsv(filepath, source_name)
        else:
            merger.load_pipeline_tsv(filepath, source_name)

    # Merge and save
    merged_df = merger.merge()
    merger.save(merged_df, args.output)

    # Print summary
    print("\n" + "=" * 60)
    print("MERGE SUMMARY")
    print("=" * 60)
    print(f"Input files:  {len(args.inputs)}")
    print(f"Sources:      {', '.join(sorted(merger.sources))}")
    print(f"Output file:  {args.output}")
    print(f"Total rows:   {len(merged_df)}")

    if not merged_df.empty:
        print(f"\nBy source:")
        for source in sorted(merger.sources):
            count = len(merged_df[merged_df['source'] == source])
            print(f"  {source}: {count}")

        dups = merged_df['is_duplicate'].sum()
        print(f"\nDuplicates:   {dups}")
    print("=" * 60)


if __name__ == '__main__':
    main()
