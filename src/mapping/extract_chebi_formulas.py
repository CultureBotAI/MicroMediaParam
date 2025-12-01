#!/usr/bin/env python3
"""
Extract molecular formulas from ChEBI OWL file.

Parses the ChEBI OWL file to extract CHEBI ID → formula mappings.
The formulas are stored as chemrof:generalized_empirical_formula annotations.

Usage:
    python -m src.mapping.extract_chebi_formulas \
        --owl-file /path/to/chebi.owl \
        --output data/curated/chebi_formulas.tsv
"""

import argparse
import logging
import re
from pathlib import Path
from typing import Dict, Optional, Tuple

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def extract_formulas_from_owl(owl_file: Path) -> Dict[str, Tuple[str, str]]:
    """
    Extract CHEBI ID, label, and formula from OWL file.

    Uses streaming to handle large files efficiently.

    Returns:
        Dict mapping CHEBI:ID -> (label, formula)
    """
    logger.info(f"Parsing ChEBI OWL file: {owl_file}")

    chebi_data = {}

    # Patterns to match
    id_pattern = re.compile(r'<oboInOwl:id>(CHEBI:\d+)</oboInOwl:id>')
    label_pattern = re.compile(r'<rdfs:label>([^<]+)</rdfs:label>')
    formula_pattern = re.compile(r'<chemrof:generalized_empirical_formula>([^<]+)</chemrof:generalized_empirical_formula>')
    class_start_pattern = re.compile(r'<owl:Class rdf:about="http://purl\.obolibrary\.org/obo/CHEBI_(\d+)"')
    class_end_pattern = re.compile(r'</owl:Class>')

    current_chebi_id = None
    current_label = None
    current_formula = None
    in_class = False

    line_count = 0

    with open(owl_file, 'r', encoding='utf-8') as f:
        for line in f:
            line_count += 1

            if line_count % 1000000 == 0:
                logger.info(f"Processed {line_count:,} lines, found {len(chebi_data):,} formulas...")

            # Check for class start
            class_match = class_start_pattern.search(line)
            if class_match:
                in_class = True
                current_chebi_id = f"CHEBI:{class_match.group(1)}"
                current_label = None
                current_formula = None
                continue

            # Check for class end
            if class_end_pattern.search(line):
                # Save data if we have formula
                if current_chebi_id and current_formula:
                    chebi_data[current_chebi_id] = (current_label or '', current_formula)

                in_class = False
                current_chebi_id = None
                current_label = None
                current_formula = None
                continue

            if not in_class:
                continue

            # Extract ID (backup method)
            id_match = id_pattern.search(line)
            if id_match:
                current_chebi_id = id_match.group(1)

            # Extract label
            label_match = label_pattern.search(line)
            if label_match:
                current_label = label_match.group(1)

            # Extract formula
            formula_match = formula_pattern.search(line)
            if formula_match:
                current_formula = formula_match.group(1)

    logger.info(f"Extracted {len(chebi_data):,} CHEBI entries with formulas")

    return chebi_data


def save_formulas(chebi_data: Dict[str, Tuple[str, str]], output_file: Path):
    """Save extracted formulas to TSV file."""
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("chebi_id\tchebi_label\tchebi_formula\n")

        for chebi_id in sorted(chebi_data.keys(), key=lambda x: int(x.split(':')[1])):
            label, formula = chebi_data[chebi_id]
            # Escape any tabs in label
            label = label.replace('\t', ' ')
            f.write(f"{chebi_id}\t{label}\t{formula}\n")

    logger.info(f"Saved {len(chebi_data):,} formulas to {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Extract molecular formulas from ChEBI OWL file"
    )
    parser.add_argument(
        "--owl-file",
        type=Path,
        required=True,
        help="Path to ChEBI OWL file"
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output TSV file"
    )

    args = parser.parse_args()

    # Extract formulas
    chebi_data = extract_formulas_from_owl(args.owl_file)

    # Save to file
    save_formulas(chebi_data, args.output)

    # Print summary
    print("\n" + "=" * 60)
    print("CHEBI FORMULA EXTRACTION COMPLETE")
    print("=" * 60)
    print(f"Total entries with formulas: {len(chebi_data):,}")
    print(f"Output file: {args.output}")
    print("=" * 60)


if __name__ == "__main__":
    main()
