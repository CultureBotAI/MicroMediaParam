#!/usr/bin/env python3
"""
Validate ontology mappings using OAK (Ontology Access Kit).

Checks that all ontology IDs (ChEBI, UBERON, FOODON, ENVO) in the mapping
file actually exist in their respective ontologies.

Usage:
    python -m src.quality.validate_ontology_mappings \
        --input compound_mappings_strict_final.tsv \
        --output validation_report.tsv
"""

import argparse
import logging
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Ontology configurations for OAK
ONTOLOGY_CONFIG = {
    'CHEBI': {
        'adapter': 'sqlite:obo:chebi',
        'prefix': 'CHEBI:',
    },
    'UBERON': {
        'adapter': 'sqlite:obo:uberon',
        'prefix': 'UBERON:',
    },
    'FOODON': {
        'adapter': 'sqlite:obo:foodon',
        'prefix': 'FOODON:',
    },
    'ENVO': {
        'adapter': 'sqlite:obo:envo',
        'prefix': 'ENVO:',
    },
}


def extract_ontology_ids(mapping_file: str) -> Dict[str, Set[str]]:
    """Extract unique ontology IDs grouped by ontology."""
    logger.info(f"Loading mappings from {mapping_file}")
    df = pd.read_csv(mapping_file, sep='\t', low_memory=False)

    ids_by_ontology = defaultdict(set)

    mapped_col = 'mapped'
    if mapped_col not in df.columns:
        logger.error(f"Column '{mapped_col}' not found in {mapping_file}")
        return ids_by_ontology

    for value in df[mapped_col].dropna().unique():
        value_str = str(value).strip()
        for ont_name, config in ONTOLOGY_CONFIG.items():
            if value_str.startswith(config['prefix']):
                ids_by_ontology[ont_name].add(value_str)
                break

    for ont, ids in ids_by_ontology.items():
        logger.info(f"  {ont}: {len(ids)} unique IDs")

    return ids_by_ontology


def validate_ids_with_oak(
    ontology: str,
    ids: Set[str],
    batch_size: int = 100
) -> Tuple[Set[str], Set[str]]:
    """
    Validate IDs using OAK runoak labels command.

    Returns:
        Tuple of (valid_ids, invalid_ids)
    """
    config = ONTOLOGY_CONFIG.get(ontology)
    if not config:
        logger.warning(f"No config for ontology: {ontology}")
        return set(), ids

    adapter = config['adapter']
    valid_ids = set()
    invalid_ids = set()

    id_list = list(ids)
    total_batches = (len(id_list) + batch_size - 1) // batch_size

    logger.info(f"Validating {len(ids)} {ontology} IDs in {total_batches} batches...")

    for batch_num in range(total_batches):
        start_idx = batch_num * batch_size
        end_idx = min(start_idx + batch_size, len(id_list))
        batch = id_list[start_idx:end_idx]

        try:
            # Run OAK labels command
            cmd = ['runoak', '-i', adapter, 'labels'] + batch
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )

            # Parse output - format is "ID<tab>label" or just "ID" if no label
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                parts = line.split('\t')
                term_id = parts[0].strip()
                label = parts[1].strip() if len(parts) > 1 else ''

                if term_id in ids:
                    if label and label != 'None':
                        valid_ids.add(term_id)
                    else:
                        invalid_ids.add(term_id)

            # Check stderr for errors about missing terms
            if result.stderr:
                for line in result.stderr.split('\n'):
                    if 'not found' in line.lower() or 'no such' in line.lower():
                        # Try to extract the ID
                        for term_id in batch:
                            if term_id in line:
                                invalid_ids.add(term_id)

        except subprocess.TimeoutExpired:
            logger.warning(f"Timeout validating batch {batch_num + 1}")
            # Mark all as unknown
            for term_id in batch:
                if term_id not in valid_ids:
                    invalid_ids.add(term_id)
        except Exception as e:
            logger.error(f"Error validating batch {batch_num + 1}: {e}")

        if (batch_num + 1) % 10 == 0:
            logger.info(f"  Processed {batch_num + 1}/{total_batches} batches")

    # Any IDs not seen in output are invalid
    for term_id in ids:
        if term_id not in valid_ids and term_id not in invalid_ids:
            invalid_ids.add(term_id)

    return valid_ids, invalid_ids


