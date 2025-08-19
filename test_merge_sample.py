#!/usr/bin/env python3
"""
Test the merge functionality with sample data.
"""

import pandas as pd
import tempfile
import os
import sys
sys.path.append('src/scripts')
from merge_compound_mappings import CompoundMappingMerger

def create_sample_data():
    """Create sample data files for testing."""
    
    # Sample composition mapping data
    composition_data = [
        # Mapped compounds
        {'medium_id': '104', 'original': 'NaCl', 'mapped': 'CHEBI:26710', 'value': 0.08, 'unit': 'g/L', 'mmol_l': 1.37, 'optional': 'no', 'source': 'json'},
        {'medium_id': '104', 'original': 'KH2PO4', 'mapped': 'PubChem:23710200', 'value': 0.04, 'unit': 'g/L', 'mmol_l': 0.29, 'optional': 'no', 'source': 'json'},
        
        # Unmapped compounds (empty mapped field)
        {'medium_id': '104', 'original': 'Na2S x 9 H2O', 'mapped': '', 'value': 0.3, 'unit': 'g/L', 'mmol_l': '', 'optional': 'no', 'source': 'json'},
        {'medium_id': '104', 'original': 'FeCl2 x 4 H2O', 'mapped': '', 'value': 0.001, 'unit': 'g/L', 'mmol_l': '', 'optional': 'no', 'source': 'json'},
        {'medium_id': '221', 'original': 'Na2S x 9 H2O', 'mapped': '', 'value': 0.5, 'unit': 'g/L', 'mmol_l': '', 'optional': 'no', 'source': 'json'},
        
        # Compound with no match available
        {'medium_id': '104', 'original': 'Unknown compound XYZ', 'mapped': '', 'value': 1.0, 'unit': 'g/L', 'mmol_l': '', 'optional': 'no', 'source': 'json'},
    ]
    
    # Sample unaccounted matches data
    matches_data = [
        {
            'original_compound': 'Na2S x 9 H2O',
            'normalized_compound': 'na2s',
            'hydration_number': 9,
            'frequency': 5,
            'chebi_match': 'Na2S',
            'chebi_id': 'CHEBI:76208',
            'chebi_original_name': 'sodium sulfide',
            'similarity_score': 100,
            'match_confidence': 'very_high',
            'matching_method': 'exact_normalized'
        },
        {
            'original_compound': 'FeCl2 x 4 H2O',
            'normalized_compound': 'fecl2',
            'hydration_number': 4,
            'frequency': 3,
            'chebi_match': 'FeCl2',
            'chebi_id': 'CHEBI:30812',
            'chebi_original_name': 'iron dichloride',
            'similarity_score': 100,
            'match_confidence': 'very_high',
            'matching_method': 'exact_normalized'
        },
        {
            'original_compound': 'CuSO4 x 5 H2O',
            'normalized_compound': 'cuso4',
            'hydration_number': 5,
            'frequency': 2,
            'chebi_match': 'CuSO4',
            'chebi_id': 'CHEBI:23414',
            'chebi_original_name': 'copper sulfate',
            'similarity_score': 100,
            'match_confidence': 'very_high',
            'matching_method': 'exact_normalized'
        }
    ]
    
    return pd.DataFrame(composition_data), pd.DataFrame(matches_data)

def test_merge():
    """Test the merge functionality."""
    print("Testing compound mapping merge...")
    
    # Create sample data
    composition_df, matches_df = create_sample_data()
    
    print("\nSample composition data:")
    print(composition_df[['medium_id', 'original', 'mapped']].to_string(index=False))
    
    print("\nSample matches data:")
    print(matches_df[['original_compound', 'chebi_id', 'similarity_score']].to_string(index=False))
    
    # Create temporary files
    with tempfile.NamedTemporaryFile(mode='w', suffix='.tsv', delete=False) as comp_file, \
         tempfile.NamedTemporaryFile(mode='w', suffix='.tsv', delete=False) as matches_file, \
         tempfile.NamedTemporaryFile(mode='w', suffix='.tsv', delete=False) as output_file:
        
        # Save sample data
        composition_df.to_csv(comp_file.name, sep='\t', index=False)
        matches_df.to_csv(matches_file.name, sep='\t', index=False)
        
        # Test merge
        merger = CompoundMappingMerger(
            composition_file=comp_file.name,
            matches_file=matches_file.name,
            output_file=output_file.name
        )
        
        try:
            merger.run_merge()
            
            # Read and display results
            result_df = pd.read_csv(output_file.name, sep='\t')
            print(f"\nMerged results ({len(result_df)} entries):")
            
            # Show key columns
            key_columns = ['medium_id', 'original', 'mapped', 'chebi_id', 'mapping_status', 'mapping_quality']
            display_columns = [col for col in key_columns if col in result_df.columns]
            print(result_df[display_columns].to_string(index=False))
            
            print(f"\nOutput saved to: {output_file.name}")
            
            # Show mapping status summary
            if 'mapping_status' in result_df.columns:
                print(f"\nMapping status summary:")
                status_counts = result_df['mapping_status'].value_counts()
                for status, count in status_counts.items():
                    print(f"  {status}: {count}")
            
        finally:
            # Clean up temporary files
            for temp_file in [comp_file.name, matches_file.name, output_file.name]:
                try:
                    os.unlink(temp_file)
                except:
                    pass

if __name__ == "__main__":
    test_merge()