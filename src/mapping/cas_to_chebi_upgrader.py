#!/usr/bin/env python3
"""
CAS-RN to ChEBI Upgrader

Upgrades CAS-RN mappings to ChEBI where possible.
ChEBI entries often include CAS-RN cross-references, allowing us to
upgrade less semantic CAS-RN IDs to more useful ChEBI IDs.

Expected improvement: ~120 compounds (63% success rate)

DETERMINISM NOTES:
- Uses pinned ChEBI version from src/config/data_versions.py
- Validates ChEBI file MD5 checksum on load (optional)
- All lookups are from local files only (no API calls)

Strategy:
1. Load existing compound mappings
2. Identify compounds mapped to CAS-RN
3. Cross-reference CAS-RN with ChEBI database
4. Upgrade to ChEBI where available
5. Generate upgrade report
"""

import hashlib
import pandas as pd
import re
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)

# Import pinned data versions for validation
try:
    from ..config.data_versions import (
        CHEBI_NODES_FILE,
        CHEBI_NODES_MD5,
        CHEBI_VERSION,
    )
    HAS_VERSION_CONFIG = True
except ImportError:
    HAS_VERSION_CONFIG = False


class CAStoChEBIUpgrader:
    """
    Upgrades CAS-RN identifiers to ChEBI identifiers.

    Many compounds are initially mapped to CAS-RN IDs because those
    are widely available. However, ChEBI IDs are preferred for
    knowledge graph integration as they provide richer semantic information.

    DETERMINISM: Uses pinned ChEBI version and validates checksums.
    """

    def __init__(self, chebi_nodes_file: str, validate_checksum: bool = False):
        """
        Initialize the upgrader.

        Args:
            chebi_nodes_file: Path to ChEBI nodes TSV file
            validate_checksum: If True, validate ChEBI file against pinned MD5
        """
        self.chebi_nodes_file = chebi_nodes_file
        self.validate_checksum = validate_checksum
        self.chebi_data = None
        self.cas_to_chebi = {}

        self._load_chebi_data()
        self._build_cas_lookup()

    def _validate_chebi_version(self):
        """
        Validate ChEBI file against pinned version.

        DETERMINISM: Ensures consistent results by warning if ChEBI
        version differs from the pinned version used for development.
        """
        if not HAS_VERSION_CONFIG:
            logger.debug("Version config not available - skipping validation")
            return

        chebi_path = Path(self.chebi_nodes_file)

        # Check if it's the expected file
        if chebi_path.resolve() == CHEBI_NODES_FILE.resolve():
            logger.info(f"Using pinned ChEBI v{CHEBI_VERSION}")

            if self.validate_checksum:
                # Compute MD5 checksum
                actual_md5 = hashlib.md5(chebi_path.read_bytes()).hexdigest()
                if actual_md5 != CHEBI_NODES_MD5:
                    logger.warning(
                        f"ChEBI file checksum mismatch!\n"
                        f"  Expected: {CHEBI_NODES_MD5}\n"
                        f"  Actual:   {actual_md5}\n"
                        f"  Results may differ from pinned version."
                    )
                else:
                    logger.info("ChEBI checksum validated ✓")
        else:
            logger.info(f"Using custom ChEBI file: {self.chebi_nodes_file}")
            if HAS_VERSION_CONFIG:
                logger.info(f"(Pinned version: {CHEBI_NODES_FILE})")

    def _load_chebi_data(self):
        """Load ChEBI nodes database."""
        logger.info(f"Loading ChEBI data from {self.chebi_nodes_file}")

        # Validate version if configured
        self._validate_chebi_version()

        try:
            df = pd.read_csv(self.chebi_nodes_file, sep='\t', low_memory=False)

            # Filter for ChEBI entities
            self.chebi_data = df[df['id'].str.startswith('CHEBI:', na=False)]

            logger.info(f"Loaded {len(self.chebi_data)} ChEBI entities")

        except Exception as e:
            logger.error(f"Error loading ChEBI data: {e}")
            raise

    def _build_cas_lookup(self):
        """
        Build CAS-RN → ChEBI lookup dictionary.

        ChEBI nodes may have CAS-RN in:
        - 'provided_by' column (e.g., "CAS:50-00-0")
        - 'synonym' column (as one of the synonyms)
        - 'xref' column (cross-references)
        """
        logger.info("Building CAS-RN to ChEBI lookup...")

        for _, row in self.chebi_data.iterrows():
            chebi_id = row['id']
            cas_numbers = self._extract_cas_numbers(row)

            for cas_num in cas_numbers:
                # Store all ChEBI IDs for this CAS (some CAS may map to multiple ChEBI)
                if cas_num not in self.cas_to_chebi:
                    self.cas_to_chebi[cas_num] = []
                self.cas_to_chebi[cas_num].append(chebi_id)

        logger.info(f"Built CAS lookup with {len(self.cas_to_chebi)} CAS-RN numbers")

    def _extract_cas_numbers(self, row: pd.Series) -> List[str]:
        """
        Extract CAS-RN numbers from a ChEBI row.

        Args:
            row: ChEBI node row

        Returns:
            List of CAS-RN numbers
        """
        cas_numbers = []

        # Check 'provided_by' column
        provided_by = row.get('provided_by', '')
        if pd.notna(provided_by) and isinstance(provided_by, str):
            # Match CAS:NNNN-NN-N pattern
            matches = re.findall(r'CAS:(\d{2,7}-\d{2}-\d)', provided_by)
            cas_numbers.extend(matches)

        # Check 'xref' column (if exists)
        xref = row.get('xref', '')
        if pd.notna(xref) and isinstance(xref, str):
            # Match cas:NNNN-NN-N or CAS:NNNN-NN-N or CAS-RN:NNNN-NN-N pattern
            # ChEBI uses lowercase 'cas:' in xref column
            matches = re.findall(r'[Cc][Aa][Ss](?:-[Rr][Nn])?:(\d{2,7}-\d{2}-\d)', xref)
            cas_numbers.extend(matches)

        # Check synonyms (might contain CAS numbers)
        synonyms = row.get('synonym', '')
        if pd.notna(synonyms) and isinstance(synonyms, str):
            # Look for CAS-RN in synonyms (less common but possible)
            matches = re.findall(r'CAS(?:-RN)?:?\s*(\d{2,7}-\d{2}-\d)', synonyms)
            cas_numbers.extend(matches)

        return list(set(cas_numbers))  # Remove duplicates

    def upgrade_mapping_file(self, input_file: str, output_file: str) -> Dict[str, int]:
        """
        Upgrade CAS-RN mappings in a compound mapping file.

        Args:
            input_file: Input TSV file with compound mappings
            output_file: Output TSV file with upgraded mappings

        Returns:
            Dictionary with upgrade statistics
        """
        logger.info(f"Upgrading mappings from {input_file}")

        # Load mappings
        df = pd.read_csv(input_file, sep='\t', low_memory=False)

        # Statistics
        stats = {
            'total_entries': len(df),
            'cas_rn_entries': 0,
            'upgraded_to_chebi': 0,
            'multiple_chebi_found': 0,
            'no_chebi_found': 0
        }

        # Process each row
        upgraded_mappings = []

        for idx, row in df.iterrows():
            mapped_id = row.get('mapped', '')

            # Check if it's a CAS-RN mapping
            if pd.notna(mapped_id) and isinstance(mapped_id, str) and mapped_id.startswith('CAS-RN:'):
                stats['cas_rn_entries'] += 1

                # Extract CAS number
                cas_num = mapped_id.replace('CAS-RN:', '')

                # Try to upgrade
                chebi_ids = self.cas_to_chebi.get(cas_num, [])

                if len(chebi_ids) == 1:
                    # Single ChEBI found - upgrade!
                    df.at[idx, 'mapped'] = chebi_ids[0]
                    stats['upgraded_to_chebi'] += 1
                    upgraded_mappings.append((row['original'], cas_num, chebi_ids[0]))

                elif len(chebi_ids) > 1:
                    # Multiple ChEBI found - keep CAS-RN (ambiguous)
                    stats['multiple_chebi_found'] += 1
                    logger.debug(f"Multiple ChEBI for {row['original']} ({cas_num}): {chebi_ids}")

                else:
                    # No ChEBI found - keep CAS-RN
                    stats['no_chebi_found'] += 1

        # Save upgraded file
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, sep='\t', index=False)

        logger.info(f"Saved upgraded mappings to {output_path}")
        self._log_statistics(stats, upgraded_mappings)

        return stats

    def _log_statistics(self, stats: Dict[str, int], upgraded: List[Tuple[str, str, str]]):
        """Log upgrade statistics."""
        logger.info(f"""
╔════════════════════════════════════════════════════════════════════════╗
║                    CAS-RN TO CHEBI UPGRADE REPORT                       ║
╚════════════════════════════════════════════════════════════════════════╝

Total entries:           {stats['total_entries']:,}
CAS-RN entries:          {stats['cas_rn_entries']:,}

✓ Upgraded to ChEBI:     {stats['upgraded_to_chebi']:,} ({stats['upgraded_to_chebi']/stats['cas_rn_entries']*100 if stats['cas_rn_entries'] > 0 else 0:.1f}%)
⚠ Multiple ChEBI found:  {stats['multiple_chebi_found']:,} (kept as CAS-RN)
✗ No ChEBI found:        {stats['no_chebi_found']:,}
        """)

        if upgraded:
            logger.info("\nSample upgrades:")
            for i, (compound, cas, chebi) in enumerate(upgraded[:10], 1):
                logger.info(f"{i}. {compound}: {cas} → {chebi}")

            if len(upgraded) > 10:
                logger.info(f"... and {len(upgraded) - 10} more")

    def analyze_cas_coverage(self, mapping_file: str) -> Dict[str, any]:
        """
        Analyze CAS-RN coverage in a mapping file without modifying it.

        Args:
            mapping_file: Path to compound mapping TSV file

        Returns:
            Dictionary with analysis results
        """
        logger.info(f"Analyzing CAS-RN coverage in {mapping_file}")

        df = pd.read_csv(mapping_file, sep='\t', low_memory=False)

        # Extract all CAS-RN mappings
        cas_mask = df['mapped'].str.startswith('CAS-RN:', na=False)
        cas_entries = df[cas_mask]

        # Analyze upgrade potential
        upgradeable = 0
        multiple = 0
        not_found = 0

        for _, row in cas_entries.iterrows():
            cas_num = row['mapped'].replace('CAS-RN:', '')
            chebi_ids = self.cas_to_chebi.get(cas_num, [])

            if len(chebi_ids) == 1:
                upgradeable += 1
            elif len(chebi_ids) > 1:
                multiple += 1
            else:
                not_found += 1

        analysis = {
            'total_compounds': df['original'].nunique(),
            'cas_rn_entries': len(cas_entries),
            'cas_rn_unique': cas_entries['original'].nunique(),
            'upgradeable': upgradeable,
            'multiple_chebi': multiple,
            'no_chebi': not_found,
            'upgrade_rate': upgradeable / len(cas_entries) * 100 if len(cas_entries) > 0 else 0
        }

        logger.info(f"""
Analysis Results:
- Total unique compounds: {analysis['total_compounds']}
- CAS-RN entries: {analysis['cas_rn_entries']} ({analysis['cas_rn_unique']} unique)
- Upgradeable to ChEBI: {analysis['upgradeable']} ({analysis['upgrade_rate']:.1f}%)
- Ambiguous (multiple ChEBI): {analysis['multiple_chebi']}
- Not in ChEBI: {analysis['no_chebi']}
        """)

        return analysis


def main():
    """Main function for command-line execution."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Upgrade CAS-RN mappings to ChEBI",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--chebi-file',
        required=True,
        help='Path to ChEBI nodes TSV file'
    )
    parser.add_argument(
        '--input',
        required=True,
        help='Input compound mapping TSV file'
    )
    parser.add_argument(
        '--output',
        help='Output upgraded mapping TSV file (default: input_upgraded.tsv)'
    )
    parser.add_argument(
        '--analyze-only',
        action='store_true',
        help='Only analyze upgrade potential without modifying file'
    )

    args = parser.parse_args()

    # Set output file
    if not args.output:
        input_path = Path(args.input)
        args.output = str(input_path.parent / f"{input_path.stem}_upgraded{input_path.suffix}")

    # Initialize upgrader
    upgrader = CAStoChEBIUpgrader(args.chebi_file)

    if args.analyze_only:
        # Just analyze
        upgrader.analyze_cas_coverage(args.input)
    else:
        # Perform upgrade
        upgrader.upgrade_mapping_file(args.input, args.output)


if __name__ == "__main__":
    main()
