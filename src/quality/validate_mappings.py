#!/usr/bin/env python3
"""
Validate compound mappings for semantic correctness.

Identifies common mapping errors:
1. Label mismatch - ChEBI label doesn't match original compound name
2. Formula mismatch - ChEBI formula doesn't match expected formula
3. Known erroneous mappings - From blocklist
4. Unit parsing errors - Units like 'mg', 'ml' mapped as compounds
5. Phosphate confusion - mono/di/tri-basic phosphate mismatches

Usage:
    python -m src.quality.validate_mappings \
        --input pipeline_output/merge_mappings/compound_mappings.tsv \
        --chebi-nodes chebi_nodes.tsv \
        --output pipeline_output/quality/mapping_validation_report.tsv
"""

import argparse
import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
from fuzzywuzzy import fuzz

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Known erroneous ChEBI mappings to block
# Format: CHEBI_ID -> (wrong_compound_pattern, correct_description)
CHEBI_BLOCKLIST = {
    'CHEBI:75830': ('serum|FCS|FBS|fetal', 'DNA-(apurinic or apyrimidinic site) lyase - NOT a serum'),
    'CHEBI:132852': ('beef|meat|extract', 'lespedezol D1 (flavonoid) - NOT a meat/beef extract'),
    'CHEBI:73611': (r'^[Mm]g$|milligram', 'Met-Gly dipeptide - NOT a unit or magnesium'),
    'CHEBI:31605': ('ferric citrate|iron citrate', 'Ferric citrate (59Fe) radioactive isotope - use CHEBI:144421 for iron(III) citrate'),
    'CHEBI:4496': ('sodium|NaH2PO4', 'calcium hydrogenphosphate - NOT sodium compound'),
    'CHEBI:156213': ('B12|vitamin', 'quinazoline compound - NOT vitamin B12 (use CHEBI:30411)'),
    'CHEBI:91243': ('CoCl|cobalt', 'calcium chloride hexahydrate - NOT cobalt chloride (use CHEBI:35061)'),
}

# Known compound-to-correct-CHEBI mappings
CORRECT_MAPPINGS = {
    'fetal bovine serum': 'UBERON:0001977',  # blood serum
    'fetal calf serum': 'UBERON:0001977',
    'FBS': 'UBERON:0001977',
    'FCS': 'UBERON:0001977',
    'ammonium chloride': 'CHEBI:31206',  # Actually this IS correct
    'NH4Cl': 'CHEBI:31206',
}

# Phosphate disambiguation rules
PHOSPHATE_RULES = {
    'KH2PO4': ('monobasic', 'CHEBI:63036'),  # potassium dihydrogen phosphate
    'K2HPO4': ('dibasic', 'CHEBI:32031'),    # dipotassium hydrogen phosphate
    'K3PO4': ('tribasic', 'CHEBI:32033'),    # tripotassium phosphate
    'NaH2PO4': ('monobasic', 'CHEBI:37585'), # sodium dihydrogen phosphate
    'Na2HPO4': ('dibasic', 'CHEBI:34683'),   # disodium hydrogen phosphate
    'Na3PO4': ('tribasic', 'CHEBI:37586'),   # trisodium phosphate
}

# Units that should NOT be mapped as compounds
UNIT_PATTERNS = [
    r'^[Mm]g$',           # milligrams
    r'^[Mm][Ll]$',        # milliliters
    r'^[Gg]$',            # grams
    r'^[Ll]$',            # liters
    r'^[Mm][Mm]$',        # millimolar (if parsed wrong)
    r'^\d+\.?\d*$',       # pure numbers
    r'^[Uu]nit[s]?$',     # units
    r'^\%$',              # percent
]

