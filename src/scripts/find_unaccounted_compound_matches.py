#!/usr/bin/env python3
"""
Find ChEBI matches for unaccounted compounds in media compositions.

This script:
1. Collects all unaccounted compounds from computed media properties
2. Loads ChEBI nodes database
3. Performs fuzzy matching with compound name normalization
4. Outputs a mapping file with suggested matches

Usage:
    python find_unaccounted_compound_matches.py [--media-dir MEDIA_DIR] [--chebi-file CHEBI_FILE] [--output OUTPUT_FILE]
"""

import pandas as pd
import json
import re
import logging
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from collections import Counter
from fuzzywuzzy import fuzz, process
import argparse

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('unaccounted_compound_matching.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class UnaccountedCompoundMatcher:
    """
    Find ChEBI matches for unaccounted compounds from media composition analysis.
    """
    
    def __init__(self, 
                 chebi_file: str = "/Users/marcin/Documents/VIMSS/ontology/KG-Hub/KG-Microbe/kg-microbe/data/transformed/ontologies/chebi_nodes.tsv",
                 media_properties_dir: str = "media_properties",
                 min_similarity: int = 70,
                 fast_mode: bool = False):
        
        self.chebi_file = chebi_file
        self.media_properties_dir = Path(media_properties_dir)
        self.min_similarity = min_similarity
        self.fast_mode = fast_mode
        
        # Storage for results
        self.unaccounted_compounds = Counter()
        self.chebi_compounds = {}
        self.matches = []
        
    def collect_unaccounted_compounds(self) -> Set[str]:
        """
        Collect all unaccounted compounds from media properties JSON files.
        
        Returns:
            Set of unique unaccounted compound names
        """
        logger.info("Collecting unaccounted compounds from media properties...")
        
        unaccounted_set = set()
        files_processed = 0
        
        # Check if media_properties directory exists
        if not self.media_properties_dir.exists():
            logger.warning(f"Media properties directory {self.media_properties_dir} does not exist.")
            logger.info("Attempting to collect from individual media files...")
            return self._collect_from_media_files()
        
        # Process all JSON files in media_properties directory
        json_files = list(self.media_properties_dir.glob("*_properties.json"))
        logger.info(f"Found {len(json_files)} media property files")
        
        for json_file in json_files:
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)
                
                # Extract unaccounted compounds
                compound_details = data.get('compound_details', {})
                unaccounted = compound_details.get('unaccounted_compounds', [])
                
                for compound in unaccounted:
                    if compound and compound.lower() not in ['distilled water', 'water']:
                        unaccounted_set.add(compound)
                        self.unaccounted_compounds[compound] += 1
                
                files_processed += 1
                
            except Exception as e:
                logger.warning(f"Error processing {json_file}: {e}")
        
        logger.info(f"Processed {files_processed} files, found {len(unaccounted_set)} unique unaccounted compounds")
        return unaccounted_set
    
    def _collect_from_media_files(self) -> Set[str]:
        """
        Fallback: collect unaccounted compounds by running analysis on media files.
        """
        logger.info("Running media property analysis to collect unaccounted compounds...")
        
        # Import the media properties calculator
        import sys
        sys.path.append('src/scripts')
        from compute_media_properties import MediaPropertiesCalculator
        
        calculator = MediaPropertiesCalculator()
        unaccounted_set = set()
        
        # Find all composition JSON files
        media_files = list(Path("media_pdfs").glob("*_composition.json"))
        logger.info(f"Analyzing {len(media_files)} media composition files...")
        
        for i, media_file in enumerate(media_files[:50]):  # Limit to first 50 for testing
            try:
                with open(media_file, 'r') as f:
                    composition = json.load(f)
                
                results = calculator.analyze_composition(composition)
                
                # Extract unaccounted compounds
                compound_details = results.get('compound_details', {})
                unaccounted = compound_details.get('unaccounted_compounds', [])
                
                for compound in unaccounted:
                    if compound and compound.lower() not in ['distilled water', 'water']:
                        unaccounted_set.add(compound)
                        self.unaccounted_compounds[compound] += 1
                
                if (i + 1) % 10 == 0:
                    logger.info(f"Processed {i + 1}/{len(media_files)} files...")
                    
            except Exception as e:
                logger.warning(f"Error analyzing {media_file}: {e}")
        
        return unaccounted_set
    
    def load_chebi_database(self) -> Dict[str, Dict]:
        """
        Load ChEBI nodes database and create searchable compound dictionary.
        
        Returns:
            Dictionary mapping normalized names to ChEBI data
        """
        logger.info(f"Loading ChEBI database from {self.chebi_file}")
        
        try:
            chebi_df = pd.read_csv(self.chebi_file, sep='\t', low_memory=False)
            logger.info(f"Loaded {len(chebi_df)} ChEBI entries")
            
            # Filter for chemical entities if category column exists
            if 'category' in chebi_df.columns:
                chem_mask = chebi_df['category'].str.contains('ChemicalEntity|ChemicalSubstance', na=False)
                chebi_df = chebi_df[chem_mask]
                logger.info(f"Filtered to {len(chebi_df)} chemical entities")
            
            compounds = {}
            
            for _, row in chebi_df.iterrows():
                entry_id = row.get('id', '')
                name = row.get('name', '')
                synonyms = row.get('synonym', '')
                
                # Add main name
                if pd.notna(name) and name.strip():
                    normalized_name = self._normalize_compound_name(name)
                    if normalized_name:
                        compounds[normalized_name] = {
                            'id': entry_id,
                            'label': name.strip(),
                            'original_name': name.strip()
                        }
                
                # Add synonyms
                if pd.notna(synonyms) and synonyms.strip():
                    synonym_list = [s.strip() for s in synonyms.split('|') if s.strip()]
                    for synonym in synonym_list:
                        normalized_syn = self._normalize_compound_name(synonym)
                        if normalized_syn and normalized_syn not in compounds:
                            compounds[normalized_syn] = {
                                'id': entry_id,
                                'label': synonym.strip(),
                                'original_name': name.strip()  # Keep original name as primary
                            }
            
            logger.info(f"Created searchable database with {len(compounds)} normalized compound names")
            return compounds
            
        except Exception as e:
            logger.error(f"Error loading ChEBI database: {e}")
            raise
    
    def _normalize_compound_name(self, name: str) -> str:
        """
        Normalize compound name for matching.
        
        Handles:
        - Hydration notation removal (x N H2O, • N H2O, . N H2O)
        - Greek/Latin prefix to number conversion (di- = 2, tri- = 3, etc.)
        - Case normalization
        - Stereochemistry removal
        - Whitespace normalization
        
        Args:
            name: Original compound name
            
        Returns:
            Normalized name for matching
        """
        if not name or pd.isna(name):
            return ""
        
        # Convert to lowercase and strip
        normalized = name.lower().strip()
        
        # Remove hydration notation - this is key for the user's request
        # Handle various hydration formats: x N H2O, • N H2O, . N H2O
        normalized = re.sub(r'\s*[x•·]\s*\d+\s*h2o\s*$', '', normalized, flags=re.IGNORECASE)
        normalized = re.sub(r'\s*[x•·]\s*\d+\s*h₂o\s*$', '', normalized, flags=re.IGNORECASE)
        normalized = re.sub(r'\s*\.\s*\d+\s*h2o\s*$', '', normalized, flags=re.IGNORECASE)
        
        # Remove other hydration patterns with Greek/Latin prefixes
        normalized = re.sub(r'\s*hydrate\s*$', '', normalized, flags=re.IGNORECASE)
        normalized = re.sub(r'\s*monohydrate\s*$', '', normalized, flags=re.IGNORECASE)
        normalized = re.sub(r'\s*dihydrate\s*$', '', normalized, flags=re.IGNORECASE)
        normalized = re.sub(r'\s*trihydrate\s*$', '', normalized, flags=re.IGNORECASE)
        normalized = re.sub(r'\s*tetrahydrate\s*$', '', normalized, flags=re.IGNORECASE)
        normalized = re.sub(r'\s*pentahydrate\s*$', '', normalized, flags=re.IGNORECASE)
        normalized = re.sub(r'\s*hexahydrate\s*$', '', normalized, flags=re.IGNORECASE)
        normalized = re.sub(r'\s*heptahydrate\s*$', '', normalized, flags=re.IGNORECASE)
        normalized = re.sub(r'\s*octahydrate\s*$', '', normalized, flags=re.IGNORECASE)
        normalized = re.sub(r'\s*nonahydrate\s*$', '', normalized, flags=re.IGNORECASE)
        normalized = re.sub(r'\s*decahydrate\s*$', '', normalized, flags=re.IGNORECASE)
        
        # Remove stereochemistry indicators
        normalized = re.sub(r'^[dl]-', '', normalized)
        normalized = re.sub(r'^[lr]-', '', normalized)
        normalized = re.sub(r'^[+-]', '', normalized)
        normalized = re.sub(r'^\([dlr+-]+\)-?', '', normalized)
        
        # Remove parenthetical content EXCEPT chemical formulas
        # Preserve patterns like (NH4), (PO4), (SO4), etc.
        # Only remove parentheses that contain stereochemistry or descriptive text
        
        # Common stereochemistry patterns to remove
        stereo_patterns = [
            r'\([dlr][+-]?\)',  # (d), (l), (r), (d+), etc.
            r'\([+-]\)',        # (+), (-)
            r'\(cis\)', r'\(trans\)',  # (cis), (trans)
            r'\(alpha\)', r'\(beta\)', r'\(gamma\)',  # Greek letters
            r'\([eEzZrRsS]\)',  # E/Z, R/S stereochemistry
        ]
        
        for pattern in stereo_patterns:
            normalized = re.sub(pattern, '', normalized, flags=re.IGNORECASE)
        
        # DO NOT remove parentheses with chemical formulas
        # These contain uppercase letters followed by optional lowercase and numbers
        # Examples: (NH4), (PO4), (SO4), (CO3), etc.
        
        # Normalize common chemical notation
        normalized = re.sub(r'\s*,\s*', ', ', normalized)  # Standardize comma spacing
        normalized = re.sub(r'\s+', ' ', normalized)  # Normalize whitespace
        normalized = normalized.strip()
        
        # Remove trailing punctuation
        normalized = normalized.rstrip('.,;:')
        
        return normalized
    
    def _get_hydration_number(self, name: str) -> Optional[int]:
        """
        Extract hydration number from compound name.
        
        Args:
            name: Compound name
            
        Returns:
            Number of water molecules, or None if not found
        """
        name_lower = name.lower().strip()
        
        # Check for explicit number patterns: x N H2O, • N H2O, . N H2O
        patterns = [
            r'[x•·]\s*(\d+)\s*h2o',
            r'\.\s*(\d+)\s*h2o',
            r'[x•·]\s*(\d+)\s*h₂o'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, name_lower)
            if match:
                return int(match.group(1))
        
        # Check for Greek/Latin prefix patterns
        prefix_to_number = {
            'mono': 1, 'uni': 1,
            'di': 2, 'bi': 2,
            'tri': 3, 'ter': 3,
            'tetra': 4, 'quad': 4,
            'penta': 5, 'quin': 5,
            'hexa': 6, 'sex': 6,
            'hepta': 7, 'sept': 7,
            'octa': 8, 'oct': 8,
            'nona': 9, 'non': 9,
            'deca': 10, 'dec': 10,
            'undeca': 11,
            'dodeca': 12
        }
        
        for prefix, number in prefix_to_number.items():
            if f'{prefix}hydrate' in name_lower:
                return number
        
        return None
    
    def _create_hydration_variants(self, base_name: str) -> List[str]:
        """
        Create multiple hydration variants of a compound name for matching.
        
        Args:
            base_name: Base compound name without hydration
            
        Returns:
            List of possible hydration variants
        """
        variants = [base_name]  # Include the base name
        
        # Common hydration states and their notations
        hydration_variants = [
            # Explicit number notation
            (1, f"{base_name}.h2o", f"{base_name} h2o"),
            (2, f"{base_name}.2h2o", f"{base_name} 2h2o"),
            (3, f"{base_name}.3h2o", f"{base_name} 3h2o"),
            (4, f"{base_name}.4h2o", f"{base_name} 4h2o"),
            (5, f"{base_name}.5h2o", f"{base_name} 5h2o"),
            (6, f"{base_name}.6h2o", f"{base_name} 6h2o"),
            (7, f"{base_name}.7h2o", f"{base_name} 7h2o"),
            (8, f"{base_name}.8h2o", f"{base_name} 8h2o"),
            (9, f"{base_name}.9h2o", f"{base_name} 9h2o"),
            (10, f"{base_name}.10h2o", f"{base_name} 10h2o"),
            
            # Greek/Latin prefix notation
            (1, f"{base_name} monohydrate", f"{base_name}monohydrate"),
            (2, f"{base_name} dihydrate", f"{base_name}dihydrate"),
            (3, f"{base_name} trihydrate", f"{base_name}trihydrate"),
            (4, f"{base_name} tetrahydrate", f"{base_name}tetrahydrate"),
            (5, f"{base_name} pentahydrate", f"{base_name}pentahydrate"),
            (6, f"{base_name} hexahydrate", f"{base_name}hexahydrate"),
            (7, f"{base_name} heptahydrate", f"{base_name}heptahydrate"),
            (8, f"{base_name} octahydrate", f"{base_name}octahydrate"),
            (9, f"{base_name} nonahydrate", f"{base_name}nonahydrate"),
            (10, f"{base_name} decahydrate", f"{base_name}decahydrate")
        ]
        
        # Add the variants (skip number, just add the name variants)
        for _, *names in hydration_variants:
            variants.extend(names)
        
        return variants
    
    def find_matches(self, unaccounted_compounds: Set[str], chebi_compounds: Dict[str, Dict]) -> List[Dict]:
        """
        Find best matches for unaccounted compounds in ChEBI database.
        
        Args:
            unaccounted_compounds: Set of unaccounted compound names
            chebi_compounds: Dictionary of ChEBI compounds
            
        Returns:
            List of match dictionaries
        """
        logger.info(f"Finding matches for {len(unaccounted_compounds)} unaccounted compounds...")
        
        matches = []
        chebi_names = list(chebi_compounds.keys())
        chebi_labels = [chebi_compounds[name]['label'] for name in chebi_names]
        
        for i, compound in enumerate(sorted(unaccounted_compounds)):
            logger.debug(f"Processing {i+1}/{len(unaccounted_compounds)}: {compound}")
            
            # Normalize the unaccounted compound name
            normalized_compound = self._normalize_compound_name(compound)
            
            if not normalized_compound:
                continue
            
            best_match = None
            best_score = 0
            best_chebi_data = None
            matching_method = ""
            
            # 1. Try exact match first
            if normalized_compound in chebi_compounds:
                best_match = chebi_compounds[normalized_compound]['label']
                best_score = 100
                best_chebi_data = chebi_compounds[normalized_compound]
                matching_method = "exact_normalized"
            else:
                # 2. Try hydration-aware matching
                # Extract hydration number from original compound
                hydration_number = self._get_hydration_number(compound)
                
                if hydration_number is not None:
                    # Try to find ChEBI compounds with matching hydration
                    base_compound = normalized_compound
                    
                    # Create possible hydration variants to search for
                    search_variants = []
                    
                    # Search for compounds that might have prefix notation in ChEBI
                    prefix_map = {
                        1: ['mono', 'uni'],
                        2: ['di', 'bi'], 
                        3: ['tri', 'ter'],
                        4: ['tetra', 'quad'],
                        5: ['penta', 'quin'],
                        6: ['hexa', 'sex'],
                        7: ['hepta', 'sept'],
                        8: ['octa', 'oct'],
                        9: ['nona', 'non'],
                        10: ['deca', 'dec'],
                        11: ['undeca'],
                        12: ['dodeca']
                    }
                    
                    if hydration_number in prefix_map:
                        for prefix in prefix_map[hydration_number]:
                            search_variants.extend([
                                f"{base_compound} {prefix}hydrate",
                                f"{base_compound}{prefix}hydrate",
                                f"{base_compound}.{hydration_number}h2o",
                                f"{base_compound} {hydration_number}h2o"
                            ])
                    
                    # Also try reverse: look for ChEBI compounds that end with hydration notation
                    # and see if their base matches our compound
                    for chebi_name, chebi_data in chebi_compounds.items():
                        chebi_hydration = self._get_hydration_number(chebi_data['label'])
                        if chebi_hydration == hydration_number:
                            chebi_base = self._normalize_compound_name(chebi_data['label'])
                            if chebi_base == base_compound:
                                best_match = chebi_data['label']
                                best_score = 100
                                best_chebi_data = chebi_data
                                matching_method = "hydration_aware_exact"
                                break
                            elif fuzz.ratio(chebi_base, base_compound) >= 90:
                                score = fuzz.ratio(chebi_base, base_compound)
                                if score > best_score:
                                    best_match = chebi_data['label']
                                    best_score = score
                                    best_chebi_data = chebi_data
                                    matching_method = "hydration_aware_fuzzy"
                    
                    # Try exact match on our search variants
                    if best_score < 100:
                        for variant in search_variants:
                            if variant in chebi_compounds:
                                best_match = chebi_compounds[variant]['label']
                                best_score = 100
                                best_chebi_data = chebi_compounds[variant]
                                matching_method = "hydration_variant_exact"
                                break
                
                # 3. Try fuzzy matching on normalized names (if no hydration match found)
                if best_score < 90 and not self.fast_mode:
                    fuzzy_results = process.extractOne(
                        normalized_compound, 
                        chebi_names, 
                        scorer=fuzz.ratio,
                        score_cutoff=self.min_similarity
                    )
                    
                    if fuzzy_results and fuzzy_results[1] > best_score:
                        matched_name, score = fuzzy_results
                        best_match = chebi_compounds[matched_name]['label']
                        best_score = score
                        best_chebi_data = chebi_compounds[matched_name]
                        matching_method = "fuzzy_normalized"
                
                # 4. Also try fuzzy matching on original labels (only for high-priority compounds in fast mode)
                if best_score < 90 and (not self.fast_mode or normalized_compound in ['(nh4)2co3', '(nh4)2hpo4', '(nh4)2so4', 'nh4cl', '(nh4)hco3']):
                    label_results = process.extractOne(
                        normalized_compound,
                        chebi_labels,
                        scorer=fuzz.ratio,
                        score_cutoff=self.min_similarity
                    )
                    
                    if label_results and label_results[1] > best_score:
                        matched_label, score = label_results
                        # Find the corresponding ChEBI data
                        for name, data in chebi_compounds.items():
                            if data['label'] == matched_label:
                                best_match = matched_label
                                best_score = score
                                best_chebi_data = data
                                matching_method = "fuzzy_label"
                                break
            
            # Record the match (or lack thereof)
            match_result = {
                'original_compound': compound,
                'normalized_compound': normalized_compound,
                'frequency': self.unaccounted_compounds[compound],
                'chebi_match': best_match if best_score >= self.min_similarity else '',
                'chebi_id': best_chebi_data['id'] if best_chebi_data else '',
                'chebi_original_name': best_chebi_data['original_name'] if best_chebi_data else '',
                'similarity_score': best_score if best_score >= self.min_similarity else 0,
                'match_confidence': self._get_confidence_level(best_score),
                'matching_method': matching_method if best_score >= self.min_similarity else 'no_match',
                'hydration_number': self._get_hydration_number(compound)
            }
            
            matches.append(match_result)
            
            if (i + 1) % 50 == 0:
                logger.info(f"Processed {i + 1}/{len(unaccounted_compounds)} compounds...")
        
        return matches
    
    def _get_confidence_level(self, score: float) -> str:
        """Get confidence level based on similarity score."""
        if score >= 95:
            return 'very_high'
        elif score >= 85:
            return 'high'
        elif score >= 75:
            return 'medium'
        elif score >= 70:
            return 'low'
        else:
            return 'no_match'
    
    def save_results(self, matches: List[Dict], output_file: str = "unaccounted_compound_matches.tsv"):
        """
        Save matching results to TSV file.
        
        Args:
            matches: List of match dictionaries
            output_file: Output file path
        """
        logger.info(f"Saving results to {output_file}")
        
        # Convert to DataFrame
        df = pd.DataFrame(matches)
        
        # Sort by frequency (most common first) and then by similarity score
        df = df.sort_values(['frequency', 'similarity_score'], ascending=[False, False])
        
        # Reorder columns
        column_order = [
            'original_compound', 
            'normalized_compound',
            'hydration_number',
            'frequency',
            'chebi_match', 
            'chebi_id', 
            'chebi_original_name',
            'similarity_score', 
            'match_confidence',
            'matching_method'
        ]
        df = df.reindex(columns=column_order)
        
        # Save to TSV
        df.to_csv(output_file, sep='\t', index=False)
        
        # Generate summary statistics
        self._generate_summary(df, output_file)
    
    def _generate_summary(self, df: pd.DataFrame, output_file: str):
        """Generate and log summary statistics."""
        total_compounds = len(df)
        matched_compounds = len(df[df['similarity_score'] > 0])
        
        confidence_counts = df['match_confidence'].value_counts()
        
        logger.info(f"""
=== MATCHING SUMMARY ===
Output file: {output_file}
Total unaccounted compounds: {total_compounds}
Successfully matched: {matched_compounds} ({matched_compounds/total_compounds*100:.1f}%)
Unmatched: {total_compounds - matched_compounds} ({(total_compounds - matched_compounds)/total_compounds*100:.1f}%)

Match confidence distribution:
{confidence_counts.to_string()}

Top 10 most frequent unaccounted compounds:
""")
        
        top_compounds = df.nlargest(10, 'frequency')[['original_compound', 'frequency', 'chebi_match', 'similarity_score']]
        for _, row in top_compounds.iterrows():
            match_info = f"→ {row['chebi_match']} ({row['similarity_score']:.0f}%)" if row['chebi_match'] else "→ No match"
            logger.info(f"  {row['original_compound']} (freq: {row['frequency']}) {match_info}")
    
    def run_matching(self, output_file: str = "unaccounted_compound_matches.tsv"):
        """
        Run the complete matching process.
        
        Args:
            output_file: Output file path
        """
        logger.info("Starting unaccounted compound matching process...")
        
        # Step 1: Collect unaccounted compounds
        unaccounted_compounds = self.collect_unaccounted_compounds()
        
        if not unaccounted_compounds:
            logger.warning("No unaccounted compounds found. Make sure media property analysis has been run.")
            return
        
        # Step 2: Load ChEBI database
        self.chebi_compounds = self.load_chebi_database()
        
        # Step 3: Find matches
        self.matches = self.find_matches(unaccounted_compounds, self.chebi_compounds)
        
        # Step 4: Save results
        self.save_results(self.matches, output_file)
        
        logger.info("Matching process completed!")

