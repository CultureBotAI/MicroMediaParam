#!/usr/bin/env python3
"""
Merge verified compound mappings with remediated mappings.

Combines:
1. Original VALID mappings from validation
2. FIXED mappings from remediation
3. Creates final verified_compound_mappings.tsv
"""

import argparse
from datetime import datetime
from pathlib import Path
from typing import Dict, Set


def load_verified_mappings(filepath: Path) -> Dict[str, Dict]:
    """Load verified mappings from validation output."""
    mappings = {}

    with open(filepath, 'r', encoding='utf-8') as f:
        header = next(f).strip().split('\t')
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) >= 6:
                compound = parts[0].lower()
                mappings[compound] = {
                    'compound_name': parts[0],
                    'identifier': parts[1],
                    'id_type': parts[2],
                    'label': parts[3],
                    'verification_date': parts[4],
                    'source': parts[5]
                }

    return mappings


def load_remediated_mappings(filepath: Path) -> Dict[str, Dict]:
    """Load fixed mappings from remediation output."""
    mappings = {}

    with open(filepath, 'r', encoding='utf-8') as f:
        header = next(f).strip().split('\t')
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) >= 6 and parts[5] == 'FIXED':
                compound = parts[0].lower()
                mappings[compound] = {
                    'compound_name': parts[0],
                    'identifier': parts[2],  # new_chebi_id
                    'id_type': 'CHEBI',
                    'label': parts[3],  # chebi_label
                    'source': parts[4]  # source (e.g., pubchem_cid:XXX)
                }

    return mappings


def main():
    parser = argparse.ArgumentParser(
        description="Merge verified and remediated compound mappings"
    )
    parser.add_argument(
        "--verified",
        type=Path,
        default=Path("data/curated/verified_compound_mappings.tsv"),
        help="Path to verified mappings"
    )
    parser.add_argument(
        "--remediated",
        type=Path,
        default=Path("pipeline_output/validation/remediated_mappings.tsv"),
        help="Path to remediated mappings"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/curated/verified_compound_mappings.tsv"),
        help="Output path for merged mappings"
    )

    args = parser.parse_args()

    # Load existing verified mappings
    verified = load_verified_mappings(args.verified)
    print(f"Loaded {len(verified)} verified mappings")

    # Load remediated mappings
    remediated = load_remediated_mappings(args.remediated)
    print(f"Loaded {len(remediated)} remediated mappings")

    # Merge - remediated takes precedence
    merged = dict(verified)  # Start with verified
    today = datetime.now().strftime('%Y-%m-%d')

    added = 0
    for compound, data in remediated.items():
        if compound not in merged:
            merged[compound] = {
                **data,
                'verification_date': today
            }
            added += 1
        else:
            # Update existing with remediated data
            merged[compound].update({
                'identifier': data['identifier'],
                'id_type': data['id_type'],
                'label': data['label'],
                'verification_date': today,
                'source': data['source']
            })

    print(f"Added {added} new mappings from remediation")
    print(f"Total merged mappings: {len(merged)}")

    # Write output
    args.output.parent.mkdir(parents=True, exist_ok=True)

    with open(args.output, 'w', encoding='utf-8') as f:
        f.write("compound_name\tidentifier\tid_type\tlabel\tverification_date\tsource\n")
        for compound in sorted(merged.keys()):
            data = merged[compound]
            f.write(f"{data['compound_name']}\t{data['identifier']}\t{data['id_type']}\t{data['label']}\t{data['verification_date']}\t{data['source']}\n")

    print(f"Output written to: {args.output}")

    # Summary statistics
    id_types = {}
    for data in merged.values():
        id_type = data['id_type']
        id_types[id_type] = id_types.get(id_type, 0) + 1

    print("\nID type breakdown:")
    for id_type, count in sorted(id_types.items(), key=lambda x: -x[1]):
        print(f"  {id_type}: {count}")


if __name__ == "__main__":
    main()
