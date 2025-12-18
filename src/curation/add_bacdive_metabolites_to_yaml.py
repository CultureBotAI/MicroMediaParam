#!/usr/bin/env python3
"""
Add BacDive Metabolites to Complex Ingredients YAML

Reads PubChem composition data for BacDive metabolites and generates
YAML entries to add to the complex ingredients database.

For simple chemical compounds (not complex mixtures), creates minimal entries with:
- Names and synonyms
- ChEBI ID (if available) or PubChem CID
- Molecular formula and weight
- CAS number (extracted from synonyms)
- Source references (PubChem)

Usage:
    python src/curation/add_bacdive_metabolites_to_yaml.py \\
        --pubchem-dir data/curated/complex_ingredients/evidence/pubchem_bacdive/ \\
        --yaml data/curated/complex_ingredients/complex_ingredient_compositions.yaml \\
        --output bacdive_metabolites_entries.yaml \\
        --dry-run

Version: 1.0.0
"""

import argparse
import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Any

import yaml

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BacDiveMetabolitesAdder:
    """Adds BacDive metabolites to complex ingredients YAML."""

    CAS_PATTERN = re.compile(r'^\d{2,7}-\d{2}-\d$')

    def __init__(self, pubchem_dir: Path, yaml_file: Path):
        """
        Initialize adder.

        Args:
            pubchem_dir: Directory with PubChem JSON files
            yaml_file: Path to complex ingredients YAML
        """
        self.pubchem_dir = pubchem_dir
        self.yaml_file = yaml_file

        self.existing_ingredients: Dict[str, Any] = {}
        self.new_entries: Dict[str, Any] = {}

        self._load_existing_yaml()

    def _load_existing_yaml(self):
        """Load existing complex ingredients YAML."""
        if self.yaml_file.exists():
            logger.info(f"Loading existing YAML from {self.yaml_file}")
            with open(self.yaml_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                self.existing_ingredients = data.get('ingredients', {})
                logger.info(f"Loaded {len(self.existing_ingredients)} existing ingredients")

    def process_pubchem_data(self) -> int:
        """
        Process all PubChem JSON files and generate YAML entries.

        Returns:
            Number of new entries generated
        """
        json_files = list(self.pubchem_dir.glob('*.json'))
        logger.info(f"Found {len(json_files)} PubChem data files")

        added = 0

        for json_file in json_files:
            logger.info(f"Processing {json_file.name}")

            with open(json_file, 'r') as f:
                data = json.load(f)

            if not data.get('success'):
                logger.warning(f"Skipping {json_file.name}: {data.get('error')}")
                continue

            # Generate YAML entry
            entry = self._generate_yaml_entry(data)

            if entry:
                ingredient_id = entry['id']

                # Check if already exists
                if ingredient_id in self.existing_ingredients:
                    logger.info(f"Ingredient {ingredient_id} already exists, skipping")
                    continue

                self.new_entries[ingredient_id] = entry['data']
                added += 1
                logger.info(f"Added entry for {ingredient_id}")

        return added

    def _generate_yaml_entry(self, pubchem_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Generate YAML entry from PubChem data.

        Args:
            pubchem_data: PubChem compound info dict

        Returns:
            Dictionary with 'id' and 'data' keys, or None if cannot generate
        """
        query_name = pubchem_data['query_name']

        # Generate ingredient ID (lowercase, underscores)
        ingredient_id = query_name.lower().replace(' ', '_').replace('-', '_')
        ingredient_id = re.sub(r'[^a-z0-9_]', '', ingredient_id)

        # Extract CAS number from synonyms
        cas_number = self._extract_cas_number(pubchem_data.get('synonyms', []))

        # Build names list (query name + top synonyms)
        names = [query_name]
        synonyms = pubchem_data.get('synonyms', [])
        if synonyms:
            # Add a few common synonyms (excluding technical codes)
            for syn in synonyms[:10]:
                if (not syn.startswith('SCHEMBL') and
                    not syn.startswith('DTXSID') and
                    not syn.startswith('RefChem') and
                    not syn.startswith('CS-') and
                    len(syn) > 3):
                    if syn not in names:
                        names.append(syn)
                if len(names) >= 5:
                    break

        # Build entry
        entry_data = {
            'names': names,
            'description': f"Chemical compound from BacDive metabolite utilization data",
            'source_references': ['PubChem_API']
        }

        # Add CAS number if found
        if cas_number:
            entry_data['cas_number'] = cas_number

        # Add ChEBI ID if available
        if pubchem_data.get('chebi_id'):
            entry_data['chebi_id'] = pubchem_data['chebi_id']

        # Add molecular properties
        if pubchem_data.get('molecular_formula') and pubchem_data.get('molecular_weight'):
            entry_data['molecular_properties'] = {
                'molecular_formula': pubchem_data['molecular_formula'],
                'molecular_weight': float(pubchem_data['molecular_weight']),
            }

            if pubchem_data.get('iupac_name'):
                entry_data['molecular_properties']['iupac_name'] = pubchem_data['iupac_name']

        # Add PubChem CID as reference
        if pubchem_data.get('cid'):
            entry_data['pubchem_cid'] = pubchem_data['cid']

        # Mark as simple compound (not a complex mixture)
        entry_data['compound_type'] = 'simple_chemical'

        return {
            'id': ingredient_id,
            'data': entry_data
        }

    def _extract_cas_number(self, synonyms: List[str]) -> Optional[str]:
        """Extract CAS number from synonyms list."""
        for syn in synonyms:
            if self.CAS_PATTERN.match(syn):
                return syn
        return None

    def write_yaml_entries(self, output_file: Path):
        """
        Write new YAML entries to a file.

        Args:
            output_file: Path to output YAML file
        """
        if not self.new_entries:
            logger.warning("No new entries to write")
            return

        logger.info(f"Writing {len(self.new_entries)} new entries to {output_file}")

        # Create a structured YAML output
        output_data = {
            'metadata': {
                'version': '1.1.0',
                'description': 'BacDive metabolites additions from PubChem',
                'generated': '2024-12-17'
            },
            'ingredients': self.new_entries
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            yaml.dump(output_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

        logger.info(f"Wrote {len(self.new_entries)} entries to {output_file}")

    def merge_into_main_yaml(self, backup: bool = True):
        """
        Merge new entries into the main complex ingredients YAML.

        Args:
            backup: Whether to create a backup of the original file
        """
        if not self.new_entries:
            logger.warning("No new entries to merge")
            return

        logger.info(f"Merging {len(self.new_entries)} new entries into {self.yaml_file}")

        # Backup original
        if backup:
            backup_file = self.yaml_file.with_suffix('.yaml.bak')
            logger.info(f"Creating backup at {backup_file}")
            with open(self.yaml_file, 'r') as src, open(backup_file, 'w') as dst:
                dst.write(src.read())

        # Load full YAML
        with open(self.yaml_file, 'r', encoding='utf-8') as f:
            full_data = yaml.safe_load(f)

        # Merge new entries
        if 'ingredients' not in full_data:
            full_data['ingredients'] = {}

        full_data['ingredients'].update(self.new_entries)

        # Update metadata
        if 'metadata' in full_data:
            full_data['metadata']['last_updated'] = '2024-12-17'

        # Write back
        with open(self.yaml_file, 'w', encoding='utf-8') as f:
            yaml.dump(full_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

        logger.info(f"Merged {len(self.new_entries)} entries into {self.yaml_file}")
        logger.info(f"Total ingredients now: {len(full_data['ingredients'])}")

    def print_summary(self):
        """Print summary of new entries."""
        if not self.new_entries:
            print("\nNo new entries generated.")
            return

        print("\n" + "=" * 70)
        print("NEW BACDIVE METABOLITES ENTRIES")
        print("=" * 70)

        for ingredient_id, data in self.new_entries.items():
            print(f"\n{ingredient_id}:")
            print(f"  Names: {', '.join(data['names'][:3])}")
            print(f"  CAS: {data.get('cas_number', 'N/A')}")
            print(f"  ChEBI: {data.get('chebi_id', 'N/A')}")
            print(f"  PubChem CID: {data.get('pubchem_cid', 'N/A')}")
            if 'molecular_properties' in data:
                props = data['molecular_properties']
                print(f"  Formula: {props.get('molecular_formula', 'N/A')}")
                print(f"  MW: {props.get('molecular_weight', 'N/A')}")

        print("\n" + "=" * 70)
        print(f"Total new entries: {len(self.new_entries)}")
        print("=" * 70)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Add BacDive metabolites to complex ingredients YAML'
    )
    parser.add_argument(
        '--pubchem-dir',
        required=True,
        help='Directory with PubChem JSON files'
    )
    parser.add_argument(
        '--yaml',
        required=True,
        help='Path to complex ingredients YAML file'
    )
    parser.add_argument(
        '--output',
        help='Output file for new entries (optional, for review before merging)'
    )
    parser.add_argument(
        '--merge',
        action='store_true',
        help='Merge new entries into main YAML file'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be added without writing files'
    )

    args = parser.parse_args()

    pubchem_dir = Path(args.pubchem_dir)
    yaml_file = Path(args.yaml)

    if not pubchem_dir.exists():
        logger.error(f"PubChem directory not found: {pubchem_dir}")
        return 1

    if not yaml_file.exists():
        logger.error(f"YAML file not found: {yaml_file}")
        return 1

    # Process
    adder = BacDiveMetabolitesAdder(pubchem_dir, yaml_file)
    added_count = adder.process_pubchem_data()

    logger.info(f"Generated {added_count} new entries")

    # Print summary
    adder.print_summary()

    if args.dry_run:
        print("\n[DRY RUN] No files were modified.")
        return 0

    # Write output
    if args.output:
        output_file = Path(args.output)
        adder.write_yaml_entries(output_file)

    # Merge into main YAML if requested
    if args.merge:
        adder.merge_into_main_yaml(backup=True)

    return 0


if __name__ == '__main__':
    exit(main())
