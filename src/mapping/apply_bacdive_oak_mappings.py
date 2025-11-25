#!/usr/bin/env python3
"""
Apply OAK ChEBI annotations to BacDive metabolites.

Processes OAK annotation JSON output and creates a TSV mapping file
with metabolite names mapped to ChEBI IDs.
"""

import argparse
import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_oak_annotations(annotations_file: Path) -> List[Dict]:
    """Load OAK annotations from JSON file."""
    with open(annotations_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_metabolites(metabolites_file: Path) -> List[str]:
    """Load list of metabolite names."""
    with open(metabolites_file, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip()]


def process_annotations(
    annotations: List[Dict],
    metabolites: List[str]
) -> Dict[str, List[Tuple[str, str, str, int]]]:
    """
    Process OAK annotations and match to metabolite names.

    Returns dict mapping metabolite_name -> [(chebi_id, chebi_label, match_type, score)]
    """
    # Build index of metabolite positions in the concatenated text
    # OAK processes text line by line, so we need to match by text content
    metabolite_matches: Dict[str, List[Tuple[str, str, str, int]]] = defaultdict(list)

    for annotation in annotations:
        match_string = annotation.get('match_string', '')
        object_id = annotation.get('object_id', '')
        object_label = annotation.get('object_label', '')
        predicate_id = annotation.get('predicate_id', '')
        matches_whole = annotation.get('matches_whole_text', False)

        if not object_id.startswith('CHEBI:'):
            continue

        # Determine match quality
        if predicate_id == 'rdfs:label':
            match_type = 'exact_label'
            score = 100
        elif predicate_id == 'oio:hasExactSynonym':
            match_type = 'exact_synonym'
            score = 95
        elif predicate_id == 'oio:hasRelatedSynonym':
            match_type = 'related_synonym'
            score = 70
        else:
            match_type = 'other'
            score = 50

        # Find which metabolite this annotation matches
        match_lower = match_string.lower()
        for metabolite in metabolites:
            metabolite_lower = metabolite.lower()
            # Check if the match string is the whole metabolite or a significant part
            if match_lower == metabolite_lower:
                metabolite_matches[metabolite].append(
                    (object_id, object_label, match_type, score + 10)  # Bonus for exact match
                )
            elif match_lower in metabolite_lower and len(match_string) > 3:
                # Partial match - lower score
                metabolite_matches[metabolite].append(
                    (object_id, object_label, match_type, score - 20)
                )

    return metabolite_matches


def select_best_mapping(
    matches: List[Tuple[str, str, str, int]]
) -> Optional[Tuple[str, str, str, int]]:
    """Select the best ChEBI mapping from multiple candidates."""
    if not matches:
        return None

    # Sort by score (descending), then by ChEBI ID (for consistency)
    sorted_matches = sorted(matches, key=lambda x: (-x[3], x[0]))
    return sorted_matches[0]


def create_mapping_tsv(
    metabolites: List[str],
    metabolite_matches: Dict[str, List[Tuple[str, str, str, int]]],
    frequency_file: Optional[Path],
    output_file: Path
) -> Dict:
    """Create TSV mapping file with best ChEBI mappings."""

    # Load frequency data if available
    frequencies: Dict[str, int] = {}
    if frequency_file and frequency_file.exists():
        with open(frequency_file, 'r', encoding='utf-8') as f:
            next(f)  # Skip header
            for line in f:
                parts = line.strip().split('\t')
                if len(parts) >= 2:
                    frequencies[parts[0]] = int(parts[1])

    stats = {
        'total_metabolites': len(metabolites),
        'mapped': 0,
        'unmapped': 0,
        'total_records_covered': 0,
        'records_mapped': 0
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("metabolite_name\tchebi_id\tchebi_label\tmatch_type\tscore\trecord_count\n")

        for metabolite in sorted(metabolites):
            matches = metabolite_matches.get(metabolite, [])
            best = select_best_mapping(matches)
            record_count = frequencies.get(metabolite, 0)
            stats['total_records_covered'] += record_count

            if best:
                chebi_id, chebi_label, match_type, score = best
                f.write(f"{metabolite}\t{chebi_id}\t{chebi_label}\t{match_type}\t{score}\t{record_count}\n")
                stats['mapped'] += 1
                stats['records_mapped'] += record_count
            else:
                f.write(f"{metabolite}\t\t\tunmapped\t0\t{record_count}\n")
                stats['unmapped'] += 1

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Apply OAK ChEBI annotations to BacDive metabolites"
    )
    parser.add_argument(
        "--annotations-file",
        type=Path,
        default=Path("pipeline_output/bacdive_metabolites/bacdive_metabolites_oak_annotations.json"),
        help="OAK annotations JSON file"
    )
    parser.add_argument(
        "--metabolites-file",
        type=Path,
        default=Path("pipeline_output/bacdive_metabolites/bacdive_metabolites_unique.txt"),
        help="List of unique metabolite names"
    )
    parser.add_argument(
        "--frequency-file",
        type=Path,
        default=Path("pipeline_output/bacdive_metabolites/bacdive_metabolites_frequency.tsv"),
        help="Frequency report TSV"
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        default=Path("pipeline_output/bacdive_metabolites/bacdive_metabolites_chebi_mappings.tsv"),
        help="Output TSV file"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("Applying OAK ChEBI Mappings to BacDive Metabolites")
    print("=" * 60)

    # Load data
    print(f"\nLoading annotations from: {args.annotations_file}")
    annotations = load_oak_annotations(args.annotations_file)
    print(f"  Loaded {len(annotations)} annotations")

    print(f"\nLoading metabolites from: {args.metabolites_file}")
    metabolites = load_metabolites(args.metabolites_file)
    print(f"  Loaded {len(metabolites)} metabolites")

    # Process annotations
    print("\nProcessing annotations...")
    metabolite_matches = process_annotations(annotations, metabolites)
    print(f"  Found matches for {len(metabolite_matches)} metabolites")

    # Create output
    print(f"\nWriting mappings to: {args.output_file}")
    stats = create_mapping_tsv(
        metabolites,
        metabolite_matches,
        args.frequency_file,
        args.output_file
    )

    # Report results
    print("\n" + "=" * 60)
    print("Results Summary")
    print("=" * 60)
    print(f"  Total metabolites: {stats['total_metabolites']}")
    print(f"  Mapped to ChEBI:   {stats['mapped']} ({stats['mapped']/stats['total_metabolites']*100:.1f}%)")
    print(f"  Unmapped:          {stats['unmapped']} ({stats['unmapped']/stats['total_metabolites']*100:.1f}%)")

    if stats['total_records_covered'] > 0:
        print(f"\n  BacDive records coverage:")
        print(f"    Total records:  {stats['total_records_covered']:,}")
        print(f"    Records mapped: {stats['records_mapped']:,} ({stats['records_mapped']/stats['total_records_covered']*100:.1f}%)")

    print(f"\nOutput file: {args.output_file}")


if __name__ == "__main__":
    main()
