#!/usr/bin/env python3
"""
Expand Complex Biological Ingredients into Constituent Chemicals.

This script takes media composition data and expands complex ingredients
(yeast extract, peptone, etc.) into their constituent amino acids, vitamins,
sugars, and other chemicals with estimated concentrations.

Input: Media composition table with complex ingredients
Output: Expanded composition table with individual chemicals

Data Sources:
- data/curated/complex_ingredients/complex_ingredient_compositions.yaml
- Literature-derived composition profiles with ChEBI mappings

Usage:
    python -m src.scripts.expand_complex_ingredients \\
        --input pipeline_output/media_summary/media_composition_table.tsv \\
        --compositions data/curated/complex_ingredients/complex_ingredient_compositions.yaml \\
        --output pipeline_output/media_summary/media_composition_expanded.tsv
"""

import argparse
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import yaml

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CircularDependencyError(Exception):
    """Raised when circular ingredient references are detected."""
    pass


class RecursionDepthError(Exception):
    """Raised when max recursion depth is exceeded."""
    pass


class ComplexIngredientExpander:
    """Expands complex biological ingredients into constituent chemicals."""

    def __init__(self, compositions_file: str, resolve_references: bool = False, max_depth: int = 3):
        """
        Initialize with complex ingredient compositions data.

        Args:
            compositions_file: Path to YAML file with ingredient compositions
            resolve_references: Whether to recursively expand sub_ingredients
            max_depth: Maximum recursion depth for sub-ingredient expansion
        """
        self.compositions_file = compositions_file
        self.compositions: Dict[str, Any] = {}
        self.name_to_ingredient: Dict[str, str] = {}
        self.resolve_references = resolve_references
        self.max_depth = max_depth

        self._load_compositions()

    def _load_compositions(self):
        """Load complex ingredient compositions from YAML."""
        logger.info(f"Loading compositions from {self.compositions_file}")

        with open(self.compositions_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        self.compositions = data.get('ingredients', {})

        # Build name lookup index (case-insensitive)
        for ingredient_id, ingredient_data in self.compositions.items():
            names = ingredient_data.get('names', [])
            for name in names:
                self.name_to_ingredient[name.lower().strip()] = ingredient_id

        logger.info(f"Loaded {len(self.compositions)} complex ingredients")
        logger.info(f"Built name index with {len(self.name_to_ingredient)} aliases")

    def is_complex_ingredient(self, name: str) -> bool:
        """Check if an ingredient name matches a complex ingredient."""
        if not name:
            return False
        return name.lower().strip() in self.name_to_ingredient

    def get_ingredient_id(self, name: str) -> Optional[str]:
        """Get the ingredient ID for a name."""
        if not name:
            return None
        return self.name_to_ingredient.get(name.lower().strip())

    def _expand_ingredient_recursive(
        self,
        ingredient_name: str,
        concentration_factor: float,
        visited: Optional[set] = None,
        depth: int = 0,
        parent_chain: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Recursively expand an ingredient, resolving sub_ingredients.

        Args:
            ingredient_name: Name of ingredient to expand
            concentration_factor: Multiplication factor for concentrations
            visited: Set of visited ingredients (for cycle detection)
            depth: Current recursion depth
            parent_chain: List of parent ingredients in expansion chain

        Returns:
            List of constituent chemicals with calculated concentrations

        Raises:
            CircularDependencyError: If circular reference detected
            RecursionDepthError: If max depth exceeded
        """
        if visited is None:
            visited = set()
        if parent_chain is None:
            parent_chain = []

        # Cycle detection
        if ingredient_name.lower() in visited:
            chain = ' → '.join(parent_chain + [ingredient_name])
            raise CircularDependencyError(
                f"Circular reference detected: {chain}"
            )

        # Depth limit
        if depth > self.max_depth:
            chain = ' → '.join(parent_chain + [ingredient_name])
            raise RecursionDepthError(
                f"Max recursion depth ({self.max_depth}) exceeded: {chain}"
            )

        # Get ingredient data
        ingredient_id = self.get_ingredient_id(ingredient_name)
        if not ingredient_id:
            return []

        ingredient_data = self.compositions.get(ingredient_id, {})
        if not ingredient_data:
            return []

        # Mark as visited
        visited.add(ingredient_name.lower())
        current_chain = parent_chain + [ingredient_name]

        constituents = []

        # Check for sub_ingredients
        sub_ingredients = ingredient_data.get('sub_ingredients', {})
        if sub_ingredients and self.resolve_references:
            # This ingredient contains other complex ingredients
            logger.debug(f"Expanding sub-ingredients of {ingredient_name}: {list(sub_ingredients.keys())}")

            for sub_name, sub_info in sub_ingredients.items():
                # Sub-ingredient amount could be dict with g_per_100g or just direct chemical
                if isinstance(sub_info, dict):
                    # Check if it has a ChEBI ID (direct chemical, not ref to another ingredient)
                    if 'chebi_id' in sub_info:
                        # This is a direct chemical constituent, not a reference
                        continue

                    sub_g_per_100g = sub_info.get('g_per_100g', 0)
                else:
                    # Assume it's a number representing g_per_100g
                    sub_g_per_100g = float(sub_info) if sub_info else 0

                if not sub_g_per_100g:
                    continue

                # Calculate concentration factor for sub-ingredient
                sub_factor = concentration_factor * (sub_g_per_100g / 100.0)

                # Recursively expand sub-ingredient
                try:
                    sub_constituents = self._expand_ingredient_recursive(
                        sub_name,
                        sub_factor,
                        visited.copy(),  # Copy to allow different branches
                        depth + 1,
                        current_chain
                    )

                    # Add source tracking
                    for constituent in sub_constituents:
                        constituent['source_ingredient'] = ' → '.join(current_chain + [sub_name])
                        constituent['expansion_depth'] = depth + 1

                    constituents.extend(sub_constituents)

                except (CircularDependencyError, RecursionDepthError) as e:
                    logger.warning(f"Skipping sub-ingredient {sub_name}: {e}")
                    continue

        # Extract direct constituent chemicals (amino_acids, vitamins, etc.)
        direct_constituents = self._extract_direct_constituents(
            ingredient_data,
            concentration_factor,
            current_chain
        )
        constituents.extend(direct_constituents)

        # Remove from visited (allows different branches)
        visited.discard(ingredient_name.lower())

        return constituents

    def _extract_direct_constituents(
        self,
        ingredient_data: Dict[str, Any],
        concentration_factor: float,
        source_chain: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Extract direct constituent chemicals (not sub-ingredients).

        Args:
            ingredient_data: Ingredient data from YAML
            concentration_factor: Multiplication factor for concentrations
            source_chain: List showing expansion path

        Returns:
            List of constituent chemicals
        """
        categories = [
            'amino_acids', 'vitamins', 'minerals', 'sugars',
            'nucleotides', 'other_compounds', 'proteins',
            'metabolites', 'trace_elements'
        ]

        constituents = []

        for category in categories:
            category_data = ingredient_data.get(category, {})
            if not category_data:
                continue

            for chemical_name, chemical_info in category_data.items():
                # Skip if not a dict
                if not isinstance(chemical_info, dict):
                    continue

                chebi_id = chemical_info.get('chebi_id', '')

                # Get concentration in g/100g or g/100ml
                g_per_100 = chemical_info.get('g_per_100g', 0) or chemical_info.get('g_per_100ml', 0)
                mg_per_100 = chemical_info.get('mg_per_100g', 0) or chemical_info.get('mg_per_100ml', 0)

                if mg_per_100 and not g_per_100:
                    g_per_100 = mg_per_100 / 1000.0

                if not g_per_100:
                    continue

                # Calculate final concentration
                final_g_per_100 = concentration_factor * g_per_100

                constituents.append({
                    'chemical_name': chemical_name,
                    'chebi_id': chebi_id,
                    'g_per_100': final_g_per_100,
                    'original_g_per_100': g_per_100,
                    'category': category,
                    'source_ingredient': ' → '.join(source_chain),
                    'expansion_depth': len(source_chain) - 1
                })

        return constituents

    def expand_ingredient(
        self,
        ingredient_name: str,
        concentration_g_ml: float,
        medium_id: str,
        include_categories: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Expand a complex ingredient into its constituent chemicals.

        Args:
            ingredient_name: Name of the complex ingredient
            concentration_g_ml: Concentration in g/mL
            medium_id: Media ID for tracking
            include_categories: Categories to include (amino_acids, vitamins, etc.)
                               If None, include all

        Returns:
            List of dictionaries with expanded chemical entries
        """
        # Use recursive expansion if enabled
        if self.resolve_references:
            return self._expand_ingredient_with_references(
                ingredient_name,
                concentration_g_ml,
                medium_id
            )

        # Original non-recursive expansion
        ingredient_id = self.get_ingredient_id(ingredient_name)
        if not ingredient_id:
            return []

        ingredient_data = self.compositions.get(ingredient_id, {})
        if not ingredient_data:
            return []

        # Default categories to expand
        if include_categories is None:
            include_categories = [
                'amino_acids', 'vitamins', 'minerals',
                'sugars', 'nucleotides', 'other_compounds'
            ]

        expanded = []

        # Convert concentration from g/mL to g/100g basis
        # If media has X g/mL of ingredient, and ingredient has Y g/100g of chemical,
        # then media has X * Y / 100 g/mL of that chemical
        conc_factor = concentration_g_ml / 100.0 if concentration_g_ml else 0

        for category in include_categories:
            category_data = ingredient_data.get(category, {})
            if not category_data:
                continue

            for chemical_name, chemical_info in category_data.items():
                # Skip if not a dict (could be a simple value)
                if not isinstance(chemical_info, dict):
                    continue

                chebi_id = chemical_info.get('chebi_id', '')
                common_name = chemical_info.get('common_name', chemical_name)

                # Get concentration (could be g_per_100g or mg_per_100g)
                g_per_100g = chemical_info.get('g_per_100g', 0)
                mg_per_100g = chemical_info.get('mg_per_100g', 0)

                if mg_per_100g and not g_per_100g:
                    g_per_100g = mg_per_100g / 1000.0

                if not g_per_100g:
                    continue

                # Calculate final concentration in g/mL
                final_conc = conc_factor * g_per_100g

                # Format chemical name nicely
                display_name = self._format_chemical_name(chemical_name)

                expanded.append({
                    'medium_id': medium_id,
                    'ingredient_name': display_name,
                    'ingredient_label': common_name if common_name != chemical_name else '',
                    'ingredient_id': chebi_id,
                    'formula': '',  # Would need formula lookup
                    'raw_concentration': f"from {ingredient_name} ({g_per_100g:.3g} g/100g)",
                    'concentration_g_ml': self._format_concentration(final_conc),
                    'source_ingredient': ingredient_name,
                    'expansion_category': category,
                })

        return expanded

    def _expand_ingredient_with_references(
        self,
        ingredient_name: str,
        concentration_g_ml: float,
        medium_id: str
    ) -> List[Dict[str, Any]]:
        """
        Expand ingredient with recursive sub-ingredient resolution.

        Args:
            ingredient_name: Name of ingredient
            concentration_g_ml: Concentration in g/mL
            medium_id: Media ID for tracking

        Returns:
            List of expanded chemical entries
        """
        # Convert concentration to factor
        conc_factor = concentration_g_ml / 100.0 if concentration_g_ml else 0

        # Use recursive expansion
        try:
            constituents = self._expand_ingredient_recursive(
                ingredient_name,
                conc_factor,
                visited=None,
                depth=0,
                parent_chain=[]
            )
        except (CircularDependencyError, RecursionDepthError) as e:
            logger.error(f"Failed to expand {ingredient_name}: {e}")
            return []

        # Convert to output format
        expanded = []
        for constituent in constituents:
            chemical_name = constituent['chemical_name']
            chebi_id = constituent['chebi_id']
            g_per_100 = constituent['g_per_100']
            original_g_per_100 = constituent['original_g_per_100']
            category = constituent['category']
            source_ingredient = constituent['source_ingredient']

            # Calculate final concentration in g/mL
            final_conc = g_per_100

            # Format chemical name
            display_name = self._format_chemical_name(chemical_name)

            expanded.append({
                'medium_id': medium_id,
                'ingredient_name': display_name,
                'ingredient_label': '',
                'ingredient_id': chebi_id,
                'formula': '',
                'raw_concentration': f"from {source_ingredient} ({original_g_per_100:.3g} g/100g)",
                'concentration_g_ml': self._format_concentration(final_conc),
                'source_ingredient': source_ingredient,
                'expansion_category': category,
            })

        return expanded

    def _format_chemical_name(self, name: str) -> str:
        """Format chemical name for display."""
        # Convert underscores to hyphens for amino acids
        name = name.replace('_', '-')
        # Capitalize L- prefix
        if name.startswith('l-'):
            name = 'L-' + name[2:]
        return name

    def _format_concentration(self, value: float) -> str:
        """Format concentration value."""
        if value == 0:
            return ''
        if value < 0.000001:
            return f"{value:.2e}"
        return f"{value:.9g}"


def expand_complex_ingredients(
    input_file: str,
    compositions_file: str,
    output_file: str,
    expand_mode: str = 'append',
    resolve_references: bool = False,
    max_depth: int = 3
) -> Dict[str, int]:
    """
    Expand complex ingredients in media composition table.

    Args:
        input_file: Input composition table
        compositions_file: YAML file with complex ingredient compositions
        output_file: Output file path
        expand_mode: 'append' to keep original rows, 'replace' to replace them
        resolve_references: Whether to recursively expand sub_ingredients
        max_depth: Maximum recursion depth for sub-ingredient expansion

    Returns:
        Statistics dictionary
    """
    logger.info(f"Reading input: {input_file}")
    df = pd.read_csv(input_file, sep='\t', low_memory=False)
    logger.info(f"Loaded {len(df)} rows")

    # Initialize expander
    expander = ComplexIngredientExpander(compositions_file, resolve_references, max_depth)
    if resolve_references:
        logger.info(f"Recursive sub-ingredient expansion enabled (max depth: {max_depth})")

    # Statistics
    stats = {
        'total_rows': len(df),
        'complex_ingredients_found': 0,
        'rows_expanded': 0,
        'new_chemical_rows': 0,
        'unique_complex_ingredients': set(),
    }

    # Collect expanded rows
    expanded_rows = []
    rows_to_keep = []

    for idx, row in df.iterrows():
        ingredient_name = row.get('ingredient_name', '')

        if expander.is_complex_ingredient(ingredient_name):
            stats['complex_ingredients_found'] += 1
            stats['unique_complex_ingredients'].add(ingredient_name.lower())

            # Get concentration
            conc_str = row.get('concentration_g_ml', '')
            try:
                concentration = float(conc_str) if conc_str else 0
            except (ValueError, TypeError):
                concentration = 0

            # Expand this ingredient
            medium_id = row.get('medium_id', '')
            expanded = expander.expand_ingredient(
                ingredient_name,
                concentration,
                medium_id
            )

            if expanded:
                stats['rows_expanded'] += 1
                stats['new_chemical_rows'] += len(expanded)
                expanded_rows.extend(expanded)

            # Keep original row in append mode
            if expand_mode == 'append':
                rows_to_keep.append(row.to_dict())
        else:
            # Keep non-complex ingredients
            rows_to_keep.append(row.to_dict())

    # Combine results
    if expand_mode == 'append':
        # Keep all original rows and add expanded
        result_df = pd.DataFrame(rows_to_keep + expanded_rows)
    else:
        # Replace complex ingredients with expanded chemicals
        result_df = pd.DataFrame(rows_to_keep + expanded_rows)

    # Ensure consistent column order
    columns = [
        'medium_id', 'ingredient_name', 'ingredient_label', 'ingredient_id',
        'formula', 'raw_concentration', 'concentration_g_ml',
        'source_ingredient', 'expansion_category'
    ]
    for col in columns:
        if col not in result_df.columns:
            result_df[col] = ''

    result_df = result_df[columns]

    # Sort by medium_id, then ingredient_name
    result_df = result_df.sort_values(['medium_id', 'ingredient_name']).reset_index(drop=True)

    # Save output
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result_df.to_csv(output_path, sep='\t', index=False)

    logger.info(f"Saved {len(result_df)} rows to {output_file}")

    # Print report
    _print_report(stats, len(result_df))

    return stats


def _print_report(stats: Dict[str, Any], final_rows: int):
    """Print expansion report."""
    print("\n" + "=" * 70)
    print("COMPLEX INGREDIENT EXPANSION REPORT")
    print("=" * 70)
    print(f"\nInput rows:                    {stats['total_rows']:,}")
    print(f"Complex ingredients found:     {stats['complex_ingredients_found']:,}")
    print(f"Unique complex ingredients:    {len(stats['unique_complex_ingredients'])}")
    print(f"\nExpansion Results:")
    print(f"  Rows expanded:               {stats['rows_expanded']:,}")
    print(f"  New chemical rows added:     {stats['new_chemical_rows']:,}")
    print(f"  Final output rows:           {final_rows:,}")

    if stats['unique_complex_ingredients']:
        print(f"\nComplex ingredients expanded:")
        for name in sorted(stats['unique_complex_ingredients'])[:10]:
            print(f"  - {name}")
        if len(stats['unique_complex_ingredients']) > 10:
            print(f"  ... and {len(stats['unique_complex_ingredients']) - 10} more")

    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Expand complex biological ingredients into constituent chemicals",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--input', '-i',
        required=True,
        help='Input media composition TSV file'
    )
    parser.add_argument(
        '--compositions', '-c',
        required=True,
        help='YAML file with complex ingredient compositions'
    )
    parser.add_argument(
        '--output', '-o',
        required=True,
        help='Output expanded composition TSV file'
    )
    parser.add_argument(
        '--mode', '-m',
        choices=['append', 'replace'],
        default='append',
        help='Expansion mode: append (keep originals) or replace'
    )
    parser.add_argument(
        '--resolve-references', '-r',
        action='store_true',
        help='Recursively expand sub_ingredients (e.g., LB broth → tryptone → amino acids)'
    )
    parser.add_argument(
        '--max-depth',
        type=int,
        default=3,
        help='Maximum recursion depth for sub-ingredient expansion (default: 3)'
    )

    args = parser.parse_args()

    expand_complex_ingredients(
        args.input,
        args.compositions,
        args.output,
        args.mode,
        args.resolve_references,
        args.max_depth
    )


if __name__ == '__main__':
    main()
