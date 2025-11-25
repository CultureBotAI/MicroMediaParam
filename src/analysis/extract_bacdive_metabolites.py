#!/usr/bin/env python3
"""
Extract unique metabolite names from BacDive metabolites without ChEBI IDs.

This script processes the bacdive_metabolites_without_chebi_ids.tsv file and
extracts unique metabolite names for mapping to ChEBI via OAK or fuzzy matching.
"""

import argparse
import logging
from pathlib import Path
from typing import Dict, List, Set

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def extract_unique_metabolites(input_file: Path, output_dir: Path) -> Dict:
    """
    Extract unique metabolite names from BacDive unmapped metabolites file.

    Args:
        input_file: Path to bacdive_metabolites_without_chebi_ids.tsv
        output_dir: Directory to write output files

    Returns:
        Dictionary with extraction statistics
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("Extracting Unique BacDive Metabolites for ChEBI Mapping")
    print("=" * 60)

    if not input_file.exists():
        print(f"Error: Input file not found: {input_file}")
        return {"error": "File not found"}

    # Read and parse the file (skip comment lines starting with #)
    metabolites: Dict[str, int] = {}  # metabolite_name -> count
    total_records = 0

    print(f"\nReading: {input_file}")

    with open(input_file, 'r', encoding='utf-8') as f:
        header_found = False
        metabolite_col_idx = None

        for line in f:
            line = line.strip()

            # Skip comment lines and empty lines
            if line.startswith('#') or not line:
                continue

            # Parse header
            if not header_found:
                cols = line.split('\t')
                try:
                    metabolite_col_idx = cols.index('metabolite_name')
                    header_found = True
                    print(f"Found header, metabolite_name at column {metabolite_col_idx + 1}")
                except ValueError:
                    print(f"Error: 'metabolite_name' column not found in header: {cols}")
                    return {"error": "Column not found"}
                continue

            # Parse data rows
            cols = line.split('\t')
            if len(cols) > metabolite_col_idx:
                metabolite = cols[metabolite_col_idx].strip()
                if metabolite:
                    metabolites[metabolite] = metabolites.get(metabolite, 0) + 1
                    total_records += 1

    print(f"\nStatistics:")
    print(f"  Total records: {total_records:,}")
    print(f"  Unique metabolites: {len(metabolites):,}")
    print(f"  Compression ratio: {total_records / len(metabolites):.1f}x")

    # Filter metabolites for mapping
    filtered_metabolites: List[str] = []
    excluded: List[str] = []

    for name in metabolites.keys():
        # Skip very short names
        if len(name) <= 1:
            excluded.append(f"{name} (too short)")
            continue
        # Skip names with no letters
        if not any(c.isalpha() for c in name):
            excluded.append(f"{name} (no letters)")
            continue
        filtered_metabolites.append(name)

    print(f"\nFiltering:")
    print(f"  Filtered metabolites: {len(filtered_metabolites)}")
    print(f"  Excluded: {len(excluded)}")

    # Sort by frequency (most common first for priority mapping)
    sorted_metabolites = sorted(
        filtered_metabolites,
        key=lambda x: metabolites[x],
        reverse=True
    )

    # Show top metabolites
    print(f"\nTop 10 metabolites by frequency:")
    for i, name in enumerate(sorted_metabolites[:10], 1):
        print(f"  {i:2d}. {name} ({metabolites[name]:,} records)")

    # Write unique metabolites list (for OAK/fuzzy matching)
    metabolites_file = output_dir / "bacdive_metabolites_unique.txt"
    print(f"\nWriting unique metabolites to: {metabolites_file}")
    with open(metabolites_file, 'w', encoding='utf-8') as f:
        for name in sorted(filtered_metabolites):
            f.write(f"{name}\n")

    # Write detailed frequency report
    frequency_file = output_dir / "bacdive_metabolites_frequency.tsv"
    print(f"Writing frequency report to: {frequency_file}")
    with open(frequency_file, 'w', encoding='utf-8') as f:
        f.write("metabolite_name\trecord_count\n")
        for name in sorted_metabolites:
            f.write(f"{name}\t{metabolites[name]}\n")

    print(f"\nOutput files:")
    print(f"  {metabolites_file} - {len(filtered_metabolites)} unique names for mapping")
    print(f"  {frequency_file} - frequency report for prioritization")

    print(f"\nNext steps:")
    print(f"  1. Run: make bacdive-metabolites-mapping")
    print(f"  2. Or use OAK directly:")
    print(f"     runoak -i sqlite:obo:chebi annotate \\")
    print(f"       --text-file {metabolites_file} \\")
    print(f"       --output-type json \\")
    print(f"       --output {output_dir}/bacdive_metabolites_oak_annotations.json")

    return {
        "total_records": total_records,
        "unique_metabolites": len(metabolites),
        "filtered_metabolites": len(filtered_metabolites),
        "excluded": len(excluded),
        "output_files": [str(metabolites_file), str(frequency_file)]
    }


def main():
    parser = argparse.ArgumentParser(
        description="Extract unique BacDive metabolites for ChEBI mapping"
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/unmapped/bacdive_metabolites_without_chebi_ids.tsv"),
        help="Input TSV file with unmapped metabolites"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("pipeline_output/bacdive_metabolites"),
        help="Output directory for extracted metabolites"
    )

    args = parser.parse_args()
    extract_unique_metabolites(args.input, args.output_dir)


if __name__ == "__main__":
    main()
