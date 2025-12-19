#!/usr/bin/env python3
"""
FOODON Ontology Mapping via OAK (Ontology Access Kit)

Deterministically maps biological ingredients to FOODON IDs using OAK.
Provides full provenance and reproducible mappings.

Usage:
    python3 -m src.mapping.oak_foodon_mapper \
        --input compound_mappings_strict_final.tsv \
        --output foodon_mappings.tsv

Dependencies:
    - oaklib (pip install oaklib)
    - FOODON ontology (automatically downloaded by OAK)
"""

import argparse
import csv
import logging
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Biological ingredients that should map to FOODON
BIOLOGICAL_INGREDIENT_PATTERNS = [
    'extract', 'peptone', 'broth', 'tryptic', 'trypticase',
    'digest', 'liquor', 'casein', 'gelatin', 'phytone'
]

# Brand names to remove during normalization
BRAND_NAMES = [
    'Bacto', 'Difco', 'Oxoid', 'Lab-Lemco', 'Pennassay',
    'PPLO', 'G ', 'BD ', 'Mueller-Hinton', 'R2A', 'LB'
]

# Common synonyms for ingredient types
INGREDIENT_SYNONYMS = {
    'trypticase': ['tryptic digest', 'tryptic soy'],
    'polypeptone': ['peptone'],
    'phytone peptone': ['soy peptone'],
    'soy peptone': ['soya peptone', 'soja peptone'],
    'corn steep liquor': ['maize steep liquor', 'maize extract'],
}

def normalize_ingredient_name(name: str) -> str:
    """
    Normalize ingredient name for better FOODON matching.

    - Lowercase
    - Remove brand names
    - Remove parenthetical notes
    - Strip extra whitespace
    - Remove hyphens/underscores
    """
    normalized = name.lower()

    # Remove parenthetical content
    import re
    normalized = re.sub(r'\([^)]*\)', '', normalized)

    # Remove brand names (case-insensitive)
    for brand in BRAND_NAMES:
        normalized = normalized.replace(brand.lower(), '')

    # Remove common separators
    normalized = normalized.replace('-', ' ').replace('_', ' ')

    # Clean up whitespace
    normalized = ' '.join(normalized.split())

    return normalized.strip()

def generate_search_terms(ingredient: str) -> list:
    """
    Generate multiple search terms for an ingredient.

    Returns list of (term, strategy) tuples in priority order.
    """
    search_terms = []

    # Strategy 1: Exact original
    search_terms.append((ingredient, 'exact'))

    # Strategy 2: Lowercase exact
    search_terms.append((ingredient.lower(), 'lowercase'))

    # Strategy 3: Normalized (cleaned)
    normalized = normalize_ingredient_name(ingredient)
    if normalized != ingredient.lower():
        search_terms.append((normalized, 'normalized'))

    # Strategy 4: Try known synonyms
    for base_term, synonyms in INGREDIENT_SYNONYMS.items():
        if base_term in normalized:
            for synonym in synonyms:
                search_terms.append((synonym, f'synonym:{base_term}'))

    # Strategy 5: Base ingredient (remove qualifiers)
    # E.g., "Bacto beef extract" → "beef extract", "extract"
    words = normalized.split()
    if len(words) > 1:
        # Try last 2 words (e.g., "beef extract")
        if len(words) >= 2:
            search_terms.append((' '.join(words[-2:]), 'base_compound'))
        # Try last word only (e.g., "extract")
        if words[-1] in ['extract', 'peptone', 'broth', 'digest', 'liquor', 'casein']:
            search_terms.append((words[-1], 'generic'))

    # Remove duplicates while preserving order
    seen = set()
    unique_terms = []
    for term, strategy in search_terms:
        if term not in seen and term:
            seen.add(term)
            unique_terms.append((term, strategy))

    return unique_terms

def should_map_to_foodon(ingredient_name: str) -> bool:
    """Check if ingredient should be mapped to FOODON."""
    name_lower = ingredient_name.lower()

    # Check if it matches biological ingredient patterns
    if any(pattern in name_lower for pattern in BIOLOGICAL_INGREDIENT_PATTERNS):
        return True

    return False

