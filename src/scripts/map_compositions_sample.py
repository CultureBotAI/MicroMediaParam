#!/usr/bin/env python3

import pandas as pd
import re
import json
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from fuzzywuzzy import fuzz
import logging
from collections import defaultdict
import random

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('composition_mapping_sample.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class SampleCompositionKGMapper:
    def __init__(self, 
                 kg_nodes_file: str = "/Users/marcin/Documents/VIMSS/ontology/KG-Hub/KG-Microbe/kg-microbe/data/merged/20250222/merged-kg_nodes.tsv",
                 kg_edges_file: str = "/Users/marcin/Documents/VIMSS/ontology/KG-Hub/KG-Microbe/kg-microbe/data/merged/20250222/merged-kg_edges.tsv",
                 json_dir: str = "media_pdfs",
                 output_file: str = "composition_kg_mapping_sample.tsv",
                 comparison_file: str = "mapping_comparison_sample.tsv",
                 sample_size: int = 50):
        
        self.kg_nodes_file = kg_nodes_file
        self.kg_edges_file = kg_edges_file
        self.json_dir = Path(json_dir)
        self.output_file = output_file
        self.comparison_file = comparison_file
        self.sample_size = sample_size
        
        # Load and cache relevant KG data
        self._load_relevant_kg_data()
        
        # Results storage
        self.results = []
        
    def _load_relevant_kg_data(self):
        """Load only relevant parts of KG data for efficiency."""
        logger.info("Loading relevant KG data...")
        
        # Load nodes - focus on chemical entities and medium nodes
        logger.info("Loading nodes...")
        nodes_df = pd.read_csv(self.kg_nodes_file, sep='\t', low_memory=False)
        
        # Filter for relevant node types
        self.chemical_nodes = nodes_df[
            nodes_df['category'].str.contains('ChemicalEntity|ChemicalSubstance', na=False)
        ].copy()
        
        self.medium_nodes = nodes_df[
            nodes_df['id'].str.startswith('medium:', na=False)
        ].copy()
        
        logger.info(f"Loaded {len(self.chemical_nodes)} chemical nodes and {len(self.medium_nodes)} medium nodes")
        
        # Build chemical lookup dictionaries
        self.name_to_id = {}
        self.synonym_to_id = {}
        
        for _, row in self.chemical_nodes.iterrows():
            node_id = row['id']
            name = row.get('name', '')
            synonyms = row.get('synonym', '')
            
            if pd.notna(name) and name.strip():
                self.name_to_id[name.lower().strip()] = node_id
            
            if pd.notna(synonyms) and synonyms.strip():
                synonym_list = [s.strip() for s in synonyms.split('|') if s.strip()]
                for synonym in synonym_list:
                    self.synonym_to_id[synonym.lower().strip()] = node_id
        
        # Load edges - focus on medium composition relationships
        logger.info("Loading edges...")
        edges_df = pd.read_csv(self.kg_edges_file, sep='\t', low_memory=False)
        
        # Filter for medium composition edges
        medium_edges = edges_df[
            (edges_df['subject'].str.startswith('medium:', na=False)) &
            (edges_df['predicate'] == 'biolink:has_part')
        ].copy()
        
        solution_edges = edges_df[
            (edges_df['subject'].str.startswith('solution:', na=False)) &
            (edges_df['predicate'] == 'biolink:has_part') &
            (edges_df['object'].str.contains('CHEBI:|CAS-RN:|PubChem:', na=False))
        ].copy()
        
        logger.info(f"Found {len(medium_edges)} medium composition edges and {len(solution_edges)} solution composition edges")
        
        # Build medium to component mappings
        self.medium_to_components = defaultdict(set)
        solution_to_components = defaultdict(set)
        
        # Build solution -> chemical mappings
        for _, edge in solution_edges.iterrows():
            solution_id = edge['subject']
            chemical_id = edge['object']
            solution_to_components[solution_id].add(chemical_id)
        
        # Build medium -> chemical mappings (through solutions)
        medium_to_solutions = medium_edges[medium_edges['object'].str.startswith('solution:', na=False)]
        for _, edge in medium_to_solutions.iterrows():
            medium_id = edge['subject']
            solution_id = edge['object']
            if solution_id in solution_to_components:
                self.medium_to_components[medium_id].update(solution_to_components[solution_id])
        
        # Add direct medium -> chemical relationships
        direct_medium_chemical = medium_edges[medium_edges['object'].str.contains('CHEBI:|CAS-RN:|PubChem:', na=False)]
        for _, edge in direct_medium_chemical.iterrows():
            medium_id = edge['subject']
            chemical_id = edge['object']
            self.medium_to_components[medium_id].add(chemical_id)
        
        logger.info(f"Built mappings for {len(self.medium_to_components)} media")
    
    def _find_best_match_string(self, compound_name: str) -> Optional[str]:
        """Find the best matching KG node ID using string matching."""
        if not compound_name or compound_name.lower() in ['distilled water', 'water']:
            return None
        
        compound_lower = compound_name.lower().strip()
        
        # Try exact matches first
        if compound_lower in self.name_to_id:
            return self.name_to_id[compound_lower]
        
        if compound_lower in self.synonym_to_id:
            return self.synonym_to_id[compound_lower]
        
        # Try fuzzy matching (limited for performance)
        best_match = None
        best_score = 0
        best_id = None
        
        # Search through a subset of names for performance
        all_names = {**self.name_to_id, **self.synonym_to_id}
        
        for kg_name, kg_id in all_names.items():
            score = fuzz.ratio(compound_lower, kg_name)
            
            if score > best_score and score >= 85:  # Fixed threshold
                best_score = score
                best_match = kg_name
                best_id = kg_id
        
        return best_id
    
    def _find_best_match_medium(self, compound_name: str, medium_id: str) -> Optional[str]:
        """Find the best matching KG node ID using medium-based lookup."""
        if not compound_name or compound_name.lower() in ['distilled water', 'water']:
            return None
        
        medium_node_id = f"medium:{medium_id}"
        
        if medium_node_id not in self.medium_to_components:
            return None
        
        medium_chemicals = self.medium_to_components[medium_node_id]
        compound_lower = compound_name.lower().strip()
        
        # Try to match against chemical names in this medium
        best_match = None
        best_score = 0
        best_id = None
        
        for chemical_id in medium_chemicals:
            # Get chemical info
            chemical_info = self.chemical_nodes[self.chemical_nodes['id'] == chemical_id]
            
            if chemical_info.empty:
                continue
            
            chemical_row = chemical_info.iloc[0]
            name = chemical_row.get('name', '')
            synonyms = chemical_row.get('synonym', '')
            
            # Check name match
            if pd.notna(name) and name.strip():
                score = fuzz.ratio(compound_lower, name.lower().strip())
                if score > best_score and score >= 85:
                    best_score = score
                    best_match = name
                    best_id = chemical_id
            
            # Check synonym matches
            if pd.notna(synonyms) and synonyms.strip():
                synonym_list = [s.strip() for s in synonyms.split('|') if s.strip()]
                for synonym in synonym_list:
                    score = fuzz.ratio(compound_lower, synonym.lower().strip())
                    if score > best_score and score >= 85:
                        best_score = score
                        best_match = synonym
                        best_id = chemical_id
        
        return best_id
    
    def _process_sample_compositions(self):
        """Process a sample of composition files."""
        logger.info("Processing sample composition files...")
        
        json_files = list(self.json_dir.glob("*_composition.json"))
        sample_files = random.sample(json_files, min(self.sample_size, len(json_files)))
        
        logger.info(f"Processing {len(sample_files)} sample files out of {len(json_files)} total")
        
        for json_file in sample_files:
            medium_match = re.search(r'medium_([^_]+)_composition\.json', json_file.name)
            medium_id = medium_match.group(1) if medium_match else json_file.stem.replace('_composition', '')
            
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if isinstance(data, list):
                    for component in data:
                        if isinstance(component, dict):
                            compound = component.get('compound', '')
                            if not compound or compound.lower() in ['distilled water', 'water']:
                                continue
                            
                            # Method 1: String matching
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
            
            except Exception as e:
                logger.debug(f"Error processing {json_file}: {e}")
                continue
        
        logger.info(f"Processed {len(sample_files)} files, extracted {len(self.results)} compound entries")
    
    def _save_results(self):
        """Save mapping results."""
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
        
        # Save main results
        main_columns = ['medium_id', 'original', 'mapped', 'value', 'concentration', 
                       'unit', 'mmol_l', 'optional', 'mapping_method', 'source']
        df_output[main_columns].to_csv(self.output_file, sep='\t', index=False)
        
        # Save comparison
        comparison_columns = ['medium_id', 'original', 'mapped_string', 'mapped_medium', 
                             'value', 'unit', 'mmol_l', 'optional', 'source']
        df[comparison_columns].to_csv(self.comparison_file, sep='\t', index=False)
        
        # Stats
        total = len(df)
        string_mapped = len(df[df['mapped_string'] != ''])
        medium_mapped = len(df[df['mapped_medium'] != ''])
        both_mapped = len(df[(df['mapped_string'] != '') & (df['mapped_medium'] != '')])
        agreement = len(df[(df['mapped_string'] == df['mapped_medium']) & (df['mapped_string'] != '')])
        final_mapped = len(df_output[df_output['mapped'] != ''])
        
        agreement_pct = agreement/both_mapped*100 if both_mapped > 0 else 0
        logger.info(f"""
=== SAMPLE MAPPING RESULTS ===
Total entries: {total}
String method: {string_mapped} ({string_mapped/total*100:.1f}%)
Medium method: {medium_mapped} ({medium_mapped/total*100:.1f}%)
Both methods: {both_mapped}
Agreement: {agreement}/{both_mapped} ({agreement_pct:.1f}%)
Final mapped: {final_mapped} ({final_mapped/total*100:.1f}%)
        """)
        
        logger.info(f"Saved results to {self.output_file} and {self.comparison_file}")
    
    def run_mapping(self):
        """Run the sample mapping process."""
        logger.info("Starting sample composition to KG mapping...")
        
        self._process_sample_compositions()
        self._save_results()
        
        logger.info("Sample mapping completed!")

def main():
    mapper = SampleCompositionKGMapper(sample_size=50)
    mapper.run_mapping()

if __name__ == "__main__":
    main()