#!/usr/bin/env python3
"""
Extract clean list of unmapped compounds from the pipeline.

Filters out PDF parsing artifacts, instructions, and noise to produce
a curated list of genuinely unmapped chemical compounds.
"""

import argparse
import re
import logging
from pathlib import Path
from typing import Dict, List, Set, Tuple
from collections import defaultdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Patterns that indicate parsing artifacts, not real compounds
NOISE_PATTERNS = [
    r'^solution\s*[→→]',  # solution expansion artifacts
    r'^\(',  # starts with parenthesis
    r'^\*',  # starts with asterisk
    r'^"',  # starts with quote
    r'^Add\b',  # instructions
    r'^After\b',  # instructions
    r'^Before\b',  # instructions
    r'^Autoclave',  # instructions
    r'^Combine',  # instructions
    r'^Dissolve',  # instructions
    r'^Filter',  # instructions
    r'^Make up',  # instructions
    r'^Mix\b',  # instructions
    r'^Pour\b',  # instructions
    r'^Prepare',  # instructions
    r'^Steril',  # instructions
    r'^Use\b',  # instructions
    r'^Cool\b',  # instructions
    r'^Heat\b',  # instructions
    r'^Adjust',  # instructions
    r'^Inoculate',  # instructions
    r'^Incubate',  # instructions
    r'^Alternatively',  # instructions
    r'^Continued',  # page artifacts
    r'^Note:',  # notes
    r'^See\b',  # references
    r'^Or\b',  # alternatives
    r'recipe',  # recipe references
    r'stock\s*\d',  # stock solution references
    r'see below',  # references
    r'see above',  # references
    r'see Medium',  # references
    r'overleaf',  # page references
    r'appropriate',  # conditionals
    r'if required',  # conditionals
    r'if necessary',  # conditionals
    r'if needed',  # conditionals
    r'optional',  # conditionals
    r'^\d+\s*(g|mg|ml|l|µ)',  # amounts without compound names
    r'^Amount',  # headers
    r'^Chemical$',  # headers
    r'^Appearance',  # descriptions
    r'^The\s+(medium|solution)',  # descriptions
    r'^A\s+rich',  # descriptions
    r'colour\s+indicates',  # descriptions
    r'should\s+be',  # descriptions
    r'may\s+be\s+used',  # suggestions
    r'plates.*BBL',  # product references
    r'Cultivation\s+of',  # methods
]

# Compile patterns for efficiency
NOISE_REGEX = [re.compile(p, re.IGNORECASE) for p in NOISE_PATTERNS]


def is_noise(compound: str) -> bool:
    """Check if a compound name is likely parsing noise."""
    compound = compound.strip()

    # Too short
    if len(compound) < 3:
        return True

    # Too long (likely a sentence)
    if len(compound) > 100:
        return True

    # Contains multiple sentences
    if compound.count('.') > 2:
        return True

    # Check against noise patterns
    for regex in NOISE_REGEX:
        if regex.search(compound):
            return True

    # Mostly numbers and punctuation
    alpha_count = sum(1 for c in compound if c.isalpha())
    if alpha_count < len(compound) * 0.3:
        return True

    return False


def is_likely_compound(compound: str) -> bool:
    """Check if a string is likely a real chemical compound name."""
    compound = compound.strip()

    # Chemical naming patterns
    chemical_patterns = [
        r'[A-Z][a-z]*\d*',  # Element-like (Na2, Ca, etc.)
        r'acid\b',
        r'ate\b',  # -ate suffix (sulfate, phosphate)
        r'ide\b',  # -ide suffix (chloride, oxide)
        r'ine\b',  # -ine suffix (glycine, alanine)
        r'ose\b',  # -ose suffix (glucose, fructose)
        r'ol\b',   # -ol suffix (ethanol, glycerol)
        r'ase\b',  # -ase suffix (enzymes)
        r'ium\b',  # -ium suffix (sodium, calcium)
        r'hydrate',
        r'anhydrous',
        r'chloride',
        r'sulfate',
        r'phosphate',
        r'nitrate',
        r'acetate',
        r'citrate',
        r'extract',
        r'peptone',
        r'tryptone',
        r'casein',
        r'yeast',
        r'agar',
    ]

    for pattern in chemical_patterns:
        if re.search(pattern, compound, re.IGNORECASE):
            return True

    # Starts with capital letter and is reasonably short
    if compound[0].isupper() and len(compound) < 50:
        return True

    return False


