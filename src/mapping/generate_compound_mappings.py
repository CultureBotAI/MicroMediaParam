#!/usr/bin/env python3
"""
Generate compound mappings from compound names using deterministic API calls.

This script replaces LLM-generated mappings with fully reproducible,
API-validated compound-to-ChEBI mappings.

Mapping Strategy (in order):
1. ChEBI nodes exact match (offline, fastest)
2. ChEBI nodes normalized match (offline)
3. PubChem name search -> ChEBI cross-reference (API)
4. Direct ChEBI/OLS4 search (API)
5. Microbiology products dictionary (UBERON/ingredient: fallback)
6. Unmapped

Usage:
    python -m src.mapping.generate_compound_mappings \
        --compounds-file pipeline_output/unmapped_analysis/all_compounds_to_map.txt \
        --chebi-nodes /path/to/chebi_nodes.tsv \
        --output data/curated/api_generated_mappings.tsv
"""

import argparse
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import pandas as pd

from .api_lookup import (
    search_pubchem_by_name,
    get_chebi_from_pubchem_cid,
    search_chebi_directly,
    REQUEST_DELAY
)
from .compound_normalizer import CompoundNameNormalizer
from .microbio_products import MicrobiologyProductMapper

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class MappingResult:
    """Result of mapping a compound name."""
    compound_name: str
    identifier: str
    id_type: str  # CHEBI, UBERON, ingredient, unmapped
    label: str
    mapping_strategy: str
    source: str


