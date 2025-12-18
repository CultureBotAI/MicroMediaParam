#!/usr/bin/env python3
"""
Import trace element and vitamin solutions from MediaDive data.

Converts MediaDive solution recipes into complex_ingredient_compositions.yaml format
for integration into the complex ingredients database.

Usage:
    python src/curation/import_mediadive_solutions.py \
        --solutions /path/to/solutions.json \
        --media /path/to/media_detailed.json \
        --output data/curated/complex_ingredients/mediadive_solutions_additions.yaml \
        --min-usage 5 \
        --categories "trace,vitamin,mineral"
"""

import json
import yaml
import argparse
import logging
from pathlib import Path
from typing import Dict, List, Set, Tuple
from collections import Counter
import re

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MediaDiveSolutionImporter:
    """Import and convert MediaDive solutions to complex ingredient YAML format."""

    def __init__(self, solutions_file: str, media_file: str):
        self.solutions_file = solutions_file
        self.media_file = media_file
        self.solutions_data: Dict = {}
        self.media_data: Dict = {}
        self.solution_usage: Counter = Counter()

    def load_data(self):
        """Load MediaDive JSON data."""
        logger.info(f"Loading solutions from {self.solutions_file}")
        with open(self.solutions_file, 'r') as f:
            self.solutions_data = json.load(f)
        logger.info(f"Loaded {len(self.solutions_data)} solutions")

        logger.info(f"Loading media from {self.media_file}")
        with open(self.media_file, 'r') as f:
            self.media_data = json.load(f)
        logger.info(f"Loaded {len(self.media_data)} media")

    def calculate_solution_usage(self):
        """Count how many media use each solution."""
        logger.info("Calculating solution usage counts...")

        for med_id, med_data in self.media_data.items():
            if not med_data or 'solutions' not in med_data:
                continue

            for sol in med_data['solutions']:
                sol_id = str(sol.get('id'))
                self.solution_usage[sol_id] += 1

        logger.info(f"Calculated usage for {len(self.solution_usage)} solutions")

    def filter_solutions_by_category(self, categories: List[str]) -> List[str]:
        """Filter solutions by category keywords (trace, vitamin, mineral)."""
        filtered_ids = []

        for sol_id, sol_data in self.solutions_data.items():
            if not sol_data or 'name' not in sol_data:
                continue

            name_lower = sol_data['name'].lower()

            # Check if solution matches any category
            matches = any(cat.lower() in name_lower for cat in categories)
            if matches:
                filtered_ids.append(sol_id)

        logger.info(f"Filtered {len(filtered_ids)} solutions matching categories: {categories}")
        return filtered_ids

    def normalize_compound_name(self, compound_name: str) -> str:
        """Normalize compound name for YAML key (lowercase, underscores)."""
        # Remove hydration notation for the key name
        name = re.sub(r'\s*x\s*\d+\s*H2O', '', compound_name, flags=re.IGNORECASE)
        name = re.sub(r'\s*\.\s*\d+\s*H2O', '', name, flags=re.IGNORECASE)

        # Convert to lowercase and replace spaces/special chars with underscores
        name = name.lower().strip()
        name = re.sub(r'[^\w\s-]', '', name)  # Remove special chars except dash
        name = re.sub(r'[\s-]+', '_', name)  # Replace spaces and dashes with underscore

        return name

    def convert_solution_to_yaml_format(self, sol_id: str, sol_data: Dict) -> Tuple[str, Dict]:
        """Convert a MediaDive solution to complex_ingredient YAML format."""

        # Create ingredient key from solution name
        ingredient_key = self.normalize_compound_name(sol_data['name'])

        # Base metadata
        ingredient_dict = {
            'common_name': sol_data['name'],
            'mediadive_solution_id': int(sol_id),
            'source_references': ['DSMZ_MediaDive_API'],
            'confidence': 'high',  # From DSMZ, very reliable
            'evidence_tier': 2,  # Manufacturer specifications
            'usage_count': self.solution_usage.get(sol_id, 0)
        }

        # Synonyms (add alternative names)
        synonyms = []
        # Add "solution X" format
        synonyms.append(f"solution:{sol_id}")

        # Extract numeric solution ID from name if present (e.g., "SL-10" -> also add "SL 10")
        name_variants = re.findall(r'SL-(\d+[A-Z]?)', sol_data['name'], re.IGNORECASE)
        for variant in name_variants:
            synonyms.append(f"SL {variant}")
            synonyms.append(f"SL-{variant}")

        if synonyms:
            ingredient_dict['synonyms'] = synonyms

        # Add volume information if relevant
        if 'volume' in sol_data and sol_data['volume']:
            ingredient_dict['note'] = f"Standard volume: {sol_data['volume']} mL"

        # Parse recipe into chemical categories
        if 'recipe' not in sol_data or not sol_data['recipe']:
            return ingredient_key, ingredient_dict

        # Categorize chemicals
        trace_elements = {}
        vitamins = {}
        other_compounds = {}

        for item in sol_data['recipe']:
            compound = item.get('compound', '')
            compound_id = item.get('compound_id')

            # Skip distilled water
            if compound.lower() in ['distilled water', 'water', 'h2o']:
                continue

            # Create chemical entry
            chem_key = self.normalize_compound_name(compound)

            chem_entry = {}

            # Determine g/100ml concentration
            # Solution volume is in mL, amounts are in g or mg
            volume_ml = sol_data.get('volume', 1000)
            g_l = item.get('g_l')

            if g_l is not None:
                # Convert g/L to g/100ml
                g_per_100ml = g_l / 10.0
                chem_entry['g_per_100ml'] = g_per_100ml
            elif 'amount' in item and 'unit' in item:
                amount = item['amount']
                unit = item['unit']

                # Convert to grams
                if unit == 'mg':
                    amount_g = amount / 1000.0
                elif unit == 'g':
                    amount_g = amount
                elif unit == 'ml':
                    # For liquids, assume density ~1 g/ml
                    amount_g = amount
                else:
                    logger.warning(f"Unknown unit {unit} for {compound}")
                    continue

                # Convert to g/100ml
                g_per_100ml = (amount_g / volume_ml) * 100.0
                chem_entry['g_per_100ml'] = g_per_100ml

            # Add attributes if present
            if 'attribute' in item and item['attribute']:
                chem_entry['attribute'] = item['attribute']

            # Add original compound name for reference
            chem_entry['original_name'] = compound

            # Categorize the chemical
            if self.is_trace_element(compound):
                trace_elements[chem_key] = chem_entry
            elif self.is_vitamin(compound):
                vitamins[chem_key] = chem_entry
            else:
                other_compounds[chem_key] = chem_entry

        # Add categories to ingredient dict
        if trace_elements:
            ingredient_dict['trace_elements'] = trace_elements
        if vitamins:
            ingredient_dict['vitamins'] = vitamins
        if other_compounds:
            ingredient_dict['other_compounds'] = other_compounds

        return ingredient_key, ingredient_dict

    def is_trace_element(self, compound: str) -> bool:
        """Check if compound is a trace element."""
        trace_indicators = [
            'FeCl', 'ZnCl', 'MnCl', 'CoCl', 'CuCl', 'NiCl',
            'MoO4', 'H3BO3', 'boric', 'molybdate',
            'FeSO4', 'ZnSO4', 'MnSO4', 'CoSO4', 'CuSO4',
            'SeO', 'WO4', 'tungstate', 'selenite'
        ]
        return any(ind in compound for ind in trace_indicators)

    def is_vitamin(self, compound: str) -> bool:
        """Check if compound is a vitamin."""
        vitamin_indicators = [
            'vitamin', 'thiamine', 'riboflavin', 'niacin', 'pyridoxine',
            'biotin', 'folic', 'cobalamin', 'pantothenic', 'nicotinic',
            'B1', 'B2', 'B3', 'B5', 'B6', 'B7', 'B9', 'B12',
            'p-aminobenzoic', 'PABA'
        ]
        return any(ind.lower() in compound.lower() for ind in vitamin_indicators)

    def generate_yaml_output(self, solution_ids: List[str], min_usage: int = 1) -> Dict:
        """Generate YAML output for selected solutions."""

        output = {
            'metadata': {
                'source': 'DSMZ MediaDive API',
                'imported_from': 'kg-microbe/data/raw/mediadive/solutions.json',
                'import_date': '2025-12-17',
                'description': 'Trace element, vitamin, and mineral solutions from MediaDive',
                'min_usage_threshold': min_usage,
                'total_solutions_imported': 0
            },
            'ingredients': {}
        }

        imported_count = 0

        for sol_id in solution_ids:
            # Filter by usage
            usage = self.solution_usage.get(sol_id, 0)
            if usage < min_usage:
                continue

            sol_data = self.solutions_data.get(sol_id)
            if not sol_data:
                continue

            # Convert to YAML format
            ingredient_key, ingredient_dict = self.convert_solution_to_yaml_format(sol_id, sol_data)

            # Skip if no chemical data
            if not any(k in ingredient_dict for k in ['trace_elements', 'vitamins', 'other_compounds']):
                continue

            output['ingredients'][ingredient_key] = ingredient_dict
            imported_count += 1

        output['metadata']['total_solutions_imported'] = imported_count

        logger.info(f"Generated YAML for {imported_count} solutions")
        return output

    def save_yaml(self, data: Dict, output_file: str):
        """Save data to YAML file."""
        logger.info(f"Saving YAML to {output_file}")

        # Create output directory if needed
        Path(output_file).parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w') as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

        logger.info(f"Saved {len(data.get('ingredients', {}))} ingredients to {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Import MediaDive solutions to complex ingredient YAML format"
    )
    parser.add_argument(
        '--solutions',
        required=True,
        help='Path to MediaDive solutions.json file'
    )
    parser.add_argument(
        '--media',
        required=True,
        help='Path to MediaDive media_detailed.json file'
    )
    parser.add_argument(
        '--output',
        required=True,
        help='Output YAML file path'
    )
    parser.add_argument(
        '--min-usage',
        type=int,
        default=5,
        help='Minimum number of media using a solution to include it (default: 5)'
    )
    parser.add_argument(
        '--categories',
        default='trace,vitamin,mineral',
        help='Comma-separated categories to filter (default: trace,vitamin,mineral)'
    )

    args = parser.parse_args()

    # Parse categories
    categories = [cat.strip() for cat in args.categories.split(',')]

    # Initialize importer
    importer = MediaDiveSolutionImporter(args.solutions, args.media)

    # Load data
    importer.load_data()

    # Calculate usage
    importer.calculate_solution_usage()

    # Filter solutions by category
    filtered_ids = importer.filter_solutions_by_category(categories)

    # Generate YAML
    yaml_data = importer.generate_yaml_output(filtered_ids, min_usage=args.min_usage)

    # Save output
    importer.save_yaml(yaml_data, args.output)

    logger.info("Import completed successfully!")


if __name__ == "__main__":
    main()
