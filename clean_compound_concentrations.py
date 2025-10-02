#!/usr/bin/env python3
"""Remove concentration prefixes from compound names in mapping file."""

import pandas as pd
import re
from pathlib import Path

def strip_concentration_prefix(name: str) -> str:
    """Remove concentration/quantity prefixes from compound names."""
    if not isinstance(name, str):
        return name

    # Remove concentration patterns at the start:
    # - Percentages: 0.2%, 5%, etc.
    # - Molarities: 1 M, 0.5 M, etc.
    # - Weights: 1 g, 100 mg, etc.
    patterns = [
        r'^\d+\.?\d*\s*%\s+',           # "0.2% " or "5% "
        r'^\d+\.?\d*\s+[mM]\s+',        # "1 M " or "0.5 m "
        r'^\d+\.?\d*\s*[Gg]\s+',        # "1g " or "100 g "
        r'^\d+\.?\d*\s*[Mm][Gg]\s+',    # "100mg " or "50 mg "
        r'^[Gg]\s+',                     # "G " prefix
    ]

    cleaned = name
    for pattern in patterns:
        cleaned = re.sub(pattern, '', cleaned)

    return cleaned.strip()

def main():
    input_file = Path("pipeline_output/merge_mappings/compound_id_mappings.tsv")

    # Load the mapping file
    df = pd.read_csv(input_file, sep='\t')

    print(f"Loaded {len(df)} compound mappings")

    # Track changes
    changed = []

    # Clean the 'original' column
    for idx, row in df.iterrows():
        original = row['original']
        cleaned = strip_concentration_prefix(original)

        if cleaned != original:
            changed.append((original, cleaned))
            df.at[idx, 'original'] = cleaned

    print(f"\nCleaned {len(changed)} compound names:")
    for old, new in sorted(changed):
        print(f"  {old} → {new}")

    # Remove duplicates based on cleaned names
    df_unique = df.drop_duplicates(subset=['original'], keep='first')

    duplicates_removed = len(df) - len(df_unique)
    if duplicates_removed > 0:
        print(f"\nRemoved {duplicates_removed} duplicate rows after cleaning")

    # Sort by compound name
    df_unique = df_unique.sort_values('original')

    # Save the cleaned file
    df_unique.to_csv(input_file, sep='\t', index=False)

    print(f"\nSaved {len(df_unique)} unique compounds to {input_file}")

if __name__ == "__main__":
    main()