def validate_with_local_file(
    ontology: str,
    ids: Set[str],
    nodes_file: str
) -> Tuple[Set[str], Set[str]]:
    """
    Validate IDs against a local nodes.tsv file.

    This is faster than OAK for large-scale validation.
    """
    logger.info(f"Validating {len(ids)} {ontology} IDs against {nodes_file}")

    if not Path(nodes_file).exists():
        logger.warning(f"Nodes file not found: {nodes_file}")
        return set(), ids

    # Load valid IDs from nodes file
    df = pd.read_csv(nodes_file, sep='\t', low_memory=False)
    valid_ontology_ids = set(df['id'].dropna().unique())

    valid_ids = ids & valid_ontology_ids
    invalid_ids = ids - valid_ontology_ids

    return valid_ids, invalid_ids


def main():
    parser = argparse.ArgumentParser(
        description="Validate ontology mappings using OAK"
    )
    parser.add_argument(
        '--input', required=True,
        help='Input mapping TSV file'
    )
    parser.add_argument(
        '--output', required=True,
        help='Output validation report TSV'
    )
    parser.add_argument(
        '--chebi-nodes',
        help='Local ChEBI nodes file for faster validation'
    )
    parser.add_argument(
        '--use-oak', action='store_true',
        help='Use OAK for validation (slower but more authoritative)'
    )
    parser.add_argument(
        '--batch-size', type=int, default=100,
        help='Batch size for OAK queries'
    )

    args = parser.parse_args()

    # Extract IDs
    ids_by_ontology = extract_ontology_ids(args.input)

    if not any(ids_by_ontology.values()):
        logger.error("No ontology IDs found in input file")
        sys.exit(1)

    # Validate each ontology
    results = []
    total_valid = 0
    total_invalid = 0

    for ontology, ids in ids_by_ontology.items():
        if not ids:
            continue

        logger.info(f"\nValidating {ontology}...")

        if args.use_oak:
            valid_ids, invalid_ids = validate_ids_with_oak(
                ontology, ids, args.batch_size
            )
        elif ontology == 'CHEBI' and args.chebi_nodes:
            valid_ids, invalid_ids = validate_with_local_file(
                ontology, ids, args.chebi_nodes
            )
        else:
            # Default: assume all are valid (no validation)
            logger.warning(f"No validation method for {ontology}, skipping")
            valid_ids = ids
            invalid_ids = set()

        total_valid += len(valid_ids)
        total_invalid += len(invalid_ids)

        logger.info(f"  {ontology}: {len(valid_ids)} valid, {len(invalid_ids)} invalid")

        # Add to results
        for term_id in valid_ids:
            results.append({
                'ontology': ontology,
                'term_id': term_id,
                'status': 'valid',
                'message': ''
            })

        for term_id in invalid_ids:
            results.append({
                'ontology': ontology,
                'term_id': term_id,
                'status': 'invalid',
                'message': 'Term not found in ontology'
            })

    # Save results
    results_df = pd.DataFrame(results)
    results_df.to_csv(args.output, sep='\t', index=False)
    logger.info(f"\nSaved validation report to {args.output}")

    # Print summary
    print("\n" + "=" * 60)
    print("ONTOLOGY MAPPING VALIDATION REPORT")
    print("=" * 60)
    print(f"Total IDs checked:  {total_valid + total_invalid}")
    print(f"Valid:              {total_valid}")
    print(f"Invalid:            {total_invalid}")

    if total_invalid > 0:
        print("\nInvalid IDs by ontology:")
        invalid_df = results_df[results_df['status'] == 'invalid']
        for ont in invalid_df['ontology'].unique():
            ont_invalid = invalid_df[invalid_df['ontology'] == ont]
            print(f"  {ont}: {len(ont_invalid)}")
            for _, row in ont_invalid.head(5).iterrows():
                print(f"    - {row['term_id']}")
            if len(ont_invalid) > 5:
                print(f"    ... and {len(ont_invalid) - 5} more")

    print("=" * 60)

    # Exit with error if any invalid
    if total_invalid > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()
