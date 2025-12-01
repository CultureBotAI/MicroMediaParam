#!/usr/bin/env python3
"""
Enrich compound mappings with ChEBI labels and molecular formulas.

Reads the final compound mappings file and adds:
- chebi_label: canonical ChEBI name
- chebi_formula: molecular formula extracted from ChEBI OWL

Uses two data sources:
1. ChEBI nodes TSV (from KG-Hub) - for labels
2. ChEBI formulas TSV (extracted from OWL) - for molecular formulas

Usage:
    python -m src.mapping.enrich_with_chebi_data \
        --input pipeline_output/merge_mappings/high_confidence_compound_mappings_final.tsv \
        --chebi-nodes /path/to/chebi_nodes.tsv \
        --chebi-formulas data/curated/chebi_formulas.tsv \
        --output pipeline_output/merge_mappings/high_confidence_compound_mappings_enriched.tsv
"""

import argparse
import logging
import re
from pathlib import Path
from typing import Dict, Optional, Tuple

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def parse_formula_from_description(description: str) -> Optional[str]:
    """
    Extract molecular formula from ChEBI description field.

    The formula is embedded as HTML like:
    "...with formula C<small><sub>15</sub></small>H<small><sub>24</sub></small>..."

    Returns clean formula like "C15H24"
    """
    if not description or pd.isna(description):
        return None

    # Pattern to find "formula X" where X contains HTML subscripts
    formula_match = re.search(r'formula\s+([^,\.]+)', str(description))
    if not formula_match:
        return None

    raw_formula = formula_match.group(1)

    # Remove HTML tags and convert subscripts
    # Pattern: element<small><sub>N</sub></small> -> elementN
    clean = re.sub(r'<small><sub>(\d+)</sub></small>', r'\1', raw_formula)
    clean = re.sub(r'<sub>(\d+)</sub>', r'\1', clean)
    clean = re.sub(r'<[^>]+>', '', clean)  # Remove any remaining HTML
    clean = clean.strip()

    # Validate it looks like a formula (starts with element symbol)
    if clean and re.match(r'^[A-Z][a-z]?\d*', clean):
        return clean

    return None


def load_chebi_formulas(formulas_file: Path) -> Dict[str, str]:
    """
    Load molecular formulas from chebi_formulas.tsv (extracted from OWL).

    Returns:
        Dict mapping CHEBI:ID -> formula
    """
    formulas = {}

    if not formulas_file.exists():
        logger.warning(f"ChEBI formulas file not found: {formulas_file}")
        return formulas

    logger.info(f"Loading ChEBI formulas from {formulas_file}")

    df = pd.read_csv(formulas_file, sep='\t')

    for _, row in df.iterrows():
        chebi_id = str(row.get('chebi_id', ''))
        formula = str(row.get('chebi_formula', '')) if pd.notna(row.get('chebi_formula')) else ''

        if chebi_id and formula:
            formulas[chebi_id] = formula

    logger.info(f"Loaded {len(formulas):,} formulas from OWL extract")

    return formulas


def load_chebi_data(
    chebi_file: Path,
    formulas_file: Optional[Path] = None
) -> Dict[str, Tuple[str, Optional[str]]]:
    """
    Load ChEBI nodes and extract name + formula.

    Args:
        chebi_file: ChEBI nodes TSV file (for labels)
        formulas_file: Optional ChEBI formulas TSV file (for molecular formulas)

    Returns:
        Dict mapping CHEBI:ID -> (name, formula)
    """
    logger.info(f"Loading ChEBI data from {chebi_file}")

    chebi_data = {}

    # Load formulas from OWL extract if available
    owl_formulas = {}
    if formulas_file:
        owl_formulas = load_chebi_formulas(formulas_file)

    df = pd.read_csv(chebi_file, sep='\t', low_memory=False)

    for _, row in df.iterrows():
        chebi_id = str(row.get('id', ''))
        if not chebi_id.startswith('CHEBI:'):
            continue

        name = str(row.get('name', '')) if pd.notna(row.get('name')) else ''

        # Get formula from OWL extract (primary source)
        formula = owl_formulas.get(chebi_id)

        # Fallback: try to parse from description
        if not formula:
            description = str(row.get('description', '')) if pd.notna(row.get('description')) else ''
            formula = parse_formula_from_description(description)

        chebi_data[chebi_id] = (name, formula)

    # Count statistics
    with_formula = sum(1 for _, (_, f) in chebi_data.items() if f)
    logger.info(f"Loaded {len(chebi_data):,} ChEBI entries, {with_formula:,} with formulas")

    return chebi_data


def enrich_mappings(
    input_file: Path,
    chebi_data: Dict[str, Tuple[str, Optional[str]]],
    output_file: Path
):
    """
    Enrich compound mappings with ChEBI labels and formulas.
    """
    logger.info(f"Reading mappings from {input_file}")
    df = pd.read_csv(input_file, sep='\t', low_memory=False)

    original_cols = list(df.columns)
    logger.info(f"Input has {len(df)} rows and {len(original_cols)} columns")

    # Add new columns after 'mapped' column
    mapped_idx = original_cols.index('mapped') if 'mapped' in original_cols else 2

    # Initialize new columns
    df['chebi_label'] = ''
    df['chebi_formula'] = ''

    # Track statistics
    stats = {
        'total': len(df),
        'chebi_rows': 0,
        'labels_added': 0,
        'formulas_added': 0
    }

    # Enrich each row
    for idx, row in df.iterrows():
        mapped_id = str(row.get('mapped', ''))

        if mapped_id.startswith('CHEBI:'):
            stats['chebi_rows'] += 1

            if mapped_id in chebi_data:
                name, formula = chebi_data[mapped_id]

                if name:
                    df.at[idx, 'chebi_label'] = name
                    stats['labels_added'] += 1

                if formula:
                    df.at[idx, 'chebi_formula'] = formula
                    stats['formulas_added'] += 1

    # Reorder columns to put new ones after 'mapped'
    new_cols = original_cols[:mapped_idx+1] + ['chebi_label', 'chebi_formula'] + original_cols[mapped_idx+1:]
    df = df[new_cols]

    # Save output
    output_file.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_file, sep='\t', index=False)

    logger.info(f"Output written to {output_file}")

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Enrich compound mappings with ChEBI labels and formulas"
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Input compound mappings TSV file"
    )
    parser.add_argument(
        "--chebi-nodes",
        type=Path,
        required=True,
        help="ChEBI nodes TSV file (for labels)"
    )
    parser.add_argument(
        "--chebi-formulas",
        type=Path,
        default=None,
        help="ChEBI formulas TSV file extracted from OWL (for molecular formulas)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output enriched TSV file"
    )

    args = parser.parse_args()

    # Load ChEBI data (with optional formulas file)
    chebi_data = load_chebi_data(args.chebi_nodes, args.chebi_formulas)

    # Enrich mappings
    stats = enrich_mappings(args.input, chebi_data, args.output)

    # Print summary
    print("\n" + "=" * 60)
    print("CHEBI ENRICHMENT COMPLETE")
    print("=" * 60)
    print(f"Total rows:        {stats['total']:,}")
    print(f"CHEBI rows:        {stats['chebi_rows']:,}")
    print(f"Labels added:      {stats['labels_added']:,} ({stats['labels_added']/stats['chebi_rows']*100:.1f}%)")
    print(f"Formulas added:    {stats['formulas_added']:,} ({stats['formulas_added']/stats['chebi_rows']*100:.1f}%)")
    print(f"Output:            {args.output}")
    print("=" * 60)


if __name__ == "__main__":
    main()