def main():
    """Main function for command-line usage."""
    parser = argparse.ArgumentParser(description='Find ChEBI matches for unaccounted compounds')
    parser.add_argument('--media-dir', 
                        default='media_properties',
                        help='Directory containing media properties JSON files')
    parser.add_argument('--chebi-file', 
                        default='/Users/marcin/Documents/VIMSS/ontology/KG-Hub/KG-Microbe/kg-microbe/data/transformed/ontologies/chebi_nodes.tsv',
                        help='Path to ChEBI nodes TSV file')
    parser.add_argument('--output', 
                        default='unaccounted_compound_matches.tsv',
                        help='Output TSV file for matches')
    parser.add_argument('--min-similarity', 
                        type=int, 
                        default=70,
                        help='Minimum similarity score for matches (0-100)')
    parser.add_argument('--fast-mode', 
                        action='store_true',
                        help='Fast mode: prioritize exact matches and reduce fuzzy search')
    parser.add_argument('-v', '--verbose', 
                        action='store_true',
                        help='Verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Initialize matcher
    matcher = UnaccountedCompoundMatcher(
        chebi_file=args.chebi_file,
        media_properties_dir=args.media_dir,
        min_similarity=args.min_similarity,
        fast_mode=args.fast_mode
    )
    
    # Run matching process
    matcher.run_matching(args.output)

if __name__ == "__main__":
    main()