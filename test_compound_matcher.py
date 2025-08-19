#!/usr/bin/env python3
"""
Quick test of the compound matching functionality with a small sample.
"""

import sys
sys.path.append('src/scripts')
from find_unaccounted_compound_matches import UnaccountedCompoundMatcher

# Test with just a few sample unaccounted compounds
test_compounds = {
    "Na2S x 9 H2O",
    "FeCl2 x 4 H2O", 
    "CoCl2 x 6 H2O",
    "MnCl2 x 4 H2O",
    "ZnCl2",
    "Na2MoO4 x 2 H2O",
    "H3BO3",
    "CuCl2 x 2 H2O",
    "Sulfur",
    "Na2CO3"
}

def test_normalization():
    """Test the normalization function."""
    matcher = UnaccountedCompoundMatcher()
    
    print("Testing compound name normalization:")
    for compound in test_compounds:
        normalized = matcher._normalize_compound_name(compound)
        print(f"  {compound} → {normalized}")

def test_small_matching():
    """Test matching with a small subset."""
    print("\nTesting ChEBI matching...")
    
    matcher = UnaccountedCompoundMatcher(min_similarity=70)
    
    # Override the collect method to use our test compounds
    matcher.unaccounted_compounds = {comp: 1 for comp in test_compounds}
    
    # Load ChEBI database (this will take a moment)
    print("Loading ChEBI database...")
    chebi_compounds = matcher.load_chebi_database()
    
    # Find matches for our test compounds
    print("Finding matches...")
    matches = matcher.find_matches(test_compounds, chebi_compounds)
    
    # Display results
    print(f"\nFound matches for {len(matches)} compounds:")
    for match in matches:
        original = match['original_compound']
        chebi_match = match['chebi_match']
        chebi_id = match['chebi_id']
        score = match['similarity_score']
        confidence = match['match_confidence']
        
        if chebi_match:
            print(f"✓ {original}")
            print(f"  → {chebi_match} ({chebi_id})")
            print(f"  → Score: {score}% ({confidence})")
        else:
            print(f"✗ {original} → No match found")
        print()

if __name__ == "__main__":
    test_normalization()
    test_small_matching()