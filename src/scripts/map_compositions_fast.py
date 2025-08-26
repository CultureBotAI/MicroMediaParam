#!/usr/bin/env python3

import pandas as pd
import re
import json
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from fuzzywuzzy import fuzz
import logging
from collections import defaultdict
import time

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('composition_mapping_fast.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class FastCompositionKGMapper:
    def __init__(self, 
                 kg_nodes_file: str = "/Users/marcin/Documents/VIMSS/ontology/KG-Hub/KG-Microbe/kg-microbe/data/merged/20250222/merged-kg_nodes.tsv",
                 kg_edges_file: str = "/Users/marcin/Documents/VIMSS/ontology/KG-Hub/KG-Microbe/kg-microbe/data/merged/20250222/merged-kg_edges.tsv",
                 json_dir: str = "media_pdfs",
                 output_file: str = "composition_kg_mapping_fast.tsv",
                 comparison_file: str = "mapping_comparison_fast.tsv",
                 max_files: int = None):
        
        self.kg_nodes_file = kg_nodes_file
        self.kg_edges_file = kg_edges_file
        self.json_dir = Path(json_dir)
        self.output_file = output_file
        self.comparison_file = comparison_file
        self.max_files = max_files
        
        # Progress tracking
        self.start_time = time.time()
        
        # Load KG data efficiently
        self._load_kg_data()
        
        # Results storage
        self.results = []
        
    def _log_progress(self, message: str):
        """Log progress with timing information."""
        elapsed = time.time() - self.start_time
        logger.info(f"[{elapsed:.1f}s] {message}")
    
    def _load_kg_data(self):
        """Load KG data with progress reporting."""
        self._log_progress("Starting KG data loading...")
        
        # Load nodes
        self._log_progress("Loading nodes file...")
        nodes_df = pd.read_csv(self.kg_nodes_file, sep='\t', low_memory=False)
        self._log_progress(f"Loaded {len(nodes_df)} nodes")
        
        # Filter chemical entities
        self._log_progress("Filtering chemical entities...")
        self.chemical_nodes = nodes_df[
            nodes_df['category'].str.contains('ChemicalEntity|ChemicalSubstance', na=False)
        ].copy()
        self._log_progress(f"Found {len(self.chemical_nodes)} chemical entities")
        
        # Build lookup dictionaries with progress
        self._log_progress("Building chemical name lookups...")
        self.name_to_id = {}
        self.synonym_to_id = {}
        
        total_chemicals = len(self.chemical_nodes)
        for i, (_, row) in enumerate(self.chemical_nodes.iterrows()):
            if i % 50000 == 0:
                self._log_progress(f"Processing chemical {i+1}/{total_chemicals}")
                
            node_id = row['id']
            name = row.get('name', '')
            synonyms = row.get('synonym', '')
            
            if pd.notna(name) and name.strip():
                self.name_to_id[name.lower().strip()] = node_id
            
            if pd.notna(synonyms) and synonyms.strip():
                synonym_list = [s.strip() for s in synonyms.split('|') if s.strip()]
                for synonym in synonym_list:
                    self.synonym_to_id[synonym.lower().strip()] = node_id
        
        self._log_progress(f"Built lookups: {len(self.name_to_id)} names, {len(self.synonym_to_id)} synonyms")
        
        # Load medium nodes
        self._log_progress("Finding medium nodes...")
        self.medium_nodes = nodes_df[nodes_df['id'].str.startswith('medium:', na=False)].copy()
        self._log_progress(f"Found {len(self.medium_nodes)} medium nodes")
        
        # Load edges with progress
        self._log_progress("Loading edges file...")
        edges_df = pd.read_csv(self.kg_edges_file, sep='\t', low_memory=False)
        self._log_progress(f"Loaded {len(edges_df)} edges")
        
        # Build medium mappings
        self._log_progress("Building medium->component mappings...")
        self._build_medium_mappings(edges_df)
        
        self._log_progress("KG data loading completed!")
    
    def _build_medium_mappings(self, edges_df: pd.DataFrame):
        """Build medium to component mappings."""
        # Find medium -> solution edges
        self._log_progress("Finding medium -> solution edges...")
        medium_solution_edges = edges_df[
            (edges_df['subject'].str.startswith('medium:', na=False)) &
            (edges_df['predicate'] == 'biolink:has_part') &
            (edges_df['object'].str.startswith('solution:', na=False))
        ]
        self._log_progress(f"Found {len(medium_solution_edges)} medium -> solution edges")
        
        # Find solution -> chemical edges  
        self._log_progress("Finding solution -> chemical edges...")
        solution_chemical_edges = edges_df[
            (edges_df['subject'].str.startswith('solution:', na=False)) &
            (edges_df['predicate'] == 'biolink:has_part') &
            (edges_df['object'].str.contains('CHEBI:|CAS-RN:|PubChem:', na=False))
        ]
        self._log_progress(f"Found {len(solution_chemical_edges)} solution -> chemical edges")
        
        # Build solution mappings
        self._log_progress("Building solution mappings...")
        solution_to_components = defaultdict(set)
        for _, edge in solution_chemical_edges.iterrows():
            solution_to_components[edge['subject']].add(edge['object'])
        
        # Build medium mappings
        self._log_progress("Building medium mappings...")
        self.medium_to_components = defaultdict(set)
        
        for _, edge in medium_solution_edges.iterrows():
            medium_id = edge['subject']
            solution_id = edge['object']
            if solution_id in solution_to_components:
                self.medium_to_components[medium_id].update(solution_to_components[solution_id])
        
        # Add direct medium -> chemical edges
        direct_edges = edges_df[
            (edges_df['subject'].str.startswith('medium:', na=False)) &
            (edges_df['predicate'] == 'biolink:has_part') &
            (edges_df['object'].str.contains('CHEBI:|CAS-RN:|PubChem:', na=False))
        ]
        
        for _, edge in direct_edges.iterrows():
            self.medium_to_components[edge['subject']].add(edge['object'])
        
        total_mappings = sum(len(comps) for comps in self.medium_to_components.values())
        self._log_progress(f"Built mappings for {len(self.medium_to_components)} media, {total_mappings} total component relationships")
    
    def _find_best_match_string(self, compound_name: str) -> Optional[str]:
        """Fast string matching - exact matches only to avoid slow fuzzy matching."""
        if not compound_name or compound_name.lower() in ['distilled water', 'water']:
            return None
        
        compound_lower = compound_name.lower().strip()
        
        # Try exact matches only (no fuzzy matching for speed)
        if compound_lower in self.name_to_id:
            return self.name_to_id[compound_lower]
        
        if compound_lower in self.synonym_to_id:
            return self.synonym_to_id[compound_lower]
        
        return None
    
    def _find_best_match_medium(self, compound_name: str, medium_id: str) -> Optional[str]:
        """Medium-based matching with limited fuzzy search."""
        if not compound_name or compound_name.lower() in ['distilled water', 'water']:
            return None
        
        medium_node_id = f"medium:{medium_id}"
        
        if medium_node_id not in self.medium_to_components:
            return None
        
        medium_chemicals = self.medium_to_components[medium_node_id]
        compound_lower = compound_name.lower().strip()
        
        # First try exact matches within the medium
        for chemical_id in medium_chemicals:
            chemical_info = self.chemical_nodes[self.chemical_nodes['id'] == chemical_id]
            
            if chemical_info.empty:
                continue
            
            chemical_row = chemical_info.iloc[0]
            name = chemical_row.get('name', '')
            synonyms = chemical_row.get('synonym', '')
            
            # Exact name match
            if pd.notna(name) and name.strip():
                if compound_lower == name.lower().strip():
                    return chemical_id
            
            # Exact synonym match
            if pd.notna(synonyms) and synonyms.strip():
                synonym_list = [s.strip().lower() for s in synonyms.split('|') if s.strip()]
                if compound_lower in synonym_list:
                    return chemical_id
        
        # If no exact match, try limited fuzzy matching only within this medium
        best_id = None
        best_score = 0
        
        # Only try fuzzy matching if the medium has a reasonable number of components
        if len(medium_chemicals) <= 100:  # Limit fuzzy search to avoid performance issues
            for chemical_id in medium_chemicals:
                chemical_info = self.chemical_nodes[self.chemical_nodes['id'] == chemical_id]
                
                if chemical_info.empty:
                    continue
                
                chemical_row = chemical_info.iloc[0]
                name = chemical_row.get('name', '')
                
                if pd.notna(name) and name.strip():
                    score = fuzz.ratio(compound_lower, name.lower().strip())
                    if score > best_score and score >= 90:  # Higher threshold for fuzzy
                        best_score = score
                        best_id = chemical_id
        
        return best_id
    
    def _process_composition_files(self):
        """Process composition files with detailed progress reporting."""
        self._log_progress("Starting composition file processing...")
        
        json_files = list(self.json_dir.glob("*_composition.json"))
        
        if self.max_files:
            json_files = json_files[:self.max_files]
        
        total_files = len(json_files)
        self._log_progress(f"Found {total_files} JSON composition files to process")
        
        files_processed = 0
        compounds_processed = 0
        
        for i, json_file in enumerate(json_files):
            # Progress reporting every 50 files
            if i % 50 == 0:
                self._log_progress(f"Processing file {i+1}/{total_files} ({files_processed} completed, {compounds_processed} compounds)")
            
            medium_match = re.search(r'medium_([^_]+)_composition\.json', json_file.name)
            medium_id = medium_match.group(1) if medium_match else json_file.stem.replace('_composition', '')
            
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                file_compounds = 0
                
                if isinstance(data, list):
                    for component in data:
                        if isinstance(component, dict):
                            compound = component.get('compound', '')
                            if not compound or compound.lower() in ['distilled water', 'water']:
                                continue
                            
                            compounds_processed += 1
                            file_compounds += 1
                            
                            # Method 1: Fast string matching
                            kg_id_string = self._find_best_match_string(compound)
                            
                            # Method 2: Medium-based matching
                            kg_id_medium = self._find_best_match_medium(compound, medium_id)
                            
                            result = {
                                'medium_id': medium_id,
                                'original': compound,
                                'mapped_string': kg_id_string or '',
                                'mapped_medium': kg_id_medium or '',
                                'value': component.get('g_l', ''),
                                'concentration': '',
                                'unit': 'g/L',
                                'mmol_l': component.get('mmol_l', ''),
                                'optional': component.get('optional', ''),
                                'source': 'json'
                            }
                            
                            self.results.append(result)
                
                files_processed += 1
                
                # Log progress for large files
                if file_compounds > 20:
                    self._log_progress(f"File {json_file.name}: {file_compounds} compounds")
                
            except Exception as e:
                self._log_progress(f"Error processing {json_file.name}: {e}")
                continue
        
        self._log_progress(f"Completed processing {files_processed} files, {compounds_processed} total compounds")
    
    def _save_results(self):
        """Save results with progress reporting."""
        self._log_progress("Saving results...")
        
        if not self.results:
            logger.warning("No results to save")
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
        
        # Save files
        main_columns = ['medium_id', 'original', 'mapped', 'value', 'concentration', 
                       'unit', 'mmol_l', 'optional', 'mapping_method', 'source']
        df_output[main_columns].to_csv(self.output_file, sep='\t', index=False)
        
        comparison_columns = ['medium_id', 'original', 'mapped_string', 'mapped_medium', 
                             'value', 'unit', 'mmol_l', 'optional', 'source']
        df[comparison_columns].to_csv(self.comparison_file, sep='\t', index=False)
        
        # Generate statistics
        total = len(df)
        string_mapped = len(df[df['mapped_string'] != ''])
        medium_mapped = len(df[df['mapped_medium'] != ''])
        both_mapped = len(df[(df['mapped_string'] != '') & (df['mapped_medium'] != '')])
        agreement = len(df[(df['mapped_string'] == df['mapped_medium']) & (df['mapped_string'] != '')])
        final_mapped = len(df_output[df_output['mapped'] != ''])
        
        agreement_pct = agreement/both_mapped*100 if both_mapped > 0 else 0
        
        self._log_progress(f"""
=== MAPPING RESULTS ===
Total entries: {total}
String method: {string_mapped} ({string_mapped/total*100:.1f}%)
Medium method: {medium_mapped} ({medium_mapped/total*100:.1f}%)
Both methods: {both_mapped}
Agreement: {agreement}/{both_mapped} ({agreement_pct:.1f}%)
Final mapped: {final_mapped} ({final_mapped/total*100:.1f}%)
        """)
        
        # Show some examples of successful mappings
        successful = df_output[df_output['mapped'] != ''].head(10)
        if not successful.empty:
            self._log_progress("Sample successful mappings:")
            for _, row in successful.iterrows():
                self._log_progress(f"  {row['original']} -> {row['mapped']} (method: {row['mapping_method']})")
        
        self._log_progress(f"Results saved to {self.output_file} and {self.comparison_file}")
    
    def run_mapping(self):
        """Run the fast mapping process."""
        self._log_progress("Starting fast composition to KG mapping...")
        
        self._process_composition_files()
        self._save_results()
        
        total_time = time.time() - self.start_time
        self._log_progress(f"Mapping completed in {total_time:.1f} seconds!")

def main():
    # Process a subset first to test performance
    mapper = FastCompositionKGMapper(max_files=100)  # Limit to first 100 files for testing
    mapper.run_mapping()

if __name__ == "__main__":
    main()