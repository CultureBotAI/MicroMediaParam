#!/usr/bin/env python3
"""
Validate compound mappings against official chemical databases.

Validates identifiers against their authoritative sources:
- ChEBI IDs: EBI ChEBI web service
- PubChem CIDs: PubChem REST API
- CAS-RN: PubChem lookup (CAS numbers are indexed)
- UBERON IDs: Skip (anatomical terms, different validation)

Preference order for identifiers: ChEBI > PubChem > CAS-RN > Other
"""

import argparse
import json
import logging
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from xml.etree import ElementTree

import requests

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# API endpoints
# Using OLS4 API for ChEBI (the old ChEBI web service is unreliable)
OLS_API_BASE = "https://www.ebi.ac.uk/ols4/api"
PUBCHEM_API_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"

# Rate limiting
REQUEST_DELAY = 0.3  # seconds between requests


@dataclass
class ValidationResult:
    """Result of validating a single compound mapping."""
    compound_name: str
    identifier: str
    id_type: str  # CHEBI, PUBCHEM, CAS, UBERON, OTHER
    expected_label: str
    actual_label: Optional[str]
    status: str  # VALID, MISMATCH, NOT_FOUND, ERROR, SKIPPED
    message: str = ""
    synonyms: List[str] = field(default_factory=list)


def detect_id_type(identifier: str) -> str:
    """Detect the type of identifier."""
    if identifier.startswith("CHEBI:"):
        return "CHEBI"
    elif identifier.startswith("UBERON:"):
        return "UBERON"
    elif identifier.startswith("PUBCHEM:") or identifier.startswith("CID:"):
        return "PUBCHEM"
    elif re.match(r'^\d{2,7}-\d{2}-\d$', identifier):
        # CAS Registry Number format: XX-XX-X to XXXXXXX-XX-X
        return "CAS"
    elif identifier.isdigit() and len(identifier) > 3:
        # Likely a PubChem CID without prefix
        return "PUBCHEM"
    else:
        return "OTHER"


def validate_chebi_id(chebi_id: str) -> Tuple[Optional[str], List[str]]:
    """
    Validate ChEBI ID against EBI OLS4 API.
    Returns (primary_name, synonyms) or (None, []) if not found.
    """
    if not chebi_id.startswith("CHEBI:"):
        chebi_id = f"CHEBI:{chebi_id}"

    # Use OLS4 API endpoint
    url = f"{OLS_API_BASE}/ontologies/chebi/terms"
    params = {"obo_id": chebi_id}

    try:
        response = requests.get(url, params=params, timeout=30)

        if response.status_code == 200:
            data = response.json()
            terms = data.get('_embedded', {}).get('terms', [])

            if terms:
                term = terms[0]
                primary_name = term.get('label', '')
                synonyms = [s.lower() for s in term.get('synonyms', [])]
                return primary_name, synonyms

    except (requests.RequestException, json.JSONDecodeError) as e:
        logger.warning(f"ChEBI OLS API error for {chebi_id}: {e}")

    return None, []


def validate_pubchem_cid(cid: str) -> Tuple[Optional[str], List[str]]:
    """
    Validate PubChem CID against official PubChem API.
    Returns (primary_name, synonyms) or (None, []) if not found.
    """
    # Extract numeric CID
    cid_num = re.sub(r'^(PUBCHEM:|CID:)', '', cid)

    url = f"{PUBCHEM_API_BASE}/compound/cid/{cid_num}/property/IUPACName,Title/JSON"

    try:
        response = requests.get(url, timeout=30)

        if response.status_code == 200:
            data = response.json()
            props = data.get('PropertyTable', {}).get('Properties', [{}])[0]
            title = props.get('Title', '')
            iupac = props.get('IUPACName', '')

            # Get synonyms
            syn_url = f"{PUBCHEM_API_BASE}/compound/cid/{cid_num}/synonyms/JSON"
            syn_response = requests.get(syn_url, timeout=30)
            synonyms = []
            if syn_response.status_code == 200:
                syn_data = syn_response.json()
                syns = syn_data.get('InformationList', {}).get('Information', [{}])[0]
                synonyms = [s.lower() for s in syns.get('Synonym', [])[:50]]

            return title or iupac, synonyms

    except (requests.RequestException, json.JSONDecodeError) as e:
        logger.warning(f"PubChem API error for {cid}: {e}")

    return None, []


