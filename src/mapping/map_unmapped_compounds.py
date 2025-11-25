#!/usr/bin/env python3
"""
Map unmapped compounds from pipeline analysis.

Handles:
1. Simple compounds that should have ChEBI (KH2PO4, Na-acetate)
2. Branded variants (Yeast extract (BD-Difco) → yeast extract)
3. Hydrated forms with variant notation (L-Cysteine·HCl·H2O)
4. Agar variants (Agar (Difco) → agar)

Note: Compound mappings are loaded from data/curated/verified_compound_mappings.tsv
which has been validated against official ChEBI/PubChem APIs.
"""

import argparse
import re
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class CompoundMapping:
    """Mapping result for a compound."""
    original: str
    normalized: str
    chebi_id: str
    chebi_label: str
    mapping_type: str
    confidence: str


# Default paths to mapping files
DEFAULT_VERIFIED_MAPPINGS_FILE = Path(__file__).parent.parent.parent / "data/curated/verified_compound_mappings.tsv"
DEFAULT_API_MAPPINGS_FILE = Path(__file__).parent.parent.parent / "data/curated/api_generated_mappings.tsv"

# Global variable to hold loaded mappings
_COMPOUND_MAPPINGS: Optional[Dict[str, Tuple[str, str]]] = None


def load_mappings_from_tsv(filepath: Path) -> Dict[str, Tuple[str, str]]:
    """
    Load compound mappings from a single TSV file.

    Expected columns: compound_name, identifier, id_type, label, ...
    (additional columns are ignored)

    Returns dict mapping compound_name -> (identifier, label)
    """
    mappings = {}

    if not filepath.exists():
        logger.debug(f"Mappings file not found: {filepath}")
        return mappings

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            header = next(f).strip().split('\t')
            for line in f:
                parts = line.strip().split('\t')
                if len(parts) >= 4:
                    compound_name = parts[0]
                    identifier = parts[1]
                    label = parts[3]
                    # Only add if identifier is present and not empty
                    if identifier and identifier.strip():
                        mappings[compound_name] = (identifier, label)

        logger.debug(f"Loaded {len(mappings)} mappings from {filepath}")
    except Exception as e:
        logger.error(f"Error loading mappings from {filepath}: {e}")

    return mappings


def load_verified_mappings(
    filepath: Optional[Path] = None,
    include_api_generated: bool = True
) -> Dict[str, Tuple[str, str]]:
    """
    Load verified compound mappings from TSV files.

    By default, loads both:
    - data/curated/verified_compound_mappings.tsv (manually verified)
    - data/curated/api_generated_mappings.tsv (deterministic API-generated)

    Args:
        filepath: Optional specific file to load (overrides default behavior)
        include_api_generated: Whether to include API-generated mappings

    Returns:
        dict mapping compound_name -> (identifier, label)
    """
    global _COMPOUND_MAPPINGS

    # Return cached mappings if available and using defaults
    if _COMPOUND_MAPPINGS is not None and filepath is None:
        return _COMPOUND_MAPPINGS

    mappings = {}

    if filepath is not None:
        # Load specific file only
        mappings = load_mappings_from_tsv(filepath)
    else:
        # Load verified mappings first (higher priority)
        if DEFAULT_VERIFIED_MAPPINGS_FILE.exists():
            verified = load_mappings_from_tsv(DEFAULT_VERIFIED_MAPPINGS_FILE)
            mappings.update(verified)
            logger.info(f"Loaded {len(verified)} verified mappings")

        # Then load API-generated mappings (fill in gaps)
        if include_api_generated and DEFAULT_API_MAPPINGS_FILE.exists():
            api_generated = load_mappings_from_tsv(DEFAULT_API_MAPPINGS_FILE)
            # Only add compounds not already in verified mappings
            new_count = 0
            for name, (identifier, label) in api_generated.items():
                if name not in mappings:
                    mappings[name] = (identifier, label)
                    new_count += 1
            logger.info(f"Loaded {new_count} additional API-generated mappings")

        if not mappings:
            logger.warning("No mappings files found. Run 'make api-mapping-full-pipeline' to generate.")

    # Cache if using default settings
    if filepath is None:
        _COMPOUND_MAPPINGS = mappings
        logger.info(f"Total compound mappings loaded: {len(mappings)}")

    return mappings


