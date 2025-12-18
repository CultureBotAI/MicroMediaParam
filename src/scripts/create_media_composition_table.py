#!/usr/bin/env python3
"""
Create Media Composition Table with Normalized Concentrations.

Generates a clean TSV table with media compositions and normalized
concentrations in g/mL (assuming 1000 mL total volume).

Output columns:
- medium_id: Media identifier
- ingredient_name: Original ingredient name
- ingredient_label: ChEBI/ontology label
- ingredient_id: ChEBI/CAS/KEGG ID
- formula: Chemical formula
- raw_concentration: Original value + unit string
- concentration_g_ml: Normalized to g/mL

Usage:
    python -m src.scripts.create_media_composition_table \\
        --input pipeline_output/merge_mappings/compound_mappings_strict_final.tsv \\
        --output pipeline_output/media_summary/media_composition_table.tsv
"""

import argparse
import logging
import re
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Unit conversion factors to g/mL (assuming 1000 mL total volume)
# For mass units: divide by 1000 mL to get g/mL
# For concentration units: already per liter, divide by 1000 to get per mL
UNIT_CONVERSIONS = {
    # Mass units (assuming 1000 mL total volume)
    'g': 1.0 / 1000,           # g -> g/mL: divide by 1000 mL
    'mg': 1.0 / 1_000_000,     # mg -> g/mL: mg/1000 -> g/1000/1000
    'µg': 1.0 / 1_000_000_000, # µg -> g/mL
    'ug': 1.0 / 1_000_000_000, # ug -> g/mL (alternate)
    'mcg': 1.0 / 1_000_000_000, # mcg -> g/mL (alternate)
    'ng': 1.0 / 1_000_000_000_000, # ng -> g/mL
    'kg': 1.0,                  # kg -> g/mL: 1000g/1000mL

    # Volume units (assuming density ~1 g/mL)
    'ml': 1.0 / 1000,          # mL -> g/mL (density ~1)
    'l': 1.0,                   # L -> g/mL (density ~1)
    'µl': 1.0 / 1_000_000,     # µL -> g/mL
    'ul': 1.0 / 1_000_000,     # uL -> g/mL (alternate)

    # Concentration units (already per liter)
    'g/l': 1.0 / 1000,         # g/L -> g/mL
    'mg/l': 1.0 / 1_000_000,   # mg/L -> g/mL
    'µg/l': 1.0 / 1_000_000_000, # µg/L -> g/mL
    'ug/l': 1.0 / 1_000_000_000, # ug/L -> g/mL
    'mcg/l': 1.0 / 1_000_000_000, # mcg/L -> g/mL
    'ng/l': 1.0 / 1_000_000_000_000, # ng/L -> g/mL
    'g/ml': 1.0,               # g/mL -> g/mL (no conversion)
    'mg/ml': 1.0 / 1000,       # mg/mL -> g/mL

    # Molar units - cannot convert without molecular weight
    'mol/l': None,
    'm': None,                  # Molar
    'mm': None,                 # Millimolar
    'µm': None,                 # Micromolar
    'um': None,                 # Micromolar (alternate)
    'nm': None,                 # Nanomolar
    'mmol/l': None,
    'µmol/l': None,
    'umol/l': None,

    # Percentage units
    '%': 10.0,                  # % (w/v) -> g/mL: 1% = 1g/100mL = 0.01g/mL * 1000 = 10
    '% (w/v)': 10.0,
    '% (v/v)': 10.0,           # Assume density ~1
    'vol%': 10.0,
    'wt%': 10.0,
}


def normalize_unit(unit: str) -> str:
    """Normalize unit string for lookup."""
    if not unit or pd.isna(unit):
        return ''

    unit = str(unit).strip().lower()
    # Remove spaces
    unit = unit.replace(' ', '')
    # Common substitutions
    unit = unit.replace('μ', 'µ')  # Greek mu to micro symbol
    unit = unit.replace('micro', 'µ')
    unit = unit.replace('milli', 'm')
    return unit


def convert_to_g_ml(value: float, unit: str) -> Tuple[Optional[float], str]:
    """
    Convert concentration value to g/mL.

    Args:
        value: Numeric concentration value
        unit: Unit string

    Returns:
        Tuple of (converted_value, status) where status is 'converted',
        'no_conversion', or 'unknown_unit'
    """
    if pd.isna(value) or value == '':
        return None, 'no_value'

    try:
        value = float(value)
    except (ValueError, TypeError):
        return None, 'invalid_value'

    norm_unit = normalize_unit(unit)

    if not norm_unit:
        return None, 'no_unit'

    # Look up conversion factor
    factor = UNIT_CONVERSIONS.get(norm_unit)

    if factor is None:
        # Check if it's a molar unit (cannot convert)
        if any(x in norm_unit for x in ['mol', 'molar']):
            return None, 'molar_unit'
        return None, 'unknown_unit'

    return value * factor, 'converted'