def extract_biological_ingredients(input_file: Path) -> dict:
    """Extract unique biological ingredients from mapping file."""
    logger.info(f"Extracting biological ingredients from {input_file}")
    
    ingredients = defaultdict(lambda: {'count': 0, 'current_id': None})
    
    with open(input_file) as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            ingredient = row.get('original', '').strip()
            current_id = row.get('mapped', '').strip()
            
            if not ingredient:
                continue
                
            if should_map_to_foodon(ingredient):
                ingredients[ingredient]['count'] += 1
                if not ingredients[ingredient]['current_id']:
                    ingredients[ingredient]['current_id'] = current_id
    
    logger.info(f"Found {len(ingredients)} unique biological ingredients")
    return dict(ingredients)

def run_oak_search(term: str, ontology: str = "foodon") -> list:
    """
    Run OAK search for a term against FOODON ontology.
    
    Returns list of (id, label) tuples.
    """
    try:
        cmd = ['runoak', '-i', f'sqlite:obo:{ontology}', 'search', term]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            logger.warning(f"OAK search failed for '{term}': {result.stderr}")
            return []
        
        # Parse output: "FOODON:12345 ! label"
        matches = []
        for line in result.stdout.strip().split('\n'):
            if '!' in line:
                parts = line.split('!')
                onto_id = parts[0].strip()
                label = parts[1].strip()
                matches.append((onto_id, label))
        
        return matches
        
    except subprocess.TimeoutExpired:
        logger.error(f"OAK search timed out for '{term}'")
        return []
    except Exception as e:
        logger.error(f"Error running OAK search for '{term}': {e}")
        return []

def map_ingredients_to_foodon(ingredients: dict) -> dict:
    """Map ingredients to FOODON using OAK with enhanced search strategies."""
    logger.info(f"Mapping {len(ingredients)} ingredients to FOODON...")
    logger.info("Using multiple search strategies: exact, lowercase, normalized, synonyms, base compound")
    logger.info("Preserving existing FOODON/ENVO IDs from current_id field")

    mappings = {}
    preserved_count = 0
    newly_mapped_count = 0

    for i, (ingredient, info) in enumerate(ingredients.items(), 1):
        current_id = info.get('current_id', '')

        # Check if ingredient already has FOODON or ENVO ID - if yes, PRESERVE IT
        if current_id.startswith('FOODON:') or current_id.startswith('ENVO:'):
            logger.info(f"[{i}/{len(ingredients)}] {ingredient} - Preserving existing {current_id}")
            # Extract label if possible (not available in current_id, leave empty)
            mappings[ingredient] = {
                'foodon_id': current_id,
                'foodon_label': '',  # Not available from current_id
                'search_term': ingredient,
                'search_strategy': 'preserved',
                'match_type': 'preserved',
                'occurrences': info['count'],
                'current_id': current_id,
                'timestamp': datetime.now().isoformat(),
                'method': 'Preserved from current_id',
                'ontology_version': 'existing'
            }
            preserved_count += 1
            continue

        # No existing FOODON/ENVO ID - search for new mapping
        logger.info(f"[{i}/{len(ingredients)}] Searching FOODON for: {ingredient}")

        # Generate multiple search terms
        search_terms = generate_search_terms(ingredient)

        foodon_id = None
        foodon_label = None
        successful_term = None
        successful_strategy = None

        # Try each search term until we get a match
        for term, strategy in search_terms:
            logger.debug(f"  Trying '{term}' (strategy: {strategy})")
            matches = run_oak_search(term)

            if matches:
                # Take first (best) match
                foodon_id, foodon_label = matches[0]
                successful_term = term
                successful_strategy = strategy
                logger.info(f"  ✓ Mapped via '{term}' ({strategy}) → {foodon_id} ({foodon_label})")
                break

        if foodon_id:
            # Successful mapping
            mappings[ingredient] = {
                'foodon_id': foodon_id,
                'foodon_label': foodon_label,
                'search_term': successful_term,
                'search_strategy': successful_strategy,
                'match_type': 'exact' if successful_term.lower() == foodon_label.lower() else 'close',
                'occurrences': info['count'],
                'current_id': info['current_id'],
                'timestamp': datetime.now().isoformat(),
                'method': f'OAK search (strategy: {successful_strategy})',
                'ontology_version': 'sqlite:obo:foodon'
            }
            newly_mapped_count += 1
        else:
            # No match found with any strategy
            logger.warning(f"  ✗ No FOODON match for: {ingredient} (tried {len(search_terms)} strategies)")
            mappings[ingredient] = {
                'foodon_id': '',
                'foodon_label': '',
                'search_term': ingredient,
                'search_strategy': 'none',
                'match_type': 'none',
                'occurrences': info['count'],
                'current_id': info['current_id'],
                'timestamp': datetime.now().isoformat(),
                'method': f'OAK search (no match after {len(search_terms)} strategies)',
                'ontology_version': 'sqlite:obo:foodon'
            }

    logger.info(f"\nMapping results:")
    logger.info(f"  Preserved existing IDs: {preserved_count}")
    logger.info(f"  Newly mapped via OAK: {newly_mapped_count}")
    logger.info(f"  Unable to map: {len(ingredients) - preserved_count - newly_mapped_count}")

    return mappings

