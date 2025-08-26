#!/usr/bin/env python3

import pandas as pd
import re
import json
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
import logging
from collections import defaultdict
import time

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class DemoCompositionKGMapper:
    def __init__(self, 
                 kg_nodes_file: str = "/Users/marcin/Documents/VIMSS/ontology/KG-Hub/KG-Microbe/kg-microbe/data/merged/20250222/merged-kg_nodes.tsv",
                 kg_edges_file: str = "/Users/marcin/Documents/VIMSS/ontology/KG-Hub/KG-Microbe/kg-microbe/data/merged/20250222/merged-kg_edges.tsv",
                 json_dir: str = "media_pdfs",
                 output_file: str = "composition_kg_mapping_demo.tsv",
                 comparison_file: str = "mapping_comparison_demo.tsv",
                 max_files: int = 10):
        
        self.start_time = time.time()
        self.max_files = max_files
        self.json_dir = Path(json_dir)
        self.output_file = output_file
        self.comparison_file = comparison_file
        self.kg_nodes_file = kg_nodes_file
        self.kg_edges_file = kg_edges_file
        
        # Load minimal KG data for demo
        self._load_demo_kg_data()
        
        self.results = []
        
    def _log_progress(self, message: str):
        """Log progress with timing information."""
        elapsed = time.time() - self.start_time
        logger.info(f"[{elapsed:.1f}s] {message}")
    
    def _normalize_name(self, name: str) -> str:
        """Simple name normalization."""
        if pd.isna(name) or name == "":
            return ""
        
        normalized = name.lower().strip()
        # Remove hydration
        normalized = re.sub(r'\s*x\s*\d+\s*h2o', '', normalized)
        normalized = re.sub(r'\s*•\s*\d+\s*h2o', '', normalized)
        # Remove parentheses
        normalized = re.sub(r'\([^)]*\)', '', normalized)
        return normalized.strip()
    
    def _is_relevant_node(self, category: str, node_id: str) -> bool:
        """Check if node is relevant for mapping."""
        if pd.isna(category):
            return False
        
        category_lower = category.lower()
        
        # Chemical entities and substances
        if 'chemicalentity' in category_lower or 'chemicalsubstance' in category_lower:
            return True
        
        # Specific node types
        if pd.notna(node_id) and isinstance(node_id, str):
            if node_id.startswith(('solution:', 'ingredient:', 'medium:')):
                return True
        
        return False
    
    def _load_demo_kg_data(self):
        """Load a sample of KG data for demonstration."""
        self._log_progress("Loading demo KG data...")
        
        # Load nodes in smaller chunks for demo
        self._log_progress("Loading relevant nodes sample...")
        nodes_df = pd.read_csv(self.kg_nodes_file, sep='\t', nrows=200000)  # Limit for demo
        
        # Filter relevant nodes
        relevant_mask = nodes_df.apply(
            lambda row: self._is_relevant_node(row.get('category', ''), row.get('id', '')), 
            axis=1
        )
        self.relevant_nodes = nodes_df[relevant_mask].copy()
        
        self._log_progress(f"Found {len(self.relevant_nodes)} relevant entities in sample")
        
        # Build lookups
        self._log_progress("Building lookups...")
        self.name_to_id = {}
        self.synonym_to_id = {}
        
        for _, row in self.relevant_nodes.iterrows():
            node_id = row['id']
            name = row.get('name', '')
            synonyms = row.get('synonym', '')
            
            if pd.notna(name) and name.strip():
                self.name_to_id[name.lower().strip()] = node_id
                # Also normalized
                norm_name = self._normalize_name(name)
                if norm_name:
                    self.name_to_id[norm_name] = node_id
            
            if pd.notna(synonyms) and synonyms.strip():
                for syn in synonyms.split('|'):
                    if syn.strip():
                        self.synonym_to_id[syn.lower().strip()] = node_id
                        # Also normalized
                        norm_syn = self._normalize_name(syn.strip())
                        if norm_syn:
                            self.synonym_to_id[norm_syn] = node_id
        
        self._log_progress(f"Built lookups: {len(self.name_to_id)} names, {len(self.synonym_to_id)} synonyms")
        
        # Load sample of medium mappings
        self._log_progress("Loading sample medium mappings...")
        edges_df = pd.read_csv(self.kg_edges_file, sep='\t', nrows=500000)  # Limit for demo
        
        # Find medium->solution edges
        medium_solution_edges = edges_df[
            (edges_df['subject'].str.startswith('medium:', na=False)) &
            (edges_df['predicate'] == 'biolink:has_part') &
            (edges_df['object'].str.startswith('solution:', na=False))
        ]
        
        # Find solution->component edges
        solution_component_edges = edges_df[
            (edges_df['subject'].str.startswith('solution:', na=False)) &
            (edges_df['predicate'] == 'biolink:has_part')
        ]
        
        # Build mappings
        solution_to_components = defaultdict(set)
        for _, edge in solution_component_edges.iterrows():
            solution_to_components[edge['subject']].add(edge['object'])
        
        self.medium_to_components = defaultdict(set)
        for _, edge in medium_solution_edges.iterrows():
            medium_id = edge['subject']
            solution_id = edge['object']
            if solution_id in solution_to_components:
                self.medium_to_components[medium_id].update(solution_to_components[solution_id])
        
        self._log_progress(f"Built mappings for {len(self.medium_to_components)} media (sample)")
        
        # Show some examples
        node_types = self.relevant_nodes['category'].value_counts().head(5)
        self._log_progress("Sample node types:")
        for node_type, count in node_types.items():
            self._log_progress(f"  {node_type}: {count}")
    
    def _find_match_string(self, compound_name: str) -> Optional[str]:
        """Find string match."""
        if not compound_name:
            return None
        
        compound_lower = compound_name.lower().strip()
        normalized = self._normalize_name(compound_name)
        
        if compound_lower in self.name_to_id:
            return self.name_to_id[compound_lower]
        
        if compound_lower in self.synonym_to_id:
            return self.synonym_to_id[compound_lower]
        
        if normalized in self.name_to_id:
            return self.name_to_id[normalized]
        
        if normalized in self.synonym_to_id:
            return self.synonym_to_id[normalized]
        
        return None
    
    def _find_match_medium(self, compound_name: str, medium_id: str) -> Optional[str]:
        """Find medium-based match."""
        if not compound_name:
            return None
        
        medium_node_id = f"medium:{medium_id}"
        if medium_node_id not in self.medium_to_components:
            return None
        
        compound_lower = compound_name.lower().strip()
        normalized = self._normalize_name(compound_name)
        
        # Check if any component in this medium matches
        for component_id in self.medium_to_components[medium_node_id]:
            component_info = self.relevant_nodes[self.relevant_nodes['id'] == component_id]
            
            if component_info.empty:
                continue
            
            component_row = component_info.iloc[0]
            name = component_row.get('name', '')
            
            if pd.notna(name) and name.strip():
                if compound_lower == name.lower().strip():
                    return component_id
                if normalized and normalized == self._normalize_name(name):
                    return component_id
        
        return None
    
    def _process_demo_files(self):
        """Process a small number of files for demonstration."""
        self._log_progress("Processing demo composition files...")
        
        json_files = list(self.json_dir.glob("*_composition.json"))[:self.max_files]
        
        self._log_progress(f"Processing {len(json_files)} demo files")
        
        for i, json_file in enumerate(json_files):
            self._log_progress(f"Processing file {i+1}/{len(json_files)}: {json_file.name}")
            
            medium_match = re.search(r'medium_([^_]+)_composition\.json', json_file.name)
            medium_id = medium_match.group(1) if medium_match else json_file.stem.replace('_composition', '')
            
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                compounds_in_file = 0
                
                if isinstance(data, list):
                    for component in data[:5]:  # Limit to first 5 compounds per file
                        if isinstance(component, dict):
                            compound = component.get('compound', '')
                            if not compound or compound.lower() in ['distilled water', 'water']:
                                continue
                            
                            compounds_in_file += 1
                            
                            # Try both methods
                            string_match = self._find_match_string(compound)
                            medium_match = self._find_match_medium(compound, medium_id)
                            
                            # Determine entity types
                            string_type = ''
                            medium_type = ''
                            
                            if string_match:
                                if string_match.startswith('CHEBI:'):
                                    string_type = 'CHEBI'
                                elif string_match.startswith('solution:'):
                                    string_type = 'solution'
                                elif string_match.startswith('ingredient:'):
                                    string_type = 'ingredient'
                                else:
                                    string_type = string_match.split(':')[0] if ':' in string_match else 'other'
                            
                            if medium_match:
                                if medium_match.startswith('CHEBI:'):
                                    medium_type = 'CHEBI'
                                elif medium_match.startswith('solution:'):
                                    medium_type = 'solution'
                                elif medium_match.startswith('ingredient:'):
                                    medium_type = 'ingredient'
                                else:
                                    medium_type = medium_match.split(':')[0] if ':' in medium_match else 'other'
                            
                            result = {
                                'medium_id': medium_id,
                                'original': compound,
                                'mapped_string': string_match or '',
                                'mapped_medium': medium_match or '',
                                'string_entity_type': string_type,
                                'medium_entity_type': medium_type,
                                'value': component.get('g_l', ''),
                                'concentration': '',
                                'unit': 'g/L',
                                'mmol_l': component.get('mmol_l', ''),
                                'optional': component.get('optional', ''),
                                'source': 'json'
                            }
                            
                            self.results.append(result)
                
                self._log_progress(f"  Found {compounds_in_file} compounds in {json_file.name}")
                
            except Exception as e:
                self._log_progress(f"Error processing {json_file.name}: {e}")
        
        self._log_progress(f"Processed {len(json_files)} files, {len(self.results)} total compounds")
    
    def _save_demo_results(self):
        """Save demonstration results."""
        self._log_progress("Saving demo results...")
        
        if not self.results:
            self._log_progress("No results to save")
            return
        
        df = pd.DataFrame(self.results)
        
        # Create main output
        df_output = df.copy()
        df_output['mapped'] = df_output.apply(
            lambda row: row['mapped_medium'] if row['mapped_medium'] else row['mapped_string'], 
            axis=1
        )
        df_output['mapping_method'] = df_output.apply(
            lambda row: 'medium' if row['mapped_medium'] else ('string' if row['mapped_string'] else 'none'),
            axis=1
        )
        df_output['entity_type'] = df_output.apply(
            lambda row: row['medium_entity_type'] if row['mapped_medium'] else row['string_entity_type'],
            axis=1
        )
        
        # Save results
        main_columns = ['medium_id', 'original', 'mapped', 'value', 'concentration', 
                       'unit', 'mmol_l', 'optional', 'mapping_method', 'entity_type', 'source']
        df_output[main_columns].to_csv(self.output_file, sep='\t', index=False)
        
        comparison_columns = ['medium_id', 'original', 'mapped_string', 'mapped_medium', 
                             'string_entity_type', 'medium_entity_type', 'value', 'unit', 'mmol_l', 'optional', 'source']
        df[comparison_columns].to_csv(self.comparison_file, sep='\t', index=False)
        
        # Statistics
        total = len(df)
        string_mapped = len(df[df['mapped_string'] != ''])
        medium_mapped = len(df[df['mapped_medium'] != ''])
        both_mapped = len(df[(df['mapped_string'] != '') & (df['mapped_medium'] != '')])
        agreement = len(df[(df['mapped_string'] == df['mapped_medium']) & (df['mapped_string'] != '')])
        final_mapped = len(df_output[df_output['mapped'] != ''])
        
        self._log_progress(f"""
=== DEMO MAPPING RESULTS ===
Total compound entries: {total}

STRING MATCHING:
  Successfully mapped: {string_mapped} ({string_mapped/total*100:.1f}%)

MEDIUM-BASED MATCHING:
  Successfully mapped: {medium_mapped} ({medium_mapped/total*100:.1f}%)

COMPARISON:
  Both methods found: {both_mapped}
  Methods agree: {agreement} ({agreement/both_mapped*100 if both_mapped > 0 else 0:.1f}%)
  Final mapped: {final_mapped} ({final_mapped/total*100:.1f}%)
        """)
        
        # Show entity type distribution
        if final_mapped > 0:
            entity_types = df_output[df_output['mapped'] != '']['entity_type'].value_counts()
            self._log_progress("Entity type distribution:")
            for etype, count in entity_types.items():
                self._log_progress(f"  {etype}: {count}")
        
        # Show examples
        successful = df_output[df_output['mapped'] != ''].head(10)
        if not successful.empty:
            self._log_progress("\nSuccessful mappings:")
            for _, row in successful.iterrows():
                self._log_progress(f"  '{row['original']}' -> {row['mapped']} ({row['entity_type']}, {row['mapping_method']})")
        
        # Show disagreements
        disagreements = df[(df['mapped_string'] != df['mapped_medium']) & (df['mapped_string'] != '') & (df['mapped_medium'] != '')]
        if not disagreements.empty:
            self._log_progress("\nMethod disagreements:")
            for _, row in disagreements.iterrows():
                self._log_progress(f"  '{row['original']}': string={row['mapped_string']}, medium={row['mapped_medium']}")
        
        self._log_progress(f"Results saved to {self.output_file} and {self.comparison_file}")
    
    def run_demo(self):
        """Run the demonstration."""
        self._log_progress("Starting DEMO composition to KG mapping...")
        
        self._process_demo_files()
        self._save_demo_results()
        
        total_time = time.time() - self.start_time
        self._log_progress(f"Demo mapping completed in {total_time:.1f} seconds!")

def main():
    mapper = DemoCompositionKGMapper(max_files=10)
    mapper.run_demo()

if __name__ == "__main__":
    main()