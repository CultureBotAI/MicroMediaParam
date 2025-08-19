#!/usr/bin/env python3
"""
Test the enhanced hydration-aware compound matching.
"""

import sys
sys.path.append('src/scripts')
from find_unaccounted_compound_matches import UnaccountedCompoundMatcher

# Test compounds with various hydration notations
test_compounds = {
    # Numeric notation (x N H2O)
    "CaCl2 x 2 H2O",
    "MgSO4 x 7 H2O", 
    "Na2S x 9 H2O",
    "FeSO4 x 7 H2O",
    "CuSO4 x 5 H2O",
    
    # Should find matches with ChEBI entries ending in "dihydrate", etc.
    "Calcium chloride dihydrate",  # Should match CaCl2 x 2 H2O
    "Magnesium sulfate heptahydrate",  # Should match MgSO4 x 7 H2O
    
    # Mixed cases
    "BaCl2 x 2 H2O",
    "ZnSO4 x 7 H2O"
}

def test_hydration_extraction():
    """Test hydration number extraction."""
    matcher = UnaccountedCompoundMatcher()
    
    print("Testing hydration number extraction:")
    for compound in test_compounds:
        hydration_num = matcher._get_hydration_number(compound)
        normalized = matcher._normalize_compound_name(compound)
        print(f"  {compound}")
        print(f"    → Hydration number: {hydration_num}")
        print(f"    → Normalized: {normalized}")
        print()

def test_hydration_matching():
    """Test enhanced matching with hydration awareness."""
    print("\nTesting hydration-aware ChEBI matching...")
    
    matcher = UnaccountedCompoundMatcher(min_similarity=70)
    
    # Override the collect method to use our test compounds
    matcher.unaccounted_compounds = {comp: 1 for comp in test_compounds}
    
    # Load ChEBI database
    print("Loading ChEBI database...")
    chebi_compounds = matcher.load_chebi_database()
    
    # Find matches for our test compounds
    print("Finding matches with hydration awareness...")
    matches = matcher.find_matches(test_compounds, chebi_compounds)
    
    # Display results grouped by matching method
    print(f"\nFound matches for {len(matches)} compounds:")
    
    methods = {}
    for match in matches:
        method = match['matching_method']
        if method not in methods:
            methods[method] = []
        methods[method].append(match)
    
    for method, method_matches in methods.items():
        print(f"\n=== {method.upper()} MATCHES ===")
        for match in method_matches:
            original = match['original_compound']
            chebi_match = match['chebi_match']
            chebi_id = match['chebi_id']
            score = match['similarity_score']
            confidence = match['match_confidence']
            hydration = match['hydration_number']
            
            if chebi_match:
                print(f"✓ {original} (hydration: {hydration})")
                print(f"  → {chebi_match} ({chebi_id})")
                print(f"  → Score: {score}% ({confidence})")
            else:
                print(f"✗ {original} (hydration: {hydration}) → No match found")
            print()

if __name__ == "__main__":
    test_hydration_extraction()
    test_hydration_matching()