def get_compound_mappings() -> Dict[str, Tuple[str, str]]:
    """Get the compound mappings dictionary, loading if needed."""
    global _COMPOUND_MAPPINGS
    if _COMPOUND_MAPPINGS is None:
        _COMPOUND_MAPPINGS = load_verified_mappings()
    return _COMPOUND_MAPPINGS


# NOTE: The legacy SIMPLE_COMPOUND_MAPPINGS dictionary has been removed.
# All compound mappings are now loaded from curated TSV files:
# - data/curated/verified_compound_mappings.tsv (API-validated mappings)
# - data/curated/api_generated_mappings.tsv (deterministic API-generated)
#
# To generate new mappings, use:
#   python -m src.mapping.generate_compound_mappings \
#       --compounds-file <compounds.txt> \
#       --chebi-nodes <chebi_nodes.tsv> \
#       --output data/curated/api_generated_mappings.tsv
#
# This ensures all mappings are reproducible and deterministic.

# Additional patterns for hydrated compounds
HYDRATE_PATTERN = re.compile(r'^(.+?)\s*[·x]\s*(\d+)\s*H2O$', re.IGNORECASE)

# Brand patterns to strip from compound names
BRAND_PATTERNS = [
    r'\s*\(BD[- ]?Difco[^)]*\)',
    r'\s*\(BD[- ]?BBL[^)]*\)',
    r'\s*\(BD[- ]?BACTO[^)]*\)',
    r'\s*\(Difco[^)]*\)',
    r'\s*\(DIFCO[^)]*\)',
    r'\s*\(Oxoid[^)]*\)',
    r'\s*\(OXOID[^)]*\)',
    r'\s*\(Bacto[^)]*\)',
    r'\s*\(BD Bacto[^)]*\)',
    r'\s*\(BD[^)]*\)',
    r'\s*\(BBL[^)]*\)',
    r'\s*\(Merck[^)]*\)',
    r'\s*\(Sigma[^)]*\)',
    r'\s*\(SIGMA[^)]*\)',
    r'\s*\(Fluka[^)]*\)',
    r'\s*\(Roth[^)]*\)',
    r'\s*\(Wako[^)]*\)',
    r'\s*\(Nissui[^)]*\)',
    r'\s*\(Sheffield[^)]*\)',
    r'\s*\(FUJIFILM[^)]*\)',
    r'\s*\(Fisher[^)]*\)',
    r'\s*\(Nihon[^)]*\)',
    r'\s*\(Biowest[^)]*\)',
    r'\s*\(GIBCO[^)]*\)',
    r'\s*\(for solid media\)',
    r'\s*\(if appropriate\)',
    r'\s*\(if necessary\)',
    r'\s*\(if needed\)',
    r'\s*\(if required\)',
    r'\s*\(optional\)',
    r'\s*\(pancreatic digest[^)]*\)',
    r'\s*\(tryptic digest[^)]*\)',
    r'\s*\(enzymatic digest[^)]*\)',
    r'\s*\(pepsin-digested[^)]*\)',
    r',\s*Noble',
    r',\s*tryptic digest',
    r',\s*if\s+.*$',
    # Remove "must not..." type phrases
    r',\s*must not[^)]*\)',
]

# Compile brand patterns
BRAND_REGEX = [re.compile(p, re.IGNORECASE) for p in BRAND_PATTERNS]


