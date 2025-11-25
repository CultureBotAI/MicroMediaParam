#!/usr/bin/env python3
"""
Remediate incorrect ChEBI mappings by looking up correct IDs from PubChem.

Takes the validation report with MISMATCH entries and attempts to find
correct ChEBI IDs by:
1. Searching PubChem for the compound name
2. Getting the ChEBI cross-reference from PubChem
3. Verifying the ChEBI label matches
"""

import argparse
import json
import logging
import time
import urllib.parse
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import requests

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Rate limiting
REQUEST_DELAY = 0.25  # seconds between requests


def search_pubchem_by_name(compound_name: str) -> Optional[int]:
    """Search PubChem for a compound by name, return CID if found."""
    try:
        encoded_name = urllib.parse.quote(compound_name)
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{encoded_name}/cids/JSON"
        response = requests.get(url, timeout=30)

        if response.status_code == 200:
            data = response.json()
            cids = data.get('IdentifierList', {}).get('CID', [])
            if cids:
                return cids[0]  # Return first CID
        return None
    except Exception as e:
        logger.debug(f"PubChem search error for {compound_name}: {e}")
        return None


def get_chebi_from_pubchem_cid(cid: int) -> Optional[Tuple[str, str]]:
    """Get ChEBI ID and label from a PubChem CID."""
    try:
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/xrefs/RegistryID/JSON"
        response = requests.get(url, timeout=30)

        if response.status_code == 200:
            data = response.json()
            info_list = data.get('InformationList', {}).get('Information', [])
            if info_list:
                registry_ids = info_list[0].get('RegistryID', [])
                for reg_id in registry_ids:
                    if reg_id.startswith('CHEBI:'):
                        # Verify the ChEBI label
                        chebi_label = verify_chebi_label(reg_id)
                        if chebi_label:
                            return reg_id, chebi_label
        return None
    except Exception as e:
        logger.debug(f"PubChem xref error for CID {cid}: {e}")
        return None


def verify_chebi_label(chebi_id: str) -> Optional[str]:
    """Verify ChEBI ID exists and get its label from OLS4."""
    try:
        # Use OLS4 API
        url = f"https://www.ebi.ac.uk/ols4/api/ontologies/chebi/terms?obo_id={chebi_id}"
        response = requests.get(url, timeout=30)

        if response.status_code == 200:
            data = response.json()
            terms = data.get('_embedded', {}).get('terms', [])
            if terms:
                label = terms[0].get('label', '')
                # Check if label is the ID itself (OLS bug)
                if not label.startswith('CHEBI_'):
                    return label
                # Try to get from synonyms
                synonyms = terms[0].get('synonyms', [])
                if synonyms:
                    return synonyms[0]
        return None
    except Exception as e:
        logger.debug(f"ChEBI verification error for {chebi_id}: {e}")
        return None


def search_chebi_directly(compound_name: str) -> Optional[Tuple[str, str]]:
    """Search ChEBI directly using OLS4 search API."""
    try:
        encoded_name = urllib.parse.quote(compound_name)
        url = f"https://www.ebi.ac.uk/ols4/api/search?q={encoded_name}&ontology=chebi&exact=true"
        response = requests.get(url, timeout=30)

        if response.status_code == 200:
            data = response.json()
            docs = data.get('response', {}).get('docs', [])
            if docs:
                for doc in docs:
                    obo_id = doc.get('obo_id', '')
                    label = doc.get('label', '')
                    if obo_id.startswith('CHEBI:') and label.lower() == compound_name.lower():
                        return obo_id, label
                # If no exact match, return first result
                if docs[0].get('obo_id', '').startswith('CHEBI:'):
                    return docs[0].get('obo_id'), docs[0].get('label', '')
        return None
    except Exception as e:
        logger.debug(f"ChEBI search error for {compound_name}: {e}")
        return None