def extract_unmapped_compounds(
    low_confidence_file: Path,
    bacdive_file: Path,
    output_dir: Path
) -> Dict:
    """Extract clean unmapped compounds from pipeline outputs."""

    output_dir.mkdir(parents=True, exist_ok=True)

    stats = {
        'low_confidence_total': 0,
        'low_confidence_unmapped_raw': 0,
        'low_confidence_unmapped_clean': 0,
        'bacdive_total': 0,
        'bacdive_unmapped': 0,
        'combined_unique': 0,
    }

    unmapped_compounds: Dict[str, Dict] = {}  # compound -> {source, count}
    noise_examples: List[str] = []

    print("=" * 70)
    print("Extracting Clean Unmapped Compounds from Pipeline")
    print("=" * 70)

    # Process low confidence mappings
    if low_confidence_file.exists():
        print(f"\n1. Processing: {low_confidence_file}")

        with open(low_confidence_file, 'r', encoding='utf-8') as f:
            header = next(f).strip().split('\t')

            # Find column indices
            original_idx = header.index('original') if 'original' in header else 1
            status_idx = header.index('mapping_status') if 'mapping_status' in header else 17

            for line in f:
                stats['low_confidence_total'] += 1
                parts = line.strip().split('\t')

                if len(parts) > max(original_idx, status_idx):
                    compound = parts[original_idx]
                    status = parts[status_idx] if status_idx < len(parts) else ''

                    if status == 'unmapped':
                        stats['low_confidence_unmapped_raw'] += 1

                        if not is_noise(compound):
                            stats['low_confidence_unmapped_clean'] += 1
                            if compound not in unmapped_compounds:
                                unmapped_compounds[compound] = {
                                    'source': 'media_composition',
                                    'count': 1,
                                    'likely_compound': is_likely_compound(compound)
                                }
                            else:
                                unmapped_compounds[compound]['count'] += 1
                        else:
                            if len(noise_examples) < 20:
                                noise_examples.append(compound[:80])

        print(f"   Total rows: {stats['low_confidence_total']:,}")
        print(f"   Unmapped (raw): {stats['low_confidence_unmapped_raw']:,}")
        print(f"   Unmapped (clean): {stats['low_confidence_unmapped_clean']:,}")
        print(f"   Noise filtered: {stats['low_confidence_unmapped_raw'] - stats['low_confidence_unmapped_clean']:,}")

    # Process BacDive metabolites
    if bacdive_file.exists():
        print(f"\n2. Processing: {bacdive_file}")

        with open(bacdive_file, 'r', encoding='utf-8') as f:
            header = next(f).strip().split('\t')

            for line in f:
                stats['bacdive_total'] += 1
                parts = line.strip().split('\t')

                if len(parts) >= 4:
                    compound = parts[0]
                    match_type = parts[3] if len(parts) > 3 else ''
                    record_count = int(parts[5]) if len(parts) > 5 and parts[5].isdigit() else 1

                    if match_type == 'unmapped':
                        stats['bacdive_unmapped'] += 1

                        if compound not in unmapped_compounds:
                            unmapped_compounds[compound] = {
                                'source': 'bacdive_metabolites',
                                'count': record_count,
                                'likely_compound': True  # BacDive is curated
                            }
                        else:
                            unmapped_compounds[compound]['count'] += record_count
                            unmapped_compounds[compound]['source'] += ',bacdive_metabolites'

        print(f"   Total metabolites: {stats['bacdive_total']}")
        print(f"   Unmapped: {stats['bacdive_unmapped']}")

    # Separate likely compounds from uncertain
    likely_compounds = {k: v for k, v in unmapped_compounds.items() if v['likely_compound']}
    uncertain_compounds = {k: v for k, v in unmapped_compounds.items() if not v['likely_compound']}

    stats['combined_unique'] = len(unmapped_compounds)

    # Write outputs
    print(f"\n3. Writing output files to: {output_dir}")

    # Main unmapped compounds file (likely real compounds)
    main_output = output_dir / "unmapped_compounds.tsv"
    with open(main_output, 'w', encoding='utf-8') as f:
        f.write("compound\tsource\toccurrences\n")
        for compound in sorted(likely_compounds.keys()):
            info = likely_compounds[compound]
            f.write(f"{compound}\t{info['source']}\t{info['count']}\n")
    print(f"   Likely compounds: {main_output} ({len(likely_compounds)} entries)")

    # Uncertain compounds file
    uncertain_output = output_dir / "unmapped_uncertain.tsv"
    with open(uncertain_output, 'w', encoding='utf-8') as f:
        f.write("compound\tsource\toccurrences\n")
        for compound in sorted(uncertain_compounds.keys()):
            info = uncertain_compounds[compound]
            f.write(f"{compound}\t{info['source']}\t{info['count']}\n")
    print(f"   Uncertain entries: {uncertain_output} ({len(uncertain_compounds)} entries)")

    # Noise examples file (for debugging)
    noise_output = output_dir / "filtered_noise_examples.txt"
    with open(noise_output, 'w', encoding='utf-8') as f:
        f.write("# Examples of filtered noise (parsing artifacts)\n")
        for example in noise_examples:
            f.write(f"{example}\n")
    print(f"   Noise examples: {noise_output}")

    # Summary report
    summary_output = output_dir / "unmapped_summary.txt"
    with open(summary_output, 'w', encoding='utf-8') as f:
        f.write("# Unmapped Compounds Summary\n")
        f.write(f"# Generated by extract_unmapped_compounds.py\n\n")
        f.write(f"## Statistics\n")
        f.write(f"Low confidence file rows: {stats['low_confidence_total']:,}\n")
        f.write(f"Low confidence unmapped (raw): {stats['low_confidence_unmapped_raw']:,}\n")
        f.write(f"Low confidence unmapped (clean): {stats['low_confidence_unmapped_clean']:,}\n")
        f.write(f"BacDive metabolites total: {stats['bacdive_total']}\n")
        f.write(f"BacDive metabolites unmapped: {stats['bacdive_unmapped']}\n")
        f.write(f"\n## Final Counts\n")
        f.write(f"Likely compounds to map: {len(likely_compounds)}\n")
        f.write(f"Uncertain entries: {len(uncertain_compounds)}\n")
        f.write(f"\n## Top unmapped by occurrence\n")

        sorted_compounds = sorted(
            likely_compounds.items(),
            key=lambda x: x[1]['count'],
            reverse=True
        )
        for compound, info in sorted_compounds[:30]:
            f.write(f"{info['count']:6d}  {compound}\n")

    print(f"   Summary: {summary_output}")

    # Print summary
    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    print(f"Likely compounds needing mapping: {len(likely_compounds)}")
    print(f"Uncertain entries (review needed): {len(uncertain_compounds)}")
    print(f"\nTop 15 unmapped by occurrence:")

    sorted_compounds = sorted(
        likely_compounds.items(),
        key=lambda x: x[1]['count'],
        reverse=True
    )
    for compound, info in sorted_compounds[:15]:
        print(f"  {info['count']:6d}  {compound}")

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Extract clean unmapped compounds from pipeline"
    )
    parser.add_argument(
        "--low-confidence",
        type=Path,
        default=Path("pipeline_output/merge_mappings/low_confidence_compound_mappings.tsv"),
        help="Low confidence mappings TSV"
    )
    parser.add_argument(
        "--bacdive",
        type=Path,
        default=Path("pipeline_output/bacdive_metabolites/bacdive_metabolites_chebi_mappings_enhanced.tsv"),
        help="BacDive metabolites mappings TSV"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("pipeline_output/unmapped_analysis"),
        help="Output directory"
    )

    args = parser.parse_args()
    extract_unmapped_compounds(args.low_confidence, args.bacdive, args.output_dir)


if __name__ == "__main__":
    main()
