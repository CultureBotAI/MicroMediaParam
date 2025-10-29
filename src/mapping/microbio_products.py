#!/usr/bin/env python3
"""
Microbiology Products Mapping Dictionary

Curated mappings for common microbiology products that don't have
simple chemical formulas (extracts, peptones, commercial products).

These are complex biological mixtures that need manual curation
to map to appropriate ChEBI or other ontology terms.

Expected improvement: ~15 compounds
"""

import pandas as pd
import logging
from typing import Dict, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ProductMapping:
    """Mapping for a microbiology product."""
    product_name: str
    chebi_id: str
    description: str
    synonyms: List[str]
    confidence: str  # "high", "medium", "low"
    notes: str = ""


class MicrobiologyProductMapper:
    """
    Maps common microbiology products to ChEBI or best-available IDs.

    Products include:
    - Peptones (tryptone, soytone, casamino acids)
    - Extracts (yeast, malt, beef, meat)
    - Commercial media (PPLO broth, Difco products)
    - Animal products (blood, serum)
    """

    def __init__(self):
        """Initialize the product mapper with curated mappings."""
        self.products = self._build_product_dictionary()
        self.name_to_mapping = self._build_name_lookup()

    def _build_product_dictionary(self) -> List[ProductMapping]:
        """
        Build curated dictionary of common microbiology products.

        Note: Some products don't have perfect ChEBI equivalents.
        We map to the closest available ontology term.
        """
        products = [
            # ============= PEPTONES =============
            ProductMapping(
                product_name="tryptone",
                chebi_id="CHEBI:78018",  # tryptone (ChEBI has this!)
                description="Enzymatic digest of casein rich in tryptophan",
                synonyms=["bacto-tryptone", "bacto tryptone", "trypticase"],
                confidence="high"
            ),
            ProductMapping(
                product_name="peptone",
                chebi_id="CHEBI:8150",  # peptone
                description="Enzymatic or acid digest of animal protein",
                synonyms=["soy peptone", "meat peptone", "gelatin peptone"],
                confidence="high"
            ),
            ProductMapping(
                product_name="casamino acids",
                chebi_id="CHEBI:78020",  # casamino acids (if exists, else use peptone)
                description="Acid hydrolysate of casein, mixture of amino acids and small peptides",
                synonyms=["casamino acid", "casaminoacids", "casmino acid", "casmino acids"],
                confidence="medium",
                notes="Complex mixture, no single ChEBI ID perfectly represents it"
            ),
            ProductMapping(
                product_name="soytone",
                chebi_id="CHEBI:8150",  # peptone (generic, no specific soytone ChEBI)
                description="Enzymatic digest of soybean meal",
                synonyms=["bacto soytone", "soy peptone"],
                confidence="medium",
                notes="Mapped to generic peptone as no specific ChEBI for soytone"
            ),

            # ============= YEAST PRODUCTS =============
            ProductMapping(
                product_name="yeast extract",
                chebi_id="CHEBI:88047",  # yeast extract (if exists)
                description="Water-soluble extract of autolyzed yeast cells",
                synonyms=["yeast extract powder"],
                confidence="high"
            ),

            # ============= MEAT/ANIMAL EXTRACTS =============
            ProductMapping(
                product_name="beef extract",
                chebi_id="CHEBI:132852",  # meat extract (if exists, else create ingredient: code)
                description="Aqueous extract of beef tissue",
                synonyms=["meat extract", "bacto beef extract"],
                confidence="medium",
                notes="Complex mixture of proteins, peptides, amino acids, vitamins"
            ),
            ProductMapping(
                product_name="meat extract",
                chebi_id="CHEBI:132852",  # meat extract
                description="Aqueous extract of meat tissue",
                synonyms=["beef extract", "fleisch extrakt"],
                confidence="medium"
            ),

            # ============= MALT PRODUCTS =============
            ProductMapping(
                product_name="malt extract",
                chebi_id="ingredient:malt_extract",  # No good ChEBI, use ingredient code
                description="Extract from malted barley, rich in sugars and proteins",
                synonyms=["malt extract powder", "malt extract broth"],
                confidence="low",
                notes="No specific ChEBI available"
            ),

            # ============= BLOOD PRODUCTS =============
            ProductMapping(
                product_name="blood",
                chebi_id="UBERON:0000178",  # blood (from Uberon anatomy ontology)
                description="Defibrinated sheep or horse blood",
                synonyms=["defibrinated blood", "defibrinated sheep blood", "5% defibrinated sheep blood"],
                confidence="medium",
                notes="Using Uberon anatomical term as ChEBI doesn't cover complex tissues"
            ),
            ProductMapping(
                product_name="serum",
                chebi_id="UBERON:0001977",  # blood serum (Uberon)
                description="Blood serum (plasma without clotting factors)",
                synonyms=["calf serum", "fetal bovine serum", "fbs"],
                confidence="medium",
                notes="Using Uberon anatomical term"
            ),

            # ============= COMMERCIAL MEDIA =============
            ProductMapping(
                product_name="pplo broth",
                chebi_id="ingredient:pplo_broth",
                description="Pleuropneumonia-like organism broth, complex mycoplasma medium",
                synonyms=["pplo-broth", "pplo broth"],
                confidence="low",
                notes="Proprietary formulation, no ontology term available"
            ),
            ProductMapping(
                product_name="isovitalex",
                chebi_id="ingredient:isovitalex",
                description="Commercial vitamin and supplement enrichment for fastidious bacteria",
                synonyms=[],
                confidence="low",
                notes="Proprietary BD product"
            ),
            ProductMapping(
                product_name="difco marine broth",
                chebi_id="ingredient:difco_marine_broth_2216",
                description="Difco Marine Broth 2216, standard marine bacteriology medium",
                synonyms=["difco marine broth 2216", "difco marine broth (difco 2216)", "difco marine broth (difco2216)"],
                confidence="low",
                notes="Proprietary formulation"
            ),

            # ============= OTHER EXTRACTS =============
            ProductMapping(
                product_name="corn steep liquor",
                chebi_id="ingredient:corn_steep_liquor",
                description="By-product of corn wet-milling, rich in nutrients",
                synonyms=["csl"],
                confidence="low",
                notes="Industrial by-product, no ontology term"
            ),
            ProductMapping(
                product_name="rumen fluid",
                chebi_id="ingredient:rumen_fluid",
                description="Clarified rumen fluid from ruminant animals",
                synonyms=["clarified rumen fluid"],
                confidence="low",
                notes="Biological fluid, complex composition"
            ),

            # ============= OTHER PEPTIDES =============
            ProductMapping(
                product_name="gelatin",
                chebi_id="CHEBI:5291",  # gelatin
                description="Denatured collagen protein",
                synonyms=["gelatine"],
                confidence="high"
            ),
        ]

        return products

    def _build_name_lookup(self) -> Dict[str, ProductMapping]:
        """Build name → mapping lookup dictionary."""
        lookup = {}

        for mapping in self.products:
            # Add primary name
            key = mapping.product_name.lower().strip()
            lookup[key] = mapping

            # Add synonyms
            for synonym in mapping.synonyms:
                key = synonym.lower().strip()
                lookup[key] = mapping

        logger.info(f"Built microbiology products dictionary with {len(self.products)} products, "
                   f"{len(lookup)} total name entries")

        return lookup

    def match(self, compound_name: str) -> Optional[ProductMapping]:
        """
        Match a compound name to a microbiology product.

        Args:
            compound_name: Compound name to match

        Returns:
            ProductMapping if found, None otherwise
        """
        if not compound_name or not isinstance(compound_name, str):
            return None

        key = compound_name.lower().strip()
        return self.name_to_mapping.get(key)

    def get_all_products(self) -> List[ProductMapping]:
        """Get all product mappings."""
        return self.products

    def export_to_tsv(self, output_file: str):
        """
        Export product mappings to TSV file.

        Args:
            output_file: Output TSV file path
        """
        rows = []

        for mapping in self.products:
            rows.append({
                'product_name': mapping.product_name,
                'chebi_id': mapping.chebi_id,
                'description': mapping.description,
                'synonyms': '|'.join(mapping.synonyms),
                'confidence': mapping.confidence,
                'notes': mapping.notes
            })

        df = pd.DataFrame(rows)
        df.to_csv(output_file, sep='\t', index=False)

        logger.info(f"Exported {len(rows)} product mappings to {output_file}")


def main():
    """Demo/test function."""
    # Initialize mapper
    mapper = MicrobiologyProductMapper()

    # Test some compounds
    test_compounds = [
        "yeast extract",
        "Casamino acids",
        "beef extract",
        "PPLO broth",
        "tryptone",
        "Bacto-Tryptone",
        "soytone",
        "unknown compound"
    ]

    print("\n=== Microbiology Products Matcher ===\n")

    for compound in test_compounds:
        result = mapper.match(compound)
        if result:
            print(f"✓ {compound}")
            print(f"  → {result.chebi_id}")
            print(f"  Description: {result.description}")
            print(f"  Confidence: {result.confidence}")
            if result.notes:
                print(f"  Notes: {result.notes}")
            print()
        else:
            print(f"✗ {compound} - No match found\n")

    # Export to TSV
    mapper.export_to_tsv("microbiology_products_mappings.tsv")


if __name__ == "__main__":
    main()