def save_mappings(mappings: dict, output_file: Path):
    """Save FOODON mappings to TSV with full provenance."""
    logger.info(f"Saving {len(mappings)} mappings to {output_file}")

    with open(output_file, 'w', newline='') as f:
        fieldnames = [
            'ingredient', 'foodon_id', 'foodon_label', 'search_term',
            'search_strategy', 'match_type', 'occurrences', 'current_id',
            'timestamp', 'method', 'ontology_version'
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter='\t')
        writer.writeheader()

        for ingredient in sorted(mappings.keys()):
            row = {'ingredient': ingredient}
            row.update(mappings[ingredient])
            writer.writerow(row)

    # Print summary
    total = len(mappings)
    matched = sum(1 for m in mappings.values() if m['foodon_id'])

    # Count by strategy
    strategy_counts = {}
    for m in mappings.values():
        if m['foodon_id']:
            strategy = m.get('search_strategy', 'unknown')
            strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1

    logger.info(f"\n=== FINAL SUMMARY ===")
    logger.info(f"  Total ingredients: {total}")
    logger.info(f"  With FOODON/ENVO IDs: {matched} ({matched/total*100:.1f}%)")
    logger.info(f"  Unmatched: {total - matched}")

    if strategy_counts:
        logger.info(f"\nIDs by source:")
        for strategy in sorted(strategy_counts.keys(), key=lambda x: strategy_counts[x], reverse=True):
            logger.info(f"  {strategy}: {strategy_counts[strategy]}")

def main():
    parser = argparse.ArgumentParser(
        description="Map biological ingredients to FOODON using OAK"
    )
    parser.add_argument(
        '--input',
        type=Path,
        required=True,
        help="Input compound mappings file (TSV)"
    )
    parser.add_argument(
        '--output',
        type=Path,
        required=True,
        help="Output FOODON mappings file (TSV)"
    )
    
    args = parser.parse_args()
    
    if not args.input.exists():
        logger.error(f"Input file not found: {args.input}")
        sys.exit(1)
    
    # Extract biological ingredients
    ingredients = extract_biological_ingredients(args.input)
    
    if not ingredients:
        logger.warning("No biological ingredients found to map")
        sys.exit(0)
    
    # Map to FOODON
    mappings = map_ingredients_to_foodon(ingredients)
    
    # Save results
    args.output.parent.mkdir(parents=True, exist_ok=True)
    save_mappings(mappings, args.output)
    
    logger.info("FOODON mapping complete!")

if __name__ == '__main__':
    main()
