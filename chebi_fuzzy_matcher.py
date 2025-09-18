#!/usr/bin/env python3
"""
Fuzzy matching for unmapped compounds using existing CHEBI nodes data
"""

import pandas as pd
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from fuzzywuzzy import fuzz, process
import re
import xml.etree.ElementTree as ET

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CHEBIFuzzyMatcher:
    """
    Use fuzzy string matching against CHEBI nodes for compound mapping.
    Much faster than OAK annotation for large-scale mapping.
    """
    
    def __init__(self, chebi_owl_file: Path):
        """
        Initialize fuzzy matcher with CHEBI OWL file.
        
        Args:
            chebi_owl_file: Path to CHEBI OWL file
        """
        self.chebi_owl_file = chebi_owl_file
        self.chebi_terms = {}
        self.chebi_synonyms = {}
        self.load_chebi_owl_data()
    
    def load_chebi_owl_data(self) -> None:
        """Load CHEBI terms and synonyms from OWL file."""
        if not self.chebi_owl_file.exists():
            raise FileNotFoundError(f"CHEBI OWL file not found: {self.chebi_owl_file}")
        
        logger.info(f"Loading CHEBI data from: {self.chebi_owl_file}")
        logger.info("This may take a few minutes for the complete CHEBI ontology...")
        
        # Parse OWL file
        try:
            tree = ET.parse(self.chebi_owl_file)
            root = tree.getroot()
        except ET.ParseError as e:
            raise ValueError(f"Failed to parse CHEBI OWL file: {e}")
        
        # Define namespaces
        namespaces = {
            'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
            'rdfs': 'http://www.w3.org/2000/01/rdf-schema#',
            'owl': 'http://www.w3.org/2002/07/owl#',
            'obo': 'http://purl.obolibrary.org/obo/',
            'oboInOwl': 'http://www.geneontology.org/formats/oboInOwl#'
        }
        
        # Find all CHEBI classes
        classes = root.findall(".//owl:Class", namespaces)
        
        logger.info(f"Found {len(classes)} OWL classes, processing CHEBI terms...")
        
        chebi_count = 0
        for cls in classes:
            # Get the class ID
            about = cls.get('{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about')
            if not about or 'CHEBI_' not in about:
                continue
            
            # Convert obo format to CHEBI format
            chebi_id = about.replace('http://purl.obolibrary.org/obo/CHEBI_', 'CHEBI:')
            
            # Get primary label
            label_elem = cls.find('rdfs:label', namespaces)
            if label_elem is not None and label_elem.text:
                primary_label = label_elem.text.strip()
                
                # Store primary label
                self.chebi_terms[primary_label.lower()] = {
                    'id': chebi_id,
                    'name': primary_label,
                    'type': 'primary'
                }
                chebi_count += 1
            
            # Get synonyms
            synonym_elems = cls.findall('.//oboInOwl:hasExactSynonym', namespaces)
            for syn_elem in synonym_elems:
                if syn_elem.text:
                    synonym = syn_elem.text.strip()
                    if synonym and synonym.lower() not in self.chebi_terms:
                        self.chebi_terms[synonym.lower()] = {
                            'id': chebi_id,
                            'name': primary_label if label_elem is not None else synonym,
                            'synonym': synonym,
                            'type': 'synonym'
                        }
            
            # Get related synonyms
            related_synonym_elems = cls.findall('.//oboInOwl:hasRelatedSynonym', namespaces)
            for syn_elem in related_synonym_elems:
                if syn_elem.text:
                    synonym = syn_elem.text.strip()
                    if synonym and synonym.lower() not in self.chebi_terms:
                        self.chebi_terms[synonym.lower()] = {
                            'id': chebi_id,
                            'name': primary_label if label_elem is not None else synonym,
                            'synonym': synonym,
                            'type': 'related_synonym'
                        }
        
        logger.info(f"Loaded {chebi_count} CHEBI terms")
        logger.info(f"Built search index with {len(self.chebi_terms)} searchable terms")
    
    def normalize_compound_name(self, name: str) -> str:
        """
        Normalize compound name for better matching.
        
        Args:
            name: Original compound name
            
        Returns:
            Normalized compound name
        """
        if not name:
            return ""
        
        # Convert to lowercase
        normalized = name.lower().strip()
        
        # Remove hydration states (enhanced patterns)
        hydration_patterns = [
            r'\s*[x×]\s*\d*\s*h2o\s*$',     # x H2O, x 2 H2O at end
            r'\s*[·•]\s*\d*\s*h2o\s*$',     # · H2O, · 2 H2O at end
            r'\s*\.\s*\d*\s*h2o\s*$',       # . H2O, . 2 H2O at end
            r'\s*\*\s*\d*\s*h2o\s*$',       # * H2O, * 2 H2O at end
            r'\s+\d*\s*h2o\s*$',            # space H2O at end
            r'\s*\(\d*\s*h2o\)\s*$',        # (H2O) at end
            r'\s*\bmonohydrate\b\s*$',      # monohydrate
            r'\s*\bdihydrate\b\s*$',        # dihydrate
            r'\s*\btrihydrate\b\s*$',       # trihydrate
            r'\s*\bhydrate\b\s*$',          # generic hydrate
        ]
        
        for pattern in hydration_patterns:
            normalized = re.sub(pattern, '', normalized, flags=re.IGNORECASE)
        
        # Clean up common variations
        normalized = re.sub(r'^na\s+', 'sodium ', normalized)    # "Na malate" -> "sodium malate"
        normalized = re.sub(r'^na-', 'sodium ', normalized)      # "Na-formate" -> "sodium formate"  
        normalized = re.sub(r'^na2-', 'disodium ', normalized)   # "Na2-fumarate" -> "disodium fumarate"
        normalized = re.sub(r'^nh4-', 'ammonium ', normalized)   # "NH4-oxalate" -> "ammonium oxalate"
        
        # Clean up extra whitespace
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        return normalized
    
    def find_exact_matches(self, compounds: List[str]) -> Dict[str, Dict]:
        """
        Find exact matches for compounds in CHEBI terms.
        
        Args:
            compounds: List of compound names to match
            
        Returns:
            Dictionary of exact matches
        """
        exact_matches = {}
        
        for compound in compounds:
            normalized = self.normalize_compound_name(compound)
            
            if normalized in self.chebi_terms:
                exact_matches[compound] = {
                    'match_type': 'exact',
                    'confidence': 1.0,
                    'chebi_id': self.chebi_terms[normalized]['id'],
                    'chebi_name': self.chebi_terms[normalized]['name'],
                    'matched_term': normalized
                }
        
        logger.info(f"Found {len(exact_matches)} exact matches")
        return exact_matches
    
    def find_fuzzy_matches(self, compounds: List[str], 
                          min_confidence: float = 0.8,
                          max_results: int = 3) -> Dict[str, List[Dict]]:
        """
        Find fuzzy matches for compounds using fuzzywuzzy.
        
        Args:
            compounds: List of compound names to match
            min_confidence: Minimum similarity score (0-1)
            max_results: Maximum results per compound
            
        Returns:
            Dictionary of fuzzy matches
        """
        fuzzy_matches = {}
        
        # Prepare search terms list
        search_terms = list(self.chebi_terms.keys())
        
        for compound in compounds:
            normalized = self.normalize_compound_name(compound)
            
            # Skip if we already have exact match
            if normalized in self.chebi_terms:
                continue
            
            # Find fuzzy matches
            matches = process.extract(normalized, search_terms, 
                                    scorer=fuzz.token_sort_ratio,
                                    limit=max_results)
            
            compound_matches = []
            for match_term, score in matches:
                # Convert score to 0-1 confidence
                confidence = score / 100.0
                
                if confidence >= min_confidence:
                    chebi_info = self.chebi_terms[match_term]
                    compound_matches.append({
                        'match_type': 'fuzzy',
                        'confidence': confidence,
                        'chebi_id': chebi_info['id'],
                        'chebi_name': chebi_info['name'],
                        'matched_term': match_term,
                        'original_term': normalized
                    })
            
            if compound_matches:
                fuzzy_matches[compound] = compound_matches
        
        logger.info(f"Found fuzzy matches for {len(fuzzy_matches)} compounds")
        return fuzzy_matches
    
    def match_compounds(self, compounds: List[str], 
                       min_fuzzy_confidence: float = 0.8) -> Dict[str, Dict]:
        """
        Match compounds using exact matches first, then fuzzy matching.
        
        Args:
            compounds: List of compound names to match
            min_fuzzy_confidence: Minimum confidence for fuzzy matches
            
        Returns:
            Dictionary of best matches per compound
        """
        logger.info(f"Matching {len(compounds)} compounds against CHEBI database")
        
        # Normalize and deduplicate compounds
        unique_compounds = list(set(compounds))
        
        # Find exact matches first
        exact_matches = self.find_exact_matches(unique_compounds)
        
        # Find compounds that need fuzzy matching
        unmatched_compounds = [c for c in unique_compounds if c not in exact_matches]
        
        # Find fuzzy matches for remaining compounds
        fuzzy_matches = self.find_fuzzy_matches(unmatched_compounds, 
                                               min_confidence=min_fuzzy_confidence)
        
        # Combine results - prefer exact matches, take best fuzzy match
        final_matches = {}
        
        # Add exact matches
        final_matches.update(exact_matches)
        
        # Add best fuzzy matches
        for compound, matches in fuzzy_matches.items():
            if matches:
                # Take the best match (highest confidence)
                best_match = max(matches, key=lambda x: x['confidence'])
                final_matches[compound] = best_match
        
        logger.info(f"Final results: {len(final_matches)} matched compounds")
        logger.info(f"  - Exact matches: {len(exact_matches)}")
        logger.info(f"  - Fuzzy matches: {len(fuzzy_matches)}")
        
        return final_matches