class DeterministicCompoundMapper:
    """
    Maps compound names to ChEBI IDs using deterministic strategies.

    All mappings are reproducible given the same inputs and API state.
    """

    def __init__(self, chebi_nodes_file: str):
        """
        Initialize the mapper.

        Args:
            chebi_nodes_file: Path to ChEBI nodes TSV file for offline matching
        """
        logger.info(f"Loading ChEBI nodes from {chebi_nodes_file}")
        self.chebi_lookup = self._load_chebi_nodes(chebi_nodes_file)
        logger.info(f"Loaded {len(self.chebi_lookup)} ChEBI name entries")

        self.chebi_normalized = self._build_normalized_lookup()
        logger.info(f"Built {len(self.chebi_normalized)} normalized ChEBI entries")

        self.normalizer = CompoundNameNormalizer()
        self.microbio_mapper = MicrobiologyProductMapper()

        # Track API call statistics
        self.stats = {
            'chebi_exact': 0,
            'chebi_normalized': 0,
            'pubchem_xref': 0,
            'chebi_search': 0,
            'microbio_products': 0,
            'unmapped': 0,
            'api_calls': 0
        }

    def _load_chebi_nodes(self, filepath: str) -> Dict[str, Tuple[str, str]]:
        """
        Load ChEBI nodes for offline exact matching.

        Returns dict: name.lower() -> (chebi_id, label)
        """
        chebi_lookup = {}

        try:
            df = pd.read_csv(filepath, sep='\t', low_memory=False)

            # Map primary names
            if 'name' in df.columns and 'id' in df.columns:
                for _, row in df.iterrows():
                    if pd.notna(row['id']) and str(row['id']).startswith('CHEBI:'):
                        chebi_id = str(row['id'])
                        if pd.notna(row.get('name')):
                            name = str(row['name']).lower().strip()
                            if name and name not in chebi_lookup:
                                chebi_lookup[name] = (chebi_id, str(row['name']))

                        # Also add synonyms
                        if 'synonym' in df.columns and pd.notna(row.get('synonym')):
                            synonyms = str(row['synonym']).split('|')
                            for syn in synonyms:
                                syn_lower = syn.lower().strip()
                                if syn_lower and syn_lower not in chebi_lookup:
                                    chebi_lookup[syn_lower] = (chebi_id, str(row['name']))

        except Exception as e:
            logger.error(f"Error loading ChEBI nodes: {e}")

        return chebi_lookup

    def _build_normalized_lookup(self) -> Dict[str, Tuple[str, str]]:
        """Build normalized name lookup from ChEBI entries."""
        normalizer = CompoundNameNormalizer()
        normalized_lookup = {}

        for name, (chebi_id, label) in self.chebi_lookup.items():
            normalized = normalizer.normalize(name)
            if normalized and normalized not in normalized_lookup:
                normalized_lookup[normalized] = (chebi_id, label)

        return normalized_lookup

    def map_compound(self, compound_name: str) -> MappingResult:
        """
        Map a single compound using deterministic strategy chain.

        Args:
            compound_name: Chemical compound name to map

        Returns:
            MappingResult with identifier and metadata
        """
        name_lower = compound_name.lower().strip()

        # Strategy 1: ChEBI exact match (offline, fastest)
        if name_lower in self.chebi_lookup:
            chebi_id, label = self.chebi_lookup[name_lower]
            self.stats['chebi_exact'] += 1
            return MappingResult(
                compound_name=compound_name,
                identifier=chebi_id,
                id_type='CHEBI',
                label=label,
                mapping_strategy='chebi_exact',
                source='chebi_nodes.tsv'
            )

        # Strategy 2: ChEBI normalized match (offline)
        normalized = self.normalizer.normalize(compound_name)
        if normalized in self.chebi_normalized:
            chebi_id, label = self.chebi_normalized[normalized]
            self.stats['chebi_normalized'] += 1
            return MappingResult(
                compound_name=compound_name,
                identifier=chebi_id,
                id_type='CHEBI',
                label=label,
                mapping_strategy='chebi_normalized',
                source='chebi_nodes.tsv'
            )

        # Strategy 3: PubChem -> ChEBI cross-reference (API)
        time.sleep(REQUEST_DELAY)
        self.stats['api_calls'] += 1
        cid = search_pubchem_by_name(compound_name)
        if cid:
            time.sleep(REQUEST_DELAY)
            self.stats['api_calls'] += 1
            result = get_chebi_from_pubchem_cid(cid)
            if result:
                chebi_id, chebi_label = result
                self.stats['pubchem_xref'] += 1
                return MappingResult(
                    compound_name=compound_name,
                    identifier=chebi_id,
                    id_type='CHEBI',
                    label=chebi_label,
                    mapping_strategy='pubchem_xref',
                    source=f'pubchem_cid:{cid}'
                )

        # Strategy 4: Direct ChEBI/OLS4 search (API)
        time.sleep(REQUEST_DELAY)
        self.stats['api_calls'] += 1
        result = search_chebi_directly(compound_name)
        if result:
            chebi_id, chebi_label = result
            self.stats['chebi_search'] += 1
            return MappingResult(
                compound_name=compound_name,
                identifier=chebi_id,
                id_type='CHEBI',
                label=chebi_label,
                mapping_strategy='chebi_search',
                source='ols4_search'
            )

        # Strategy 5: Microbiology products fallback (offline)
        product = self.microbio_mapper.match(compound_name)
        if product:
            id_type = 'CHEBI'
            if product.chebi_id.startswith('UBERON:'):
                id_type = 'UBERON'
            elif product.chebi_id.startswith('ingredient:'):
                id_type = 'ingredient'

            self.stats['microbio_products'] += 1
            return MappingResult(
                compound_name=compound_name,
                identifier=product.chebi_id,
                id_type=id_type,
                label=product.description,
                mapping_strategy='microbio_products',
                source='curated'
            )

        # Strategy 6: Unmapped
        self.stats['unmapped'] += 1
        return MappingResult(
            compound_name=compound_name,
            identifier='',
            id_type='unmapped',
            label='',
            mapping_strategy='unmapped',
            source=''
        )

    def get_stats(self) -> Dict:
        """Get mapping statistics."""
        total = sum(v for k, v in self.stats.items() if k != 'api_calls')
        mapped = total - self.stats['unmapped']

        return {
            **self.stats,
            'total': total,
            'mapped': mapped,
            'coverage': f"{mapped / total * 100:.1f}%" if total > 0 else "0%"
        }


def load_compound_names(filepath: Path) -> List[str]:
    """Load compound names from file (one per line or TSV first column)."""
    compounds = []

    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            # Handle TSV format (take first column)
            if '\t' in line:
                compound = line.split('\t')[0]
            else:
                compound = line
            if compound:
                compounds.append(compound)

    return compounds