def normalize_compound_name(name: str) -> str:
    """Normalize compound name by removing brands and standardizing."""
    normalized = name.strip()

    # Remove brand suffixes
    for regex in BRAND_REGEX:
        normalized = regex.sub('', normalized)

    # Standardize common variations
    normalized = normalized.strip()

    # Handle "Na-" prefix variations
    normalized = re.sub(r'^Na[\s-]+', 'Na-', normalized)

    # Standardize hydration notation
    normalized = re.sub(r'·(\d+)\s*H2O', r' x \1 H2O', normalized)
    normalized = re.sub(r'\.(\d+)\s*H2O', r' x \1 H2O', normalized)

    return normalized


def extract_base_compound(name: str) -> Optional[str]:
    """Extract base compound from concentration/solution strings."""

    # Pattern 0: Handle "X solution" where X is compound (ending with "solution" attached or separate)
    # e.g., "1 M MgSO4solution" → "MgSO4"
    # e.g., "5% Na2S·9H2O solution" → "Na2S·9H2O"
    attached_solution = re.match(
        r'^(.+?)solution\s*$',
        name, re.IGNORECASE
    )
    if attached_solution:
        result = attached_solution.group(1).strip()
        # Try to extract compound from concentration prefix
        conc_match = re.match(
            r'^[\d.]+\s*(?:[mM]|%|N|mM|g/?(?:100\s*)?m?l)\s*(?:\([wv/]+\))?\s*(.+)$',
            result, re.IGNORECASE
        )
        if conc_match:
            return conc_match.group(1).strip().rstrip('*')
        # Or just return the result if it looks like a compound
        if result and len(result) > 2 and not result[0].isdigit():
            return result.rstrip('*')

    # Pattern 1: Extract compound before "buffer" or "solution"
    # e.g., "Sodium Potassium phosphate buffer" → "Sodium Potassium phosphate"
    # e.g., "Sodium dithionite solution (100 mg/L)*" → "Sodium dithionite"
    buffer_solution_match = re.match(
        r'^(.+?)\s+(?:buffer|solution)\b',
        name, re.IGNORECASE
    )
    if buffer_solution_match:
        result = buffer_solution_match.group(1).strip()
        # Remove trailing concentration info
        result = re.sub(r'\s*\([^)]*\)\s*$', '', result)
        result = result.rstrip('*')
        if result and len(result) > 2:
            return result

    # Pattern 2: Concentration + compound + "solution" (with or without space)
    # e.g., "0.01 M FeSO4·5H2Osolution" → "FeSO4·5H2O"
    # e.g., "0.1 M KH2PO4solution" → "KH2PO4"
    # e.g., "5% Na2S·9H2O solution" → "Na2S·9H2O"
    conc_solution_patterns = [
        r'^[\d.]+\s*[mM]\s+(.+?)(?:solution|\s+solution)',
        r'^[\d.]+\s*%\s*(?:\([wv/]+\))?\s*(.+?)(?:solution|\s+solution)',
        r'^[\d.]+\s*N\s+(.+?)(?:solution|\s+solution)',
        r'^[\d.]+\s*m[Mm]\s+(.+?)(?:solution|\s+solution)',
        r'^[\d.]+\s*g/?(?:100\s*)?m?[lL]\s+(.+?)(?:solution|\s+solution)',
        # Pattern with parenthetical pH: "0.5 M Crotonic acid (pH 7.0)"
        r'^[\d.]+\s*[mM]\s+(.+?)\s*\(pH\s*[\d.]+\)\s*$',
    ]

    for pattern in conc_solution_patterns:
        match = re.match(pattern, name, re.IGNORECASE)
        if match:
            result = match.group(1).strip()
            result = result.rstrip('*')
            # Remove trailing parenthetical info like "(in 0.02 N HCl)"
            result = re.sub(r'\s*\(in\s+[^)]+\)\s*$', '', result)
            result = re.sub(r'\s*\(pH\s+[^)]+\)\s*$', '', result)
            result = re.sub(r'\s*\(freshly[^)]*\)\s*$', '', result)
            if result and len(result) > 1:
                return result

    # Pattern 3: Simple concentration patterns
    patterns = [
        r'^[\d.]+\s*[mM]\s+(.+?)(?:\s*$)',
        r'^[\d.]+\s*%\s*(?:\([wv/]+\))?\s*(.+?)(?:\s*$)',
        r'^[\d.]+\s*N\s+(.+?)$',
        r'^[\d.]+\s*m[Mm]\s+(.+?)$',
    ]

    for pattern in patterns:
        match = re.match(pattern, name, re.IGNORECASE)
        if match:
            result = match.group(1).strip()
            result = result.rstrip('*')
            # Clean up parenthetical suffixes
            result = re.sub(r'\s*\([^)]*\)\s*$', '', result)
            if result and len(result) > 1:
                return result

    return None