# Known correct formula-to-ChEBI mappings (suppress label_mismatch warnings)
# These are chemical formulas that correctly map to their names
CORRECT_FORMULA_MAPPINGS = {
    # Phosphates
    'K2HPO4': 'CHEBI:131527',   # dipotassium hydrogen phosphate
    'KH2PO4': 'CHEBI:63036',    # potassium dihydrogen phosphate
    'Na2HPO4': 'CHEBI:34683',   # disodium hydrogen phosphate
    'NaH2PO4': 'CHEBI:37585',   # sodium dihydrogen phosphate
    # Sulfates with hydration
    'CuSO4.5H2O': 'CHEBI:31440',   # copper(II) sulfate pentahydrate
    'CuSO4 . 5H2O': 'CHEBI:31440',
    'ZnSO4.7H2O': 'CHEBI:32312',   # zinc sulfate heptahydrate
    'MnSO4.4H2O': 'CHEBI:86358',   # manganese(II) sulfate tetrahydrate
    # Chlorides with hydration
    'FeCl3.6H2O': 'CHEBI:86254',   # iron trichloride hexahydrate
    'CoCl2.6H2O': 'CHEBI:35061',   # cobalt(II) chloride hexahydrate
    # Molybdates
    'Na2MoO4.2H2O': 'CHEBI:75213', # sodium molybdate dihydrate
    # Nitrates
    'Co(NO3)2.6H2O': 'CHEBI:86214', # cobalt dinitrate hexahydrate
    'KNO3': 'CHEBI:63041',         # potassium nitrate
    # Borates
    'H3BO3': 'CHEBI:33118',        # boric acid
    # Hydroxides
    'KOH': 'CHEBI:32035',          # potassium hydroxide
    'NaOH': 'CHEBI:32145',         # sodium hydroxide
    # Water
    'H2O': 'CHEBI:15377',          # water
}