def save_checkpoint(results: List[MappingResult], output_path: Path, checkpoint_num: int):
    """Save checkpoint with current results."""
    checkpoint_path = output_path.parent / f"{output_path.stem}_checkpoint_{checkpoint_num}.tsv"

    with open(checkpoint_path, 'w', encoding='utf-8') as f:
        f.write("compound_name\tidentifier\tid_type\tlabel\tmapping_strategy\tsource\n")
        for r in results:
            f.write(f"{r.compound_name}\t{r.identifier}\t{r.id_type}\t{r.label}\t{r.mapping_strategy}\t{r.source}\n")

    logger.info(f"Saved checkpoint: {checkpoint_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate compound mappings via deterministic API calls"
    )
    parser.add_argument(
        "--compounds-file",
        type=Path,
        required=True,
        help="File with compound names (one per line or TSV)"
    )
    parser.add_argument(
        "--chebi-nodes",
        type=Path,
        required=True,
        help="ChEBI nodes TSV file for offline matching"
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output TSV file"
    )
    parser.add_argument(
        "--checkpoint-interval",
        type=int,
        default=100,
        help="Save checkpoint every N compounds (default: 100)"
    )
    parser.add_argument(
        "--resume-from",
        type=Path,
        default=None,
        help="Resume from checkpoint file"
    )

    args = parser.parse_args()

    # Load compound names
    logger.info(f"Loading compounds from {args.compounds_file}")
    compounds = load_compound_names(args.compounds_file)

    # Deduplicate (case-insensitive)
    seen = set()
    unique_compounds = []
    for c in compounds:
        key = c.lower().strip()
        if key not in seen:
            seen.add(key)
            unique_compounds.append(c)

    logger.info(f"Loaded {len(unique_compounds)} unique compound names")

    # Initialize mapper
    mapper = DeterministicCompoundMapper(str(args.chebi_nodes))

    # Resume from checkpoint if specified
    results = []
    start_idx = 0
    processed_names: Set[str] = set()

    if args.resume_from and args.resume_from.exists():
        logger.info(f"Resuming from checkpoint: {args.resume_from}")
        with open(args.resume_from, 'r', encoding='utf-8') as f:
            header = next(f)
            for line in f:
                parts = line.strip().split('\t')
                if len(parts) >= 6:
                    results.append(MappingResult(
                        compound_name=parts[0],
                        identifier=parts[1],
                        id_type=parts[2],
                        label=parts[3],
                        mapping_strategy=parts[4],
                        source=parts[5]
                    ))
                    processed_names.add(parts[0].lower().strip())
        logger.info(f"Loaded {len(results)} existing results from checkpoint")

    # Process compounds
    checkpoint_num = 0
    total = len(unique_compounds)

    for i, compound in enumerate(unique_compounds):
        # Skip already processed
        if compound.lower().strip() in processed_names:
            continue

        result = mapper.map_compound(compound)
        results.append(result)

        # Progress logging
        if (i + 1) % 50 == 0 or i == total - 1:
            stats = mapper.get_stats()
            logger.info(
                f"Progress: {i + 1}/{total} | "
                f"Mapped: {stats['mapped']} ({stats['coverage']}) | "
                f"API calls: {stats['api_calls']}"
            )

        # Save checkpoint
        if (i + 1) % args.checkpoint_interval == 0:
            checkpoint_num += 1
            save_checkpoint(results, args.output, checkpoint_num)

    # Save final output
    args.output.parent.mkdir(parents=True, exist_ok=True)

    with open(args.output, 'w', encoding='utf-8') as f:
        f.write("compound_name\tidentifier\tid_type\tlabel\tmapping_strategy\tsource\tgeneration_date\n")
        generation_date = datetime.now().strftime('%Y-%m-%d')
        for r in results:
            f.write(f"{r.compound_name}\t{r.identifier}\t{r.id_type}\t{r.label}\t{r.mapping_strategy}\t{r.source}\t{generation_date}\n")

    logger.info(f"Output written to: {args.output}")

    # Print final statistics
    stats = mapper.get_stats()
    print("\n" + "=" * 60)
    print("DETERMINISTIC COMPOUND MAPPING COMPLETE")
    print("=" * 60)
    print(f"Total compounds:     {stats['total']}")
    print(f"Mapped:              {stats['mapped']} ({stats['coverage']})")
    print(f"Unmapped:            {stats['unmapped']}")
    print()
    print("By strategy:")
    print(f"  ChEBI exact:       {stats['chebi_exact']}")
    print(f"  ChEBI normalized:  {stats['chebi_normalized']}")
    print(f"  PubChem xref:      {stats['pubchem_xref']}")
    print(f"  ChEBI search:      {stats['chebi_search']}")
    print(f"  Microbio products: {stats['microbio_products']}")
    print()
    print(f"Total API calls:     {stats['api_calls']}")
    print("=" * 60)


if __name__ == "__main__":
    main()