def extract_compound_variations(name: str) -> List[str]:
    """Generate variations of compound name to try for matching."""
    variations = [name]
    cleaned = name.strip()

    # Pattern: Remove percentage in parentheses
    # e.g., "HCl (25%)" → "HCl", "HCl (25%, v/v)" → "HCl"
    pct_removed = re.sub(r'\s*\(\d+\.?\d*%[^)]*\)\s*$', '', cleaned)
    if pct_removed != cleaned:
        variations.append(pct_removed.strip())

    # Pattern: Remove "(anhydrous)" or similar parenthetical descriptors
    # e.g., "MgCl2 (anhydrous)" → "MgCl2"
    desc_removed = re.sub(r'\s*\((?:anhydrous|hydrate|pure|analytical)[^)]*\)\s*$', '', cleaned, flags=re.IGNORECASE)
    if desc_removed != cleaned:
        variations.append(desc_removed.strip())

    # Pattern: Extract up to first open parenthesis (fallback)
    # e.g., "Fe(NH4)2(SO4)2 x 7 H2O (0.1% w/v)" - need to be careful with chemical formulas
    # Only apply if parenthesis contains non-chemical info (%, w/v, etc.)
    paren_match = re.match(r'^(.+?)\s+\([^()]*(?:%|w/v|v/v|pH|mg|ml|freshly)[^()]*\)\s*$', cleaned, re.IGNORECASE)
    if paren_match:
        variations.append(paren_match.group(1).strip())

    # Pattern: Remove trailing asterisks and whitespace
    if cleaned.endswith('*'):
        variations.append(cleaned.rstrip('*').strip())

    return list(dict.fromkeys(variations))  # Remove duplicates while preserving order


def parse_hydrate(name: str) -> Optional[Tuple[str, int]]:
    """Parse hydrate notation and return (base_compound, water_molecules)."""
    # Various hydrate patterns
    hydrate_patterns = [
        # "CoCl2·6H2O" or "CoCl2·6 H2O"
        (r'^(.+?)\s*[·.]\s*(\d+)\s*H2O\s*$', lambda m: (m.group(1), int(m.group(2)))),
        # "CoCl2 x 6H2O" or "CoCl2 x 6 H2O"
        (r'^(.+?)\s*x\s*(\d+)\s*H2O\s*$', lambda m: (m.group(1), int(m.group(2)))),
        # "CaCl2 x H2O" (single water)
        (r'^(.+?)\s*x\s*H2O\s*$', lambda m: (m.group(1), 1)),
        # "CaCl2·H2O" (single water)
        (r'^(.+?)\s*[·.]\s*H2O\s*$', lambda m: (m.group(1), 1)),
        # "Thiamine·HCl·2H2O" - compound with HCl then hydrate
        (r'^(.+?[·.]HCl)\s*[·.]\s*(\d+)\s*H2O\s*$', lambda m: (m.group(1), int(m.group(2)))),
        # "CaCl 2 x 2 H2O" - malformed but common
        (r'^(.+?)\s+x\s+(\d+)\s+H2O\s*$', lambda m: (m.group(1), int(m.group(2)))),
    ]

    for pattern, extractor in hydrate_patterns:
        match = re.match(pattern, name, re.IGNORECASE)
        if match:
            base, waters = extractor(match)
            return (base.strip(), waters)

    return None