def validate_cas_number(cas: str) -> Tuple[Optional[str], List[str], Optional[str]]:
    """
    Validate CAS Registry Number via PubChem lookup.
    Returns (primary_name, synonyms, pubchem_cid) or (None, [], None) if not found.
    """
    url = f"{PUBCHEM_API_BASE}/compound/name/{cas}/property/IUPACName,Title/JSON"

    try:
        response = requests.get(url, timeout=30)

        if response.status_code == 200:
            data = response.json()
            props = data.get('PropertyTable', {}).get('Properties', [{}])[0]
            title = props.get('Title', '')
            cid = props.get('CID')

            # Get synonyms
            if cid:
                syn_url = f"{PUBCHEM_API_BASE}/compound/cid/{cid}/synonyms/JSON"
                syn_response = requests.get(syn_url, timeout=30)
                synonyms = []
                if syn_response.status_code == 200:
                    syn_data = syn_response.json()
                    syns = syn_data.get('InformationList', {}).get('Information', [{}])[0]
                    synonyms = [s.lower() for s in syns.get('Synonym', [])[:50]]

                return title, synonyms, f"PUBCHEM:{cid}"

    except (requests.RequestException, json.JSONDecodeError) as e:
        logger.warning(f"CAS lookup error for {cas}: {e}")

    return None, [], None


