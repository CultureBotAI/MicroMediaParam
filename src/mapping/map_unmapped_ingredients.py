#!/usr/bin/env python3
"""
Map unmapped MediaDive ingredients using multi-ontology OLS and PubChem fallback.

Strategy:
1. Classify each ingredient as biological material or chemical
2. For biological materials: search UBERON → FOODON → ENVO via OLS4
3. For chemicals: search PubChem for compound ID
4. Combine results into unified output

Usage:
    python -m src.mapping.map_unmapped_ingredients \
        --input unmapped_mediadive_ingredients.tsv \
        --output additional_ingredient_mappings.tsv \
        --ols-cache data/cache/ols_multi_ontology_cache.tsv \
        --pubchem-cache data/cache/pubchem_lookup_cache.tsv
"""

import argparse
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from src.mapping.ols_multi_ontology_lookup import batch_search_ols
from src.mapping.pubchem_fallback_lookup import batch_pubchem_lookup
from src.mapping.compound_normalizer import (
    normalize_for_mapping,
    is_solution_or_media,
    extract_buffer_compound,
    lookup_biological_product,
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Patterns to identify biological materials (search OLS with UBERON/FOODON/ENVO)
BIOLOGICAL_PATTERNS = [
    r'\bextract\b',
    r'\bpeptone\b',
    r'\bblood\b',
    r'\bserum\b',
    r'\bplasma\b',
    r'\bbroth\b',
    r'\bdigest\b',
    r'\bhydrolysate\b',
    r'\bhydrolyzate\b',
    r'\btryptone\b',
    r'\bcasein\b',
    r'\bagar\b',
    r'\byeast\b',
    r'\bbeef\b',
    r'\bmeat\b',
    r'\bheart\b',
    r'\bbrain\b',
    r'\bliver\b',
    r'\bmilk\b',
    r'\bwhey\b',
    r'\begg\b',
    r'\bgelatin\b',
    r'\bstarch\b',
    r'\bcellulose\b',
    r'\bchitin\b',
    r'\bpectin\b',
    r'\bsoy\b',
    r'\bsoya\b',
    r'\bsoytone\b',
    r'\binfusion\b',
    r'\btissue\b',
    r'\borgan\b',
    r'\bbile\b',
    r'\bseawater\b',
    r'\bsea water\b',
    r'\bsoil\b',
    r'\bhumus\b',
    r'\bcompost\b',
]

# Compile patterns for efficiency
BIOLOGICAL_REGEX = re.compile(
    '|'.join(BIOLOGICAL_PATTERNS),
    re.IGNORECASE
)


@dataclass
class MappingStats:
    """Statistics from mapping run."""
    total: int = 0
    biological: int = 0
    chemical: int = 0
    ols_mapped: int = 0
    pubchem_mapped: int = 0
    unmapped: int = 0
    normalized_count: int = 0  # Number of names that were modified by normalization
    skipped_solutions: int = 0  # Number of solution/media entries skipped
    buffer_extractions: int = 0  # Number of buffer compounds extracted
    by_ontology: Dict[str, int] = None

    def __post_init__(self):
        if self.by_ontology is None:
            self.by_ontology = {}


def classify_ingredient(name: str) -> str:
    """
    Classify ingredient as 'biological' or 'chemical'.

    Args:
        name: Ingredient name

    Returns:
        'biological' or 'chemical'
    """
    if not name:
        return 'chemical'

    if BIOLOGICAL_REGEX.search(name):
        return 'biological'

    return 'chemical'


def map_unmapped_ingredients(
    unmapped_file: Path,
    output_file: Path,
    ols_cache: Optional[Path] = None,
    pubchem_cache: Optional[Path] = None,
    ontologies: List[str] = None
) -> MappingStats:
    """
    Map unmapped ingredients using OLS and PubChem.

    Args:
        unmapped_file: Input TSV with unmapped ingredients
        output_file: Output TSV with mappings
        ols_cache: Cache file for OLS results
        pubchem_cache: Cache file for PubChem results
        ontologies: Ontologies for OLS search

    Returns:
        MappingStats with results
    """
    if ontologies is None:
        ontologies = ["uberon", "foodon", "envo"]

    logger.info(f"Reading unmapped ingredients from {unmapped_file}")

    # Read file - check if it has a header by looking at first row
    first_line = unmapped_file.read_text().split('\n')[0]
    has_header = first_line.startswith('id') or first_line.startswith('original') or 'name' in first_line.lower()

    if has_header:
        df = pd.read_csv(unmapped_file, sep='\t')
        id_col = df.columns[0]
        name_col = df.columns[1] if len(df.columns) > 1 else df.columns[0]
    else:
        # No header - assign column names
        df = pd.read_csv(unmapped_file, sep='\t', header=None, names=['id', 'name'])
        id_col = 'id'
        name_col = 'name'

    logger.info(f"Using ID column: {id_col}, name column: {name_col}")

    # Normalize and classify ingredients
    biological_items = []  # (id, original_name, normalized_name)
    chemical_items = []    # (id, original_name, normalized_name)
    skipped_items = []     # (id, original_name, reason)
    normalized_count = 0
    buffer_extractions = 0

    for _, row in df.iterrows():
        item_id = str(row[id_col])
        original_name = str(row[name_col]) if pd.notna(row[name_col]) else ""

        # Skip solution/media entries (they are mixtures, not single compounds)
        if is_solution_or_media(original_name):
            skipped_items.append((item_id, original_name, 'solution/media'))
            logger.debug(f"Skipped solution/media: '{original_name}'")
            continue

        # Check if this is a buffer - extract the compound name if so
        buffer_compound = extract_buffer_compound(original_name)
        if buffer_compound:
            # Use the extracted buffer compound for lookup
            normalized_name = buffer_compound
            buffer_extractions += 1
            logger.debug(f"Buffer extracted: '{original_name}' → '{normalized_name}'")
        else:
            # Apply normalization for better mapping
            normalized_name = normalize_for_mapping(original_name)

        if normalized_name != original_name and normalized_name:
            normalized_count += 1
            logger.debug(f"Normalized: '{original_name}' → '{normalized_name}'")

        # Use normalized name for classification
        if classify_ingredient(normalized_name) == 'biological':
            biological_items.append((item_id, original_name, normalized_name))
        else:
            chemical_items.append((item_id, original_name, normalized_name))

    logger.info(f"Skipped {len(skipped_items)} solution/media entries")
    logger.info(f"Extracted {buffer_extractions} buffer compounds")
    logger.info(f"Normalized {normalized_count} compound names")
    logger.info(f"Classified {len(biological_items)} biological, {len(chemical_items)} chemical")

    stats = MappingStats(
        total=len(df),
        biological=len(biological_items),
        chemical=len(chemical_items),
        normalized_count=normalized_count,
        skipped_solutions=len(skipped_items),
        buffer_extractions=buffer_extractions
    )

    # Search OLS for biological materials using normalized names
    logger.info(f"Searching OLS for {len(biological_items)} biological materials...")
    biological_normalized = [normalized for _, _, normalized in biological_items]
    ols_results = batch_search_ols(biological_normalized, ontologies, ols_cache)

    # Search PubChem for chemicals using normalized names
    logger.info(f"Searching PubChem for {len(chemical_items)} chemicals...")
    chemical_normalized = [normalized for _, _, normalized in chemical_items]
    pubchem_results = batch_pubchem_lookup(chemical_normalized, pubchem_cache)

    # Build unified output
    output_rows = []

    # Process biological items
    curated_mapped = 0
    for item_id, original_name, normalized_name in biological_items:
        # First, check curated biological products dictionary
        curated_id = lookup_biological_product(original_name) or lookup_biological_product(normalized_name)

        if curated_id:
            curated_mapped += 1
            # Parse ontology prefix from ID
            prefix = curated_id.split(':')[0].lower()
            stats.by_ontology[prefix] = stats.by_ontology.get(prefix, 0) + 1

            output_rows.append({
                'original_id': item_id,
                'original_name': original_name,
                'normalized_name': normalized_name,
                'mapped_id': curated_id,
                'mapped_label': original_name,  # Use original as label
                'formula': '',
                'mapping_source': 'curated_biological',
                'ingredient_type': 'biological'
            })
            continue

        # Try OLS search
        ols_result = ols_results.get(normalized_name)

        if ols_result:
            ontology_id, label, source = ols_result
            stats.ols_mapped += 1
            stats.by_ontology[source] = stats.by_ontology.get(source, 0) + 1

            output_rows.append({
                'original_id': item_id,
                'original_name': original_name,
                'normalized_name': normalized_name,
                'mapped_id': ontology_id,
                'mapped_label': label,
                'formula': '',
                'mapping_source': f'ols4:{source}',
                'ingredient_type': 'biological'
            })
        else:
            # Try PubChem as fallback for biological that didn't match
            pubchem_result = batch_pubchem_lookup([normalized_name], pubchem_cache).get(normalized_name)
            if pubchem_result:
                cid, iupac, formula = pubchem_result
                stats.pubchem_mapped += 1
                output_rows.append({
                    'original_id': item_id,
                    'original_name': original_name,
                    'normalized_name': normalized_name,
                    'mapped_id': f'PUBCHEM.COMPOUND:{cid}',
                    'mapped_label': iupac,
                    'formula': formula,
                    'mapping_source': 'pubchem',
                    'ingredient_type': 'biological'
                })
            else:
                stats.unmapped += 1
                output_rows.append({
                    'original_id': item_id,
                    'original_name': original_name,
                    'normalized_name': normalized_name,
                    'mapped_id': '',
                    'mapped_label': '',
                    'formula': '',
                    'mapping_source': '',
                    'ingredient_type': 'biological'
                })

    logger.info(f"Mapped {curated_mapped} biological items via curated dictionary")

    # Process chemical items
    for item_id, original_name, normalized_name in chemical_items:
        pubchem_result = pubchem_results.get(normalized_name)

        if pubchem_result:
            cid, iupac, formula = pubchem_result
            stats.pubchem_mapped += 1

            output_rows.append({
                'original_id': item_id,
                'original_name': original_name,
                'normalized_name': normalized_name,
                'mapped_id': f'PUBCHEM.COMPOUND:{cid}',
                'mapped_label': iupac,
                'formula': formula,
                'mapping_source': 'pubchem',
                'ingredient_type': 'chemical'
            })
        else:
            stats.unmapped += 1
            output_rows.append({
                'original_id': item_id,
                'original_name': original_name,
                'normalized_name': normalized_name,
                'mapped_id': '',
                'mapped_label': '',
                'formula': '',
                'mapping_source': '',
                'ingredient_type': 'chemical'
            })

    # Save output
    output_df = pd.DataFrame(output_rows)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_df.to_csv(output_file, sep='\t', index=False)

    logger.info(f"Saved {len(output_df)} mappings to {output_file}")

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Map unmapped ingredients using OLS and PubChem"
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Input TSV with unmapped ingredients (id<TAB>name)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output TSV with mappings"
    )
    parser.add_argument(
        "--ols-cache",
        type=Path,
        default=None,
        help="Cache file for OLS results"
    )
    parser.add_argument(
        "--pubchem-cache",
        type=Path,
        default=None,
        help="Cache file for PubChem results"
    )
    parser.add_argument(
        "--ontologies",
        type=str,
        default="uberon,foodon,envo",
        help="Comma-separated ontologies for OLS search"
    )

    args = parser.parse_args()

    ontologies = [o.strip() for o in args.ontologies.split(",")]

    stats = map_unmapped_ingredients(
        args.input,
        args.output,
        args.ols_cache,
        args.pubchem_cache,
        ontologies
    )

    # Print summary
    print("\n" + "=" * 60)
    print("UNMAPPED INGREDIENTS MAPPING COMPLETE")
    print("=" * 60)
    print(f"Total ingredients:     {stats.total}")
    print(f"Skipped solutions:     {stats.skipped_solutions}")
    print(f"Buffer extractions:    {stats.buffer_extractions}")
    print(f"Names normalized:      {stats.normalized_count}")
    print()
    print("Classification (after skipping solutions):")
    print(f"  Biological:          {stats.biological}")
    print(f"  Chemical:            {stats.chemical}")
    print(f"  Processed:           {stats.biological + stats.chemical}")
    print()
    print("Mapping results:")
    print(f"  OLS mapped:          {stats.ols_mapped}")
    print(f"  PubChem mapped:      {stats.pubchem_mapped}")
    print(f"  Total mapped:        {stats.ols_mapped + stats.pubchem_mapped}")
    print(f"  Unmapped:            {stats.unmapped}")
    print()

    if stats.by_ontology:
        print("OLS mappings by ontology:")
        for ont, count in sorted(stats.by_ontology.items(), key=lambda x: -x[1]):
            print(f"  {ont.upper()}: {count}")
        print()

    processed = stats.biological + stats.chemical
    total_mapped = stats.ols_mapped + stats.pubchem_mapped
    success_rate = total_mapped / processed * 100 if processed > 0 else 0
    print(f"Success rate:          {success_rate:.1f}% (of processed)")
    print()
    print(f"Output:                {args.output}")
    print("=" * 60)


if __name__ == "__main__":
    main()