def try_lookup(name: str, mapping_type: str, confidence: str, original: str) -> Optional[CompoundMapping]:
    """Try to look up a compound name in the mappings dictionary.

    Uses verified compound mappings loaded from TSV files (verified and API-generated).
    All mappings are deterministic and reproducible.
    """
    # Get verified mappings (loaded from TSV)
    verified_mappings = get_compound_mappings()

    # Try exact match first (preferred - these are API-validated)
    if name in verified_mappings:
        chebi_id, chebi_label = verified_mappings[name]
        return CompoundMapping(
            original=original,
            normalized=name,
            chebi_id=chebi_id,
            chebi_label=chebi_label,
            mapping_type=mapping_type + '_verified',
            confidence=confidence
        )

    # Case-insensitive lookup in verified mappings
    name_lower = name.lower()
    for key, (chebi_id, chebi_label) in verified_mappings.items():
        if key.lower() == name_lower:
            return CompoundMapping(
                original=original,
                normalized=key,
                chebi_id=chebi_id,
                chebi_label=chebi_label,
                mapping_type=mapping_type + '_verified_case',
                confidence=confidence
            )

    return None


def map_compound(name: str) -> Optional[CompoundMapping]:
    """Try to map a compound to ChEBI."""

    # First try direct lookup
    result = try_lookup(name, 'direct', 'high', name)
    if result:
        return result

    # Normalize (remove brands) and try again
    normalized = normalize_compound_name(name)
    if normalized != name:
        result = try_lookup(normalized, 'normalized', 'high', name)
        if result:
            return result

    # Try variations (percentage removal, parenthetical removal, etc.)
    for variation in extract_compound_variations(name):
        if variation != name:
            result = try_lookup(variation, 'variation', 'high', name)
            if result:
                return result
            # Also try normalized version
            var_normalized = normalize_compound_name(variation)
            if var_normalized != variation:
                result = try_lookup(var_normalized, 'variation_norm', 'high', name)
                if result:
                    return result

    # Try extracting base compound from concentration/solution strings
    base = extract_base_compound(name)
    if base:
        result = try_lookup(base, 'extracted_base', 'medium', name)
        if result:
            return result

        # Also try normalized version of extracted base
        base_normalized = normalize_compound_name(base)
        if base_normalized != base:
            result = try_lookup(base_normalized, 'extracted_normalized', 'medium', name)
            if result:
                return result

        # Try hydrate parsing on extracted base
        hydrate_info = parse_hydrate(base)
        if hydrate_info:
            hydrate_base, _ = hydrate_info
            result = try_lookup(hydrate_base, 'extracted_hydrate', 'medium', name)
            if result:
                return result

    # Try extracting base from normalized name
    base = extract_base_compound(normalized)
    if base:
        result = try_lookup(base, 'norm_extracted', 'medium', name)
        if result:
            return result

    # Try hydrate pattern matching on original and normalized
    for test_name in [name, normalized]:
        hydrate_info = parse_hydrate(test_name)
        if hydrate_info:
            hydrate_base, _ = hydrate_info
            result = try_lookup(hydrate_base, 'hydrate_base', 'medium', name)
            if result:
                return result
            # Also try normalized hydrate base
            hydrate_base_norm = normalize_compound_name(hydrate_base)
            if hydrate_base_norm != hydrate_base:
                result = try_lookup(hydrate_base_norm, 'hydrate_norm', 'medium', name)
                if result:
                    return result

    # Try stripping percentage/concentration prefix
    stripped = re.sub(r'^\d+\.?\d*\s*%\s*', '', name)
    if stripped != name:
        result = try_lookup(stripped, 'stripped_pct', 'medium', name)
        if result:
            return result
        stripped_norm = normalize_compound_name(stripped)
        if stripped_norm != stripped:
            result = try_lookup(stripped_norm, 'stripped_norm', 'medium', name)
            if result:
                return result
        # Try variations on stripped
        for variation in extract_compound_variations(stripped):
            result = try_lookup(variation, 'stripped_var', 'medium', name)
            if result:
                return result

    # Fallback: try extracting up to parenthesis containing non-chemical info
    paren_match = re.match(r'^([A-Za-z][A-Za-z0-9·.x\s]+?)\s*\([^()]*(?:%|w/v|v/v|anhydrous|pH)[^()]*\)', name, re.IGNORECASE)
    if paren_match:
        fallback = paren_match.group(1).strip()
        result = try_lookup(fallback, 'paren_fallback', 'low', name)
        if result:
            return result

    return None