def normalize_label(s: str) -> str:
    """Normalize label for comparison."""
    s = s.lower()
    s = re.sub(r'[\(\)\[\]\-,·]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def labels_match(expected: str, actual: str, synonyms: List[str]) -> Tuple[bool, str]:
    """
    Check if expected label matches actual label or synonyms.
    Returns (match, reason).
    """
    expected_norm = normalize_label(expected)
    actual_norm = normalize_label(actual)

    # Direct match
    if expected_norm == actual_norm:
        return True, "Label matches primary name"

    # Check synonyms
    if expected_norm in [normalize_label(s) for s in synonyms]:
        return True, f"Label matches synonym (primary: {actual})"

    # Check if expected is substring of actual or vice versa
    if expected_norm in actual_norm or actual_norm in expected_norm:
        return True, "Label partially matches"

    return False, f"Expected '{expected}', got '{actual}'"


def validate_mapping(
    compound_name: str,
    identifier: str,
    expected_label: str,
    api_cache: Dict
) -> ValidationResult:
    """Validate a single compound mapping."""

    id_type = detect_id_type(identifier)

    # Skip UBERON (anatomical terms)
    if id_type == "UBERON":
        return ValidationResult(
            compound_name=compound_name,
            identifier=identifier,
            id_type=id_type,
            expected_label=expected_label,
            actual_label=None,
            status="SKIPPED",
            message="UBERON IDs validated separately"
        )

    # Check cache
    if identifier in api_cache:
        actual_label, synonyms = api_cache[identifier]
    else:
        # Query appropriate API
        if id_type == "CHEBI":
            actual_label, synonyms = validate_chebi_id(identifier)
        elif id_type == "PUBCHEM":
            actual_label, synonyms = validate_pubchem_cid(identifier)
        elif id_type == "CAS":
            actual_label, synonyms, _ = validate_cas_number(identifier)
        else:
            return ValidationResult(
                compound_name=compound_name,
                identifier=identifier,
                id_type=id_type,
                expected_label=expected_label,
                actual_label=None,
                status="SKIPPED",
                message=f"Unknown identifier type: {id_type}"
            )

        api_cache[identifier] = (actual_label, synonyms)
        time.sleep(REQUEST_DELAY)

    if actual_label is None:
        return ValidationResult(
            compound_name=compound_name,
            identifier=identifier,
            id_type=id_type,
            expected_label=expected_label,
            actual_label=None,
            synonyms=[],
            status="NOT_FOUND",
            message=f"{id_type} ID {identifier} not found in database"
        )

    # Check label match
    match, reason = labels_match(expected_label, actual_label, synonyms)

    return ValidationResult(
        compound_name=compound_name,
        identifier=identifier,
        id_type=id_type,
        expected_label=expected_label,
        actual_label=actual_label,
        synonyms=synonyms,
        status="VALID" if match else "MISMATCH",
        message=reason
    )


def extract_mappings_from_script(script_path: Path) -> List[Tuple[str, str, str]]:
    """
    Extract compound mappings from map_unmapped_compounds.py.
    Returns list of (compound_name, identifier, label) tuples.
    """
    mappings = []

    with open(script_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Pattern: 'compound name': ('IDENTIFIER', 'label'),
    pattern = r"'([^']+)':\s*\('([^']+)',\s*'([^']+)'\)"

    for match in re.finditer(pattern, content):
        compound_name = match.group(1)
        identifier = match.group(2)
        label = match.group(3)
        mappings.append((compound_name, identifier, label))

    logger.info(f"Found {len(mappings)} mappings in script")

    # Count by type
    type_counts = {}
    for _, identifier, _ in mappings:
        id_type = detect_id_type(identifier)
        type_counts[id_type] = type_counts.get(id_type, 0) + 1

    for id_type, count in sorted(type_counts.items()):
        logger.info(f"  {id_type}: {count}")

    return mappings


def load_mappings_from_tsv(tsv_path: Path) -> List[Tuple[str, str, str]]:
    """Load mappings from TSV file."""
    mappings = []

    with open(tsv_path, 'r', encoding='utf-8') as f:
        header = next(f)
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) >= 3:
                compound_name = parts[0]
                identifier = parts[1]
                label = parts[2]
                mappings.append((compound_name, identifier, label))

    return mappings


def validate_all_mappings(
    mappings: List[Tuple[str, str, str]],
    sample_size: Optional[int] = None
) -> List[ValidationResult]:
    """Validate all mappings against appropriate APIs."""

    if sample_size:
        import random
        mappings = random.sample(mappings, min(sample_size, len(mappings)))

    results = []
    total = len(mappings)
    api_cache = {}

    logger.info(f"Validating {total} mappings...")

    for i, (compound_name, identifier, label) in enumerate(mappings):
        if (i + 1) % 50 == 0:
            logger.info(f"Progress: {i + 1}/{total} ({100*(i+1)//total}%)")

        result = validate_mapping(compound_name, identifier, label, api_cache)
        results.append(result)

    return results


def write_validation_report(results: List[ValidationResult], output_path: Path):
    """Write validation results to TSV file."""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("compound_name\tidentifier\tid_type\texpected_label\tactual_label\tstatus\tmessage\n")

        for r in results:
            f.write(f"{r.compound_name}\t{r.identifier}\t{r.id_type}\t{r.expected_label}\t")
            f.write(f"{r.actual_label or 'N/A'}\t{r.status}\t{r.message}\n")

    logger.info(f"Validation report written to: {output_path}")


def write_verified_mappings(results: List[ValidationResult], output_path: Path):
    """Write only verified (VALID) mappings to TSV file."""

    valid_results = [r for r in results if r.status == "VALID"]

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("compound_name\tidentifier\tid_type\tlabel\tverification_date\tsource\n")

        verification_date = datetime.now().strftime("%Y-%m-%d")

        for r in valid_results:
            label = r.actual_label if r.actual_label else r.expected_label
            source = f"{r.id_type} API validation"
            f.write(f"{r.compound_name}\t{r.identifier}\t{r.id_type}\t{label}\t")
            f.write(f"{verification_date}\t{source}\n")

    logger.info(f"Verified mappings written to: {output_path}")
    logger.info(f"Total verified: {len(valid_results)}")


def print_summary(results: List[ValidationResult]):
    """Print summary of validation results."""

    valid = [r for r in results if r.status == "VALID"]
    mismatch = [r for r in results if r.status == "MISMATCH"]
    not_found = [r for r in results if r.status == "NOT_FOUND"]
    skipped = [r for r in results if r.status == "SKIPPED"]
    errors = [r for r in results if r.status == "ERROR"]

    total_checked = len(results) - len(skipped)

    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    print(f"Total mappings: {len(results)}")
    print(f"  Checked:    {total_checked}")
    print(f"  Skipped:    {len(skipped)} (UBERON/other)")
    print()
    if total_checked > 0:
        print(f"Results (of {total_checked} checked):")
        print(f"  ✓ Valid:      {len(valid)} ({100*len(valid)//total_checked}%)")
        print(f"  ⚠ Mismatch:   {len(mismatch)} ({100*len(mismatch)//total_checked}%)")
        print(f"  ✗ Not found:  {len(not_found)} ({100*len(not_found)//total_checked}%)")
    print("=" * 60)

    # By ID type
    print("\nBy identifier type:")
    for id_type in ["CHEBI", "PUBCHEM", "CAS", "UBERON", "OTHER"]:
        type_results = [r for r in results if r.id_type == id_type]
        if type_results:
            type_valid = len([r for r in type_results if r.status == "VALID"])
            type_total = len([r for r in type_results if r.status != "SKIPPED"])
            if type_total > 0:
                print(f"  {id_type}: {type_valid}/{type_total} valid")

    if mismatch:
        print("\nLabel mismatches (ID exists but label differs):")
        for r in mismatch[:10]:
            print(f"  {r.identifier}: expected '{r.expected_label}', got '{r.actual_label}'")
        if len(mismatch) > 10:
            print(f"  ... and {len(mismatch) - 10} more")

    if not_found:
        print("\nNot found in database:")
        for r in not_found[:10]:
            print(f"  {r.identifier}: {r.compound_name}")
        if len(not_found) > 10:
            print(f"  ... and {len(not_found) - 10} more")


def main():
    parser = argparse.ArgumentParser(
        description="Validate compound mappings against official chemical databases"
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="Input file (TSV or Python script)"
    )
    parser.add_argument(
        "--output-report",
        type=Path,
        default=Path("validation_report.tsv"),
        help="Output validation report TSV"
    )
    parser.add_argument(
        "--output-verified",
        type=Path,
        help="Output verified mappings TSV (only VALID entries)"
    )
    parser.add_argument(
        "--sample",
        type=int,
        help="Validate only N random mappings (for testing)"
    )
    parser.add_argument(
        "--from-script",
        action="store_true",
        help="Extract mappings from map_unmapped_compounds.py"
    )

    args = parser.parse_args()

    # Determine input source
    if args.from_script or (args.input and args.input.suffix == '.py'):
        script_path = args.input or Path("src/mapping/map_unmapped_compounds.py")
        if not script_path.exists():
            logger.error(f"Script not found: {script_path}")
            sys.exit(1)
        mappings = extract_mappings_from_script(script_path)
    elif args.input and args.input.suffix == '.tsv':
        mappings = load_mappings_from_tsv(args.input)
    else:
        script_path = Path("src/mapping/map_unmapped_compounds.py")
        if not script_path.exists():
            logger.error("No input specified and default script not found")
            sys.exit(1)
        mappings = extract_mappings_from_script(script_path)

    if not mappings:
        logger.error("No mappings found to validate")
        sys.exit(1)

    # Validate
    results = validate_all_mappings(mappings, sample_size=args.sample)

    # Write reports
    write_validation_report(results, args.output_report)

    if args.output_verified:
        write_verified_mappings(results, args.output_verified)

    # Print summary
    print_summary(results)

    # Return non-zero if there are issues
    invalid_count = sum(1 for r in results if r.status in ["MISMATCH", "NOT_FOUND"])
    if invalid_count > 0:
        logger.warning(f"{invalid_count} mappings need attention")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