def main():
    """Test the CHEBI fuzzy matcher."""
    print("🧬 CHEBI Fuzzy Matching for Unmapped Compounds")
    print("=" * 50)
    
    # Check if CHEBI OWL file exists at the specified location
    chebi_owl_file = Path.home() / "Documents/VIMSS/ontology/KG-Hub/KG-Microbe/kg-microbe/data/raw/chebi.owl"
    
    if not chebi_owl_file.exists():
        # Try alternative locations
        alt_locations = [
            Path("chebi.owl"),
            Path("data/chebi.owl"),
            Path("../kg-microbe/data/raw/chebi.owl"),
            Path("~/Documents/VIMSS/ontology/KG-Hub/KG-Microbe/kg-microbe/data/raw/chebi.owl").expanduser()
        ]
        
        for alt_file in alt_locations:
            if alt_file.exists():
                chebi_owl_file = alt_file
                break
        else:
            print(f"❌ CHEBI OWL file not found. Tried:")
            print(f"  - {Path.home() / 'Documents/VIMSS/ontology/KG-Hub/KG-Microbe/kg-microbe/data/raw/chebi.owl'}")
            for alt_file in alt_locations:
                print(f"  - {alt_file}")
            return
    
    print(f"📁 Using CHEBI OWL file: {chebi_owl_file}")
    print(f"📏 File size: {chebi_owl_file.stat().st_size / (1024*1024):.1f} MB")
    
    # Get unmapped compounds
    mapping_file = Path("composition_kg_mapping.tsv")
    if not mapping_file.exists():
        print(f"❌ Mapping file not found: {mapping_file}")
        return
    
    df = pd.read_csv(mapping_file, sep='\t')
    unmapped_mask = df['mapped'].isna() | (df['mapped'] == '') | (df['mapped'].str.strip() == '')
    unmapped_compounds = df[unmapped_mask]['original'].unique().tolist()
    
    print(f"📊 Found {len(unmapped_compounds)} unmapped compounds")
    
    # Test with first 10 for speed
    test_compounds = unmapped_compounds[:10]
    print(f"🧪 Testing with first {len(test_compounds)} compounds:")
    for i, compound in enumerate(test_compounds, 1):
        print(f"  {i:2d}. {compound}")
    
    # Initialize matcher
    try:
        matcher = CHEBIFuzzyMatcher(chebi_owl_file)
    except Exception as e:
        print(f"❌ Failed to initialize matcher: {e}")
        return
    
    # Match compounds
    matches = matcher.match_compounds(test_compounds, min_fuzzy_confidence=0.7)
    
    # Display results
    print(f"\\n📋 Matching Results:")
    print("-" * 30)
    
    for compound in test_compounds:
        if compound in matches:
            match = matches[compound]
            print(f"\\n✅ {compound}")
            print(f"   → {match['chebi_name']} ({match['chebi_id']})")
            print(f"   Type: {match['match_type']}, Confidence: {match['confidence']:.3f}")
        else:
            print(f"\\n❌ {compound}")
            print("   → No match found")
    
    print(f"\\n📈 Summary:")
    print(f"   Tested: {len(test_compounds)} compounds")
    print(f"   Matched: {len(matches)} compounds ({len(matches)/len(test_compounds)*100:.1f}%)")

if __name__ == "__main__":
    main()