def process_unmapped_compounds(
    input_file: Path,
    output_file: Path
) -> Dict:
    """Process unmapped compounds and create mappings."""

    stats = {
        'total': 0,
        'mapped': 0,
        'unmapped': 0,
        'by_type': {}
    }

    mappings: List[CompoundMapping] = []
    still_unmapped: List[Tuple[str, int]] = []

    print("=" * 70)
    print("Mapping Unmapped Compounds")
    print("=" * 70)

    with open(input_file, 'r', encoding='utf-8') as f:
        header = next(f)
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) >= 3:
                compound = parts[0]
                occurrences = int(parts[2]) if parts[2].isdigit() else 1
                stats['total'] += 1

                result = map_compound(compound)
                if result:
                    mappings.append(result)
                    stats['mapped'] += 1
                    stats['by_type'][result.mapping_type] = stats['by_type'].get(result.mapping_type, 0) + 1
                else:
                    still_unmapped.append((compound, occurrences))
                    stats['unmapped'] += 1

    # Write mappings
    print(f"\nWriting mappings to: {output_file}")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("original\tnormalized\tchebi_id\tchebi_label\tmapping_type\tconfidence\n")
        for m in mappings:
            f.write(f"{m.original}\t{m.normalized}\t{m.chebi_id}\t{m.chebi_label}\t{m.mapping_type}\t{m.confidence}\n")

    # Write still unmapped
    still_unmapped_file = output_file.parent / "still_unmapped.tsv"
    print(f"Writing still unmapped to: {still_unmapped_file}")
    with open(still_unmapped_file, 'w', encoding='utf-8') as f:
        f.write("compound\toccurrences\n")
        for compound, occurrences in sorted(still_unmapped, key=lambda x: -x[1]):
            f.write(f"{compound}\t{occurrences}\n")

    # Print summary
    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    print(f"Total compounds processed: {stats['total']}")
    print(f"Successfully mapped: {stats['mapped']} ({stats['mapped']/stats['total']*100:.1f}%)")
    print(f"Still unmapped: {stats['unmapped']} ({stats['unmapped']/stats['total']*100:.1f}%)")

    print(f"\nMappings by type:")
    for mtype, count in sorted(stats['by_type'].items(), key=lambda x: -x[1]):
        print(f"  {mtype}: {count}")

    print(f"\nTop 20 still unmapped by occurrence:")
    for compound, occurrences in sorted(still_unmapped, key=lambda x: -x[1])[:20]:
        print(f"  {occurrences:6d}  {compound[:60]}")

    return stats


def main():
    parser = argparse.ArgumentParser(description="Map unmapped compounds to ChEBI")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("pipeline_output/unmapped_analysis/unmapped_compounds.tsv"),
        help="Input unmapped compounds TSV"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("pipeline_output/unmapped_analysis/new_mappings.tsv"),
        help="Output mappings TSV"
    )

    args = parser.parse_args()
    process_unmapped_compounds(args.input, args.output)


if __name__ == "__main__":
    main()
