#!/usr/bin/env python3
"""
Extract all unique compound names from the pipeline for mapping.

Collects compound names from:
- Media composition JSON files
- composition_kg_mapping.tsv
- unmapped_compounds.tsv
- The old SIMPLE_COMPOUND_MAPPINGS dictionary keys (for transition)

Usage:
    python -m src.mapping.extract_all_compound_names \
        --input-dir pipeline_output/data_conversion/media_compositions \
        --kg-mapping pipeline_output/kg_mapping/composition_kg_mapping.tsv \
        --output pipeline_output/unmapped_analysis/all_compounds_to_map.txt
"""

import argparse
import json
import logging
from pathlib import Path
from typing import Set

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def extract_from_json_files(input_dir: Path) -> Set[str]:
    """Extract compound names from media composition JSON files."""
    compounds = set()

    json_files = list(input_dir.glob("*.json"))
    logger.info(f"Found {len(json_files)} JSON files in {input_dir}")

    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Handle different JSON structures
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        name = item.get('name') or item.get('ingredient') or item.get('compound')
                        if name:
                            compounds.add(str(name).strip())
            elif isinstance(data, dict):
                if 'ingredients' in data:
                    for ingredient in data['ingredients']:
                        if isinstance(ingredient, dict):
                            name = ingredient.get('name') or ingredient.get('ingredient')
                            if name:
                                compounds.add(str(name).strip())
                elif 'composition' in data:
                    for comp in data['composition']:
                        if isinstance(comp, dict):
                            name = comp.get('name') or comp.get('ingredient')
                            if name:
                                compounds.add(str(name).strip())

        except Exception as e:
            logger.debug(f"Error processing {json_file}: {e}")

    return compounds


def extract_from_kg_mapping(kg_mapping_file: Path) -> Set[str]:
    """Extract compound names from composition KG mapping TSV."""
    compounds = set()

    if not kg_mapping_file.exists():
        logger.warning(f"KG mapping file not found: {kg_mapping_file}")
        return compounds

    try:
        with open(kg_mapping_file, 'r', encoding='utf-8') as f:
            header = next(f).strip().split('\t')

            # Find the 'original' column (usually column 1)
            original_idx = 1
            for i, col in enumerate(header):
                if col.lower() == 'original':
                    original_idx = i
                    break

            for line in f:
                parts = line.strip().split('\t')
                if len(parts) > original_idx:
                    name = parts[original_idx].strip()
                    if name and name != '' and not name.startswith('solution:'):
                        compounds.add(name)

    except Exception as e:
        logger.error(f"Error reading KG mapping: {e}")

    return compounds


def extract_from_unmapped_file(unmapped_file: Path) -> Set[str]:
    """Extract compound names from unmapped compounds TSV."""
    compounds = set()

    if not unmapped_file.exists():
        logger.warning(f"Unmapped file not found: {unmapped_file}")
        return compounds

    try:
        with open(unmapped_file, 'r', encoding='utf-8') as f:
            header = next(f)
            for line in f:
                parts = line.strip().split('\t')
                if parts:
                    name = parts[0].strip()
                    if name:
                        compounds.add(name)

    except Exception as e:
        logger.error(f"Error reading unmapped file: {e}")

    return compounds


def extract_from_old_dictionary() -> Set[str]:
    """
    Extract compound names from the old SIMPLE_COMPOUND_MAPPINGS dictionary.

    This ensures we don't lose coverage during the transition.
    """
    compounds = set()

    try:
        # Import the old dictionary
        from src.mapping.map_unmapped_compounds import SIMPLE_COMPOUND_MAPPINGS
        compounds = set(SIMPLE_COMPOUND_MAPPINGS.keys())
        logger.info(f"Extracted {len(compounds)} compound names from old dictionary")
    except ImportError:
        logger.warning("Could not import old SIMPLE_COMPOUND_MAPPINGS dictionary")
    except Exception as e:
        logger.warning(f"Error extracting from old dictionary: {e}")

    return compounds


def main():
    parser = argparse.ArgumentParser(
        description="Extract all unique compound names from the pipeline"
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("pipeline_output/data_conversion/media_compositions"),
        help="Directory with media composition JSON files"
    )
    parser.add_argument(
        "--kg-mapping",
        type=Path,
        default=Path("pipeline_output/kg_mapping/composition_kg_mapping.tsv"),
        help="KG mapping TSV file"
    )
    parser.add_argument(
        "--unmapped-file",
        type=Path,
        default=Path("pipeline_output/unmapped_analysis/unmapped_compounds.tsv"),
        help="Unmapped compounds TSV file"
    )
    parser.add_argument(
        "--include-old-dict",
        action="store_true",
        help="Include compound names from old SIMPLE_COMPOUND_MAPPINGS"
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output file (one compound per line)"
    )

    args = parser.parse_args()

    all_compounds: Set[str] = set()

    # Extract from JSON files
    if args.input_dir.exists():
        json_compounds = extract_from_json_files(args.input_dir)
        logger.info(f"Extracted {len(json_compounds)} compounds from JSON files")
        all_compounds.update(json_compounds)

    # Extract from KG mapping
    kg_compounds = extract_from_kg_mapping(args.kg_mapping)
    logger.info(f"Extracted {len(kg_compounds)} compounds from KG mapping")
    all_compounds.update(kg_compounds)

    # Extract from unmapped file
    unmapped_compounds = extract_from_unmapped_file(args.unmapped_file)
    logger.info(f"Extracted {len(unmapped_compounds)} compounds from unmapped file")
    all_compounds.update(unmapped_compounds)

    # Optionally include old dictionary
    if args.include_old_dict:
        dict_compounds = extract_from_old_dictionary()
        all_compounds.update(dict_compounds)

    # Filter out empty/invalid entries
    valid_compounds = {
        c for c in all_compounds
        if c and c.strip() and len(c.strip()) > 1
    }

    # Sort and write output
    args.output.parent.mkdir(parents=True, exist_ok=True)

    sorted_compounds = sorted(valid_compounds, key=str.lower)

    with open(args.output, 'w', encoding='utf-8') as f:
        for compound in sorted_compounds:
            f.write(f"{compound}\n")

    logger.info(f"Written {len(sorted_compounds)} unique compound names to {args.output}")

    # Print summary
    print("\n" + "=" * 50)
    print("COMPOUND EXTRACTION SUMMARY")
    print("=" * 50)
    print(f"Total unique compounds: {len(sorted_compounds)}")
    print(f"Output file: {args.output}")
    print("=" * 50)


if __name__ == "__main__":
    main()