def create_composition_table(input_file: str, output_file: str) -> dict:
    """
    Create media composition table with normalized concentrations.

    Args:
        input_file: Path to compound_mappings_strict_final.tsv
        output_file: Path to output file

    Returns:
        Statistics dictionary
    """
    logger.info(f"Reading input file: {input_file}")
    df = pd.read_csv(input_file, sep='\t', low_memory=False)
    logger.info(f"Loaded {len(df)} rows")

    # Statistics
    stats = {
        'total_rows': len(df),
        'converted': 0,
        'no_value': 0,
        'no_unit': 0,
        'molar_unit': 0,
        'unknown_unit': 0,
        'invalid_value': 0,
    }

    # Track unknown units
    unknown_units = {}

    # Create output rows
    output_rows = []

    for _, row in df.iterrows():
        medium_id = row.get('medium_id', '')
        ingredient_name = row.get('original', '')
        ingredient_label = row.get('chebi_label', '')
        ingredient_id = row.get('mapped', '')
        formula = row.get('chebi_formula', '')
        value = row.get('value', '')
        unit = row.get('unit', '')

        # Create raw concentration string
        if pd.notna(value) and value != '':
            if pd.notna(unit) and unit != '':
                raw_concentration = f"{value} {unit}"
            else:
                raw_concentration = str(value)
        else:
            raw_concentration = ''

        # Convert to g/mL
        concentration_g_ml, status = convert_to_g_ml(value, unit)

        stats[status] = stats.get(status, 0) + 1

        if status == 'unknown_unit':
            norm_unit = normalize_unit(unit)
            unknown_units[norm_unit] = unknown_units.get(norm_unit, 0) + 1

        # Format concentration
        if concentration_g_ml is not None:
            # Use scientific notation for very small values
            if concentration_g_ml < 0.000001:
                conc_str = f"{concentration_g_ml:.2e}"
            else:
                conc_str = f"{concentration_g_ml:.9g}"
        else:
            conc_str = ''

        output_rows.append({
            'medium_id': medium_id if pd.notna(medium_id) else '',
            'ingredient_name': ingredient_name if pd.notna(ingredient_name) else '',
            'ingredient_label': ingredient_label if pd.notna(ingredient_label) else '',
            'ingredient_id': ingredient_id if pd.notna(ingredient_id) else '',
            'formula': formula if pd.notna(formula) else '',
            'raw_concentration': raw_concentration,
            'concentration_g_ml': conc_str,
        })

    # Create output DataFrame
    output_df = pd.DataFrame(output_rows)

    # Sort by medium_id, then ingredient_name
    output_df = output_df.sort_values(['medium_id', 'ingredient_name']).reset_index(drop=True)

    # Save output
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_df.to_csv(output_path, sep='\t', index=False)

    logger.info(f"Saved {len(output_df)} rows to {output_file}")

    # Print report
    print("\n" + "=" * 70)
    print("MEDIA COMPOSITION TABLE REPORT")
    print("=" * 70)
    print(f"\nTotal rows processed:      {stats['total_rows']:,}")
    print(f"\nConversion Results:")
    print(f"  Successfully converted:  {stats['converted']:,}")
    print(f"  No value:                {stats['no_value']:,}")
    print(f"  No unit:                 {stats['no_unit']:,}")
    print(f"  Molar units (skipped):   {stats['molar_unit']:,}")
    print(f"  Unknown units:           {stats['unknown_unit']:,}")
    print(f"  Invalid values:          {stats.get('invalid_value', 0):,}")

    if unknown_units:
        print(f"\nUnknown units encountered:")
        for unit, count in sorted(unknown_units.items(), key=lambda x: -x[1])[:10]:
            print(f"  '{unit}': {count}")

    if stats['converted'] > 0:
        conversion_rate = stats['converted'] / stats['total_rows'] * 100
        print(f"\nConversion rate: {conversion_rate:.1f}%")

    print("=" * 70)

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Create media composition table with normalized concentrations",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--input', '-i',
        required=True,
        help='Input compound mappings TSV file'
    )
    parser.add_argument(
        '--output', '-o',
        required=True,
        help='Output media composition table TSV file'
    )

    args = parser.parse_args()

    create_composition_table(args.input, args.output)


if __name__ == '__main__':
    main()
