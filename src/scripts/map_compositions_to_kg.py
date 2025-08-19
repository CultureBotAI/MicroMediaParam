#!/usr/bin/env python3

import pandas as pd
import re
import json
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from fuzzywuzzy import fuzz
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('composition_mapping.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class CompositionKGMapper:
    def __init__(self, 
                 kg_nodes_file: str = "/Users/marcin/Documents/VIMSS/ontology/KG-Hub/KG-Microbe/kg-microbe/data/merged/20250222/merged-kg_nodes.tsv",
                 composition_dir: str = "media_compositions",
                 json_dir: str = "media_pdfs",
                 output_file: str = "composition_kg_mapping.tsv",
                 similarity_threshold: int = 85):
        
        self.kg_nodes_file = kg_nodes_file
        self.composition_dir = Path(composition_dir)
        self.json_dir = Path(json_dir)
        self.output_file = output_file
        self.similarity_threshold = similarity_threshold
        
        # Load KG nodes
        self.kg_nodes = self._load_kg_nodes()
        
        # Create chemical name lookup dictionaries
        self.name_to_id = {}
        self.synonym_to_id = {}
        self.normalized_name_to_id = {}
        self._build_lookup_dicts()
        
        # Results storage
        self.results = []
        
    def _load_kg_nodes(self) -> pd.DataFrame:
        """Load the KG-Microbe nodes file."""
        logger.info(f"Loading KG nodes from {self.kg_nodes_file}")
        try:
            df = pd.read_csv(self.kg_nodes_file, sep='\t', low_memory=False)
            # Filter for chemical entities
            chemical_df = df[df['category'].str.contains('ChemicalEntity|ChemicalSubstance', na=False)]
            logger.info(f"Loaded {len(chemical_df)} chemical entities from {len(df)} total nodes")
            return chemical_df
        except Exception as e:
            logger.error(f"Error loading KG nodes: {e}")
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
        
        for _, row in self.kg_nodes.iterrows():
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
    
    def _find_best_match(self, compound_name: str) -> Optional[str]:
        """Find the best matching KG node ID for a compound name."""
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
        
        # Process JSON files first (more structured data)
        json_files = list(self.json_dir.glob("*_composition.json"))
        logger.info(f"Found {len(json_files)} JSON composition files")
        
        # Progress tracking
        processed_files = 0
        total_compounds = 0
        mapped_compounds = 0
        total_files = len(json_files)
        
        for i, json_file in enumerate(json_files, 1):
            medium_id = re.search(r'medium_([^_]+)_composition\.json', json_file.name)
            medium_id = medium_id.group(1) if medium_id else json_file.stem
            
            # Progress reporting
            if i % 50 == 0 or i == total_files:
                progress_pct = (i / total_files) * 100
                mapping_rate = (mapped_compounds / max(total_compounds, 1)) * 100
                logger.info(f"Progress: {i}/{total_files} files ({progress_pct:.1f}%) - Medium {medium_id} - {mapped_compounds}/{total_compounds} compounds mapped ({mapping_rate:.1f}%)")
            
            compositions = self._extract_composition_from_json(json_file)
            
            for comp in compositions:
                compound = comp.get('compound', '')
                if not compound or compound.lower() in ['distilled water', 'water']:
                    continue
                
                total_compounds += 1
                
                # Find KG mapping
                kg_id = self._find_best_match(compound)
                if kg_id:
                    mapped_compounds += 1
                
                # Extract numerical values
                g_l_value = comp.get('g_l')
                mmol_l_value = comp.get('mmol_l')
                value = comp.get('value', g_l_value)
                unit = comp.get('unit', 'g/L')
                
                # Add result
                result = {
                    'medium_id': medium_id,
                    'original': compound,
                    'mapped': kg_id if kg_id else '',
                    'value': value if pd.notna(value) and value is not None else '',
                    'concentration': '',  # To be filled later
                    'unit': unit,
                    'mmol_l': mmol_l_value if pd.notna(mmol_l_value) and mmol_l_value is not None else '',
                    'optional': comp.get('optional', ''),
                    'source': 'json'
                }
                
                self.results.append(result)
        
        logger.info(f"Processed {len(json_files)} JSON files, extracted {len(self.results)} compound entries")
        logger.info(f"Compound mapping summary: {mapped_compounds}/{total_compounds} compounds mapped ({mapped_compounds/total_compounds*100:.1f}% success rate)")
    
    def _save_results(self):
        """Save mapping results to TSV file."""
        if not self.results:
            logger.warning("No results to save")
            return
        
        df = pd.DataFrame(self.results)
        
        # Reorder columns as requested
        column_order = ['medium_id', 'original', 'mapped', 'value', 'concentration', 'unit', 'mmol_l', 'optional', 'source']
        df = df.reindex(columns=column_order)
        
        # Save to TSV
        df.to_csv(self.output_file, sep='\t', index=False)
        logger.info(f"Saved {len(df)} mappings to {self.output_file}")
        
        # Create summary statistics
        self._create_summary_stats(df)
    
    def _create_summary_stats(self, df: pd.DataFrame):
        """Create and log summary statistics."""
        total_compounds = len(df)
        mapped_compounds = len(df[df['mapped'] != ''])
        unique_compounds = df['original'].nunique()
        unique_mapped = df[df['mapped'] != '']['mapped'].nunique()
        
        logger.info(f"""
=== MAPPING SUMMARY ===
Total compound entries: {total_compounds}
Successfully mapped: {mapped_compounds} ({mapped_compounds/total_compounds*100:.1f}%)
Unmapped: {total_compounds - mapped_compounds} ({(total_compounds - mapped_compounds)/total_compounds*100:.1f}%)
Unique compound names: {unique_compounds}
Unique KG nodes mapped: {unique_mapped}
        """)
        
        # Show top unmapped compounds
        unmapped = df[df['mapped'] == '']['original'].value_counts().head(10)
        if not unmapped.empty:
            logger.info("Top unmapped compounds:")
            for compound, count in unmapped.items():
                logger.info(f"  {compound}: {count} occurrences")
        
        # Show mapping distribution by medium
        media_stats = df.groupby('medium_id').agg({
            'original': 'count',
            'mapped': lambda x: (x != '').sum()
        }).rename(columns={'original': 'total', 'mapped': 'mapped_count'})
        media_stats['mapping_rate'] = media_stats['mapped_count'] / media_stats['total'] * 100
        
        logger.info(f"Average mapping rate per medium: {media_stats['mapping_rate'].mean():.1f}%")
        logger.info(f"Media with 100% mapping: {(media_stats['mapping_rate'] == 100).sum()}")
        logger.info(f"Media with 0% mapping: {(media_stats['mapping_rate'] == 0).sum()}")
    
    def run_mapping(self):
        """Run the complete mapping process."""
        logger.info("Starting composition to KG mapping process...")
        
        self._process_composition_files()
        self._save_results()
        
        logger.info("Mapping process completed!")

def main():
    """Main function to run the composition mapping."""
    mapper = CompositionKGMapper()
    mapper.run_mapping()

if __name__ == "__main__":
    main()