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
        logging.FileHandler('composition_mapping_comprehensive.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ComprehensiveCompositionKGMapper:
    def __init__(self, 
                 kg_nodes_file: str = "/Users/marcin/Documents/VIMSS/ontology/KG-Hub/KG-Microbe/kg-microbe/data/merged/20250222/merged-kg_nodes.tsv",
                 kg_edges_file: str = "/Users/marcin/Documents/VIMSS/ontology/KG-Hub/KG-Microbe/kg-microbe/data/merged/20250222/merged-kg_edges.tsv",
                 json_dir: str = "media_pdfs",
                 output_file: str = "composition_kg_mapping_comprehensive.tsv",
                 comparison_file: str = "mapping_comparison_comprehensive.tsv"):
        
        # Progress tracking
        self.start_time = time.time()
        
        self.kg_nodes_file = kg_nodes_file
        self.kg_edges_file = kg_edges_file
        self.json_dir = Path(json_dir)
        self.output_file = output_file
        self.comparison_file = comparison_file
        
        # Load KG data efficiently
        self._load_kg_data()
        
        # Results storage
        self.results = []
        
    def _log_progress(self, message: str):
        """Log progress with timing information."""
        elapsed = time.time() - self.start_time
        logger.info(f"[{elapsed:.1f}s] {message}")
    
    def _normalize_chemical_name(self, name: str) -> str:
        """Normalize chemical name for better matching."""
        if pd.isna(name) or name == "":
            return ""
        
        # Convert to lowercase
        normalized = name.lower().strip()
        
        # Remove common prefixes/suffixes
        normalized = re.sub(r'^(d|l|dl)-', '', normalized)
        normalized = re.sub(r'^(\+|-)\s*', '', normalized)
        
        # Normalize hydration notation
        normalized = re.sub(r'\s*x\s*\d+\s*h2o', '', normalized)
        normalized = re.sub(r'\s*•\s*\d+\s*h2o', '', normalized)
        normalized = re.sub(r'\s*\.\s*\d+\s*h2o', '', normalized)
        
        # Remove parenthetical information 
        normalized = re.sub(r'\([^)]*\)', '', normalized)
        
        # Normalize whitespace and punctuation
        normalized = re.sub(r'[,;]', '', normalized)
        normalized = re.sub(r'\s+', ' ', normalized)
        normalized = normalized.strip()
        
        return normalized
    
    def _is_relevant_node(self, category: str, node_id: str) -> bool:
        """Check if a node is relevant for composition mapping."""
        if pd.isna(category):
            return False
        
        category_lower = category.lower()
        
        # Always include chemical entities and substances
        if 'chemicalentity' in category_lower or 'chemicalsubstance' in category_lower:
            return True
        
        # Include specific node types that are media components
        if pd.notna(node_id) and isinstance(node_id, str):
            if node_id.startswith(('solution:', 'ingredient:', 'medium:')):
                return True
        
        # Include other potentially relevant categories
        relevant_categories = [
            'chemicalrole',  # Chemical roles
            'environmentalfeature',  # Environmental features
        ]
        
        for relevant in relevant_categories:
            if relevant in category_lower:
                return True
        
        return False
    
    def _load_kg_data(self):
        """Load KG data with comprehensive entity types."""
        self._log_progress("Starting comprehensive KG data loading...")
        
        # Load and filter relevant nodes
        self._log_progress("Loading and filtering relevant nodes...")
        nodes_chunks = pd.read_csv(self.kg_nodes_file, sep='\t', chunksize=100000, low_memory=False)
        
        relevant_nodes_list = []
        total_nodes = 0
        
        for chunk in nodes_chunks:
            total_nodes += len(chunk)
            
            # Filter for relevant nodes (not just chemicals)
            relevant_chunk = chunk[
                chunk.apply(lambda row: self._is_relevant_node(row.get('category', ''), row.get('id', '')), axis=1)
            ]
            
            if not relevant_chunk.empty:
                relevant_nodes_list.append(relevant_chunk)
            
            if total_nodes % 500000 == 0:
                self._log_progress(f"Processed {total_nodes} nodes...")
        
        if relevant_nodes_list:
            self.relevant_nodes = pd.concat(relevant_nodes_list, ignore_index=True)
        else:
            self.relevant_nodes = pd.DataFrame()
        
        self._log_progress(f"Found {len(self.relevant_nodes)} relevant entities from {total_nodes} total nodes")
        
        # Log node type distribution
        node_type_counts = self.relevant_nodes['category'].value_counts()
        self._log_progress("Relevant node type distribution:")
        for node_type, count in node_type_counts.head(10).items():
            self._log_progress(f"  {node_type}: {count}")
        
        # Check for specific entity types we expect
        solution_count = len(self.relevant_nodes[self.relevant_nodes['id'].str.startswith('solution:', na=False)])
        ingredient_count = len(self.relevant_nodes[self.relevant_nodes['id'].str.startswith('ingredient:', na=False)])  
        medium_count = len(self.relevant_nodes[self.relevant_nodes['id'].str.startswith('medium:', na=False)])
        
        self._log_progress(f"Found {solution_count} solution nodes, {ingredient_count} ingredient nodes, {medium_count} medium nodes")
        
        # Build lookup dictionaries for all relevant entities
        self._log_progress("Building comprehensive lookup dictionaries...")
        self.exact_name_to_id = {}
        self.exact_synonym_to_id = {}
        self.normalized_name_to_id = {}
        
        for _, row in self.relevant_nodes.iterrows():
            node_id = row['id']
            name = row.get('name', '')
            synonyms = row.get('synonym', '')
            
            # Exact name matches
            if pd.notna(name) and name.strip():
                name_key = name.lower().strip()
                self.exact_name_to_id[name_key] = node_id
                
                # Also add normalized version
                norm_name = self._normalize_chemical_name(name)
                if norm_name:
                    self.normalized_name_to_id[norm_name] = node_id
            
            # Exact synonym matches
            if pd.notna(synonyms) and synonyms.strip():
                synonym_list = [s.strip() for s in synonyms.split('|') if s.strip()]
                for synonym in synonym_list:
                    syn_key = synonym.lower().strip()
                    self.exact_synonym_to_id[syn_key] = node_id
                    
                    # Also add normalized version
                    norm_syn = self._normalize_chemical_name(synonym)
                    if norm_syn:
                        self.normalized_name_to_id[norm_syn] = node_id
        
        self._log_progress(f"Built comprehensive lookups: {len(self.exact_name_to_id)} names, {len(self.exact_synonym_to_id)} synonyms, {len(self.normalized_name_to_id)} normalized")
        
        # Load medium mappings
        self._log_progress("Loading medium mappings...")
        self._load_medium_mappings()
        
        self._log_progress("Comprehensive KG data loading completed!")
    
    def _load_medium_mappings(self):
        """Load medium to component mappings efficiently."""
        # Load edges in chunks
        self._log_progress("Loading edges for medium mappings...")
        
        edges_chunks = pd.read_csv(self.kg_edges_file, sep='\t', chunksize=500000, low_memory=False)
        
        medium_solution_edges = []
        solution_component_edges = []
        medium_direct_edges = []
        
        total_edges = 0
        
        for chunk in edges_chunks:
            total_edges += len(chunk)
            
            # Find medium -> solution edges
            medium_sols = chunk[
                (chunk['subject'].str.startswith('medium:', na=False)) &
                (chunk['predicate'] == 'biolink:has_part') &
                (chunk['object'].str.startswith('solution:', na=False))
            ]
            
            # Find solution -> any component edges (not just CHEBI)
            sol_comps = chunk[
                (chunk['subject'].str.startswith('solution:', na=False)) &
                (chunk['predicate'] == 'biolink:has_part')
            ]
            
            # Find direct medium -> component edges (not just CHEBI)
            med_direct = chunk[
                (chunk['subject'].str.startswith('medium:', na=False)) &
                (chunk['predicate'] == 'biolink:has_part') &
                (~chunk['object'].str.startswith('solution:', na=False))  # Exclude solutions
            ]
            
            if not medium_sols.empty:
                medium_solution_edges.append(medium_sols)
            
            if not sol_comps.empty:
                solution_component_edges.append(sol_comps)
            
            if not med_direct.empty:
                medium_direct_edges.append(med_direct)
            
            if total_edges % 1000000 == 0:
                self._log_progress(f"Processed {total_edges} edges...")
        
        # Combine edge dataframes
        if medium_solution_edges:
            medium_solution_df = pd.concat(medium_solution_edges, ignore_index=True)
        else:
            medium_solution_df = pd.DataFrame()
        
        if solution_component_edges:
            solution_component_df = pd.concat(solution_component_edges, ignore_index=True)
        else:
            solution_component_df = pd.DataFrame()
        
        if medium_direct_edges:
            medium_direct_df = pd.concat(medium_direct_edges, ignore_index=True)
        else:
            medium_direct_df = pd.DataFrame()
        
        self._log_progress(f"Found {len(medium_solution_df)} medium->solution, {len(solution_component_df)} solution->component, and {len(medium_direct_df)} direct medium->component edges")
        
        # Build mappings
        self._log_progress("Building comprehensive medium component mappings...")
        
        # Build solution -> components mapping
        solution_to_components = defaultdict(set)
        for _, edge in solution_component_df.iterrows():
            solution_to_components[edge['subject']].add(edge['object'])
        
        # Build medium -> components mapping
        self.medium_to_components = defaultdict(set)
        
        # Add components through solutions
        for _, edge in medium_solution_df.iterrows():
            medium_id = edge['subject']
            solution_id = edge['object']
            if solution_id in solution_to_components:
                self.medium_to_components[medium_id].update(solution_to_components[solution_id])
        
        # Add direct medium -> component relationships
        for _, edge in medium_direct_df.iterrows():
            self.medium_to_components[edge['subject']].add(edge['object'])
        
        # Create reverse lookup: component -> list of media it appears in
        self.component_to_media = defaultdict(set)
        for medium_id, components in self.medium_to_components.items():
            for component_id in components:
                self.component_to_media[component_id].add(medium_id)
        
        total_mappings = sum(len(comps) for comps in self.medium_to_components.values())
        self._log_progress(f"Built mappings for {len(self.medium_to_components)} media, {total_mappings} total component relationships")
        
        # Show examples of what types of components we found
        component_examples = set()
        for components in list(self.medium_to_components.values())[:10]:
            component_examples.update(list(components)[:5])
        
        if component_examples:
            self._log_progress("Example component types found in media:")
            for comp_id in list(component_examples)[:20]:
                comp_prefix = comp_id.split(':')[0] if ':' in comp_id else comp_id
                self._log_progress(f"  {comp_prefix}: {comp_id}")
    
    def _find_best_match_string(self, compound_name: str) -> Optional[str]:
        """Find exact string matches across all relevant entity types."""
        if not compound_name or compound_name.lower() in ['distilled water', 'water']:
            return None
        
        compound_lower = compound_name.lower().strip()
        normalized_compound = self._normalize_chemical_name(compound_name)
        
        # Try exact matches in order of preference
        if compound_lower in self.exact_name_to_id:
            return self.exact_name_to_id[compound_lower]
        
        if compound_lower in self.exact_synonym_to_id:
            return self.exact_synonym_to_id[compound_lower]
        
        if normalized_compound and normalized_compound in self.normalized_name_to_id:
            return self.normalized_name_to_id[normalized_compound]
        
        return None
    
    def _find_best_match_medium(self, compound_name: str, medium_id: str) -> Optional[str]:
        """Find exact matches within the medium context across all entity types."""
        if not compound_name or compound_name.lower() in ['distilled water', 'water']:
            return None
        
        medium_node_id = f"medium:{medium_id}"
        
        if medium_node_id not in self.medium_to_components:
            return None
        
        medium_components = self.medium_to_components[medium_node_id]
        compound_lower = compound_name.lower().strip()
        normalized_compound = self._normalize_chemical_name(compound_name)
        
        # Try to find exact matches within this medium's known components
        for component_id in medium_components:
            # Get the component's names from our lookup
            component_info = self.relevant_nodes[self.relevant_nodes['id'] == component_id]
            
            if component_info.empty:
                continue
            
            component_row = component_info.iloc[0]
            name = component_row.get('name', '')
            synonyms = component_row.get('synonym', '')
            
            # Exact name match
            if pd.notna(name) and name.strip():
                if compound_lower == name.lower().strip():
                    return component_id
                
                # Normalized name match
                norm_name = self._normalize_chemical_name(name)
                if norm_name and normalized_compound == norm_name:
                    return component_id
            
            # Exact synonym matches
            if pd.notna(synonyms) and synonyms.strip():
                synonym_list = [s.strip() for s in synonyms.split('|') if s.strip()]
                for synonym in synonym_list:
                    if compound_lower == synonym.lower().strip():
                        return component_id
                    
                    # Normalized synonym match
                    norm_syn = self._normalize_chemical_name(synonym)
                    if norm_syn and normalized_compound == norm_syn:
                        return component_id
        
        return None
    
    def _process_composition_files(self):
        """Process composition files with comprehensive entity mapping."""
        self._log_progress("Starting comprehensive composition file processing...")
        
        json_files = list(self.json_dir.glob("*_composition.json"))
        total_files = len(json_files)
        
        self._log_progress(f"Found {total_files} JSON composition files to process")
        
        files_processed = 0
        compounds_processed = 0
        
        for i, json_file in enumerate(json_files):
            # Progress every 100 files
            if i % 100 == 0:
                elapsed = time.time() - self.start_time
                rate = files_processed / elapsed if elapsed > 0 else 0
                eta = (total_files - files_processed) / rate if rate > 0 else 0
                self._log_progress(f"File {i+1}/{total_files} ({files_processed} done, {compounds_processed} compounds, {rate:.1f} files/sec, ETA: {eta:.0f}s)")
            
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
                            
                            compounds_processed += 1
                            
                            # Method 1: Comprehensive string matching
                            kg_id_string = self._find_best_match_string(compound)
                            
                            # Method 2: Comprehensive medium-based matching
                            kg_id_medium = self._find_best_match_medium(compound, medium_id)
                            
                            # Determine the entity type of successful mappings
                            string_entity_type = ''
                            medium_entity_type = ''
                            
                            if kg_id_string:
                                if kg_id_string.startswith('CHEBI:'):
                                    string_entity_type = 'CHEBI'
                                elif kg_id_string.startswith('solution:'):
                                    string_entity_type = 'solution'
                                elif kg_id_string.startswith('ingredient:'):
                                    string_entity_type = 'ingredient'
                                elif kg_id_string.startswith('medium:'):
                                    string_entity_type = 'medium'
                                else:
                                    string_entity_type = kg_id_string.split(':')[0] if ':' in kg_id_string else 'other'
                            
                            if kg_id_medium:
                                if kg_id_medium.startswith('CHEBI:'):
                                    medium_entity_type = 'CHEBI'
                                elif kg_id_medium.startswith('solution:'):
                                    medium_entity_type = 'solution'
                                elif kg_id_medium.startswith('ingredient:'):
                                    medium_entity_type = 'ingredient'
                                elif kg_id_medium.startswith('medium:'):
                                    medium_entity_type = 'medium'
                                else:
                                    medium_entity_type = kg_id_medium.split(':')[0] if ':' in kg_id_medium else 'other'
                            
                            result = {
                                'medium_id': medium_id,
                                'original': compound,
                                'mapped_string': kg_id_string or '',
                                'mapped_medium': kg_id_medium or '',
                                'string_entity_type': string_entity_type,
                                'medium_entity_type': medium_entity_type,
                                'value': component.get('g_l', ''),
                                'concentration': '',
                                'unit': 'g/L',
                                'mmol_l': component.get('mmol_l', ''),
                                'optional': component.get('optional', ''),
                                'source': 'json'
                            }
                            
                            self.results.append(result)
                
                files_processed += 1
                
            except Exception as e:
                self._log_progress(f"Error processing {json_file.name}: {e}")
                files_processed += 1
                continue
        
        self._log_progress(f"Completed processing {files_processed} files, {compounds_processed} total compounds")
    
    def _save_results(self):
        """Save results and generate comprehensive comparison."""
        self._log_progress("Saving comprehensive results and generating analysis...")
        
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
        df_output['entity_type'] = df_output.apply(
            lambda row: row['medium_entity_type'] if row['mapped_medium'] else row['string_entity_type'],
            axis=1
        )
        
        # Save files
        main_columns = ['medium_id', 'original', 'mapped', 'value', 'concentration', 
                       'unit', 'mmol_l', 'optional', 'mapping_method', 'entity_type', 'source']
        df_output[main_columns].to_csv(self.output_file, sep='\t', index=False)
        
        comparison_columns = ['medium_id', 'original', 'mapped_string', 'mapped_medium', 
                             'string_entity_type', 'medium_entity_type', 'value', 'unit', 'mmol_l', 'optional', 'source']
        df[comparison_columns].to_csv(self.comparison_file, sep='\t', index=False)
        
        # Comprehensive analysis
        total = len(df)
        string_mapped = len(df[df['mapped_string'] != ''])
        medium_mapped = len(df[df['mapped_medium'] != ''])
        both_mapped = len(df[(df['mapped_string'] != '') & (df['mapped_medium'] != '')])
        string_only = len(df[(df['mapped_string'] != '') & (df['mapped_medium'] == '')])
        medium_only = len(df[(df['mapped_string'] == '') & (df['mapped_medium'] != '')])
        agreement = len(df[(df['mapped_string'] == df['mapped_medium']) & (df['mapped_string'] != '')])
        disagreement = len(df[(df['mapped_string'] != df['mapped_medium']) & (df['mapped_string'] != '') & (df['mapped_medium'] != '')])
        final_mapped = len(df_output[df_output['mapped'] != ''])
        
        self._log_progress(f"""
=== COMPREHENSIVE MAPPING RESULTS ===
Total compound entries: {total}

STRING MATCHING (all entity types):
  Successfully mapped: {string_mapped} ({string_mapped/total*100:.1f}%)
  String-only mappings: {string_only}

MEDIUM-BASED MATCHING (all entity types):
  Successfully mapped: {medium_mapped} ({medium_mapped/total*100:.1f}%)
  Medium-only mappings: {medium_only}

COMPARISON:
  Both methods found: {both_mapped}
  Methods agree: {agreement} ({agreement/both_mapped*100 if both_mapped > 0 else 0:.1f}%)
  Methods disagree: {disagreement}
  Final mapped: {final_mapped} ({final_mapped/total*100:.1f}%)
  Unmapped: {total - final_mapped} ({(total - final_mapped)/total*100:.1f}%)
        """)
        
        # Entity type analysis
        self._log_progress("Entity type distribution in successful mappings:")
        entity_type_counts = df_output[df_output['mapped'] != '']['entity_type'].value_counts()
        for entity_type, count in entity_type_counts.items():
            self._log_progress(f"  {entity_type}: {count} ({count/final_mapped*100 if final_mapped > 0 else 0:.1f}%)")
        
        # Method effectiveness
        method_stats = df_output['mapping_method'].value_counts()
        self._log_progress("Mapping method distribution:")
        for method, count in method_stats.items():
            self._log_progress(f"  {method}: {count} ({count/total*100:.1f}%)")
        
        # Show some successful mappings by entity type
        for entity_type in ['CHEBI', 'solution', 'ingredient']:
            examples = df_output[
                (df_output['mapped'] != '') & 
                (df_output['entity_type'] == entity_type)
            ].head(5)
            
            if not examples.empty:
                self._log_progress(f"\nSample {entity_type} mappings:")
                for _, row in examples.iterrows():
                    self._log_progress(f"  '{row['original']}' -> {row['mapped']} (method: {row['mapping_method']})")
        
        # Show disagreements
        disagreements = df[(df['mapped_string'] != df['mapped_medium']) & (df['mapped_string'] != '') & (df['mapped_medium'] != '')].head(10)
        if not disagreements.empty:
            self._log_progress(f"\nMethod disagreements ({len(disagreements)} shown):")
            for _, row in disagreements.iterrows():
                self._log_progress(f"  '{row['original']}': string={row['mapped_string']} ({row['string_entity_type']}), medium={row['mapped_medium']} ({row['medium_entity_type']})")
        
        # Show top unmapped
        unmapped = df_output[df_output['mapped'] == '']['original'].value_counts().head(15)
        if not unmapped.empty:
            self._log_progress("\nTop unmapped compounds:")
            for compound, count in unmapped.items():
                self._log_progress(f"  '{compound}': {count} occurrences")
        
        self._log_progress(f"Comprehensive results saved to {self.output_file} and {self.comparison_file}")
    
    def run_mapping(self):
        """Run the comprehensive mapping process."""
        self._log_progress("Starting COMPREHENSIVE composition to KG mapping...")
        
        self._process_composition_files()
        self._save_results()
        
        total_time = time.time() - self.start_time
        self._log_progress(f"Comprehensive mapping completed in {total_time:.1f} seconds!")

def main():
    mapper = ComprehensiveCompositionKGMapper()
    mapper.run_mapping()

if __name__ == "__main__":
    main()