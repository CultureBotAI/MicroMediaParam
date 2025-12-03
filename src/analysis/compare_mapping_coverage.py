#!/usr/bin/env python3
"""
Compare mapping coverage between two compound mapping files.

Generates a markdown table showing unique compound counts by prefix.

Usage:
    python -m src.analysis.compare_mapping_coverage \
        --old pipeline_output/merge_mappings/attic/high_confidence_compound_mappings_final.tsv \
        --new pipeline_output/merge_mappings/compound_mappings.tsv \
        --output docs/mapping_coverage_comparison.md
"""

import argparse
from collections import defaultdict
from pathlib import Path
from typing import Dict, Tuple

import pandas as pd


# Prefixes grouped by category
ONTOLOGY_PREFIXES = ['CHEBI', 'UBERON', 'FOODON', 'KEGG']
DATABASE_PREFIXES = ['PubChem', 'CAS-RN']
REFERENCE_PREFIXES = ['medium']
UNMAPPED_PREFIXES = ['ingredient']


def get_prefix(mapping_id: str) -> str:
    """Extract prefix from mapping ID."""
    if pd.isna(mapping_id) or not mapping_id:
        return ''
    mapping_id = str(mapping_id)
    if ':' in mapping_id:
        return mapping_id.split(':')[0]
    return mapping_id


def count_unique_compounds_by_prefix(df: pd.DataFrame, mapped_col: str = 'mapped') -> Dict[str, int]:
    """Count unique compounds (by 'original' column) for each mapping prefix."""
    counts = defaultdict(set)

    for _, row in df.iterrows():
        original = row.get('original', '')
        mapped = row.get(mapped_col, '')
        prefix = get_prefix(mapped)
        if prefix and original:
            counts[prefix].add(original)

    return {k: len(v) for k, v in counts.items()}


def compare_mappings(old_file: Path, new_file: Path) -> Tuple[Dict[str, int], Dict[str, int]]:
    """Compare mapping coverage between two files."""
    old_df = pd.read_csv(old_file, sep='\t', low_memory=False)
    new_df = pd.read_csv(new_file, sep='\t', low_memory=False)

    old_counts = count_unique_compounds_by_prefix(old_df)
    new_counts = count_unique_compounds_by_prefix(new_df)

    return old_counts, new_counts


def format_change(old: int, new: int) -> str:
    """Format the change between old and new values."""
    diff = new - old
    if diff > 0:
        return f"**+{diff}**"
    elif diff < 0:
        if 'ingredient' in str(old):  # Special case for unmapped
            return f"**{diff}** (improved)"
        return f"{diff}"
    return "same"


def generate_markdown_table(old_counts: Dict[str, int], new_counts: Dict[str, int]) -> str:
    """Generate markdown comparison table."""
    lines = [
        "# Compound Mapping Coverage Comparison",
        "",
        "This table compares unique compound counts by mapping prefix between two mapping files.",
        "",
        "| Prefix | Old | New | Change |",
        "|--------|-----|-----|--------|",
    ]

    # Ontology IDs section
    lines.append("| **Ontology IDs** | | | |")
    ontology_old_total = 0
    ontology_new_total = 0
    for prefix in ONTOLOGY_PREFIXES:
        old = old_counts.get(prefix, 0)
        new = new_counts.get(prefix, 0)
        ontology_old_total += old
        ontology_new_total += new
        change = format_change(old, new)
        lines.append(f"| {prefix} | {old} | {new} | {change} |")

    change = format_change(ontology_old_total, ontology_new_total)
    lines.append(f"| **Subtotal Ontology** | **{ontology_old_total}** | **{ontology_new_total}** | {change} |")
    lines.append("| | | | |")

    # Database IDs section
    lines.append("| **Database IDs** | | | |")
    db_old_total = 0
    db_new_total = 0
    for prefix in DATABASE_PREFIXES:
        old = old_counts.get(prefix, 0)
        new = new_counts.get(prefix, 0)
        db_old_total += old
        db_new_total += new
        change = format_change(old, new)
        lines.append(f"| {prefix} | {old} | {new} | {change} |")

    change = format_change(db_old_total, db_new_total)
    lines.append(f"| **Subtotal Database** | **{db_old_total}** | **{db_new_total}** | {change} |")
    lines.append("| | | | |")

    # References section
    lines.append("| **References** | | | |")
    for prefix in REFERENCE_PREFIXES:
        old = old_counts.get(prefix, 0)
        new = new_counts.get(prefix, 0)
        change = format_change(old, new)
        lines.append(f"| {prefix} | {old} | {new} | {change} |")
    lines.append("| | | | |")

    # Unmapped section
    lines.append("| **Unmapped** | | | |")
    for prefix in UNMAPPED_PREFIXES:
        old = old_counts.get(prefix, 0)
        new = new_counts.get(prefix, 0)
        diff = new - old
        if diff < 0:
            change = f"**{diff}** (improved)"
        elif diff > 0:
            change = f"+{diff}"
        else:
            change = "same"
        lines.append(f"| {prefix} | {old} | {new} | {change} |")

    # Grand total
    lines.append("| | | | |")
    all_old = sum(old_counts.values())
    all_new = sum(new_counts.values())
    change = format_change(all_old, all_new)
    lines.append(f"| **Grand Total** | **{all_old:,}** | **{all_new:,}** | {change} |")

    # Summary
    ontology_gain = ontology_new_total - ontology_old_total
    unmapped_reduction = old_counts.get('ingredient', 0) - new_counts.get('ingredient', 0)

    lines.extend([
        "",
        "## Summary",
        "",
        f"- **+{ontology_gain}** unique compounds upgraded to proper ontology IDs",
        f"- **-{unmapped_reduction}** reduction in unmapped `ingredient:` compounds",
        f"- New ontology coverage: CHEBI ({new_counts.get('CHEBI', 0)}), "
        f"UBERON ({new_counts.get('UBERON', 0)}), "
        f"FOODON ({new_counts.get('FOODON', 0)}), "
        f"KEGG ({new_counts.get('KEGG', 0)})",
    ])

    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(
        description='Compare mapping coverage between two compound mapping files'
    )
    parser.add_argument(
        '--old', '-o',
        type=Path,
        required=True,
        help='Old mapping file for comparison'
    )
    parser.add_argument(
        '--new', '-n',
        type=Path,
        required=True,
        help='New mapping file for comparison'
    )
    parser.add_argument(
        '--output', '-out',
        type=Path,
        default=None,
        help='Output markdown file (default: print to stdout)'
    )

    args = parser.parse_args()

    old_counts, new_counts = compare_mappings(args.old, args.new)
    markdown = generate_markdown_table(old_counts, new_counts)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(markdown)
        print(f"Saved comparison to {args.output}")
    else:
        print(markdown)


if __name__ == '__main__':
    main()
