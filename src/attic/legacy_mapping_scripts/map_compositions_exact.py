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
        logging.FileHandler('composition_mapping_exact.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ExactCompositionKGMapper:
    def __init__(self, 
                 kg_nodes_file: str = "/Users/marcin/Documents/VIMSS/ontology/KG-Hub/KG-Microbe/kg-microbe/data/merged/20250222/merged-kg_nodes.tsv",
                 kg_edges_file: str = "/Users/marcin/Documents/VIMSS/ontology/KG-Hub/KG-Microbe/kg-microbe/data/merged/20250222/merged-kg_edges.tsv",
                 json_dir: str = "media_pdfs",
                 output_file: str = "composition_kg_mapping_exact.tsv",
                 comparison_file: str = "mapping_comparison_exact.tsv"):
        
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
    
    def _load_kg_data(self):
        """Load KG data with progress reporting - EXACT MATCHES ONLY."""
        self._log_progress("Starting KG data loading...")
        
        # Load and filter chemical nodes only
        self._log_progress("Loading and filtering chemical nodes...")
        nodes_chunks = pd.read_csv(self.kg_nodes_file, sep='\t', chunksize=100000, low_memory=False)
        
        chemical_nodes_list = []
        total_nodes = 0
        
        for chunk in nodes_chunks:
            total_nodes += len(chunk)
            chemical_chunk = chunk[chunk['category'].str.contains('ChemicalEntity|ChemicalSubstance', na=False)]
            if not chemical_chunk.empty:
                chemical_nodes_list.append(chemical_chunk)
            
            if total_nodes % 500000 == 0:
                self._log_progress(f"Processed {total_nodes} nodes...")
        
        if chemical_nodes_list:
            self.chemical_nodes = pd.concat(chemical_nodes_list, ignore_index=True)
        else:
            self.chemical_nodes = pd.DataFrame()
        
        self._log_progress(f"Found {len(self.chemical_nodes)} chemical entities from {total_nodes} total nodes")
        
        # Build lookup dictionaries - EXACT MATCHES ONLY
        self._log_progress("Building exact match lookups...")
        self.exact_name_to_id = {}
        self.exact_synonym_to_id = {}
        self.normalized_name_to_id = {}
        
        for _, row in self.chemical_nodes.iterrows():
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
        
        self._log_progress(f"Built exact lookups: {len(self.exact_name_to_id)} names, {len(self.exact_synonym_to_id)} synonyms, {len(self.normalized_name_to_id)} normalized")
        
        # Load medium mappings
        self._log_progress("Loading medium mappings...")
        self._load_medium_mappings()
        
        self._log_progress("KG data loading completed!")
    
    def _load_medium_mappings(self):
        """Load medium to component mappings efficiently."""
        # Load edges in chunks
        self._log_progress("Loading edges for medium mappings...")
        
        edges_chunks = pd.read_csv(self.kg_edges_file, sep='\t', chunksize=500000, low_memory=False)
        
        medium_solution_edges = []
        solution_chemical_edges = []
        
        total_edges = 0
        
        for chunk in edges_chunks:
            total_edges += len(chunk)
            
            # Find relevant edges
            medium_sols = chunk[
                (chunk['subject'].str.startswith('medium:', na=False)) &
                (chunk['predicate'] == 'biolink:has_part') &
                (chunk['object'].str.startswith('solution:', na=False))
            ]
            
            sol_chems = chunk[
                (chunk['subject'].str.startswith('solution:', na=False)) &
                (chunk['predicate'] == 'biolink:has_part') &
                (chunk['object'].str.contains('CHEBI:|CAS-RN:|PubChem:', na=False))
            ]
            
            if not medium_sols.empty:
                medium_solution_edges.append(medium_sols)
            
            if not sol_chems.empty:
                solution_chemical_edges.append(sol_chems)
            
            if total_edges % 1000000 == 0:
                self._log_progress(f"Processed {total_edges} edges...")
        
        # Combine edge dataframes
        if medium_solution_edges:
            medium_solution_df = pd.concat(medium_solution_edges, ignore_index=True)
        else:
            medium_solution_df = pd.DataFrame()
        
        if solution_chemical_edges:
            solution_chemical_df = pd.concat(solution_chemical_edges, ignore_index=True)
        else:
            solution_chemical_df = pd.DataFrame()
        
        self._log_progress(f"Found {len(medium_solution_df)} medium->solution and {len(solution_chemical_df)} solution->chemical edges")
        
        # Build mappings
        self._log_progress("Building medium component mappings...")
        
        # Build solution -> components mapping
        solution_to_components = defaultdict(set)
        for _, edge in solution_chemical_df.iterrows():
            solution_to_components[edge['subject']].add(edge['object'])
        
        # Build medium -> components mapping (through solutions)
        self.medium_to_components = defaultdict(set)
        for _, edge in medium_solution_df.iterrows():
            medium_id = edge['subject']
            solution_id = edge['object']
            if solution_id in solution_to_components:
                self.medium_to_components[medium_id].update(solution_to_components[solution_id])
        
        # Create reverse lookup: chemical -> list of media it appears in
        self.chemical_to_media = defaultdict(set)
        for medium_id, chemicals in self.medium_to_components.items():
            for chemical_id in chemicals:
                self.chemical_to_media[chemical_id].add(medium_id)
        
        # Build fast lookup for chemical info to avoid repeated DataFrame queries
        self._log_progress("Building fast chemical info lookup...")
        self.chemical_info_lookup = {}
        for _, row in self.chemical_nodes.iterrows():
            node_id = row['id']
            self.chemical_info_lookup[node_id] = {
                'name': row.get('name', ''),
                'synonyms': row.get('synonym', '')
            }
        
        total_mappings = sum(len(comps) for comps in self.medium_to_components.values())
        self._log_progress(f"Built mappings for {len(self.medium_to_components)} media, {total_mappings} total component relationships")
    
    def _find_best_match_string(self, compound_name: str) -> Optional[str]:
        """Find exact string matches only - super fast."""
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
        """Find exact matches within the medium context - OPTIMIZED."""
        if not compound_name or compound_name.lower() in ['distilled water', 'water']:
            return None
        
        medium_node_id = f"medium:{medium_id}"
        
        if medium_node_id not in self.medium_to_components:
            return None
        
        medium_chemicals = self.medium_to_components[medium_node_id]
        compound_lower = compound_name.lower().strip()
        normalized_compound = self._normalize_chemical_name(compound_name)
        
        # Try to find exact matches within this medium's known chemicals
        for chemical_id in medium_chemicals:
            # Use fast lookup instead of DataFrame query
            if chemical_id not in self.chemical_info_lookup:
                continue
            
            chemical_info = self.chemical_info_lookup[chemical_id]
            name = chemical_info['name']
            synonyms = chemical_info['synonyms']
            
            # Exact name match
            if pd.notna(name) and name.strip():
                if compound_lower == name.lower().strip():
                    return chemical_id
                
                # Normalized name match
                norm_name = self._normalize_chemical_name(name)
                if norm_name and normalized_compound == norm_name:
                    return chemical_id
            
            # Exact synonym matches
            if pd.notna(synonyms) and synonyms.strip():
                synonym_list = [s.strip() for s in synonyms.split('|') if s.strip()]
                for synonym in synonym_list:
                    if compound_lower == synonym.lower().strip():
                        return chemical_id
                    
                    # Normalized synonym match
                    norm_syn = self._normalize_chemical_name(synonym)
                    if norm_syn and normalized_compound == norm_syn:
                        return chemical_id
        
        return None
    
    def _process_composition_files(self):
        """Process composition files - EXACT MATCHES ONLY for speed."""
        self._log_progress("Starting composition file processing...")
        
        self._log_progress("Getting list of JSON files...")
        json_files = list(self.json_dir.glob("*_composition.json"))
        total_files = len(json_files)
        
        self._log_progress(f"Found {total_files} JSON composition files to process")
        
        files_processed = 0
        compounds_processed = 0
        
        self._log_progress("Starting to iterate through files...")
        
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
                            
                            # Method 1: Exact string matching (very fast)
                            kg_id_string = self._find_best_match_string(compound)
                            
                            # Method 2: Exact medium-based matching (optimized)
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
                
            except Exception as e:
                self._log_progress(f"Error processing {json_file.name}: {e}")
                files_processed += 1
                continue
        
        self._log_progress(f"Completed processing {files_processed} files, {compounds_processed} total compounds")
    
    def _save_results(self):
        """Save results and generate comprehensive comparison."""
        self._log_progress("Saving results and generating comparison...")
        
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
        
        # Detailed analysis
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
=== EXACT MATCHING RESULTS ===
Total compound entries: {total}

STRING MATCHING (exact only):
  Successfully mapped: {string_mapped} ({string_mapped/total*100:.1f}%)
  String-only mappings: {string_only}

MEDIUM-BASED MATCHING (exact only):
  Successfully mapped: {medium_mapped} ({medium_mapped/total*100:.1f}%)
  Medium-only mappings: {medium_only}

COMPARISON:
  Both methods found: {both_mapped}
  Methods agree: {agreement} ({agreement/both_mapped*100 if both_mapped > 0 else 0:.1f}%)
  Methods disagree: {disagreement}
  Final mapped: {final_mapped} ({final_mapped/total*100:.1f}%)
  Unmapped: {total - final_mapped} ({(total - final_mapped)/total*100:.1f}%)
        """)
        
        # Method effectiveness by medium
        method_stats = df_output['mapping_method'].value_counts()
        self._log_progress("Mapping method distribution:")
        for method, count in method_stats.items():
            self._log_progress(f"  {method}: {count} ({count/total*100:.1f}%)")
        
        # Show some successful mappings
        successful = df_output[df_output['mapped'] != ''].head(20)
        if not successful.empty:
            self._log_progress(f"\nSample successful mappings ({len(successful)} shown):")
            for _, row in successful.iterrows():
                self._log_progress(f"  '{row['original']}' -> {row['mapped']} (method: {row['mapping_method']})")
        
        # Show disagreements
        disagreements = df[(df['mapped_string'] != df['mapped_medium']) & (df['mapped_string'] != '') & (df['mapped_medium'] != '')].head(10)
        if not disagreements.empty:
            self._log_progress(f"\nMethod disagreements ({len(disagreements)} shown):")
            for _, row in disagreements.iterrows():
                self._log_progress(f"  '{row['original']}': string={row['mapped_string']}, medium={row['mapped_medium']}")
        
        # Show top unmapped
        unmapped = df_output[df_output['mapped'] == '']['original'].value_counts().head(15)
        if not unmapped.empty:
            self._log_progress("\nTop unmapped compounds (exact matching only):")
            for compound, count in unmapped.items():
                self._log_progress(f"  '{compound}': {count} occurrences")
        
        self._log_progress(f"Results saved to {self.output_file} and {self.comparison_file}")
    
    def run_mapping(self):
        """Run the exact matching mapping process."""
        self._log_progress("Starting EXACT-ONLY composition to KG mapping...")
        
        self._process_composition_files()
        self._save_results()
        
        total_time = time.time() - self.start_time
        self._log_progress(f"Exact mapping completed in {total_time:.1f} seconds!")

def main():
    mapper = ExactCompositionKGMapper()
    mapper.run_mapping()

if __name__ == "__main__":
    main()