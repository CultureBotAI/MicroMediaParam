#!/usr/bin/env python3
"""
Integrate newly mapped compounds back into the high-confidence mappings.

Takes the output from map_unmapped_compounds.py and merges it with
the existing high-confidence and low-confidence mapping files.
"""

import argparse
import logging
from pathlib import Path
from typing import Dict, Set

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_new_mappings(filepath: Path) -> Dict[str, Dict]:
    """Load new mappings from map_unmapped_compounds.py output."""
    mappings = {}
    with open(filepath, 'r', encoding='utf-8') as f:
        header = next(f).strip().split('\t')
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) >= 4:
                original = parts[0]
                normalized = parts[1]
                chebi_id = parts[2]
                chebi_label = parts[3]
                mapping_type = parts[4] if len(parts) > 4 else 'dictionary'
                confidence = parts[5] if len(parts) > 5 else 'medium'

                mappings[original.lower()] = {
                    'original': original,
                    'normalized': normalized,
                    'chebi_id': chebi_id,
                    'chebi_label': chebi_label,
                    'mapping_type': mapping_type,
                    'confidence': confidence
                }
    return mappings


def integrate_mappings(
    new_mappings_file: Path,
    high_confidence_file: Path,
    low_confidence_file: Path,
    output_file: Path
):
    """Integrate new mappings into the high-confidence file."""

    # Load new mappings
    new_mappings = load_new_mappings(new_mappings_file)
    logger.info(f"Loaded {len(new_mappings)} new mappings")

    # Track which compounds we've upgraded
    upgraded_compounds: Set[str] = set()

    # Read existing high-confidence file and add new mappings
    output_rows = []
    header = None

    with open(high_confidence_file, 'r', encoding='utf-8') as f:
        header = next(f).strip()
        for line in f:
            output_rows.append(line.strip())

    # Read low-confidence file and upgrade mappings where we have new data
    low_conf_kept = 0
    low_conf_upgraded = 0

    with open(low_confidence_file, 'r', encoding='utf-8') as f:
        lc_header = next(f).strip()
        lc_cols = lc_header.split('\t')

        # Find the ingredient column (usually column 1 or named 'ingredient')
        ingredient_idx = 1  # default
        for i, col in enumerate(lc_cols):
            if col.lower() in ['ingredient', 'compound', 'name']:
                ingredient_idx = i
                break

        for line in f:
            parts = line.strip().split('\t')
            if len(parts) > ingredient_idx:
                ingredient = parts[ingredient_idx].lower()

                if ingredient in new_mappings:
                    # Upgrade this compound with new mapping
                    new_map = new_mappings[ingredient]
                    # Create upgraded row - update the ChEBI columns
                    # Assuming columns: media_id, ingredient, chebi_id, chebi_label, ...
                    if len(parts) >= 4:
                        parts[2] = new_map['chebi_id']
                        parts[3] = new_map['chebi_label']
                    output_rows.append('\t'.join(parts))
                    upgraded_compounds.add(ingredient)
                    low_conf_upgraded += 1
                else:
                    low_conf_kept += 1

    # Write output
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(header + '\n')
        for row in output_rows:
            f.write(row + '\n')

    # Report statistics
    logger.info(f"Integration complete:")
    logger.info(f"  - Original high-confidence entries preserved")
    logger.info(f"  - Low-confidence upgraded to high: {low_conf_upgraded}")
    logger.info(f"  - Low-confidence unchanged: {low_conf_kept}")
    logger.info(f"  - Unique compounds upgraded: {len(upgraded_compounds)}")
    logger.info(f"Output written to: {output_file}")

    # Write summary of upgrades
    summary_file = output_file.parent / "unmapped_integration_summary.txt"
    with open(summary_file, 'w', encoding='utf-8') as f:
        f.write("Unmapped Compounds Integration Summary\n")
        f.write("=" * 40 + "\n\n")
        f.write(f"New mappings available: {len(new_mappings)}\n")
        f.write(f"Low-confidence upgraded: {low_conf_upgraded}\n")
        f.write(f"Low-confidence unchanged: {low_conf_kept}\n")
        f.write(f"\nUpgraded compounds:\n")
        for compound in sorted(upgraded_compounds):
            if compound in new_mappings:
                m = new_mappings[compound]
                f.write(f"  {m['original']} -> {m['chebi_id']} ({m['chebi_label']})\n")


def main():
    parser = argparse.ArgumentParser(
        description="Integrate unmapped compound mappings into pipeline"
    )
    parser.add_argument(
        "--new-mappings",
        type=Path,
        required=True,
        help="Path to new_mappings.tsv from map_unmapped_compounds.py"
    )
    parser.add_argument(
        "--high-confidence",
        type=Path,
        required=True,
        help="Path to high_confidence_compound_mappings*.tsv"
    )
    parser.add_argument(
        "--low-confidence",
        type=Path,
        required=True,
        help="Path to low_confidence_compound_mappings.tsv"
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output file path"
    )

    args = parser.parse_args()

    integrate_mappings(
        args.new_mappings,
        args.high_confidence,
        args.low_confidence,
        args.output
    )


if __name__ == "__main__":
    main()
