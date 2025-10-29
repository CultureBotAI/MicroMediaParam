#!/usr/bin/env python3

import pandas as pd
import re
import json
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from fuzzywuzzy import fuzz
import logging
from collections import defaultdict

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('composition_mapping_enhanced.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class EnhancedCompositionKGMapper:
    def __init__(self, 
                 kg_nodes_file: str = "/Users/marcin/Documents/VIMSS/ontology/KG-Hub/KG-Microbe/kg-microbe/data/merged/20250222/merged-kg_nodes.tsv",
                 kg_edges_file: str = "/Users/marcin/Documents/VIMSS/ontology/KG-Hub/KG-Microbe/kg-microbe/data/merged/20250222/merged-kg_edges.tsv",
                 composition_dir: str = "media_compositions",
                 json_dir: str = "media_pdfs",
                 output_file: str = "composition_kg_mapping_enhanced.tsv",
                 comparison_file: str = "mapping_comparison.tsv",
                 similarity_threshold: int = 85):
        
        self.kg_nodes_file = kg_nodes_file
        self.kg_edges_file = kg_edges_file
        self.composition_dir = Path(composition_dir)
        self.json_dir = Path(json_dir)
        self.output_file = output_file
        self.comparison_file = comparison_file
        self.similarity_threshold = similarity_threshold
        
        # Load KG data
        self.kg_nodes = self._load_kg_nodes()
        self.kg_edges = self._load_kg_edges()
        
        # Create lookup dictionaries for direct string matching
        self.name_to_id = {}
        self.synonym_to_id = {}
        self.normalized_name_to_id = {}
        self._build_lookup_dicts()
        
        # Build medium-based mapping structures
        self.medium_to_components = defaultdict(set)
        self.solution_to_components = defaultdict(set)
        self._build_medium_mappings()
        
        # Results storage
        self.results = []
        
    def _load_kg_nodes(self) -> pd.DataFrame:
        """Load the KG-Microbe nodes file."""
        logger.info(f"Loading KG nodes from {self.kg_nodes_file}")
        try:
            df = pd.read_csv(self.kg_nodes_file, sep='\t', low_memory=False)
            logger.info(f"Loaded {len(df)} total nodes")
            return df
        except Exception as e:
            logger.error(f"Error loading KG nodes: {e}")
            raise
    
    def _load_kg_edges(self) -> pd.DataFrame:
        """Load the KG-Microbe edges file."""
        logger.info(f"Loading KG edges from {self.kg_edges_file}")
        try:
            df = pd.read_csv(self.kg_edges_file, sep='\t', low_memory=False)
            logger.info(f"Loaded {len(df)} edges")
            return df
        except Exception as e:
            logger.error(f"Error loading KG edges: {e}")
            raise
    
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
        
        # Remove parenthetical information (often stereochemistry)
        normalized = re.sub(r'\([^)]*\)', '', normalized)
        
        # Normalize whitespace and punctuation
        normalized = re.sub(r'[,;]', '', normalized)
        normalized = re.sub(r'\s+', ' ', normalized)
        normalized = normalized.strip()
        
        return normalized
    
    def _build_lookup_dicts(self):
        """Build lookup dictionaries for efficient name matching."""
        logger.info("Building chemical name lookup dictionaries...")
        
        # Filter for chemical entities
        chemical_df = self.kg_nodes[self.kg_nodes['category'].str.contains('ChemicalEntity|ChemicalSubstance', na=False)]
        logger.info(f"Found {len(chemical_df)} chemical entities from {len(self.kg_nodes)} total nodes")
        
        for _, row in chemical_df.iterrows():
            node_id = row['id']
            name = row.get('name', '')
            synonyms = row.get('synonym', '')
            
            # Main name
            if pd.notna(name) and name.strip():
                self.name_to_id[name.lower().strip()] = node_id
                norm_name = self._normalize_chemical_name(name)
                if norm_name:
                    self.normalized_name_to_id[norm_name] = node_id
            
            # Synonyms
            if pd.notna(synonyms) and synonyms.strip():
                synonym_list = [s.strip() for s in synonyms.split('|') if s.strip()]
                for synonym in synonym_list:
                    self.synonym_to_id[synonym.lower().strip()] = node_id
                    norm_syn = self._normalize_chemical_name(synonym)
                    if norm_syn:
                        self.normalized_name_to_id[norm_syn] = node_id
        
        logger.info(f"Built lookup with {len(self.name_to_id)} names, "
                   f"{len(self.synonym_to_id)} synonyms, "
                   f"{len(self.normalized_name_to_id)} normalized names")
    
    def _build_medium_mappings(self):
        """Build medium to component mappings from KG edges."""
        logger.info("Building medium to component mappings from KG...")
        
        # Find medium -> solution relationships (has_part)
        medium_solution_edges = self.kg_edges[
            (self.kg_edges['subject'].str.startswith('medium:', na=False)) &
            (self.kg_edges['predicate'] == 'biolink:has_part') &
            (self.kg_edges['object'].str.startswith('solution:', na=False))
        ]
        
        logger.info(f"Found {len(medium_solution_edges)} medium -> solution relationships")
        
        # Find solution -> chemical relationships (has_part)
        solution_chemical_edges = self.kg_edges[
            (self.kg_edges['subject'].str.startswith('solution:', na=False)) &
            (self.kg_edges['predicate'] == 'biolink:has_part') &
            (self.kg_edges['object'].str.contains('CHEBI:|CAS-RN:|PubChem:', na=False))
        ]
        
        logger.info(f"Found {len(solution_chemical_edges)} solution -> chemical relationships")
        
        # Build solution to components mapping
        for _, edge in solution_chemical_edges.iterrows():
            solution_id = edge['subject']
            chemical_id = edge['object']
            self.solution_to_components[solution_id].add(chemical_id)
        
        # Build medium to components mapping (through solutions)
        for _, edge in medium_solution_edges.iterrows():
            medium_id = edge['subject']
            solution_id = edge['object']
            
            # Add all chemicals from this solution to the medium
            if solution_id in self.solution_to_components:
                self.medium_to_components[medium_id].update(self.solution_to_components[solution_id])
        
        # Also check for direct medium -> chemical relationships
        direct_medium_chemical_edges = self.kg_edges[
            (self.kg_edges['subject'].str.startswith('medium:', na=False)) &
            (self.kg_edges['predicate'] == 'biolink:has_part') &
            (self.kg_edges['object'].str.contains('CHEBI:|CAS-RN:|PubChem:', na=False))
        ]
        
        logger.info(f"Found {len(direct_medium_chemical_edges)} direct medium -> chemical relationships")
        
        for _, edge in direct_medium_chemical_edges.iterrows():
            medium_id = edge['subject']
            chemical_id = edge['object']
            self.medium_to_components[medium_id].add(chemical_id)
        
        total_media = len(self.medium_to_components)
        total_components = sum(len(components) for components in self.medium_to_components.values())
        logger.info(f"Built mappings for {total_media} media with {total_components} total component relationships")
    
    def _find_best_match_string(self, compound_name: str) -> Optional[str]:
        """Find the best matching KG node ID for a compound name using string matching."""
        if not compound_name or compound_name.lower() in ['distilled water', 'water']:
            return None
        
        original_name = compound_name.lower().strip()
        normalized_name = self._normalize_chemical_name(compound_name)
        
        # Try exact matches first
        # 1. Direct name match
        if original_name in self.name_to_id:
            return self.name_to_id[original_name]
        
        # 2. Direct synonym match
        if original_name in self.synonym_to_id:
            return self.synonym_to_id[original_name]
        
        # 3. Normalized name match
        if normalized_name in self.normalized_name_to_id:
            return self.normalized_name_to_id[normalized_name]
        
        # Try fuzzy matching
        best_match = None
        best_score = 0
        best_id = None
        
        # Search through all names and synonyms
        all_names = {**self.name_to_id, **self.synonym_to_id, **self.normalized_name_to_id}
        
        for kg_name, kg_id in all_names.items():
            # Try matching against original name
            score1 = fuzz.ratio(original_name, kg_name)
            score2 = fuzz.ratio(normalized_name, kg_name) if normalized_name else 0
            
            max_score = max(score1, score2)
            
            if max_score > best_score and max_score >= self.similarity_threshold:
                best_score = max_score
                best_match = kg_name
                best_id = kg_id
        
        if best_match:
            logger.debug(f"Fuzzy matched '{compound_name}' to '{best_match}' (score: {best_score})")
        
        return best_id
    
    def _find_best_match_medium(self, compound_name: str, medium_id: str) -> Optional[str]:
        """Find the best matching KG node ID using medium-based lookup."""
        if not compound_name or compound_name.lower() in ['distilled water', 'water']:
            return None
        
        # Construct medium node ID
        medium_node_id = f"medium:{medium_id}"
        
        if medium_node_id not in self.medium_to_components:
            return None
        
        # Get all chemical components for this medium
        medium_chemicals = self.medium_to_components[medium_node_id]
        
        if not medium_chemicals:
            return None
        
        # Try to match the compound name against the names of chemicals in this medium
        best_match = None
        best_score = 0
        best_id = None
        
        normalized_compound = self._normalize_chemical_name(compound_name)
        original_compound = compound_name.lower().strip()
        
        for chemical_id in medium_chemicals:
            # Get the chemical's name and synonyms from nodes
            chemical_node = self.kg_nodes[self.kg_nodes['id'] == chemical_id]
            
            if chemical_node.empty:
                continue
            
            chemical_row = chemical_node.iloc[0]
            name = chemical_row.get('name', '')
            synonyms = chemical_row.get('synonym', '')
            
            # Check name match
            if pd.notna(name) and name.strip():
                score1 = fuzz.ratio(original_compound, name.lower().strip())
                score2 = fuzz.ratio(normalized_compound, self._normalize_chemical_name(name))
                max_score = max(score1, score2)
                
                if max_score > best_score and max_score >= self.similarity_threshold:
                    best_score = max_score
                    best_match = name
                    best_id = chemical_id
            
            # Check synonym matches
            if pd.notna(synonyms) and synonyms.strip():
                synonym_list = [s.strip() for s in synonyms.split('|') if s.strip()]
                for synonym in synonym_list:
                    score1 = fuzz.ratio(original_compound, synonym.lower().strip())
                    score2 = fuzz.ratio(normalized_compound, self._normalize_chemical_name(synonym))
                    max_score = max(score1, score2)
                    
                    if max_score > best_score and max_score >= self.similarity_threshold:
                        best_score = max_score
                        best_match = synonym
                        best_id = chemical_id
        
        if best_match:
            logger.debug(f"Medium-based matched '{compound_name}' to '{best_match}' (score: {best_score}) for medium {medium_id}")
        
        return best_id
    
    def _extract_composition_from_json(self, json_file: Path) -> List[Dict]:
        """Extract composition data from JSON file."""
        compositions = []
        
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if isinstance(data, list):
                # Handle array format like medium_1324_composition.json
                for component in data:
                    if isinstance(component, dict):
                        compound = component.get('compound', '')
                        g_l = component.get('g_l')
                        mmol_l = component.get('mmol_l')
                        optional = component.get('optional', '')
                        
                        compositions.append({
                            'compound': compound,
                            'g_l': g_l,
                            'mmol_l': mmol_l,
                            'optional': optional,
                            'medium_id': component.get('medium_id', '')
                        })
            
            elif isinstance(data, dict):
                # Handle dictionary format
                components = data.get('components', [])
                if isinstance(components, list):
                    for component in components:
                        if isinstance(component, dict):
                            compound = component.get('name', component.get('compound', ''))
                            amount = component.get('amount', component.get('g_l'))
                            unit = component.get('unit', 'g/L')
                            optional = component.get('optional', '')
                            
                            compositions.append({
                                'compound': compound,
                                'value': amount,
                                'unit': unit,
                                'optional': optional,
                                'medium_id': data.get('medium_id', '')
                            })
        
        except Exception as e:
            logger.debug(f"Error reading JSON {json_file}: {e}")
        
        return compositions
    
    def _process_composition_files(self):
        """Process all composition files and extract compound data."""
        logger.info("Processing composition files...")
        
        # Process JSON files (more structured data)
        json_files = list(self.json_dir.glob("*_composition.json"))
        logger.info(f"Found {len(json_files)} JSON composition files")
        
        for json_file in json_files:
            medium_match = re.search(r'medium_([^_]+)_composition\.json', json_file.name)
            medium_id = medium_match.group(1) if medium_match else json_file.stem.replace('_composition', '')
            
            compositions = self._extract_composition_from_json(json_file)
            
            for comp in compositions:
                compound = comp.get('compound', '')
                if not compound or compound.lower() in ['distilled water', 'water']:
                    continue
                
                # Method 1: Direct string matching
                kg_id_string = self._find_best_match_string(compound)
                
                # Method 2: Medium-based matching
                kg_id_medium = self._find_best_match_medium(compound, medium_id)
                
                # Extract numerical values
                g_l_value = comp.get('g_l')
                mmol_l_value = comp.get('mmol_l')
                value = comp.get('value', g_l_value)
                unit = comp.get('unit', 'g/L')
                
                # Add result with both mapping methods
                result = {
                    'medium_id': medium_id,
                    'original': compound,
                    'mapped_string': kg_id_string if kg_id_string else '',
                    'mapped_medium': kg_id_medium if kg_id_medium else '',
                    'value': value if pd.notna(value) and value is not None else '',
                    'concentration': '',  # To be filled later
                    'unit': unit,
                    'mmol_l': mmol_l_value if pd.notna(mmol_l_value) and mmol_l_value is not None else '',
                    'optional': comp.get('optional', ''),
                    'source': 'json'
                }
                
                self.results.append(result)
        
        logger.info(f"Processed {len(json_files)} JSON files, extracted {len(self.results)} compound entries")
    
    def _save_results(self):
        """Save mapping results to TSV files."""
        if not self.results:
            logger.warning("No results to save")
            return
        
        df = pd.DataFrame(self.results)
        
        # Create main output with combined mapping approach
        df_output = df.copy()
        
        # Choose best mapping (prefer medium-based when available, fall back to string-based)
        df_output['mapped'] = df_output.apply(
            lambda row: row['mapped_medium'] if row['mapped_medium'] else row['mapped_string'], 
            axis=1
        )
        
        # Add mapping method column
        df_output['mapping_method'] = df_output.apply(
            lambda row: 'medium' if row['mapped_medium'] else ('string' if row['mapped_string'] else 'none'),
            axis=1
        )
        
        # Reorder columns for main output
        main_columns = ['medium_id', 'original', 'mapped', 'value', 'concentration', 
                       'unit', 'mmol_l', 'optional', 'mapping_method', 'source']
        df_output_final = df_output.reindex(columns=main_columns)
        
        # Save main results
        df_output_final.to_csv(self.output_file, sep='\t', index=False)
        logger.info(f"Saved {len(df_output_final)} mappings to {self.output_file}")
        
        # Create comparison file with both mapping approaches
        comparison_columns = ['medium_id', 'original', 'mapped_string', 'mapped_medium', 
                             'value', 'unit', 'mmol_l', 'optional', 'source']
        df_comparison = df.reindex(columns=comparison_columns)
        df_comparison.to_csv(self.comparison_file, sep='\t', index=False)
        logger.info(f"Saved comparison data to {self.comparison_file}")
        
        # Create summary statistics
        self._create_summary_stats(df_output_final, df)
    
    def _create_summary_stats(self, df_final: pd.DataFrame, df_comparison: pd.DataFrame):
        """Create and log summary statistics."""
        total_compounds = len(df_final)
        
        # String mapping stats
        string_mapped = len(df_comparison[df_comparison['mapped_string'] != ''])
        string_only = len(df_comparison[
            (df_comparison['mapped_string'] != '') & 
            (df_comparison['mapped_medium'] == '')
        ])
        
        # Medium mapping stats  
        medium_mapped = len(df_comparison[df_comparison['mapped_medium'] != ''])
        medium_only = len(df_comparison[
            (df_comparison['mapped_medium'] != '') & 
            (df_comparison['mapped_string'] == '')
        ])
        
        # Combined stats
        both_mapped = len(df_comparison[
            (df_comparison['mapped_string'] != '') & 
            (df_comparison['mapped_medium'] != '')
        ])
        
        final_mapped = len(df_final[df_final['mapped'] != ''])
        
        # Agreement stats
        agreement = len(df_comparison[
            (df_comparison['mapped_string'] == df_comparison['mapped_medium']) &
            (df_comparison['mapped_string'] != '')
        ])
        
        logger.info(f"""
=== ENHANCED MAPPING SUMMARY ===
Total compound entries: {total_compounds}

STRING MATCHING:
  - Successfully mapped: {string_mapped} ({string_mapped/total_compounds*100:.1f}%)
  - String-only mappings: {string_only}

MEDIUM-BASED MATCHING:
  - Successfully mapped: {medium_mapped} ({medium_mapped/total_compounds*100:.1f}%)
  - Medium-only mappings: {medium_only}

COMBINED RESULTS:
  - Both methods mapped: {both_mapped}
  - Methods agree: {agreement} ({agreement/both_mapped*100:.1f}% of overlapping mappings)
  - Final mapped: {final_mapped} ({final_mapped/total_compounds*100:.1f}%)
  - Unmapped: {total_compounds - final_mapped} ({(total_compounds - final_mapped)/total_compounds*100:.1f}%)
        """)
        
        # Method distribution
        method_counts = df_final['mapping_method'].value_counts()
        logger.info("Mapping method distribution:")
        for method, count in method_counts.items():
            logger.info(f"  {method}: {count} ({count/total_compounds*100:.1f}%)")
        
        # Show disagreements (mapped by both methods but different results)
        disagreements = df_comparison[
            (df_comparison['mapped_string'] != '') & 
            (df_comparison['mapped_medium'] != '') & 
            (df_comparison['mapped_string'] != df_comparison['mapped_medium'])
        ]
        
        if len(disagreements) > 0:
            logger.info(f"\nFound {len(disagreements)} disagreements between methods:")
            for _, row in disagreements.head(10).iterrows():
                logger.info(f"  '{row['original']}': string='{row['mapped_string']}', medium='{row['mapped_medium']}'")
        
        # Top unmapped compounds
        unmapped = df_final[df_final['mapped'] == '']['original'].value_counts().head(10)
        if not unmapped.empty:
            logger.info("\nTop unmapped compounds:")
            for compound, count in unmapped.items():
                logger.info(f"  {compound}: {count} occurrences")
    
    def run_mapping(self):
        """Run the complete enhanced mapping process."""
        logger.info("Starting enhanced composition to KG mapping process...")
        
        self._process_composition_files()
        self._save_results()
        
        logger.info("Enhanced mapping process completed!")

def main():
    """Main function to run the enhanced composition mapping."""
    mapper = EnhancedCompositionKGMapper()
    mapper.run_mapping()

if __name__ == "__main__":
    main()