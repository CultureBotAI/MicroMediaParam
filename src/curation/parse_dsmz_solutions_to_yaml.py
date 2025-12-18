#!/usr/bin/env python3
"""
Parse DSMZ Solution Compositions to YAML

Reads DSMZ solution JSON files (from MediaDive API) and generates YAML entries
for the complex ingredients database. Focuses on trace element solutions,
vitamin solutions, and other standardized DSMZ formulations.

High-priority solutions:
- Selenite-tungstate solution (22 occurrences in unmapped data)
- Wolfe's vitamin/mineral solutions
- Trace element solutions (SL-10, SL-12, etc.)

Usage:
    python src/curation/parse_dsmz_solutions_to_yaml.py \\
        --solution-dir solution_texts/ \\
        --output dsmz_solutions_additions.yaml \\
        --priority "Selenite-tungstate" "Wolfe" "SL-10"

Version: 1.0.0
"""

import argparse
import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Set

import yaml

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DSMZSolutionParser:
    """Parses DSMZ solution JSON files and generates YAML entries."""

    # Common compound to ChEBI mappings for trace element solutions
    COMPOUND_MAPPINGS = {
        # Selenite/Tungstate compounds
        'na2seo3': {'chebi_id': 'CHEBI:64734', 'name': 'sodium selenite'},
        'na2seo3 x 5 h2o': {'chebi_id': 'CHEBI:64734', 'name': 'sodium selenite pentahydrate'},
        'na2wo4': {'chebi_id': 'CHEBI:75790', 'name': 'sodium tungstate'},
        'na2wo4 x 2 h2o': {'chebi_id': 'CHEBI:75790', 'name': 'sodium tungstate dihydrate'},
        'na2moo4': {'chebi_id': 'CHEBI:75211', 'name': 'sodium molybdate'},
        'na2moo4 x 2 h2o': {'chebi_id': 'CHEBI:75211', 'name': 'sodium molybdate dihydrate'},

        # Common salts
        'naoh': {'chebi_id': 'CHEBI:32145', 'name': 'sodium hydroxide'},
        'hcl': {'chebi_id': 'CHEBI:17883', 'name': 'hydrochloric acid'},
        'h2so4': {'chebi_id': 'CHEBI:26836', 'name': 'sulfuric acid'},

        # Nickel compounds
        'nicl2': {'chebi_id': 'CHEBI:34887', 'name': 'nickel dichloride'},
        'nicl2 x 6 h2o': {'chebi_id': 'CHEBI:34887', 'name': 'nickel chloride hexahydrate'},

        # Cobalt compounds
        'cocl2': {'chebi_id': 'CHEBI:35701', 'name': 'cobalt dichloride'},
        'cocl2 x 6 h2o': {'chebi_id': 'CHEBI:35701', 'name': 'cobalt chloride hexahydrate'},

        # Iron compounds
        'fecl2': {'chebi_id': 'CHEBI:30812', 'name': 'iron(II) chloride'},
        'fecl2 x 4 h2o': {'chebi_id': 'CHEBI:30812', 'name': 'iron(II) chloride tetrahydrate'},
        'fecl3': {'chebi_id': 'CHEBI:30808', 'name': 'iron(III) chloride'},
        'fecl3 x 6 h2o': {'chebi_id': 'CHEBI:30808', 'name': 'iron(III) chloride hexahydrate'},

        # Zinc compounds
        'zncl2': {'chebi_id': 'CHEBI:49976', 'name': 'zinc dichloride'},
        'znso4': {'chebi_id': 'CHEBI:27363', 'name': 'zinc sulfate'},
        'znso4 x 7 h2o': {'chebi_id': 'CHEBI:27363', 'name': 'zinc sulfate heptahydrate'},

        # Manganese compounds
        'mncl2': {'chebi_id': 'CHEBI:34342', 'name': 'manganese dichloride'},
        'mncl2 x 4 h2o': {'chebi_id': 'CHEBI:34342', 'name': 'manganese chloride tetrahydrate'},
        'mnso4': {'chebi_id': 'CHEBI:131528', 'name': 'manganese(II) sulfate'},

        # Copper compounds
        'cucl2': {'chebi_id': 'CHEBI:49553', 'name': 'copper(II) chloride'},
        'cucl2 x 2 h2o': {'chebi_id': 'CHEBI:49553', 'name': 'copper chloride dihydrate'},

        # EDTA
        'edta': {'chebi_id': 'CHEBI:42191', 'name': 'EDTA'},
        'na2-edta': {'chebi_id': 'CHEBI:64734', 'name': 'disodium EDTA'},

        # Vitamins (common in vitamin solutions)
        'thiamine': {'chebi_id': 'CHEBI:18385', 'name': 'thiamine'},
        'thiamine-hcl': {'chebi_id': 'CHEBI:49105', 'name': 'thiamine hydrochloride'},
        'riboflavin': {'chebi_id': 'CHEBI:17015', 'name': 'riboflavin'},
        'pyridoxine': {'chebi_id': 'CHEBI:16709', 'name': 'pyridoxine'},
        'biotin': {'chebi_id': 'CHEBI:15956', 'name': 'biotin'},
        'folic acid': {'chebi_id': 'CHEBI:27470', 'name': 'folic acid'},
        'cobalamin': {'chebi_id': 'CHEBI:23334', 'name': 'cobalamin'},
        'vitamin b12': {'chebi_id': 'CHEBI:176843', 'name': 'vitamin B12'},

        # Other
        'distilled water': {'chebi_id': 'CHEBI:15377', 'name': 'water'},
        'h2o': {'chebi_id': 'CHEBI:15377', 'name': 'water'},
    }

    def __init__(self, solution_dir: Path):
        """
        Initialize parser.

        Args:
            solution_dir: Directory containing solution JSON files
        """
        self.solution_dir = Path(solution_dir)
        self.solutions: Dict[str, Any] = {}

    def parse_solution_file(self, solution_file: Path) -> Optional[Dict[str, Any]]:
        """
        Parse a single DSMZ solution JSON file.

        Args:
            solution_file: Path to solution JSON file

        Returns:
            Parsed solution data or None if parsing fails
        """
        try:
            with open(solution_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            if 'data' not in data or data.get('status') != 200:
                logger.warning(f"Invalid solution file: {solution_file.name}")
                return None

            solution_data = data['data']

            return {
                'id': solution_data.get('id'),
                'name': solution_data.get('name'),
                'volume': solution_data.get('volume'),
                'recipe': solution_data.get('recipe', []),
                'steps': solution_data.get('steps', []),
            }

        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error in {solution_file.name}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error parsing {solution_file.name}: {e}")
            return None

    def parse_all_solutions(self) -> int:
        """
        Parse all solution JSON files in the directory.

        Returns:
            Number of solutions successfully parsed
        """
        json_files = list(self.solution_dir.glob('solution_*.md'))  # .md extension but JSON content
        logger.info(f"Found {len(json_files)} solution files")

        parsed_count = 0

        for json_file in json_files:
            solution_data = self.parse_solution_file(json_file)

            if solution_data:
                solution_id = solution_data['id']
                solution_name = solution_data['name']

                self.solutions[solution_name] = solution_data
                parsed_count += 1

                if parsed_count % 20 == 0:
                    logger.info(f"Parsed {parsed_count} solutions...")

        logger.info(f"Successfully parsed {parsed_count} solutions")
        return parsed_count

    def filter_priority_solutions(self, priority_keywords: List[str]) -> Dict[str, Any]:
        """
        Filter solutions by priority keywords.

        Args:
            priority_keywords: List of keywords to match in solution names

        Returns:
            Dictionary of matching solutions
        """
        if not priority_keywords:
            return self.solutions

        filtered = {}

        for name, data in self.solutions.items():
            for keyword in priority_keywords:
                if keyword.lower() in name.lower():
                    filtered[name] = data
                    break

        logger.info(f"Filtered {len(filtered)} priority solutions from {len(self.solutions)} total")
        return filtered

    def generate_yaml_entry(self, solution_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate YAML entry from solution data.

        Args:
            solution_data: Parsed solution data

        Returns:
            Dictionary with YAML entry
        """
        solution_name = solution_data['name']
        ingredient_id = self._normalize_name(solution_name)

        # Build names list
        names = [solution_name]

        # Add common variations
        if 'solution' in solution_name.lower():
            # Add version without 'solution'
            short_name = solution_name.replace(' solution', '').replace(' Solution', '')
            if short_name not in names:
                names.append(short_name)

        # Build entry
        entry = {
            'names': names,
            'description': f"DSMZ trace element/vitamin solution (ID: {solution_data['id']})",
            'source_references': ['DSMZ_MediaDive'],
            'dsmz_solution_id': solution_data['id'],
            'compound_type': 'solution_mixture',
        }

        # Parse recipe into trace_elements or vitamins
        recipe = solution_data.get('recipe', [])

        trace_elements = {}
        vitamins = {}
        other_compounds = {}

        for item in recipe:
            compound_name = item.get('compound', '') or ''
            amount = item.get('amount')
            unit = item.get('unit', '')
            g_l = item.get('g_l')

            # Skip empty or water compounds
            if not compound_name or 'water' in compound_name.lower():
                continue

            # Normalize compound name for lookup
            normalized = self._normalize_compound_name(compound_name)

            # Get ChEBI mapping
            mapping = self.COMPOUND_MAPPINGS.get(normalized, {})
            chebi_id = mapping.get('chebi_id')
            standard_name = mapping.get('name', compound_name)

            # Determine category
            if any(vit in normalized for vit in ['vitamin', 'thiamine', 'riboflavin', 'pyridoxine', 'biotin', 'folic', 'cobalamin']):
                category = vitamins
            elif any(metal in normalized for metal in ['fe', 'zn', 'mn', 'cu', 'co', 'ni', 'mo', 'se', 'w']):
                category = trace_elements
            else:
                category = other_compounds

            # Build compound entry
            compound_entry = {}

            if chebi_id:
                compound_entry['chebi_id'] = chebi_id

            # Convert to mg_per_100ml (solution basis)
            if g_l is not None:
                mg_per_100ml = g_l * 100  # g/L → mg/100mL
                compound_entry['mg_per_100ml'] = mg_per_100ml
            elif amount and unit:
                # Calculate mg_per_100ml from amount and unit
                if unit == 'mg':
                    volume_L = solution_data.get('volume', 1000) / 1000
                    mg_per_100ml = (amount / volume_L) / 10  # mg total → mg/100mL
                    compound_entry['mg_per_100ml'] = mg_per_100ml
                elif unit == 'g':
                    volume_L = solution_data.get('volume', 1000) / 1000
                    mg_per_100ml = (amount * 1000 / volume_L) / 10
                    compound_entry['mg_per_100ml'] = mg_per_100ml

            compound_entry['original_compound_name'] = compound_name

            # Add to appropriate category
            category[standard_name] = compound_entry

        # Add categories to entry
        if trace_elements:
            entry['trace_elements'] = trace_elements
        if vitamins:
            entry['vitamins'] = vitamins
        if other_compounds:
            entry['other_compounds'] = other_compounds

        # Add usage note
        volume_ml = solution_data.get('volume', 1000)
        entry['preparation_note'] = f"Standard preparation: dissolve components in {volume_ml} ml distilled water"

        entry['typical_usage'] = "Added at 1-10 ml per liter of growth medium"

        return {
            'id': ingredient_id,
            'data': entry
        }

    def _normalize_name(self, name: str) -> str:
        """Normalize solution name to ingredient ID."""
        normalized = name.lower().strip()
        normalized = re.sub(r'[^\w\s-]', '', normalized)
        normalized = normalized.replace(' ', '_').replace('-', '_')
        return normalized

    def _normalize_compound_name(self, name: str) -> str:
        """Normalize compound name for lookup."""
        normalized = name.lower().strip()
        # Remove extra spaces
        normalized = re.sub(r'\s+', ' ', normalized)
        return normalized

    def generate_yaml_for_solutions(
        self,
        solutions: Dict[str, Any],
        output_file: Path
    ):
        """
        Generate YAML file for solutions.

        Args:
            solutions: Dictionary of solutions to process
            output_file: Path to output YAML file
        """
        entries = {}

        for solution_name, solution_data in solutions.items():
            logger.info(f"Generating YAML for: {solution_name}")

            entry = self.generate_yaml_entry(solution_data)
            entries[entry['id']] = entry['data']

        # Create output structure
        output_data = {
            'metadata': {
                'version': '1.1.0',
                'description': 'DSMZ solution compositions from MediaDive',
                'generated': '2024-12-17',
                'source': 'DSMZ MediaDive REST API'
            },
            'ingredients': entries
        }

        # Write YAML
        with open(output_file, 'w', encoding='utf-8') as f:
            yaml.dump(output_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

        logger.info(f"Wrote {len(entries)} solution entries to {output_file}")

    def print_summary(self, solutions: Dict[str, Any]):
        """Print summary of solutions."""
        print("\n" + "=" * 70)
        print("DSMZ SOLUTIONS SUMMARY")
        print("=" * 70)

        for name, data in sorted(solutions.items()):
            recipe_count = len(data.get('recipe', []))
            print(f"\n{name} (ID: {data['id']})")
            print(f"  Components: {recipe_count}")
            print(f"  Volume: {data.get('volume', 'N/A')} ml")

        print("\n" + "=" * 70)
        print(f"Total solutions: {len(solutions)}")
        print("=" * 70)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Parse DSMZ solutions to YAML format'
    )
    parser.add_argument(
        '--solution-dir',
        required=True,
        help='Directory with DSMZ solution JSON files'
    )
    parser.add_argument(
        '--output',
        required=True,
        help='Output YAML file'
    )
    parser.add_argument(
        '--priority',
        nargs='*',
        help='Priority keywords to filter solutions (e.g., "Selenite" "Wolfe" "SL-10")'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be generated without writing file'
    )

    args = parser.parse_args()

    solution_dir = Path(args.solution_dir)
    output_file = Path(args.output)

    if not solution_dir.exists():
        logger.error(f"Solution directory not found: {solution_dir}")
        return 1

    # Parse solutions
    parser_obj = DSMZSolutionParser(solution_dir)
    parsed_count = parser_obj.parse_all_solutions()

    if parsed_count == 0:
        logger.error("No solutions parsed")
        return 1

    # Filter priority solutions if requested
    if args.priority:
        solutions = parser_obj.filter_priority_solutions(args.priority)
    else:
        solutions = parser_obj.solutions

    # Print summary
    parser_obj.print_summary(solutions)

    if args.dry_run:
        print("\n[DRY RUN] No files were modified.")
        return 0

    # Generate YAML
    parser_obj.generate_yaml_for_solutions(solutions, output_file)

    return 0


if __name__ == '__main__':
    exit(main())