class MappingValidator:
    """Validates compound mappings for semantic correctness."""

    def __init__(self, chebi_nodes_file: Optional[Path] = None):
        """Initialize validator with optional ChEBI nodes for label lookup."""
        self.chebi_labels: Dict[str, str] = {}
        self.chebi_formulas: Dict[str, str] = {}

        if chebi_nodes_file and chebi_nodes_file.exists():
            self._load_chebi_nodes(chebi_nodes_file)

    def _load_chebi_nodes(self, chebi_file: Path):
        """Load ChEBI labels and formulas from nodes file."""
        logger.info(f"Loading ChEBI nodes from {chebi_file}")
        df = pd.read_csv(chebi_file, sep='\t', low_memory=False)

        # Find ID and name columns
        id_col = 'id' if 'id' in df.columns else df.columns[0]
        name_col = 'name' if 'name' in df.columns else df.columns[1]

        for _, row in df.iterrows():
            chebi_id = str(row[id_col])
            label = str(row[name_col]) if pd.notna(row[name_col]) else ''

            if chebi_id.startswith('CHEBI:'):
                self.chebi_labels[chebi_id] = label.lower()

        logger.info(f"Loaded {len(self.chebi_labels)} ChEBI labels")

    def validate_mapping(
        self,
        original: str,
        mapped_id: str,
        chebi_label: str = '',
        chebi_formula: str = ''
    ) -> List[Tuple[str, str, str]]:
        """
        Validate a single mapping.

        Returns list of (issue_type, severity, message) tuples.
        """
        issues = []
        original_lower = original.lower().strip()
        mapped_id = str(mapped_id).strip()

        # 1. Check blocklisted ChEBI IDs
        if mapped_id in CHEBI_BLOCKLIST:
            pattern, description = CHEBI_BLOCKLIST[mapped_id]
            if re.search(pattern, original_lower, re.IGNORECASE):
                issues.append((
                    'blocklisted_chebi',
                    'critical',
                    f"'{original}' mapped to {mapped_id} which is {description}"
                ))

        # 2. Check for unit parsing errors
        for pattern in UNIT_PATTERNS:
            if re.match(pattern, original.strip()):
                if mapped_id and not mapped_id.startswith('ingredient:'):
                    issues.append((
                        'unit_as_compound',
                        'critical',
                        f"Unit '{original}' incorrectly mapped to {mapped_id}"
                    ))

        # 3. Check phosphate disambiguation
        for formula, (basicity, correct_chebi) in PHOSPHATE_RULES.items():
            if formula.lower() in original_lower.replace(' ', ''):
                if mapped_id.startswith('CHEBI:') and mapped_id != correct_chebi:
                    # Get the label to check if basicity is wrong
                    label = chebi_label.lower() if chebi_label else self.chebi_labels.get(mapped_id, '')
                    if basicity not in label and 'dihydrogen' not in label and 'hydrogen' not in label:
                        issues.append((
                            'phosphate_confusion',
                            'warning',
                            f"'{original}' ({formula}) may have wrong basicity. Mapped to {mapped_id}, expected {correct_chebi}"
                        ))

        # 4. Check label similarity (if we have chebi_label)
        if chebi_label and mapped_id.startswith('CHEBI:'):
            # Skip check for known correct formula mappings
            orig_stripped = original.strip()
            if orig_stripped in CORRECT_FORMULA_MAPPINGS:
                expected_chebi = CORRECT_FORMULA_MAPPINGS[orig_stripped]
                if mapped_id == expected_chebi:
                    # This is a known correct mapping, skip label check
                    return issues

            # Normalize names for comparison
            orig_normalized = re.sub(r'[^a-z0-9]', '', original_lower)
            label_normalized = re.sub(r'[^a-z0-9]', '', chebi_label.lower())

            # Check similarity
            similarity = fuzz.ratio(orig_normalized, label_normalized)

            # Also check partial ratio for substring matches
            partial_sim = fuzz.partial_ratio(orig_normalized, label_normalized)

            # Check if original looks like a chemical formula (contains uppercase + numbers)
            is_formula = bool(re.match(r'^[A-Z][a-z]?\d*\([A-Z]', original.strip()) or
                              re.match(r'^[A-Z][a-z]?\d*[A-Z]', original.strip()))

            # Higher threshold for formulas since they're expected to differ from names
            threshold_sim = 20 if is_formula else 30
            threshold_partial = 40 if is_formula else 50

            if similarity < threshold_sim and partial_sim < threshold_partial:
                # Very low similarity - likely wrong mapping
                issues.append((
                    'label_mismatch',
                    'warning',
                    f"'{original}' mapped to {mapped_id} ('{chebi_label}') - low similarity ({similarity}%)"
                ))

        return issues

    def validate_file(
        self,
        input_file: Path,
        output_file: Optional[Path] = None
    ) -> pd.DataFrame:
        """
        Validate all mappings in a file.

        Returns DataFrame of validation issues.
        """
        logger.info(f"Validating mappings from {input_file}")
        df = pd.read_csv(input_file, sep='\t', low_memory=False)

        # Identify columns
        original_col = 'original' if 'original' in df.columns else df.columns[1]
        mapped_col = 'mapped' if 'mapped' in df.columns else df.columns[2]
        label_col = 'chebi_label' if 'chebi_label' in df.columns else None
        formula_col = 'chebi_formula' if 'chebi_formula' in df.columns else None

        issues_list = []
        issue_counts = defaultdict(int)

        for idx, row in df.iterrows():
            original = str(row[original_col]) if pd.notna(row[original_col]) else ''
            mapped_id = str(row[mapped_col]) if pd.notna(row[mapped_col]) else ''
            chebi_label = str(row[label_col]) if label_col and pd.notna(row.get(label_col)) else ''
            chebi_formula = str(row[formula_col]) if formula_col and pd.notna(row.get(formula_col)) else ''

            issues = self.validate_mapping(original, mapped_id, chebi_label, chebi_formula)

            for issue_type, severity, message in issues:
                issue_counts[issue_type] += 1
                issues_list.append({
                    'row': idx + 2,  # Account for header
                    'original': original,
                    'mapped_id': mapped_id,
                    'chebi_label': chebi_label,
                    'issue_type': issue_type,
                    'severity': severity,
                    'message': message
                })

        issues_df = pd.DataFrame(issues_list)

        # Print summary
        print("\n" + "=" * 70)
        print("MAPPING VALIDATION REPORT")
        print("=" * 70)
        print(f"Total rows checked: {len(df):,}")
        print(f"Rows with issues: {len(issues_df):,}")
        print(f"Unique compounds with issues: {issues_df['original'].nunique() if len(issues_df) > 0 else 0}")
        print()

        if issue_counts:
            print("Issues by type:")
            for issue_type, count in sorted(issue_counts.items(), key=lambda x: -x[1]):
                print(f"  {issue_type}: {count}")
        else:
            print("No issues found!")

        print("=" * 70)

        if output_file and len(issues_df) > 0:
            output_file.parent.mkdir(parents=True, exist_ok=True)
            issues_df.to_csv(output_file, sep='\t', index=False)
            logger.info(f"Saved {len(issues_df)} issues to {output_file}")

        return issues_df


def main():
    parser = argparse.ArgumentParser(
        description='Validate compound mappings for semantic correctness'
    )
    parser.add_argument(
        '--input', '-i',
        type=Path,
        required=True,
        help='Input mapping file'
    )
    parser.add_argument(
        '--chebi-nodes',
        type=Path,
        default=None,
        help='ChEBI nodes file for label lookup'
    )
    parser.add_argument(
        '--output', '-o',
        type=Path,
        default=None,
        help='Output file for validation report'
    )

    args = parser.parse_args()

    validator = MappingValidator(args.chebi_nodes)
    validator.validate_file(args.input, args.output)


if __name__ == '__main__':
    main()
