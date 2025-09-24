#!/usr/bin/env python3
"""
Expand solution: references in the mapping data with their constituent chemical ingredients.
"""

import pandas as pd
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
import argparse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SolutionExpander:
    def __init__(self, solution_compositions_dir: str = "solution_compositions"):
        self.solution_compositions_dir = Path(solution_compositions_dir)
        self.solution_data = {}
        self.load_solution_compositions()
    
    def load_solution_compositions(self):
        """Load all solution composition data."""
        
        if not self.solution_compositions_dir.exists():
            logger.warning(f"Solution compositions directory not found: {self.solution_compositions_dir}")
            return
        
        composition_files = list(self.solution_compositions_dir.glob("solution_*_composition.json"))
        logger.info(f"Loading {len(composition_files)} solution compositions...")
        
        for comp_file in composition_files:
            try:
                with open(comp_file, 'r') as f:
                    data = json.load(f)
                
                solution_id = data['solution_id']
                self.solution_data[solution_id] = data
                logger.debug(f"Loaded solution {solution_id}: {len(data['composition'])} components")
                
            except Exception as e:
                logger.error(f"Failed to load {comp_file}: {e}")
        
        logger.info(f"Successfully loaded {len(self.solution_data)} solution compositions")
    
    def expand_mapping_data(self, input_file: str, output_file: str):
        """Expand solution references in mapping data to individual chemical components."""
        
        logger.info(f"Loading mapping data from: {input_file}")
        df = pd.read_csv(input_file, sep='\t')
        
        # Find solution entries
        solution_entries = df[df['mapped'].str.startswith('solution:', na=False)].copy()
        logger.info(f"Found {len(solution_entries)} solution entries to expand")
        
        if len(solution_entries) == 0:
            logger.info("No solution entries found. Copying original file.")
            df.to_csv(output_file, sep='\t', index=False)
            return
        
        # Track expansion statistics
        expansion_stats = {
            'solutions_found': 0,
            'solutions_expanded': 0,
            'total_components_added': 0,
            'failed_expansions': []
        }
        
        # Process each unique solution
        unique_solutions = solution_entries['mapped'].unique()
        logger.info(f"Processing {len(unique_solutions)} unique solutions...")
        
        expanded_rows = []
        
        for solution_ref in unique_solutions:
            solution_id = solution_ref.replace('solution:', '')
            expansion_stats['solutions_found'] += 1
            
            if solution_id not in self.solution_data:
                logger.warning(f"Solution {solution_id} composition not available")
                expansion_stats['failed_expansions'].append(solution_id)
                continue
            
            solution_info = self.solution_data[solution_id]
            solution_name = solution_info['solution_name']
            components = solution_info['composition']
            
            if not components:
                logger.warning(f"Solution {solution_id} has no components")
                expansion_stats['failed_expansions'].append(solution_id)
                continue
            
            logger.info(f"Expanding solution {solution_id} ({solution_name}) with {len(components)} components")
            expansion_stats['solutions_expanded'] += 1
            expansion_stats['total_components_added'] += len(components)
            
            # Get all entries for this solution
            solution_rows = solution_entries[solution_entries['mapped'] == solution_ref]
            
            for _, solution_row in solution_rows.iterrows():
                # For each component in the solution, create a new row
                for component in components:
                    new_row = solution_row.copy()
                    
                    # Update key fields for the component
                    component_name = component['name']
                    new_row['original'] = f"{solution_name} → {component_name}"
                    new_row['mapped'] = ''  # Will need mapping
                    new_row['base_compound'] = component_name
                    new_row['base_formula'] = component_name.replace(' ', '')
                    new_row['water_molecules'] = 0
                    new_row['hydrate_formula'] = component_name.replace(' ', '')
                    new_row['base_chebi_id'] = ''
                    new_row['base_chebi_label'] = ''
                    new_row['base_chebi_formula'] = ''
                    new_row['hydration_state'] = 'anhydrous'
                    new_row['hydration_parsing_method'] = 'solution_expansion'
                    new_row['hydration_confidence'] = 'high'
                    
                    # Handle concentration scaling
                    solution_concentration = solution_row.get('value', 0) or 0
                    solution_unit = solution_row.get('unit', '') or ''
                    component_concentration = component.get('concentration', 0)
                    component_unit = component.get('unit', '')
                    
                    # Calculate scaled concentration
                    try:
                        scaled_concentration = self.calculate_scaled_concentration(
                            solution_concentration, solution_unit,
                            component_concentration, component_unit
                        )
                        new_row['value'] = scaled_concentration
                        new_row['unit'] = component_unit
                    except Exception as e:
                        logger.debug(f"Concentration scaling failed for {component_name}: {e}")
                        new_row['value'] = component_concentration
                        new_row['unit'] = component_unit
                    
                    # Add source information
                    new_row['source'] = 'solution_expansion'
                    new_row['base_compound_for_mapping'] = component_name
                    
                    expanded_rows.append(new_row)
        
        # Remove original solution entries and add expanded components
        non_solution_entries = df[~df['mapped'].str.startswith('solution:', na=False)]
        expanded_df = pd.DataFrame(expanded_rows)
        
        if len(expanded_rows) > 0:
            final_df = pd.concat([non_solution_entries, expanded_df], ignore_index=True)
        else:
            final_df = non_solution_entries
        
        # Save expanded dataset
        final_df.to_csv(output_file, sep='\t', index=False)
        
        # Log statistics
        logger.info(f"\n=== SOLUTION EXPANSION SUMMARY ===")
        logger.info(f"Original entries: {len(df):,}")
        logger.info(f"Solution entries found: {len(solution_entries):,}")
        logger.info(f"Solutions available for expansion: {expansion_stats['solutions_found']}")
        logger.info(f"Solutions successfully expanded: {expansion_stats['solutions_expanded']}")
        logger.info(f"Total components added: {expansion_stats['total_components_added']:,}")
        logger.info(f"Final dataset size: {len(final_df):,}")
        logger.info(f"Net change: {len(final_df) - len(df):+,} entries")
        
        if expansion_stats['failed_expansions']:
            logger.warning(f"Failed to expand solutions: {expansion_stats['failed_expansions']}")
        
        logger.info(f"✓ Expanded dataset saved to: {output_file}")
        
        return final_df
    
    def calculate_scaled_concentration(self, solution_conc: float, solution_unit: str,
                                     component_conc: float, component_unit: str) -> float:
        """Calculate the scaled concentration of a component in the final medium."""
        
        if not solution_conc or not component_conc:
            return component_conc
        
        # Simple scaling for now - can be enhanced with unit conversions
        # Assume solution is used as specified, so scale component concentration accordingly
        
        # If solution is used in ml/L and component is in g/L, need to scale
        if 'ml' in solution_unit.lower() and solution_unit.lower().endswith('/l'):
            # Convert ml/L to fraction
            scale_factor = solution_conc / 1000.0  # ml to L fraction
            return component_conc * scale_factor
        
        elif 'g' in solution_unit.lower() and solution_unit.lower().endswith('/l'):
            # If both in g/L, assume solution has density ~1 g/ml
            # This is approximate and may need refinement
            scale_factor = solution_conc / 1000.0  # Rough approximation
            return component_conc * scale_factor
        
        else:
            # Default: use component concentration as-is
            return component_conc
    
    def create_expansion_report(self, output_file: str = "solution_expansion_report.json"):
        """Create a report of available solutions and their components."""
        
        report = {
            'total_solutions': len(self.solution_data),
            'solutions': {},
            'summary_statistics': {
                'total_components': 0,
                'avg_components_per_solution': 0,
                'solutions_by_component_count': {}
            }
        }
        
        total_components = 0
        component_counts = {}
        
        for solution_id, data in self.solution_data.items():
            num_components = len(data['composition'])
            total_components += num_components
            
            # Count distribution
            count_bucket = f"{(num_components // 10) * 10}-{(num_components // 10) * 10 + 9}"
            component_counts[count_bucket] = component_counts.get(count_bucket, 0) + 1
            
            report['solutions'][solution_id] = {
                'name': data['solution_name'],
                'component_count': num_components,
                'components': [comp['name'] for comp in data['composition'][:10]]  # First 10 for preview
            }
        
        if len(self.solution_data) > 0:
            report['summary_statistics']['total_components'] = total_components
            report['summary_statistics']['avg_components_per_solution'] = total_components / len(self.solution_data)
            report['summary_statistics']['solutions_by_component_count'] = component_counts
        
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Solution expansion report saved to: {output_file}")
        return report

def main():
    parser = argparse.ArgumentParser(description="Expand solution references to chemical components")
    parser.add_argument("--input", required=True, help="Input TSV mapping file")
    parser.add_argument("--output", required=True, help="Output TSV mapping file with expanded solutions")
    parser.add_argument("--compositions-dir", default="solution_compositions", help="Directory with solution compositions")
    parser.add_argument("--report", action="store_true", help="Generate expansion report")
    
    args = parser.parse_args()
    
    expander = SolutionExpander(args.compositions_dir)
    
    if args.report:
        expander.create_expansion_report()
    
    if Path(args.input).exists():
        expander.expand_mapping_data(args.input, args.output)
    else:
        logger.error(f"Input file not found: {args.input}")

if __name__ == "__main__":
    main()