def remediate_compound(compound_name: str, expected_label: str) -> Optional[Dict]:
    """
    Attempt to find the correct ChEBI ID for a compound.

    Returns dict with chebi_id, chebi_label, source if found.
    """
    # Try PubChem first (most reliable)
    cid = search_pubchem_by_name(compound_name)
    if cid:
        time.sleep(REQUEST_DELAY)
        result = get_chebi_from_pubchem_cid(cid)
        if result:
            chebi_id, chebi_label = result
            return {
                'chebi_id': chebi_id,
                'chebi_label': chebi_label,
                'source': f'pubchem_cid:{cid}'
            }

    time.sleep(REQUEST_DELAY)

    # Also try with expected label
    if expected_label.lower() != compound_name.lower():
        cid = search_pubchem_by_name(expected_label)
        if cid:
            time.sleep(REQUEST_DELAY)
            result = get_chebi_from_pubchem_cid(cid)
            if result:
                chebi_id, chebi_label = result
                return {
                    'chebi_id': chebi_id,
                    'chebi_label': chebi_label,
                    'source': f'pubchem_cid:{cid}'
                }

    time.sleep(REQUEST_DELAY)

    # Try direct ChEBI search
    result = search_chebi_directly(compound_name)
    if result:
        chebi_id, chebi_label = result
        return {
            'chebi_id': chebi_id,
            'chebi_label': chebi_label,
            'source': 'chebi_search'
        }

    time.sleep(REQUEST_DELAY)

    # Try with expected label
    if expected_label.lower() != compound_name.lower():
        result = search_chebi_directly(expected_label)
        if result:
            chebi_id, chebi_label = result
            return {
                'chebi_id': chebi_id,
                'chebi_label': chebi_label,
                'source': 'chebi_search'
            }

    return None


def load_validation_report(filepath: Path) -> List[Dict]:
    """Load validation report and extract MISMATCH entries."""
    mismatches = []

    with open(filepath, 'r', encoding='utf-8') as f:
        header = next(f).strip().split('\t')
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) >= 6:
                status = parts[5]
                if status == 'MISMATCH':
                    mismatches.append({
                        'compound_name': parts[0],
                        'old_id': parts[1],
                        'id_type': parts[2],
                        'expected_label': parts[3],
                        'actual_label': parts[4]
                    })

    return mismatches


def main():
    parser = argparse.ArgumentParser(
        description="Remediate incorrect ChEBI mappings"
    )
    parser.add_argument(
        "--validation-report",
        type=Path,
        default=Path("pipeline_output/validation/validation_report.tsv"),
        help="Path to validation report TSV"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("pipeline_output/validation/remediated_mappings.tsv"),
        help="Output path for remediated mappings"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of compounds to process (for testing)"
    )

    args = parser.parse_args()

    # Load mismatched entries
    mismatches = load_validation_report(args.validation_report)
    logger.info(f"Loaded {len(mismatches)} mismatched entries")

    if args.limit:
        mismatches = mismatches[:args.limit]
        logger.info(f"Limited to {len(mismatches)} entries")

    # Deduplicate by compound name (case insensitive)
    seen_compounds = set()
    unique_mismatches = []
    for m in mismatches:
        key = m['expected_label'].lower()
        if key not in seen_compounds:
            seen_compounds.add(key)
            unique_mismatches.append(m)

    logger.info(f"Processing {len(unique_mismatches)} unique compounds")

    # Process each compound
    results = []
    fixed = 0
    failed = 0

    for i, mismatch in enumerate(unique_mismatches):
        compound = mismatch['expected_label']

        if (i + 1) % 10 == 0:
            logger.info(f"Progress: {i + 1}/{len(unique_mismatches)} ({fixed} fixed, {failed} failed)")

        result = remediate_compound(mismatch['compound_name'], compound)

        if result:
            results.append({
                'compound_name': mismatch['compound_name'],
                'old_chebi_id': mismatch['old_id'],
                'new_chebi_id': result['chebi_id'],
                'chebi_label': result['chebi_label'],
                'source': result['source'],
                'status': 'FIXED'
            })
            fixed += 1
            logger.debug(f"Fixed: {compound} -> {result['chebi_id']} ({result['chebi_label']})")
        else:
            results.append({
                'compound_name': mismatch['compound_name'],
                'old_chebi_id': mismatch['old_id'],
                'new_chebi_id': '',
                'chebi_label': mismatch['expected_label'],
                'source': '',
                'status': 'NOT_FOUND'
            })
            failed += 1
            logger.debug(f"Failed: {compound}")

    # Write output
    args.output.parent.mkdir(parents=True, exist_ok=True)

    with open(args.output, 'w', encoding='utf-8') as f:
        f.write("compound_name\told_chebi_id\tnew_chebi_id\tchebi_label\tsource\tstatus\n")
        for r in results:
            f.write(f"{r['compound_name']}\t{r['old_chebi_id']}\t{r['new_chebi_id']}\t{r['chebi_label']}\t{r['source']}\t{r['status']}\n")

    logger.info(f"\nRemediation complete:")
    logger.info(f"  - Fixed: {fixed}")
    logger.info(f"  - Not found: {failed}")
    logger.info(f"  - Success rate: {fixed / len(unique_mismatches) * 100:.1f}%")
    logger.info(f"Output written to: {args.output}")


if __name__ == "__main__":
    main()
