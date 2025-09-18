#!/usr/bin/env python3
"""
PubChem Chemical Properties TSV Generator

Generates chemical_properties.tsv files in the format required by the
MicroMediaParam compute_media_properties.py script from PubChem data.

Author: MicroMediaParam Project
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import pandas as pd

from .property_extractor import ProcessedChemicalProperties

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PubChemTSVGenerator:
    """
    Generate chemical_properties.tsv files from processed PubChem data.
    
    Output format compatible with MicroMediaParam:
    compound_name	molecular_weight	pka_values	charge_states	ion_charges	solubility_g_per_L	activity_coefficient	description
    """
    
    def __init__(self):
        self.required_columns = [
            'compound_name',
            'molecular_weight', 
            'pka_values',
            'charge_states',
            'ion_charges',
            'solubility_g_per_L',
            'activity_coefficient',
            'description'
        ]
    
    def format_pka_values(self, pka_values: List[float]) -> str:
        """Format pKa values as comma-separated string."""
        if not pka_values:
            return ""
        return ",".join(f"{pka:.2f}" for pka in pka_values)
    
    def format_charge_states(self, charge_states: List[int]) -> str:
        """Format charge states as comma-separated string."""
        if not charge_states:
            return "0"
        return ",".join(str(charge) for charge in charge_states)
    
    def format_ion_charges(self, ion_charges: Dict[str, int]) -> str:
        """Format ion charges as comma-separated key:value pairs."""
        if not ion_charges:
            return ""
        return ",".join(f"{ion}:{charge}" for ion, charge in ion_charges.items())
    
    def validate_compound_data(self, compound: ProcessedChemicalProperties) -> bool:
        """Validate that compound data has required fields."""
        if not compound.compound_name:
            logger.warning("Compound missing name")
            return False
        
        if not compound.molecular_weight or compound.molecular_weight <= 0:
            logger.warning(f"Compound {compound.compound_name} has invalid molecular weight")
            return False
        
        if compound.solubility_g_per_L is None or compound.solubility_g_per_L < 0:
            logger.warning(f"Compound {compound.compound_name} has invalid solubility")
            return False
        
        return True
    
    def generate_tsv_from_processed_data(self, 
                                       processed_compounds: List[ProcessedChemicalProperties],
                                       output_file: Path,
                                       merge_with_existing: bool = True) -> None:
        """
        Generate TSV file from processed chemical properties.
        
        Args:
            processed_compounds: List of processed chemical properties
            output_file: Output TSV file path
            merge_with_existing: Whether to merge with existing TSV file
        """
        # Load existing data if requested
        existing_data = []
        if merge_with_existing and output_file.exists():
            try:
                existing_df = pd.read_csv(output_file, sep='\t')
                existing_data = existing_df.to_dict('records')
                logger.info(f"Loaded {len(existing_data)} existing compounds from {output_file}")
            except Exception as e:
                logger.warning(f"Could not load existing TSV file: {e}")
        
        # Convert processed compounds to TSV format
        tsv_data = []
        existing_names = {row.get('compound_name', '').lower() for row in existing_data}
        
        for compound in processed_compounds:
            if not self.validate_compound_data(compound):
                continue
            
            # Skip if compound already exists (when merging)
            if merge_with_existing and compound.compound_name.lower() in existing_names:
                logger.debug(f"Skipping existing compound: {compound.compound_name}")
                continue
            
            row = {
                'compound_name': compound.compound_name,
                'molecular_weight': f"{compound.molecular_weight:.2f}",
                'pka_values': self.format_pka_values(compound.pka_values),
                'charge_states': self.format_charge_states(compound.charge_states),
                'ion_charges': self.format_ion_charges(compound.ion_charges),
                'solubility_g_per_L': f"{compound.solubility_g_per_L:.4f}",
                'activity_coefficient': f"{compound.activity_coefficient:.2f}",
                'description': compound.description or compound.compound_name
            }
            
            tsv_data.append(row)
        
        # Combine existing and new data
        all_data = existing_data + tsv_data
        
        # Create DataFrame and save
        df = pd.DataFrame(all_data)
        df = df[self.required_columns]  # Ensure column order
        
        # Remove duplicates based on compound_name
        df = df.drop_duplicates(subset=['compound_name'], keep='first')
        
        # Sort by compound name
        df = df.sort_values('compound_name')
        
        # Save to TSV
        df.to_csv(output_file, sep='\t', index=False)
        
        logger.info(f"Generated TSV file with {len(df)} compounds: {output_file}")
        logger.info(f"Added {len(tsv_data)} new compounds from PubChem")
    
    def generate_tsv_from_json(self, 
                             processed_data_file: Path,
                             output_file: Path,
                             merge_with_existing: bool = True) -> None:
        """
        Generate TSV file from processed JSON data.
        
        Args:
            processed_data_file: Path to processed chemical data JSON
            output_file: Output TSV file path
            merge_with_existing: Whether to merge with existing TSV file
        """
        # Load processed data
        with open(processed_data_file, 'r') as f:
            data = json.load(f)
        
        # Convert to ProcessedChemicalProperties objects
        processed_compounds = []
        for item in data:
            compound = ProcessedChemicalProperties(
                compound_name=item['compound_name'],
                molecular_weight=item['molecular_weight'],
                pka_values=item['pka_values'],
                charge_states=item['charge_states'],
                ion_charges=item['ion_charges'],
                solubility_g_per_L=item['solubility_g_per_L'],
                activity_coefficient=item['activity_coefficient'],
                description=item['description'],
                formula=item.get('formula'),
                source=item.get('source', 'pubchem')
            )
            processed_compounds.append(compound)
        
        # Generate TSV
        self.generate_tsv_from_processed_data(
            processed_compounds, output_file, merge_with_existing
        )
    
    def validate_tsv_format(self, tsv_file: Path) -> bool:
        """
        Validate that TSV file has correct format for compute_media_properties.py.
        
        Args:
            tsv_file: Path to TSV file to validate
            
        Returns:
            True if format is valid, False otherwise
        """
        try:
            df = pd.read_csv(tsv_file, sep='\t')
            
            # Check required columns
            missing_cols = set(self.required_columns) - set(df.columns)
            if missing_cols:
                logger.error(f"Missing required columns: {missing_cols}")
                return False
            
            # Check data types and formats
            for index, row in df.iterrows():
                compound_name = row['compound_name']
                
                # Check molecular weight
                try:
                    mw = float(row['molecular_weight'])
                    if mw <= 0:
                        logger.error(f"{compound_name}: Invalid molecular weight {mw}")
                        return False
                except ValueError:
                    logger.error(f"{compound_name}: Non-numeric molecular weight")
                    return False
                
                # Check pKa values format
                pka_str = row['pka_values']
                if pd.notna(pka_str) and str(pka_str).strip():
                    try:
                        pka_values = [float(x.strip()) for x in str(pka_str).split(',')]
                    except ValueError:
                        logger.error(f"{compound_name}: Invalid pKa format: {pka_str}")
                        return False
                
                # Check ion charges format
                ion_charges_str = row['ion_charges']
                if pd.notna(ion_charges_str) and str(ion_charges_str).strip():
                    try:
                        for pair in str(ion_charges_str).split(','):
                            if ':' not in pair:
                                raise ValueError("Missing colon separator")
                            ion, charge = pair.strip().split(':')
                            int(charge)  # Validate charge is integer
                    except ValueError:
                        logger.error(f"{compound_name}: Invalid ion charges format: {ion_charges_str}")
                        return False
            
            logger.info(f"TSV file validation passed: {len(df)} compounds")
            return True
            
        except Exception as e:
            logger.error(f"TSV validation failed: {e}")
            return False
    
    def compare_with_existing_database(self, new_tsv_file: Path, existing_tsv_file: Path) -> Dict[str, Any]:
        """
        Compare new PubChem data with existing chemical database.
        
        Args:
            new_tsv_file: Path to new TSV file
            existing_tsv_file: Path to existing chemical_properties.tsv
            
        Returns:
            Dictionary with comparison statistics
        """
        stats = {
            'new_compounds': 0,
            'updated_compounds': 0,
            'conflicts': [],
            'improvements': []
        }
        
        if not existing_tsv_file.exists():
            logger.info("No existing database to compare with")
            return stats
        
        try:
            new_df = pd.read_csv(new_tsv_file, sep='\t')
            existing_df = pd.read_csv(existing_tsv_file, sep='\t')
            
            # Create lookup dictionaries
            existing_compounds = {row['compound_name'].lower(): row for _, row in existing_df.iterrows()}
            
            for _, new_row in new_df.iterrows():
                compound_name = new_row['compound_name'].lower()
                
                if compound_name not in existing_compounds:
                    stats['new_compounds'] += 1
                else:
                    existing_row = existing_compounds[compound_name]
                    
                    # Check for improvements in data quality
                    improvements = []
                    
                    # Check if PubChem has better pKa data
                    if (pd.isna(existing_row['pka_values']) or not str(existing_row['pka_values']).strip()) and \
                       (pd.notna(new_row['pka_values']) and str(new_row['pka_values']).strip()):
                        improvements.append('Added pKa values')
                    
                    # Check if PubChem has better solubility data
                    if pd.isna(existing_row['solubility_g_per_L']) and pd.notna(new_row['solubility_g_per_L']):
                        improvements.append('Added solubility data')
                    
                    # Check if PubChem has better ion charge data
                    if (pd.isna(existing_row['ion_charges']) or not str(existing_row['ion_charges']).strip()) and \
                       (pd.notna(new_row['ion_charges']) and str(new_row['ion_charges']).strip()):
                        improvements.append('Added ion charge data')
                    
                    if improvements:
                        stats['improvements'].append({
                            'compound': new_row['compound_name'],
                            'improvements': improvements
                        })
                        stats['updated_compounds'] += 1
                    
                    # Check for conflicts
                    conflicts = []
                    
                    # Molecular weight conflicts (>5% difference)
                    try:
                        new_mw = float(new_row['molecular_weight'])
                        existing_mw = float(existing_row['molecular_weight'])
                        if abs(new_mw - existing_mw) / existing_mw > 0.05:
                            conflicts.append(f'MW: {existing_mw} vs {new_mw}')
                    except (ValueError, TypeError):
                        pass
                    
                    if conflicts:
                        stats['conflicts'].append({
                            'compound': new_row['compound_name'],
                            'conflicts': conflicts
                        })
            
            logger.info(f"Database comparison completed:")
            logger.info(f"  New compounds: {stats['new_compounds']}")
            logger.info(f"  Updated compounds: {stats['updated_compounds']}")
            logger.info(f"  Conflicts: {len(stats['conflicts'])}")
            logger.info(f"  Improvements: {len(stats['improvements'])}")
            
        except Exception as e:
            logger.error(f"Failed to compare databases: {e}")
        
        return stats

def main():
    """Test the TSV generator."""
    # Create test data
    test_compounds = [
        ProcessedChemicalProperties(
            compound_name="test_glucose",
            molecular_weight=180.16,
            pka_values=[],
            charge_states=[0],
            ion_charges={},
            solubility_g_per_L=909.0,
            activity_coefficient=1.0,
            description="Test glucose from PubChem CID:5793",
            formula="C6H12O6",
            source="pubchem_cid_5793"
        ),
        ProcessedChemicalProperties(
            compound_name="test_glycine",
            molecular_weight=75.07,
            pka_values=[2.34, 9.60],
            charge_states=[-1, 0, 1],
            ion_charges={'COO-': -1, 'NH3+': 1},
            solubility_g_per_L=249.9,
            activity_coefficient=1.0,
            description="Test glycine from PubChem CID:750",
            formula="C2H5NO2",
            source="pubchem_cid_750"
        )
    ]
    
    # Generate TSV
    generator = PubChemTSVGenerator()
    output_file = Path("test_pubchem_chemical_properties.tsv")
    
    generator.generate_tsv_from_processed_data(test_compounds, output_file, merge_with_existing=False)
    
    # Validate the generated file
    is_valid = generator.validate_tsv_format(output_file)
    print(f"Generated TSV is valid: {is_valid}")
    
    # Clean up
    if output_file.exists():
        output_file.unlink()

if __name__ == "__main__":
    main()