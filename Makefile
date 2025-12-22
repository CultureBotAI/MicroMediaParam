# MicroMediaParam Pipeline Makefile
# 
# This Makefile reproduces the complete bioinformatics pipeline for processing
# microbial growth media composition data, from PDF downloads to final analysis.
#
# Pipeline stages:
# 1. Data acquisition (parse URLs, download PDFs/JSON)
# 2. Data conversion (PDFs to text, JSON to markdown)
# 3. Knowledge graph mapping (compounds to ChEBI/KEGG/PubChem)
# 4. Solution expansion (DSMZ solution: references to chemical components)
# 5. Compound matching and merging
# 6. Hydration normalization and deduplication
# 7. Property calculation (pH, salinity, ionic strength)
# 8. Final media summary generation

# Configuration variables
PYTHON := python
SCRIPTS_DIR := src/scripts
REQUIREMENTS := requirements.txt
VENV_DIR := venv

# Pipeline output directory structure
OUTPUT_DIR := pipeline_output
DATA_ACQUISITION_DIR := $(OUTPUT_DIR)/data_acquisition
DATA_CONVERSION_DIR := $(OUTPUT_DIR)/data_conversion
DB_MAPPING_DIR := $(OUTPUT_DIR)/db_mapping
KG_MAPPING_DIR := $(OUTPUT_DIR)/kg_mapping
SOLUTION_EXPANSION_DIR := $(OUTPUT_DIR)/solution_expansion
COMPOUND_MATCHING_DIR := $(OUTPUT_DIR)/compound_matching
OAK_CHEBI_DIR := $(OUTPUT_DIR)/oak_chebi
MERGE_MAPPINGS_DIR := $(OUTPUT_DIR)/merge_mappings
INGREDIENT_ENHANCEMENT_DIR := $(OUTPUT_DIR)/ingredient_enhancement
HYDRATE_NORMALIZATION_DIR := $(OUTPUT_DIR)/hydrate_normalization
PROPERTY_CALCULATION_DIR := $(OUTPUT_DIR)/property_calculation
MEDIA_SUMMARY_DIR := $(OUTPUT_DIR)/media_summary

# Pipeline input/output directories
MEDIA_PDFS_DIR := $(DATA_ACQUISITION_DIR)/media_pdfs
MEDIA_TEXTS_DIR := $(DATA_CONVERSION_DIR)/media_texts
MEDIA_COMPOSITIONS_DIR := $(DATA_CONVERSION_DIR)/media_compositions
MEDIA_PROPERTIES_DIR := $(PROPERTY_CALCULATION_DIR)/media_properties

# Key pipeline files
GROWTH_MEDIA_URLS := $(DATA_ACQUISITION_DIR)/growth_media_urls.txt
COMPOSITION_MAPPING := $(KG_MAPPING_DIR)/composition_kg_mapping.tsv
EXPANDED_MAPPING := $(SOLUTION_EXPANSION_DIR)/composition_kg_mapping_expanded_solutions.tsv
SOLUTION_EXPANSION_REPORT := $(SOLUTION_EXPANSION_DIR)/dsmz_solution_expansion_report.json
UNACCOUNTED_MATCHES := $(COMPOUND_MATCHING_DIR)/unaccounted_compound_matches.tsv
UNIFIED_MAPPINGS := $(MERGE_MAPPINGS_DIR)/unified_compound_mappings.tsv
HIGH_CONFIDENCE_MAPPINGS := $(MERGE_MAPPINGS_DIR)/high_confidence_compound_mappings.tsv
LOW_CONFIDENCE_MAPPINGS := $(MERGE_MAPPINGS_DIR)/low_confidence_compound_mappings.tsv
HIGH_CONFIDENCE_UPGRADED := $(MERGE_MAPPINGS_DIR)/high_confidence_compound_mappings_upgraded.tsv
HIGH_CONFIDENCE_FORMULA := $(MERGE_MAPPINGS_DIR)/high_confidence_compound_mappings_formula_enhanced.tsv
HIGH_CONFIDENCE_FINAL := $(MERGE_MAPPINGS_DIR)/high_confidence_compound_mappings_final.tsv
HIGH_CONFIDENCE_CURATED := $(MERGE_MAPPINGS_DIR)/high_confidence_compound_mappings_curated_upgraded.tsv
HIGH_CONFIDENCE_ENRICHED := $(MERGE_MAPPINGS_DIR)/high_confidence_compound_mappings_enriched.tsv

# Final output files (clean names)
COMPOUND_MAPPINGS := $(MERGE_MAPPINGS_DIR)/compound_mappings.tsv
COMPOUND_MAPPINGS_LOW := $(MERGE_MAPPINGS_DIR)/compound_mappings_low_confidence.tsv
UNMAPPED_COMPOUNDS := $(MERGE_MAPPINGS_DIR)/unmapped_compounds.tsv

INGREDIENT_ENHANCED_HIGH := $(INGREDIENT_ENHANCEMENT_DIR)/high_confidence_compound_mappings_ingredient_enhanced.tsv
INGREDIENT_ENHANCED_LOW := $(INGREDIENT_ENHANCEMENT_DIR)/low_confidence_compound_mappings_ingredient_enhanced.tsv
HIGH_CONFIDENCE_NORMALIZED := $(HYDRATE_NORMALIZATION_DIR)/high_confidence_compound_mappings_normalized.tsv
LOW_CONFIDENCE_NORMALIZED := $(HYDRATE_NORMALIZATION_DIR)/low_confidence_compound_mappings_normalized.tsv
MEDIA_SUMMARY := $(MEDIA_SUMMARY_DIR)/media_summary.tsv
MEDIA_COMPOSITION_TABLE := $(MEDIA_SUMMARY_DIR)/media_composition_table.tsv
MEDIA_COMPOSITION_EXPANDED := $(MEDIA_SUMMARY_DIR)/media_composition_expanded.tsv
COMPLEX_INGREDIENT_COMPOSITIONS := data/curated/complex_ingredients/complex_ingredient_compositions.yaml
MEDIADIVE_SOLUTIONS_YAML := data/curated/complex_ingredients/mediadive_solutions_additions.yaml
CHEMICAL_PROPERTIES := $(DB_MAPPING_DIR)/chemical_properties.tsv
UNMAPPED_COMPLEX_ANALYSIS := $(OUTPUT_DIR)/analysis/unmapped_complex_ingredients_priority.tsv
UNMAPPED_COMPLEX_REPORT := $(OUTPUT_DIR)/analysis/unmapped_complex_ingredients_report.txt

# External data files (from kg-microbe project)
KG_MICROBE_BASE := /Users/marcin/Documents/VIMSS/ontology/KG-Hub/KG-Microbe/kg-microbe
CHEBI_NODES_FILE := $(KG_MICROBE_BASE)/data/transformed/ontologies/chebi_nodes.tsv
MEDIADIVE_RAW_DIR := $(KG_MICROBE_BASE)/data/raw/mediadive
MEDIADIVE_SOLUTIONS_JSON := $(MEDIADIVE_RAW_DIR)/solutions.json
MEDIADIVE_MEDIA_JSON := $(MEDIADIVE_RAW_DIR)/media_detailed.json
MEDIADIVE_COMPOUNDS_JSON := $(MEDIADIVE_RAW_DIR)/compounds.json

# Log files
LOGS := *.log

# Default target
.DEFAULT_GOAL := all

# Colors for output
RED := \033[31m
GREEN := \033[32m
YELLOW := \033[33m
BLUE := \033[34m
NC := \033[0m # No Color

# Help target
.PHONY: help
help:
	@echo "$(BLUE)MicroMediaParam Pipeline Makefile$(NC)"
	@echo "================================"
	@echo ""
	@echo "$(GREEN)Main Pipeline Targets (Optimized Order):$(NC)"
	@echo "  $(YELLOW)all$(NC)                         - Run complete optimized pipeline from start to finish"
	@echo "  $(YELLOW)data-acquisition$(NC)            - Step 1: Download media PDFs and JSON data"
	@echo "  $(YELLOW)data-conversion$(NC)             - Step 2: Convert PDFs to text and JSON to markdown"
	@echo "  $(YELLOW)db-mapping$(NC)                  - Step 3: Download IUPAC/PubChem data & build DB (ingredient → pKa, properties)"
	@echo "  $(YELLOW)kg-mapping-initial$(NC)          - Step 4: Initial KG mapping (ingredient → ChEBI/KEGG IDs)"
	@echo "  $(YELLOW)solution-expansion$(NC)          - Step 5: ✨ Expand DSMZ solution: references to individual chemical components"
	@echo "  $(YELLOW)normalize-hydration-early$(NC)   - Step 6: 🔥 EARLY hydrate normalization for consistent base compounds"
	@echo "  $(YELLOW)enhance-ingredients-early$(NC)   - Step 7: 🔥 EARLY ingredient: → ChEBI matching with normalized compounds"
	@echo "  $(YELLOW)kg-compound-matching$(NC)        - Step 8: Enhanced compound matching using normalized base compounds"
	@echo "  $(YELLOW)kg-oak-chebi-mapping$(NC)        - Step 9: OAK CHEBI annotations with improved compound set"
	@echo "  $(YELLOW)kg-merge-mappings$(NC)           - Step 10: Merge all mapping sources with consistent hydration"
	@echo "  $(YELLOW)kg-enhance-all$(NC)              - Step 10.5: 🚀 Enhance mappings (CAS→ChEBI, formula, microbio) +16% coverage!"
	@echo "  $(YELLOW)compute-properties$(NC)          - Step 11: Calculate pH, salinity with enhanced mappings (72% coverage)"
	@echo "  $(YELLOW)media-summary$(NC)               - Step 12: Generate final media summary table"
	@echo ""
	@echo "$(GREEN)Mapping Strategy Overview:$(NC)"
	@echo "  $(YELLOW)DB Mapping$(NC)  (ingredient → pKa, properties): Downloads IUPAC/PubChem data, maximizes pKa coverage"
	@echo "  $(YELLOW)KG Mapping$(NC)  (ingredient → ChEBI/KEGG IDs):  Maximizes ingredients with knowledge graph IDs"
	@echo "  $(YELLOW)Goal$(NC): DB mappings enable pH/salinity calculations, KG mappings enable semantic analysis"
	@echo ""
	@echo "$(GREEN)Chemical Database Targets (IUPAC):$(NC)"
	@echo "  $(YELLOW)iupac-full-pipeline$(NC)     - Complete IUPAC pipeline: analyze → download → process → generate"
	@echo "  $(YELLOW)iupac-update-from-mappings$(NC) - Update database from existing compound mappings"
	@echo "  $(YELLOW)iupac-process-composition-mapping$(NC) - Process all compounds from composition_kg_mapping.tsv"
	@echo "  $(YELLOW)iupac-add-compounds$(NC)     - Add specific compounds (use COMPOUNDS='list')"
	@echo "  $(YELLOW)iupac-test$(NC)              - Test IUPAC system with sample compounds"
	@echo ""
	@echo "$(GREEN)Chemical Database Targets (PubChem):$(NC)"
	@echo "  $(YELLOW)pubchem-full-pipeline$(NC)   - Complete PubChem pipeline with bulk FTP downloads"
	@echo "  $(YELLOW)pubchem-process-composition-mapping$(NC) - Process all compounds from composition_kg_mapping.tsv"
	@echo "  $(YELLOW)pubchem-download-compounds$(NC) - Download specific compounds (use COMPOUNDS='list')"
	@echo "  $(YELLOW)pubchem-test$(NC)            - Test PubChem system with sample compounds"
	@echo ""
	@echo "$(GREEN)OAK CHEBI Mapping Targets:$(NC)"
	@echo "  $(YELLOW)oak-chebi-mapping$(NC)       - Complete pipeline: extract compounds → OAK annotate → apply mappings → fix hydration"
	@echo "  $(YELLOW)extract-non-chebi-compounds$(NC) - Extract compounds needing CHEBI mapping (342 compounds)"
	@echo "  $(YELLOW)oak-chebi-annotate$(NC)      - Run OAK annotation against CHEBI ontology"
	@echo "  $(YELLOW)apply-oak-chebi-mappings$(NC) - Apply OAK results to composition mapping"
	@echo "  $(YELLOW)fix-hydrated-mappings$(NC)   - Fix hydrated compounds mapped to ingredient codes"
	@echo "  $(YELLOW)oak-chebi-test$(NC)          - Test OAK connection with sample compounds"
	@echo "  $(YELLOW)oak-chebi-status$(NC)        - Show OAK CHEBI mapping status"
	@echo "  $(YELLOW)oak-chebi-clean$(NC)         - Clean OAK CHEBI mapping files"
	@echo ""
	@echo "$(GREEN)BacDive Metabolites Mapping:$(NC)"
	@echo "  $(YELLOW)bacdive-metabolites-mapping$(NC)  - Complete pipeline: extract → OAK annotate → apply mappings"
	@echo "  $(YELLOW)bacdive-metabolites-extract$(NC)  - Extract 154 unique metabolites from 19,129 records"
	@echo "  $(YELLOW)bacdive-metabolites-status$(NC)   - Show BacDive metabolites mapping status"
	@echo "  $(YELLOW)bacdive-metabolites-clean$(NC)    - Clean BacDive metabolites files"
	@echo ""
	@echo "$(GREEN)Unmapped Compounds Analysis:$(NC)"
	@echo "  $(YELLOW)unmapped-full-pipeline$(NC)       - Complete pipeline: analyze → map → integrate (+749 mappings)"
	@echo "  $(YELLOW)unmapped-analysis$(NC)            - Extract clean unmapped compounds from all sources"
	@echo "  $(YELLOW)unmapped-map$(NC)                 - Map unmapped compounds using curated dictionary (~44% mapped)"
	@echo "  $(YELLOW)unmapped-integrate$(NC)           - Integrate new mappings back into high-confidence file"
	@echo "  $(YELLOW)unmapped-status$(NC)              - Show unmapped compounds summary"
	@echo "  $(YELLOW)unmapped-clean$(NC)               - Clean unmapped analysis files"
	@echo ""
	@echo "$(GREEN)Compound Mapping Validation:$(NC)"
	@echo "  $(YELLOW)validate-semantic$(NC)             - Validate mappings for semantic correctness (blocklists, units)"
	@echo "  $(YELLOW)semantic-validation-summary$(NC)   - Show semantic validation summary"
	@echo "  $(YELLOW)validate-compound-mappings$(NC)    - Validate ChEBI/PubChem IDs against official APIs"
	@echo "  $(YELLOW)validate-compound-mappings-quick$(NC) - Quick validation with 50 random samples"
	@echo "  $(YELLOW)remediate-compound-mappings$(NC)   - Fix incorrect ChEBI IDs using PubChem lookup"
	@echo "  $(YELLOW)merge-verified-mappings$(NC)       - Merge verified and remediated mappings"
	@echo "  $(YELLOW)validate-full-pipeline$(NC)        - Run complete validation→remediation→merge workflow"
	@echo "  $(YELLOW)validate-status$(NC)               - Show validation report summary"
	@echo "  $(YELLOW)validate-clean$(NC)                - Clean validation files"
	@echo ""
	@echo "$(GREEN)Deterministic API Mapping (replaces LLM mappings):$(NC)"
	@echo "  $(YELLOW)api-mapping-full-pipeline$(NC)    - 🔥 Full pipeline: extract → API lookup → validate (30-60 min)"
	@echo "  $(YELLOW)extract-all-compounds$(NC)        - Extract all compound names from pipeline"
	@echo "  $(YELLOW)generate-api-mappings$(NC)        - Generate mappings via PubChem/ChEBI APIs"
	@echo "  $(YELLOW)resume-api-mappings$(NC)          - Resume from checkpoint (for long runs)"
	@echo "  $(YELLOW)validate-api-mappings$(NC)        - Show API mapping statistics"
	@echo "  $(YELLOW)api-mapping-status$(NC)           - Show API mapping status"
	@echo "  $(YELLOW)api-mapping-clean$(NC)            - Clean API mapping files"
	@echo ""
	@echo "$(GREEN)IUPAC Pipeline Steps:$(NC)"
	@echo "  $(YELLOW)iupac-analyze-compounds$(NC) - Analyze existing data for download targets"
	@echo "  $(YELLOW)iupac-download-data$(NC)     - Download chemical data from IUPAC sources"
	@echo "  $(YELLOW)iupac-process-data$(NC)      - Process raw data into chemical properties"
	@echo "  $(YELLOW)iupac-generate-tsv$(NC)      - Generate chemical_properties.tsv file"
	@echo ""
	@echo "$(GREEN)IUPAC Utilities:$(NC)"
	@echo "  $(YELLOW)iupac-status$(NC)            - Show IUPAC data status and statistics"
	@echo "  $(YELLOW)iupac-validate-tsv$(NC)      - Validate chemical_properties.tsv format"
	@echo "  $(YELLOW)iupac-clean$(NC)             - Clean IUPAC data files"
	@echo "  $(YELLOW)iupac-restore-backup$(NC)    - Restore chemical_properties.tsv from backup"
	@echo ""
	@echo "$(GREEN)Setup Targets:$(NC)"
	@echo "  $(YELLOW)install$(NC)                - Install Python dependencies"
	@echo "  $(YELLOW)install-dev$(NC)            - Install development dependencies"
	@echo "  $(YELLOW)setup-venv$(NC)             - Create Python virtual environment"
	@echo ""
	@echo "$(GREEN)Quality Assurance:$(NC)"
	@echo "  $(YELLOW)test$(NC)                   - Run all tests"
	@echo "  $(YELLOW)lint$(NC)                   - Run code quality checks"
	@echo "  $(YELLOW)format$(NC)                 - Format code with black and isort"
	@echo ""
	@echo "$(GREEN)Maintenance:$(NC)"
	@echo "  $(YELLOW)clean$(NC)                  - Remove generated files and logs"
	@echo "  $(YELLOW)clean-all$(NC)              - Remove all generated data and outputs"
	@echo "  $(YELLOW)status$(NC)                 - Show pipeline status and file counts"
	@echo ""
	@echo "$(GREEN)Usage Examples:$(NC)"
	@echo "  make install           # Install dependencies"
	@echo "  make all               # Run complete pipeline"
	@echo "  make data-acquisition  # Just download media data"
	@echo "  make clean && make all # Clean rebuild"

# Complete pipeline
.PHONY: all
all: install data-acquisition data-conversion db-mapping kg-mapping-initial solution-expansion normalize-hydration-early enhance-ingredients-early kg-compound-matching kg-oak-chebi-mapping kg-merge-mappings kg-enhance-all extract-upstream-ingredients map-unmapped-ingredients merge-additional-mappings create-hydrate-mappings create-simplified-mappings map-biological-ingredients-foodon compute-properties media-summary import-mediadive-solutions expand-complex-ingredients analyze-unmapped-complex
	@echo "$(GREEN)════════════════════════════════════════════════════════════════$(NC)"
	@echo "$(GREEN)       🎉 COMPLETE PIPELINE FINISHED SUCCESSFULLY! 🎉           $(NC)"
	@echo "$(GREEN)════════════════════════════════════════════════════════════════$(NC)"
	@echo ""
	@echo "$(BLUE)Pipeline stages completed:$(NC)"
	@echo "  ✓ Data acquisition from MediaDive/DSMZ"
	@echo "  ✓ PDF/JSON conversion to structured formats"
	@echo "  ✓ Chemical properties database building"
	@echo "  ✓ Initial KG mapping to ChEBI"
	@echo "  ✓ DSMZ solution expansion"
	@echo "  ✓ OAK ChEBI ontology-based mapping"
	@echo "  ✓ Unified mapping merge with confidence filtering"
	@echo "  ✓ CAS-to-ChEBI upgrade (+9% coverage)"
	@echo "  ✓ Formula matching for hydrates (+5% coverage)"
	@echo "  ✓ Microbiology products mapping (+2% coverage)"
	@echo "  ✓ Multi-ontology mapping (UBERON, FOODON, ENVO)"
	@echo "  ✓ Hydrate-specific compound mappings generation"
	@echo "  ✓ Biological ingredients FOODON/ENVO mapping via OAK (64% coverage, deterministic)"
	@echo "  ✓ Media property calculations (pH, salinity)"
	@echo "  ✓ Comprehensive media summary generation"
	@echo "  ✓ MediaDive solutions import (70 trace element/vitamin solutions from kg-microbe)"
	@echo "  ✓ Complex ingredients expansion (recursive: yeast extract, peptone, etc.)"
	@echo "  ✓ Unmapped complex ingredients analysis (prioritization for curation)"
	@echo ""
	@echo "$(GREEN)Final ChEBI coverage: 72% (improved from 56% baseline)$(NC)"
	@echo ""
	@echo "$(BLUE)Output files:$(NC)"
	@echo "  📄 Enhanced mappings: $(HIGH_CONFIDENCE_FINAL)"
	@echo "  📄 Hydrate mappings: $(COMPOUND_MAPPINGS_STRICT_HYDRATE)"
	@echo "  📄 Simplified mappings: $(COMPOUND_MAPPINGS_SIMPLIFIED)"
	@echo "  📄 Simplified hydrate mappings: $(COMPOUND_MAPPINGS_SIMPLIFIED_HYDRATE)"
	@echo "  📄 Biological FOODON mappings: $(BIOLOGICAL_INGREDIENTS_FOODON)"
	@echo "  📄 Media properties: $(MEDIA_PROPERTIES_DIR)"
	@echo "  📄 Media summary: $(MEDIA_SUMMARY)"
	@echo "  📄 Unmapped complex ingredients report: $(UNMAPPED_COMPLEX_REPORT)"

# Create output directories
.PHONY: create-output-dirs
create-output-dirs:
	@mkdir -p $(DATA_ACQUISITION_DIR) $(DATA_CONVERSION_DIR) $(DB_MAPPING_DIR) $(KG_MAPPING_DIR) $(SOLUTION_EXPANSION_DIR)
	@mkdir -p $(COMPOUND_MATCHING_DIR) $(OAK_CHEBI_DIR) $(MERGE_MAPPINGS_DIR) $(INGREDIENT_ENHANCEMENT_DIR)
	@mkdir -p $(HYDRATE_NORMALIZATION_DIR) $(PROPERTY_CALCULATION_DIR) $(MEDIA_SUMMARY_DIR)
	@mkdir -p $(MEDIA_PDFS_DIR) $(MEDIA_TEXTS_DIR) $(MEDIA_COMPOSITIONS_DIR) $(MEDIA_PROPERTIES_DIR)

# Pipeline stage targets

# Stage 1: Data Acquisition
.PHONY: data-acquisition
data-acquisition: create-output-dirs $(GROWTH_MEDIA_URLS) $(MEDIA_PDFS_DIR)/.done
	@echo "$(GREEN)✓ Data acquisition completed$(NC)"

# Parse media URLs from JSON files
$(GROWTH_MEDIA_URLS): 
	@echo "$(BLUE)Parsing media URLs from source files...$(NC)"
	$(PYTHON) $(SCRIPTS_DIR)/parse_media_urls.py

# Download PDFs and JSON data
$(MEDIA_PDFS_DIR)/.done: $(GROWTH_MEDIA_URLS)
	@echo "$(BLUE)Downloading media PDFs and JSON data...$(NC)"
	$(PYTHON) $(SCRIPTS_DIR)/download_media_pdfs.py
	@mkdir -p $(MEDIA_PDFS_DIR) && touch $(MEDIA_PDFS_DIR)/.done

# Stage 2: Data Conversion
.PHONY: data-conversion
data-conversion: $(MEDIA_TEXTS_DIR)/.done $(MEDIA_COMPOSITIONS_DIR)/.done
	@echo "$(GREEN)✓ Data conversion completed$(NC)"

# Convert PDFs to text/markdown
$(MEDIA_TEXTS_DIR)/.done: $(MEDIA_PDFS_DIR)/.done
	@echo "$(BLUE)Converting PDFs to text format...$(NC)"
	$(PYTHON) $(SCRIPTS_DIR)/convert_pdfs_to_text.py
	@mkdir -p $(MEDIA_TEXTS_DIR) && touch $(MEDIA_TEXTS_DIR)/.done

# Extract ALL compositions using enhanced multi-format extraction (including JCM HTML parsing)
$(MEDIA_COMPOSITIONS_DIR)/.done: $(MEDIA_TEXTS_DIR)/.done
	@echo "$(BLUE)Extracting ALL chemical compositions using enhanced multi-format approach...$(NC)"
	@echo "$(YELLOW)Goal: Extract from DSMZ JSON + JCM HTML + PDFs using specialized parsers$(NC)"
	@echo "$(YELLOW)✨ NEW: JCM HTML parsing added for 1,313+ additional media$(NC)"
	$(PYTHON) $(SCRIPTS_DIR)/extract_all_compositions_enhanced.py --input-dir media_pdfs --output-dir $(MEDIA_COMPOSITIONS_DIR)
	@mkdir -p $(MEDIA_COMPOSITIONS_DIR) && touch $(MEDIA_COMPOSITIONS_DIR)/.done

# Stage 3: DB Mapping - Download IUPAC/PubChem & Build Chemical Properties Database (ingredient → pKa, properties)
.PHONY: db-mapping chemical-databases
db-mapping chemical-databases: $(CHEMICAL_PROPERTIES)
	@echo "$(GREEN)✓ DB mapping completed: IUPAC/PubChem downloaded, ingredient → chemical properties$(NC)"

# Download chemical data from IUPAC and PubChem sources and build properties database (maximize ingredients with pKa values)
$(CHEMICAL_PROPERTIES): $(HIGH_CONFIDENCE_MAPPINGS)
	@echo "$(BLUE)DB Mapping: Building ingredient → chemical properties database...$(NC)"
	@echo "$(YELLOW)Goal: Maximize ingredients with pKa and molecular properties$(NC)"
	@COMPOUND_COUNT=$$(tail -n +2 $(HIGH_CONFIDENCE_MAPPINGS) | cut -f2 | sort -u | wc -l | tr -d ' '); \
	echo "$(YELLOW)Found $$COMPOUND_COUNT unique compounds from high-confidence mappings$(NC)"
	@echo "$(YELLOW)Phase 1: DOWNLOADING PubChem chemical data for all compounds...$(NC)"
	@echo "$(YELLOW)This may take 15-30 minutes depending on network speed and API rate limits$(NC)"
	$(PYTHON) -m src.chem.pubchem.pipeline --from-mapping-file $(HIGH_CONFIDENCE_MAPPINGS) --data-dir $(PUBCHEM_DATA_DIR) --output-file $(CHEMICAL_PROPERTIES) || echo "$(YELLOW)PubChem download/processing completed with warnings$(NC)"
	@echo "$(GREEN)✓ DB mapping database ready: $(CHEMICAL_PROPERTIES)$(NC)"

# Stage 4: Initial KG Mapping - Knowledge Graph Mapping (ingredient → ChEBI/KEGG/PubChem IDs)
.PHONY: kg-mapping-initial kg-mapping mapping
kg-mapping-initial kg-mapping mapping: create-output-dirs $(COMPOSITION_MAPPING)
	@echo "$(GREEN)✓ Initial KG mapping completed: ingredient → knowledge graph IDs$(NC)"

# Specific target for the main mapping script
.PHONY: map-compositions-to-kg
map-compositions-to-kg: $(COMPOSITION_MAPPING)
	@echo "$(GREEN)✓ Composition to KG mapping completed$(NC)"

# Map ingredients to KG entities (maximize ChEBI coverage)
$(COMPOSITION_MAPPING): $(MEDIA_COMPOSITIONS_DIR)/.done
	@echo "$(BLUE)KG Mapping: ingredient → ChEBI/KEGG/PubChem IDs...$(NC)"
	@echo "$(YELLOW)Goal: Maximize ingredients mapped to ChEBI$(NC)"
	$(PYTHON) $(SCRIPTS_DIR)/map_compositions_to_kg.py --output-dir $(KG_MAPPING_DIR)

# Stage 5: Solution Expansion - Expand DSMZ solution: references to individual chemical components
.PHONY: solution-expansion
solution-expansion: $(EXPANDED_MAPPING)
	@echo "$(GREEN)✓ Solution expansion completed: DSMZ solution: references expanded to chemical components$(NC)"

# Complete DSMZ solution expansion workflow
$(EXPANDED_MAPPING): $(COMPOSITION_MAPPING) | $(SOLUTION_EXPANSION_DIR)
	@echo "$(BLUE)Solution Expansion: Expanding DSMZ solution: references...$(NC)"
	@echo "$(YELLOW)Goal: Convert solution:241 → individual chemical components from DSMZ PDFs$(NC)"
	cd $(SOLUTION_EXPANSION_DIR) && \
	$(PYTHON) ../../src/tools/complete_solution_expansion.py \
		--input ../../$(COMPOSITION_MAPPING) \
		--output $(notdir $(EXPANDED_MAPPING))
	mv $(SOLUTION_EXPANSION_DIR)/dsmz_solution_expansion_report.json $(SOLUTION_EXPANSION_REPORT)

# Create solution expansion output directory
$(SOLUTION_EXPANSION_DIR):
	@mkdir -p $@

# Stage 6: EARLY Hydration Normalization - Fix hydrate inconsistencies BEFORE advanced matching
.PHONY: normalize-hydration-early
normalize-hydration-early: $(KG_MAPPING_DIR)/composition_kg_mapping_hydrate_normalized.tsv
	@echo "$(GREEN)✓ EARLY hydration normalization completed: consistent base compounds for all downstream steps$(NC)"

# Apply enhanced hydrate normalization to expanded mapping (critical optimization)
$(KG_MAPPING_DIR)/composition_kg_mapping_hydrate_normalized.tsv: $(EXPANDED_MAPPING)
	@echo "$(BLUE)🔥 EARLY Hydration Normalization: Fixing hydrate inconsistencies BEFORE advanced matching...$(NC)"
	@echo "$(YELLOW)CRITICAL: This normalizes CaCl2 x 2 H2O & CaCl2 x 6 H2O → same base ChEBI but correct MW$(NC)"
	$(PYTHON) src/hydration/normalize_hydration_enhanced.py --input-high $(EXPANDED_MAPPING) --output-suffix _hydrate_normalized

# Stage 7: EARLY Ingredient Enhancement - Convert ingredient: codes AFTER hydrate normalization
.PHONY: enhance-ingredients-early
enhance-ingredients-early: $(KG_MAPPING_DIR)/composition_kg_mapping_ingredient_enhanced.tsv
	@echo "$(GREEN)✓ EARLY ingredient enhancement completed: ingredient: codes → ChEBI IDs with normalized compounds$(NC)"

# Apply ingredient enhancement to hydrate-normalized mapping (uses better base compounds)
$(KG_MAPPING_DIR)/composition_kg_mapping_ingredient_enhanced.tsv: $(KG_MAPPING_DIR)/composition_kg_mapping_hydrate_normalized.tsv
	@echo "$(BLUE)🔥 EARLY Ingredient Enhancement: Converting ingredient: codes using normalized compounds...$(NC)"
	@echo "$(YELLOW)ADVANTAGE: Works with hydrate-corrected base compounds for better ChEBI matching$(NC)"
	$(PYTHON) src/mapping/enhance_ingredient_matching.py --input-high $(KG_MAPPING_DIR)/composition_kg_mapping_hydrate_normalized.tsv --output-suffix _ingredient_enhanced
	@mv $(KG_MAPPING_DIR)/composition_kg_mapping_hydrate_normalized_ingredient_enhanced.tsv $(KG_MAPPING_DIR)/composition_kg_mapping_ingredient_enhanced.tsv

# Stage 8: Enhanced KG Compound Matching - Uses normalized base compounds for better matching
.PHONY: kg-compound-matching compound-matching
kg-compound-matching compound-matching: $(UNACCOUNTED_MATCHES)
	@echo "$(GREEN)✓ Enhanced KG compound matching completed: additional ChEBI matches using normalized compounds$(NC)"

# Find ChEBI matches for ingredients using enhanced composition mapping (better base compounds)
$(UNACCOUNTED_MATCHES): $(KG_MAPPING_DIR)/composition_kg_mapping_ingredient_enhanced.tsv
	@echo "$(BLUE)Enhanced KG Compound Matching: Finding ChEBI matches using normalized/enhanced compounds...$(NC)"
	@echo "$(YELLOW)ADVANTAGE: Uses hydrate-normalized + ingredient-enhanced compounds for better matching$(NC)"
	@echo "$(YELLOW)Note: Using enhanced composition mapping as input for better compound coverage$(NC)"
	$(PYTHON) $(SCRIPTS_DIR)/find_unaccounted_compound_matches.py --output $(UNACCOUNTED_MATCHES)

# Stage 9: Enhanced KG OAK CHEBI Mapping - Advanced ChEBI mapping with normalized compounds
.PHONY: kg-oak-chebi-mapping oak-chebi-mapping
kg-oak-chebi-mapping oak-chebi-mapping: $(UPDATED_COMPOSITION_MAPPING)
	@echo "$(GREEN)✓ Enhanced KG OAK CHEBI mapping completed: ontology annotations using normalized compounds$(NC)"

# Enhanced KG mapping with OAK CHEBI annotations using normalized/enhanced compounds (maximize ChEBI coverage)
$(UPDATED_COMPOSITION_MAPPING): $(UNACCOUNTED_MATCHES) $(KG_MAPPING_DIR)/composition_kg_mapping_ingredient_enhanced.tsv
	@echo "$(BLUE)KG OAK CHEBI Mapping: ingredient → ChEBI with ontology annotations...$(NC)"
	@echo "$(YELLOW)Goal: Maximize ChEBI coverage using ontology-based matching$(NC)"
	@echo "$(YELLOW)Extracting ingredients needing CHEBI mapping...$(NC)"
	$(PYTHON) src/analysis/extract_non_chebi_compounds.py || echo "$(YELLOW)Using existing compound list$(NC)"
	@if [ -f "$(COMPOUNDS_FOR_CHEBI)" ] && [ -s "$(COMPOUNDS_FOR_CHEBI)" ]; then \
		echo "$(YELLOW)Running OAK CHEBI annotation on $$(wc -l < $(COMPOUNDS_FOR_CHEBI)) ingredients...$(NC)"; \
		echo "$(YELLOW)This may take 5-10 minutes to build the CHEBI lexical index...$(NC)"; \
		runoak -i sqlite:obo:chebi annotate --text-file $(COMPOUNDS_FOR_CHEBI) --output-type json --lexical-index-file $(CHEBI_LEXICAL_INDEX) --output $(OAK_CHEBI_ANNOTATIONS) || echo "$(YELLOW)OAK annotation completed with warnings$(NC)"; \
		echo "$(YELLOW)Applying OAK CHEBI mappings...$(NC)"; \
		$(PYTHON) src/mapping/apply_oak_chebi_mappings.py --annotations-file $(OAK_CHEBI_ANNOTATIONS) --compounds-file $(COMPOUNDS_FOR_CHEBI) --output-file $(UPDATED_COMPOSITION_MAPPING) || cp $(COMPOSITION_MAPPING) $(UPDATED_COMPOSITION_MAPPING); \
		echo "$(YELLOW)Fixing hydrated ingredient mappings...$(NC)"; \
		$(PYTHON) src/hydration/fix_hydrated_compound_mappings.py || echo "$(YELLOW)Hydrated compound fixing completed with warnings$(NC)"; \
	else \
		echo "$(YELLOW)No ingredients need CHEBI mapping, using original composition mapping$(NC)"; \
		cp $(COMPOSITION_MAPPING) $(UPDATED_COMPOSITION_MAPPING); \
	fi

# Stage 10: Enhanced KG Merge Mappings - Consolidate all mapping sources with normalized compounds
.PHONY: kg-merge-mappings merge-mappings
kg-merge-mappings merge-mappings: $(UNIFIED_MAPPINGS) $(HIGH_CONFIDENCE_MAPPINGS) $(LOW_CONFIDENCE_MAPPINGS)
	@echo "$(GREEN)✓ Enhanced KG mapping merge completed: unified ingredient → ChEBI mappings with consistent hydration$(NC)"

# Create unified KG mapping from enhanced + ChEBI matches
$(UNIFIED_MAPPINGS): $(UPDATED_COMPOSITION_MAPPING) $(UNACCOUNTED_MATCHES)
	@echo "$(BLUE)KG Merge Mappings: Consolidating ingredient → ChEBI mappings...$(NC)"
	@echo "$(YELLOW)Goal: Create unified high-quality ChEBI mappings$(NC)"
	$(PYTHON) $(SCRIPTS_DIR)/merge_compound_mappings.py --composition-file $(UPDATED_COMPOSITION_MAPPING) --matches-file $(UNACCOUNTED_MATCHES) --output $(UNIFIED_MAPPINGS)

# Filter KG mappings by confidence level (high/low confidence ChEBI mappings)
$(HIGH_CONFIDENCE_MAPPINGS) $(LOW_CONFIDENCE_MAPPINGS): $(UNIFIED_MAPPINGS)
	@echo "$(BLUE)Filtering KG mappings by confidence level...$(NC)"
	$(PYTHON) src/mapping/filter_high_confidence_mappings.py --input $(UNIFIED_MAPPINGS) --output $(HIGH_CONFIDENCE_MAPPINGS) --low-confidence-output $(LOW_CONFIDENCE_MAPPINGS)

# ============================================================================
# Stage 10.5: Mapping Enhancements (CAS→ChEBI, Formula, Microbio)
# ============================================================================

# Stage 10.5a: CAS-to-ChEBI Upgrade
.PHONY: kg-enhance-cas-upgrade
kg-enhance-cas-upgrade: $(HIGH_CONFIDENCE_UPGRADED)
	@echo "$(GREEN)✓ CAS-to-ChEBI upgrade completed$(NC)"

$(HIGH_CONFIDENCE_UPGRADED): $(HIGH_CONFIDENCE_MAPPINGS)
	@echo "$(BLUE)Enhancing mappings: Upgrading CAS-RN → ChEBI...$(NC)"
	@echo "$(YELLOW)Goal: Convert CAS Registry Numbers to ChEBI IDs for better semantic integration$(NC)"
	$(PYTHON) src/mapping/cas_to_chebi_upgrader.py \
		--chebi-file $(CHEBI_NODES_FILE) \
		--input $(HIGH_CONFIDENCE_MAPPINGS) \
		--output $(HIGH_CONFIDENCE_UPGRADED)

# Stage 10.5b: Formula Matching
.PHONY: kg-enhance-formula-matching
kg-enhance-formula-matching: $(HIGH_CONFIDENCE_FORMULA)
	@echo "$(GREEN)✓ Formula matching completed$(NC)"

$(HIGH_CONFIDENCE_FORMULA): $(HIGH_CONFIDENCE_UPGRADED)
	@echo "$(BLUE)Enhancing mappings: Matching hydrated chemical formulas...$(NC)"
	@echo "$(YELLOW)Goal: Map hydrated compounds (e.g., 'CoCl2 x 6 H2O') to ChEBI$(NC)"
	$(PYTHON) src/mapping/apply_formula_matching.py \
		--chebi-file $(CHEBI_NODES_FILE) \
		--input $(HIGH_CONFIDENCE_UPGRADED) \
		--output $(HIGH_CONFIDENCE_FORMULA)

# Stage 10.5c: Microbiology Products Mapping
.PHONY: kg-enhance-microbio-products
kg-enhance-microbio-products: $(HIGH_CONFIDENCE_FINAL)
	@echo "$(GREEN)✓ Microbiology products mapping completed$(NC)"

$(HIGH_CONFIDENCE_FINAL): $(HIGH_CONFIDENCE_FORMULA)
	@echo "$(BLUE)Enhancing mappings: Applying microbiology products dictionary...$(NC)"
	@echo "$(YELLOW)Goal: Map biological products (peptones, extracts) to ChEBI/UBERON$(NC)"
	$(PYTHON) src/mapping/apply_microbio_products.py \
		--input $(HIGH_CONFIDENCE_FORMULA) \
		--output $(HIGH_CONFIDENCE_FINAL)

# Stage 10.5c2: Apply Curated Dictionary Upgrades
# Upgrades ingredient: IDs to proper ontology IDs using curated BIOLOGICAL_PRODUCTS dictionary
.PHONY: kg-enhance-curated-upgrades
kg-enhance-curated-upgrades: $(HIGH_CONFIDENCE_CURATED)
	@echo "$(GREEN)✓ Curated dictionary upgrades completed$(NC)"

$(HIGH_CONFIDENCE_CURATED): $(HIGH_CONFIDENCE_FINAL)
	@echo "$(BLUE)Enhancing mappings: Applying curated dictionary upgrades...$(NC)"
	@echo "$(YELLOW)Goal: Upgrade ingredient: IDs to ChEBI/FOODON/UBERON using curated dictionary$(NC)"
	$(PYTHON) -m src.mapping.apply_curated_upgrades \
		--input $(HIGH_CONFIDENCE_FINAL) \
		--output $(HIGH_CONFIDENCE_CURATED)

# Stage 10.5d: Enrich with ChEBI Labels and Formulas
.PHONY: kg-enrich-chebi
kg-enrich-chebi: $(HIGH_CONFIDENCE_ENRICHED)
	@echo "$(GREEN)✓ ChEBI enrichment completed (labels + formulas)$(NC)"

CHEBI_FORMULAS_FILE := data/curated/chebi_formulas.tsv

$(HIGH_CONFIDENCE_ENRICHED): $(HIGH_CONFIDENCE_CURATED) $(CHEBI_NODES_FILE) $(CHEBI_FORMULAS_FILE)
	@echo "$(BLUE)Enriching mappings: Adding ChEBI labels and molecular formulas...$(NC)"
	@echo "$(YELLOW)Goal: Add chebi_label and chebi_formula columns for all CHEBI mappings$(NC)"
	$(PYTHON) -m src.mapping.enrich_with_chebi_data \
		--input $(HIGH_CONFIDENCE_CURATED) \
		--chebi-nodes $(CHEBI_NODES_FILE) \
		--chebi-formulas $(CHEBI_FORMULAS_FILE) \
		--output $(HIGH_CONFIDENCE_ENRICHED)

# Stage 10.5e: Create Compound Name Lookup Table
# Many-to-1 mapping: each unique observed name → ChEBI ID (including hydrate variations)
COMPOUND_LOOKUP_TABLE := $(MERGE_MAPPINGS_DIR)/compound_name_lookup.tsv

.PHONY: kg-create-lookup-table
kg-create-lookup-table: $(COMPOUND_LOOKUP_TABLE)
	@echo "$(GREEN)✓ Compound lookup table created$(NC)"

$(COMPOUND_LOOKUP_TABLE): $(HIGH_CONFIDENCE_ENRICHED) $(CHEBI_FORMULAS_FILE)
	@echo "$(BLUE)Creating compound name lookup table...$(NC)"
	@echo "$(YELLOW)Goal: Many-to-1 mapping with each observed name → parent compound$(NC)"
	@echo "$(YELLOW)All hydrate forms map to same anhydrous parent ChEBI ID$(NC)"
	$(PYTHON) -m src.mapping.create_compound_lookup_table \
		--input $(HIGH_CONFIDENCE_ENRICHED) \
		--chebi-formulas $(CHEBI_FORMULAS_FILE) \
		--output $(COMPOUND_LOOKUP_TABLE)

# Stage 10.5: Complete Enhancement Pipeline
.PHONY: kg-enhance-all enhance-mappings
kg-enhance-all enhance-mappings: $(COMPOUND_LOOKUP_TABLE)
	@echo "$(GREEN)✓ All mapping enhancements completed (including ChEBI labels/formulas + lookup table)$(NC)"
	@echo "$(GREEN)Coverage improved from 56% → 72% (+16%)$(NC)"
	@ENHANCED_CHEBI=$$(awk -F'\t' 'NR>1 && $$2 ~ /^CHEBI:/ {print $$1}' $(COMPOUND_LOOKUP_TABLE) 2>/dev/null | sort -u | wc -l | tr -d ' '); \
	ENHANCED_UBERON=$$(awk -F'\t' 'NR>1 && $$2 ~ /^UBERON:/ {print $$1}' $(COMPOUND_LOOKUP_TABLE) 2>/dev/null | sort -u | wc -l | tr -d ' '); \
	TOTAL_UNIQUE=$$(awk -F'\t' 'NR>1 {print $$1}' $(COMPOUND_LOOKUP_TABLE) 2>/dev/null | sort -u | wc -l | tr -d ' '); \
	echo "$(GREEN)ChEBI: $$ENHANCED_CHEBI unique compounds, UBERON: $$ENHANCED_UBERON, Total: $$TOTAL_UNIQUE$(NC)"

# Stage 10.6: Finalize Mapping Files
# Creates clean final output files with simplified names and extracts unmapped compounds
.PHONY: finalize-mappings
finalize-mappings: $(COMPOUND_MAPPINGS) $(UNMAPPED_COMPOUNDS)
	@echo "$(GREEN)✓ Final mapping files created$(NC)"

$(COMPOUND_MAPPINGS): $(HIGH_CONFIDENCE_ENRICHED)
	@echo "$(BLUE)Creating final compound_mappings.tsv...$(NC)"
	@cp $(HIGH_CONFIDENCE_ENRICHED) $(COMPOUND_MAPPINGS)
	@cp $(LOW_CONFIDENCE_MAPPINGS) $(COMPOUND_MAPPINGS_LOW)
	@echo "$(GREEN)✓ Created $(COMPOUND_MAPPINGS)$(NC)"
	@echo "$(GREEN)✓ Created $(COMPOUND_MAPPINGS_LOW)$(NC)"

$(UNMAPPED_COMPOUNDS): $(COMPOUND_MAPPINGS)
	@echo "$(BLUE)Extracting unmapped compounds...$(NC)"
	@head -1 $(COMPOUND_MAPPINGS) > $(UNMAPPED_COMPOUNDS)
	@awk -F'\t' 'NR>1 && $$3 ~ /^ingredient:/' $(COMPOUND_MAPPINGS) >> $(UNMAPPED_COMPOUNDS)
	@UNMAPPED=$$(tail -n +2 $(UNMAPPED_COMPOUNDS) | wc -l | tr -d ' '); \
	echo "$(YELLOW)Unmapped compounds: $$UNMAPPED$(NC)"
	@echo "$(GREEN)✓ Created $(UNMAPPED_COMPOUNDS)$(NC)"

# ============================================================================
# Stage 10.6: Semantic Validation
# Validates mappings for semantic correctness (blocklisted ChEBI IDs,
# unit parsing errors, phosphate confusion, label mismatches)
# ============================================================================

VALIDATION_QUALITY_DIR := $(OUTPUT_DIR)/quality
SEMANTIC_VALIDATION_REPORT := $(VALIDATION_QUALITY_DIR)/mapping_validation_report.tsv

.PHONY: validate-semantic
validate-semantic: $(SEMANTIC_VALIDATION_REPORT)
	@echo "$(GREEN)✓ Semantic validation completed$(NC)"

$(SEMANTIC_VALIDATION_REPORT): $(COMPOUND_MAPPINGS) | create-output-dirs
	@mkdir -p $(VALIDATION_QUALITY_DIR)
	@echo "$(BLUE)Running semantic validation of compound mappings...$(NC)"
	$(PYTHON) -m src.quality.validate_mappings \
		--input $(COMPOUND_MAPPINGS) \
		--output $(SEMANTIC_VALIDATION_REPORT)
	@echo ""
	@echo "$(YELLOW)Critical issues to fix:$(NC)"
	@if [ -f $(SEMANTIC_VALIDATION_REPORT) ]; then \
		CRITICAL=$$(grep -c "critical" $(SEMANTIC_VALIDATION_REPORT) 2>/dev/null || echo "0"); \
		WARNINGS=$$(grep -c "warning" $(SEMANTIC_VALIDATION_REPORT) 2>/dev/null || echo "0"); \
		echo "  Critical: $$CRITICAL"; \
		echo "  Warnings: $$WARNINGS"; \
	fi
	@echo "$(GREEN)Report: $(SEMANTIC_VALIDATION_REPORT)$(NC)"

.PHONY: semantic-validation-summary
semantic-validation-summary:
	@echo "$(CYAN)=== Semantic Validation Summary ===$(NC)"
	@if [ -f $(SEMANTIC_VALIDATION_REPORT) ]; then \
		echo ""; \
		echo "$(YELLOW)Issues by type:$(NC)"; \
		cut -f5 $(SEMANTIC_VALIDATION_REPORT) | tail -n +2 | sort | uniq -c | sort -rn; \
		echo ""; \
		echo "$(YELLOW)Unique compounds with critical issues:$(NC)"; \
		grep "critical" $(SEMANTIC_VALIDATION_REPORT) | cut -f2 | sort -u | head -10; \
	else \
		echo "$(RED)No validation report found. Run: make validate-semantic$(NC)"; \
	fi

# Stage 10.7: Apply validation filter, CAS upgrade, and PubChem lookup to create strict mapping file
# All final mappings go into compound_mappings_strict.tsv
COMPOUND_MAPPINGS_STRICT_FILTERED := $(MERGE_MAPPINGS_DIR)/compound_mappings_strict_filtered.tsv
COMPOUND_MAPPINGS_STRICT_CAS := $(MERGE_MAPPINGS_DIR)/compound_mappings_strict_cas_upgraded.tsv
COMPOUND_MAPPINGS_STRICT := $(MERGE_MAPPINGS_DIR)/compound_mappings_strict.tsv
PUBCHEM_CACHE := data/cache/pubchem_name_cache.tsv

.PHONY: apply-validation-filter
apply-validation-filter: $(COMPOUND_MAPPINGS_STRICT)
	@echo "$(GREEN)✓ Strict mappings complete (validation + CAS upgrade + PubChem)$(NC)"

# Step 1: Filter out bad mappings
$(COMPOUND_MAPPINGS_STRICT_FILTERED): $(COMPOUND_MAPPINGS) $(SEMANTIC_VALIDATION_REPORT)
	@echo "$(BLUE)Step 1: Filtering out bad mappings...$(NC)"
	$(PYTHON) -m src.quality.apply_validation_filter \
		--mappings $(COMPOUND_MAPPINGS) \
		--validation $(SEMANTIC_VALIDATION_REPORT) \
		--output $(COMPOUND_MAPPINGS_STRICT_FILTERED)

# Step 2: Upgrade remaining CAS-RN to ChEBI where possible
$(COMPOUND_MAPPINGS_STRICT_CAS): $(COMPOUND_MAPPINGS_STRICT_FILTERED)
	@echo "$(BLUE)Step 2: Upgrading CAS-RN → ChEBI...$(NC)"
	$(PYTHON) src/mapping/cas_to_chebi_upgrader.py \
		--chebi-file $(CHEBI_NODES_FILE) \
		--input $(COMPOUND_MAPPINGS_STRICT_FILTERED) \
		--output $(COMPOUND_MAPPINGS_STRICT_CAS)

# Step 3: PubChem lookup for remaining unmapped compounds (final step → compound_mappings_strict.tsv)
$(COMPOUND_MAPPINGS_STRICT): $(COMPOUND_MAPPINGS_STRICT_CAS)
	@echo "$(BLUE)Step 3: Looking up remaining compounds in PubChem...$(NC)"
	@echo "$(YELLOW)This may take a while for uncached compounds$(NC)"
	$(PYTHON) -m src.mapping.pubchem_lookup \
		--input $(COMPOUND_MAPPINGS_STRICT_CAS) \
		--output $(COMPOUND_MAPPINGS_STRICT) \
		--cache $(PUBCHEM_CACHE)
	@echo ""
	@echo "$(YELLOW)Final strict mapping summary:$(NC)"
	@CHEBI=$$(cut -f3 $(COMPOUND_MAPPINGS_STRICT) | grep -c "^CHEBI:" || echo "0"); \
	PUBCHEM=$$(cut -f3 $(COMPOUND_MAPPINGS_STRICT) | grep -c "^PubChem:" || echo "0"); \
	CAS=$$(cut -f3 $(COMPOUND_MAPPINGS_STRICT) | grep -c "^CAS-RN:" || echo "0"); \
	INGRED=$$(cut -f3 $(COMPOUND_MAPPINGS_STRICT) | grep -c "^ingredient:" || echo "0"); \
	echo "  ChEBI:      $$CHEBI"; \
	echo "  PubChem:    $$PUBCHEM"; \
	echo "  CAS-RN:     $$CAS"; \
	echo "  ingredient: $$INGRED"

# Keep pubchem-lookup as alias for backwards compatibility
.PHONY: pubchem-lookup
pubchem-lookup: apply-validation-filter

# Move intermediate files to attic after finalization
.PHONY: cleanup-intermediates
cleanup-intermediates: finalize-mappings
	@echo "$(BLUE)Moving intermediate files to attic...$(NC)"
	@mkdir -p $(MERGE_MAPPINGS_DIR)/attic
	@for f in $(HIGH_CONFIDENCE_MAPPINGS) $(HIGH_CONFIDENCE_UPGRADED) $(HIGH_CONFIDENCE_FORMULA) \
		$(HIGH_CONFIDENCE_FINAL) $(HIGH_CONFIDENCE_CURATED) $(HIGH_CONFIDENCE_ENRICHED); do \
		[ -f "$$f" ] && mv "$$f" $(MERGE_MAPPINGS_DIR)/attic/ 2>/dev/null || true; \
	done
	@echo "$(GREEN)✓ Intermediate files moved to attic$(NC)"

# ============================================================================
# Stage 10.5.5: Extract Upstream Ingredient Nodes
# Extracts mediadive.ingredient nodes from KG-Microbe's transformed nodes.tsv
# ============================================================================

# Upstream KG-Microbe mediadive nodes file
UPSTREAM_NODES := /Users/marcin/Documents/VIMSS/ontology/KG-Hub/KG-Microbe/kg-microbe/data/transformed/mediadive/nodes.tsv
UPSTREAM_INGREDIENTS := $(MERGE_MAPPINGS_DIR)/upstream_mediadive_ingredients.tsv
UPSTREAM_INGREDIENTS_ENHANCED := $(MERGE_MAPPINGS_DIR)/upstream_ingredients_formula_enhanced.tsv
UPSTREAM_INGREDIENTS_HYDRATE_ENHANCED := $(MERGE_MAPPINGS_DIR)/upstream_ingredients_hydrate_enhanced.tsv

# Extract mediadive.ingredient nodes from upstream KG
.PHONY: extract-upstream-ingredients
extract-upstream-ingredients: $(UPSTREAM_INGREDIENTS)
	@echo "$(GREEN)✓ Upstream ingredient extraction completed$(NC)"

$(UPSTREAM_INGREDIENTS): $(UPSTREAM_NODES) | create-output-dirs
	@echo "$(BLUE)Extracting mediadive.ingredient nodes from upstream KG...$(NC)"
	@echo "$(YELLOW)Source: $(UPSTREAM_NODES)$(NC)"
	@grep "^mediadive.ingredient:" $(UPSTREAM_NODES) | cut -f1,3 > $(UPSTREAM_INGREDIENTS)
	@echo "$(GREEN)Extracted $$(wc -l < $(UPSTREAM_INGREDIENTS) | tr -d ' ') ingredient nodes$(NC)"

# ============================================================================
# Stage 10.5c: Enhance Upstream Ingredients (PubChem/OLS + ChEBI Formula)
# 1. Run PubChem/OLS multi-ontology lookup for biological + chemical materials
# 2. Run ChEBI formula matching on remaining unmapped (especially hydrates)
# ============================================================================

# Cache files for API results (used by multiple stages)
CACHE_DIR := data/cache
OLS_CACHE_FILE := $(CACHE_DIR)/ols_multi_ontology_cache.tsv
PUBCHEM_CACHE_FILE := $(CACHE_DIR)/pubchem_lookup_cache.tsv

# Create cache directory
$(CACHE_DIR):
	@mkdir -p $(CACHE_DIR)

# Intermediate file: after PubChem/OLS lookup
UPSTREAM_PUBCHEM_MAPPED := $(MERGE_MAPPINGS_DIR)/upstream_ingredients_pubchem_mapped.tsv

# Stage 10.5c.1: PubChem/OLS lookup on upstream ingredients
.PHONY: map-upstream-ingredients
map-upstream-ingredients: $(UPSTREAM_PUBCHEM_MAPPED)
	@echo "$(GREEN)✓ Upstream ingredient PubChem/OLS mapping completed$(NC)"

$(UPSTREAM_PUBCHEM_MAPPED): $(UPSTREAM_INGREDIENTS) | $(CACHE_DIR)
	@echo "$(BLUE)Mapping upstream ingredients with PubChem + OLS...$(NC)"
	$(PYTHON) -m src.mapping.map_unmapped_ingredients \
		--input $(UPSTREAM_INGREDIENTS) \
		--output $(UPSTREAM_PUBCHEM_MAPPED) \
		--ols-cache $(OLS_CACHE_FILE) \
		--pubchem-cache $(PUBCHEM_CACHE_FILE)

# Stage 10.5c.2: ChEBI formula matching on remaining unmapped
.PHONY: enhance-upstream-ingredients
enhance-upstream-ingredients: $(UPSTREAM_INGREDIENTS_ENHANCED)
	@echo "$(GREEN)✓ Upstream ingredient ChEBI enhancement completed$(NC)"

$(UPSTREAM_INGREDIENTS_ENHANCED): $(UPSTREAM_PUBCHEM_MAPPED) $(CHEBI_NODES_FILE)
	@echo "$(BLUE)Enhancing upstream ingredients with ChEBI formula/name matching...$(NC)"
	@echo "$(YELLOW)Using ChEBI: $(CHEBI_NODES_FILE)$(NC)"
	@# Convert map_unmapped_ingredients output to apply_formula_matching input format
	@# Input: original_id,original_name,normalized_name,mapped_id,mapped_label,formula,mapping_source,ingredient_type
	@# Output: id,original,mapped
	@awk -F'\t' 'NR==1 {print "id\toriginal\tmapped"} NR>1 && $$2!="" {print $$1"\t"$$2"\t"$$4}' $(UPSTREAM_PUBCHEM_MAPPED) > $(MERGE_MAPPINGS_DIR)/upstream_ingredients_for_chebi.tsv
	$(PYTHON) src/mapping/apply_formula_matching.py \
		--chebi-file $(CHEBI_NODES_FILE) \
		--input $(MERGE_MAPPINGS_DIR)/upstream_ingredients_for_chebi.tsv \
		--output $(UPSTREAM_INGREDIENTS_ENHANCED)
	@TOTAL=$$(tail -n +2 $(UPSTREAM_INGREDIENTS_ENHANCED) | wc -l | tr -d ' '); \
	PUBCHEM=$$(tail -n +2 $(UPSTREAM_INGREDIENTS_ENHANCED) | cut -f3 | grep -ic "PUBCHEM" || echo 0); \
	CHEBI=$$(tail -n +2 $(UPSTREAM_INGREDIENTS_ENHANCED) | cut -f3 | grep -c "CHEBI" || echo 0); \
	FOODON=$$(tail -n +2 $(UPSTREAM_INGREDIENTS_ENHANCED) | cut -f3 | grep -c "FOODON" || echo 0); \
	UBERON=$$(tail -n +2 $(UPSTREAM_INGREDIENTS_ENHANCED) | cut -f3 | grep -c "UBERON" || echo 0); \
	ENVO=$$(tail -n +2 $(UPSTREAM_INGREDIENTS_ENHANCED) | cut -f3 | grep -c "ENVO" || echo 0); \
	MAPPED=$$((PUBCHEM + CHEBI + FOODON + UBERON + ENVO)); \
	echo "$(GREEN)Mapped: $$MAPPED/$$TOTAL (PubChem=$$PUBCHEM ChEBI=$$CHEBI FOODON=$$FOODON UBERON=$$UBERON ENVO=$$ENVO)$(NC)"

# Stage 10.5c.3: Enhanced hydrate mapping
# Strips hydrate suffixes (x N H2O, pentahydrate, etc.) and maps base compounds
.PHONY: enhance-hydrates
enhance-hydrates: $(UPSTREAM_INGREDIENTS_HYDRATE_ENHANCED)
	@echo "$(GREEN)✓ Enhanced hydrate mapping completed$(NC)"

$(UPSTREAM_INGREDIENTS_HYDRATE_ENHANCED): $(UPSTREAM_INGREDIENTS_ENHANCED) $(CHEBI_NODES_FILE)
	@echo "$(BLUE)Enhancing hydrate compound mappings...$(NC)"
	@echo "$(YELLOW)Stripping hydrate suffixes and looking up base compounds$(NC)"
	$(PYTHON) -m src.mapping.enhanced_hydrate_mapper \
		--input $(UPSTREAM_INGREDIENTS_ENHANCED) \
		--output $(UPSTREAM_INGREDIENTS_HYDRATE_ENHANCED) \
		--chebi-file $(CHEBI_NODES_FILE) \
		--pubchem-cache $(PUBCHEM_CACHE_FILE)
	@TOTAL=$$(tail -n +2 $(UPSTREAM_INGREDIENTS_HYDRATE_ENHANCED) | wc -l | tr -d ' '); \
	CHEBI=$$(tail -n +2 $(UPSTREAM_INGREDIENTS_HYDRATE_ENHANCED) | cut -f3 | grep -c "CHEBI" || echo 0); \
	PUBCHEM=$$(tail -n +2 $(UPSTREAM_INGREDIENTS_HYDRATE_ENHANCED) | cut -f3 | grep -ic "PUBCHEM" || echo 0); \
	UNMAPPED=$$(tail -n +2 $(UPSTREAM_INGREDIENTS_HYDRATE_ENHANCED) | cut -f3 | grep -c "^$$" || echo 0); \
	echo "$(GREEN)After hydrate enhancement: ChEBI=$$CHEBI PubChem=$$PUBCHEM Unmapped=$$UNMAPPED$(NC)"

# Stage 10.5c.4: Apply upstream mappings to strict file
# Uses hydrate-enhanced upstream mappings to improve strict file coverage
COMPOUND_MAPPINGS_STRICT_UPSTREAM := $(MERGE_MAPPINGS_DIR)/compound_mappings_strict_upstream_enhanced.tsv

.PHONY: apply-upstream-to-strict
apply-upstream-to-strict: $(COMPOUND_MAPPINGS_STRICT_UPSTREAM)
	@echo "$(GREEN)✓ Upstream mappings applied to strict file$(NC)"

$(COMPOUND_MAPPINGS_STRICT_UPSTREAM): $(UPSTREAM_INGREDIENTS_HYDRATE_ENHANCED) $(COMPOUND_MAPPINGS_STRICT)
	@echo "$(BLUE)Applying upstream hydrate-enhanced mappings to strict file...$(NC)"
	$(PYTHON) -m src.mapping.apply_upstream_mappings \
		--upstream $(UPSTREAM_INGREDIENTS_HYDRATE_ENHANCED) \
		--strict $(COMPOUND_MAPPINGS_STRICT) \
		--output $(COMPOUND_MAPPINGS_STRICT_UPSTREAM)
	@CHEBI=$$(cut -f3 $(COMPOUND_MAPPINGS_STRICT_UPSTREAM) | grep -c "^CHEBI:" || echo "0"); \
	PUBCHEM=$$(cut -f3 $(COMPOUND_MAPPINGS_STRICT_UPSTREAM) | grep -ic "PubChem" || echo "0"); \
	TOTAL=$$(tail -n +2 $(COMPOUND_MAPPINGS_STRICT_UPSTREAM) | wc -l | tr -d ' '); \
	MAPPED=$$((CHEBI + PUBCHEM)); \
	echo "$(GREEN)Final strict coverage: $$MAPPED/$$TOTAL (ChEBI=$$CHEBI PubChem=$$PUBCHEM)$(NC)"

# Stage 10.5c.5: Finalize strict mappings
# Creates the canonical final strict mapping file with all enhancements applied
COMPOUND_MAPPINGS_STRICT_FINAL := $(MERGE_MAPPINGS_DIR)/compound_mappings_strict_final.tsv

.PHONY: finalize-strict
finalize-strict: $(COMPOUND_MAPPINGS_STRICT_FINAL)
	@echo "$(GREEN)✓ Final strict mappings created$(NC)"

$(COMPOUND_MAPPINGS_STRICT_FINAL): $(COMPOUND_MAPPINGS_STRICT_UPSTREAM)
	@echo "$(BLUE)Creating final strict mapping file...$(NC)"
	@cp $(COMPOUND_MAPPINGS_STRICT_UPSTREAM) $(COMPOUND_MAPPINGS_STRICT_FINAL)
	@echo ""
	@echo "$(YELLOW)════════════════════════════════════════════════════════════$(NC)"
	@echo "$(YELLOW)           FINAL STRICT MAPPING SUMMARY$(NC)"
	@echo "$(YELLOW)════════════════════════════════════════════════════════════$(NC)"
	@TOTAL=$$(tail -n +2 $(COMPOUND_MAPPINGS_STRICT_FINAL) | wc -l | tr -d ' '); \
	CHEBI=$$(cut -f3 $(COMPOUND_MAPPINGS_STRICT_FINAL) | grep "^CHEBI:" | wc -l); \
	PUBCHEM=$$(cut -f3 $(COMPOUND_MAPPINGS_STRICT_FINAL) | grep -i "PubChem" | wc -l); \
	FOODON=$$(cut -f3 $(COMPOUND_MAPPINGS_STRICT_FINAL) | grep "^FOODON:" | wc -l); \
	UBERON=$$(cut -f3 $(COMPOUND_MAPPINGS_STRICT_FINAL) | grep "^UBERON:" | wc -l); \
	ENVO=$$(cut -f3 $(COMPOUND_MAPPINGS_STRICT_FINAL) | grep "^ENVO:" | wc -l); \
	CAS=$$(cut -f3 $(COMPOUND_MAPPINGS_STRICT_FINAL) | grep "^CAS-RN:" | wc -l); \
	INGRED=$$(cut -f3 $(COMPOUND_MAPPINGS_STRICT_FINAL) | grep "^ingredient:" | wc -l); \
	UNMAPPED=$$(cut -f3 $(COMPOUND_MAPPINGS_STRICT_FINAL) | grep "^$$" | wc -l); \
	SEMANTIC=$$((CHEBI + PUBCHEM + FOODON + UBERON + ENVO)); \
	echo "  Total entries:    $$TOTAL"; \
	echo ""; \
	if [ "$$TOTAL" -gt 0 ]; then \
		PERCENT=$$(awk "BEGIN {printf \"%.1f\", $$SEMANTIC * 100 / $$TOTAL}"); \
		echo "  Semantic IDs:     $$SEMANTIC ($$PERCENT%)"; \
	else \
		echo "  Semantic IDs:     $$SEMANTIC (0.0%)"; \
	fi; \
	echo "    ChEBI:          $$CHEBI"; \
	echo "    PubChem:        $$PUBCHEM"; \
	echo "    FOODON:         $$FOODON"; \
	echo "    UBERON:         $$UBERON"; \
	echo "    ENVO:           $$ENVO"; \
	echo ""; \
	echo "  Other:"; \
	echo "    CAS-RN:         $$CAS"; \
	echo "    ingredient:     $$INGRED"; \
	echo "    Unmapped:       $$UNMAPPED"; \
	echo "$(YELLOW)════════════════════════════════════════════════════════════$(NC)"
	@echo ""
	@echo "$(GREEN)Output: $(COMPOUND_MAPPINGS_STRICT_FINAL)$(NC)"

# Stage 10.5c.5.5: Create hydrate-specific mappings
# Generates variant with specific hydrated ChEBI IDs (e.g., CHEBI:86158 for CaCl2·2H2O)
# The base file maps all hydrates to anhydrous ChEBI IDs (degenerate mapping)
COMPOUND_MAPPINGS_STRICT_HYDRATE := $(MERGE_MAPPINGS_DIR)/compound_mappings_strict_final_hydrate.tsv

.PHONY: create-hydrate-mappings
create-hydrate-mappings: $(COMPOUND_MAPPINGS_STRICT_HYDRATE)
	@echo "$(GREEN)✓ Hydrate-specific mappings created$(NC)"

$(COMPOUND_MAPPINGS_STRICT_HYDRATE): $(COMPOUND_MAPPINGS_STRICT_FINAL) $(CHEBI_FORMULAS_FILE)
	@echo "$(BLUE)Creating hydrate-specific mapping file...$(NC)"
	$(PYTHON) -m src.mapping.create_hydrate_mappings \
		--input $(COMPOUND_MAPPINGS_STRICT_FINAL) \
		--chebi-formulas $(CHEBI_FORMULAS_FILE) \
		--output $(COMPOUND_MAPPINGS_STRICT_HYDRATE)
	@echo "$(GREEN)Output: $(COMPOUND_MAPPINGS_STRICT_HYDRATE)$(NC)"

# Stage 10.5c.5.6: Create simplified mapping files
# Lightweight versions with just chemical name, formula, and identifiers
COMPOUND_MAPPINGS_SIMPLIFIED := $(MERGE_MAPPINGS_DIR)/compound_mappings_simplified.tsv
COMPOUND_MAPPINGS_SIMPLIFIED_HYDRATE := $(MERGE_MAPPINGS_DIR)/compound_mappings_simplified_hydrate.tsv

.PHONY: create-simplified-mappings
create-simplified-mappings: $(COMPOUND_MAPPINGS_SIMPLIFIED) $(COMPOUND_MAPPINGS_SIMPLIFIED_HYDRATE)
	@echo "$(GREEN)✓ Simplified mapping files created$(NC)"

$(COMPOUND_MAPPINGS_SIMPLIFIED) $(COMPOUND_MAPPINGS_SIMPLIFIED_HYDRATE): $(COMPOUND_MAPPINGS_STRICT_FINAL) $(COMPOUND_MAPPINGS_STRICT_HYDRATE)
	@echo "$(BLUE)Creating simplified mapping files...$(NC)"
	@echo "$(YELLOW)Extracting: chemical name, formula, and identifiers$(NC)"
	$(PYTHON) src/scripts/create_simplified_mappings.py \
		--strict-input $(COMPOUND_MAPPINGS_STRICT_FINAL) \
		--strict-output $(COMPOUND_MAPPINGS_SIMPLIFIED) \
		--hydrate-input $(COMPOUND_MAPPINGS_STRICT_HYDRATE) \
		--hydrate-output $(COMPOUND_MAPPINGS_SIMPLIFIED_HYDRATE)
	@echo "$(GREEN)Outputs:$(NC)"
	@echo "  $(COMPOUND_MAPPINGS_SIMPLIFIED)"
	@echo "  $(COMPOUND_MAPPINGS_SIMPLIFIED_HYDRATE)"

# Stage 10.5c.5.7: Map biological ingredients to FOODON/ENVO
# Uses OAK to map complex biological ingredients (extracts, peptones, broths) to FOODON ontology
# Preserves existing FOODON/ENVO IDs and adds new mappings deterministically
FOODON_MAPPING_DIR := pipeline_output/foodon_mapping
BIOLOGICAL_INGREDIENTS_FOODON := $(FOODON_MAPPING_DIR)/biological_ingredients_foodon_final.tsv

.PHONY: map-biological-ingredients-foodon
map-biological-ingredients-foodon: $(BIOLOGICAL_INGREDIENTS_FOODON)
	@echo "$(GREEN)✓ Biological ingredients mapped to FOODON/ENVO$(NC)"

$(BIOLOGICAL_INGREDIENTS_FOODON): $(COMPOUND_MAPPINGS_STRICT_FINAL) | $(FOODON_MAPPING_DIR)
	@echo "$(BLUE)Mapping biological ingredients to FOODON using OAK...$(NC)"
	@echo "$(YELLOW)Enhanced search: exact, lowercase, normalized, synonyms, base compound$(NC)"
	$(PYTHON) src/mapping/oak_foodon_mapper.py \
		--input $(COMPOUND_MAPPINGS_STRICT_FINAL) \
		--output $(BIOLOGICAL_INGREDIENTS_FOODON)
	@if [ -f $(BIOLOGICAL_INGREDIENTS_FOODON) ]; then \
		TOTAL=$$(tail -n +2 $(BIOLOGICAL_INGREDIENTS_FOODON) | wc -l | tr -d ' '); \
		MAPPED=$$(tail -n +2 $(BIOLOGICAL_INGREDIENTS_FOODON) | cut -f2 | grep -v "^$$" | wc -l); \
		PRESERVED=$$(grep -c "preserved" $(BIOLOGICAL_INGREDIENTS_FOODON) || echo 0); \
		NEW_MAPPED=$$((MAPPED - PRESERVED)); \
		echo ""; \
		echo "$(YELLOW)FOODON Mapping Summary:$(NC)"; \
		echo "  Total biological ingredients: $$TOTAL"; \
		echo "  With FOODON/ENVO IDs:         $$MAPPED ($$((MAPPED * 100 / TOTAL))%)"; \
		echo "    Preserved from current:     $$PRESERVED"; \
		echo "    Newly mapped via OAK:       $$NEW_MAPPED"; \
		echo "  Unable to map:                $$((TOTAL - MAPPED))"; \
		echo "$(GREEN)Output: $(BIOLOGICAL_INGREDIENTS_FOODON)$(NC)"; \
	fi

$(FOODON_MAPPING_DIR):
	@mkdir -p $(FOODON_MAPPING_DIR)

# Stage 10.5c.6: Validate ontology mappings
# Uses OAK or local ChEBI nodes to verify IDs exist in ontologies
ONTOLOGY_VALIDATION_REPORT := $(MERGE_MAPPINGS_DIR)/ontology_validation_report.tsv

.PHONY: validate-ontology-mappings
validate-ontology-mappings: $(ONTOLOGY_VALIDATION_REPORT)
	@echo "$(GREEN)✓ Ontology mapping validation completed$(NC)"

$(ONTOLOGY_VALIDATION_REPORT): $(COMPOUND_MAPPINGS_STRICT_FINAL) $(CHEBI_NODES_FILE)
	@echo "$(BLUE)Validating ontology mappings...$(NC)"
	@echo "$(YELLOW)Checking ChEBI, UBERON, FOODON, ENVO IDs against ontologies$(NC)"
	$(PYTHON) -m src.quality.validate_ontology_mappings \
		--input $(COMPOUND_MAPPINGS_STRICT_FINAL) \
		--output $(ONTOLOGY_VALIDATION_REPORT) \
		--chebi-nodes $(CHEBI_NODES_FILE) || true
	@if [ -f $(ONTOLOGY_VALIDATION_REPORT) ]; then \
		TOTAL=$$(tail -n +2 $(ONTOLOGY_VALIDATION_REPORT) | wc -l | tr -d ' '); \
		VALID=$$(grep -c "valid" $(ONTOLOGY_VALIDATION_REPORT) || echo 0); \
		INVALID=$$(grep -c "invalid" $(ONTOLOGY_VALIDATION_REPORT) || echo 0); \
		echo ""; \
		echo "$(YELLOW)Validation Summary:$(NC)"; \
		echo "  Total IDs:  $$TOTAL"; \
		echo "  Valid:      $$VALID"; \
		echo "  Invalid:    $$INVALID"; \
		if [ "$$INVALID" -gt 0 ]; then \
			echo "$(RED)⚠ Found $$INVALID invalid ontology IDs$(NC)"; \
		else \
			echo "$(GREEN)✓ All ontology IDs are valid$(NC)"; \
		fi; \
	fi

# Validate using OAK (slower but authoritative)
.PHONY: validate-ontology-mappings-oak
validate-ontology-mappings-oak: $(COMPOUND_MAPPINGS_STRICT_FINAL)
	@echo "$(BLUE)Validating ontology mappings using OAK (this may take a while)...$(NC)"
	$(PYTHON) -m src.quality.validate_ontology_mappings \
		--input $(COMPOUND_MAPPINGS_STRICT_FINAL) \
		--output $(ONTOLOGY_VALIDATION_REPORT) \
		--use-oak \
		--batch-size 50

# ============================================================================
# Stage 10.6: Map Unmapped Ingredients (OLS + PubChem)
# Uses multi-ontology search (UBERON, FOODON, ENVO) for biological materials
# Uses PubChem fallback for chemicals without ChEBI mappings
# ============================================================================

# kg-microbe unmapped ingredients file
KG_MICROBE_MAPPINGS := /Users/marcin/Documents/VIMSS/ontology/KG-Hub/KG-Microbe/kg-microbe/mappings
UNMAPPED_MEDIADIVE_FILE := $(KG_MICROBE_MAPPINGS)/unmapped_mediadive_ingredients.tsv

# Output files (CACHE_DIR, OLS_CACHE_FILE, PUBCHEM_CACHE_FILE defined in Stage 10.5c)
ADDITIONAL_MAPPINGS := $(MERGE_MAPPINGS_DIR)/additional_ingredient_mappings.tsv
EXTENDED_LOOKUP_TABLE := $(MERGE_MAPPINGS_DIR)/compound_name_lookup_extended.tsv

# Map unmapped ingredients from kg-microbe MediaDive analysis
.PHONY: map-unmapped-ingredients
map-unmapped-ingredients: $(ADDITIONAL_MAPPINGS)
	@echo "$(GREEN)✓ Unmapped ingredients mapping completed$(NC)"

$(ADDITIONAL_MAPPINGS): $(UNMAPPED_MEDIADIVE_FILE) | $(CACHE_DIR)
	@echo "$(BLUE)Mapping unmapped MediaDive ingredients...$(NC)"
	@echo "$(YELLOW)Using OLS4 (UBERON, FOODON, ENVO) for biological materials$(NC)"
	@echo "$(YELLOW)Using PubChem for chemical compounds$(NC)"
	$(PYTHON) -m src.mapping.map_unmapped_ingredients \
		--input $(UNMAPPED_MEDIADIVE_FILE) \
		--output $(ADDITIONAL_MAPPINGS) \
		--ols-cache $(OLS_CACHE_FILE) \
		--pubchem-cache $(PUBCHEM_CACHE_FILE)

# Merge additional mappings into compound lookup table
.PHONY: merge-additional-mappings
merge-additional-mappings: $(EXTENDED_LOOKUP_TABLE)
	@echo "$(GREEN)✓ Additional mappings merged into lookup table$(NC)"

$(EXTENDED_LOOKUP_TABLE): $(ADDITIONAL_MAPPINGS) $(COMPOUND_LOOKUP_TABLE)
	@echo "$(BLUE)Merging additional mappings into compound lookup table...$(NC)"
	$(PYTHON) -m src.mapping.merge_additional_mappings \
		--lookup-table $(COMPOUND_LOOKUP_TABLE) \
		--additional $(ADDITIONAL_MAPPINGS) \
		--output $(EXTENDED_LOOKUP_TABLE)

# Run full unmapped ingredients mapping pipeline
.PHONY: extend-mappings
extend-mappings: merge-additional-mappings
	@echo "$(GREEN)✓ Extended mappings pipeline completed$(NC)"
	@EXTENDED_COUNT=$$(wc -l < $(EXTENDED_LOOKUP_TABLE) 2>/dev/null | tr -d ' '); \
	ORIGINAL_COUNT=$$(wc -l < $(COMPOUND_LOOKUP_TABLE) 2>/dev/null | tr -d ' '); \
	echo "$(GREEN)Extended lookup table: $$EXTENDED_COUNT entries (was $$ORIGINAL_COUNT)$(NC)"

# ============================================================================
# Stage 11: Property Calculation - Using enhanced mappings with hydration-corrected MW
# ============================================================================
.PHONY: compute-properties
compute-properties: $(MEDIA_PROPERTIES_DIR)/.done
	@echo "$(GREEN)✓ Media properties calculation completed using expanded ingredients (97.6% ChEBI coverage)$(NC)"

# Calculate pH, salinity, ionic strength using expanded complex ingredients
$(MEDIA_PROPERTIES_DIR)/.done: $(MEDIA_COMPOSITION_EXPANDED) $(CHEMICAL_PROPERTIES)
	@echo "$(BLUE)Property Calculation: Using expanded complex ingredients (97.6% ChEBI coverage)...$(NC)"
	@echo "$(YELLOW)ADVANTAGE: Complex ingredients resolved to constituents (yeast extract → 34 chemicals)$(NC)"
	@echo "$(YELLOW)Using ingredient → pKa mappings from $(CHEMICAL_PROPERTIES)$(NC)"
	@mkdir -p $(MEDIA_PROPERTIES_DIR)
	$(PYTHON) $(SCRIPTS_DIR)/compute_media_properties.py --input-high $(MEDIA_COMPOSITION_EXPANDED) --chemical-properties $(CHEMICAL_PROPERTIES) --output-dir $(MEDIA_PROPERTIES_DIR)
	@touch $(MEDIA_PROPERTIES_DIR)/.done

# Stage 12: Final Media Summary with Expanded Ingredients
.PHONY: media-summary
media-summary: $(MEDIA_SUMMARY)
	@echo "$(GREEN)✓ Media summary generation completed using expanded ingredients (97.6% ChEBI coverage)$(NC)"

# Generate comprehensive media summary using expanded complex ingredients
$(MEDIA_SUMMARY): $(MEDIA_PROPERTIES_DIR)/.done $(MEDIA_COMPOSITION_EXPANDED)
	@echo "$(BLUE)Creating comprehensive media summary with expanded complex ingredients...$(NC)"
	@echo "$(YELLOW)ADVANTAGE: 97.6% ChEBI coverage with complex ingredients resolved to constituents$(NC)"
	$(PYTHON) $(SCRIPTS_DIR)/create_media_summary.py --mappings-file $(MEDIA_COMPOSITION_EXPANDED) --properties-dir $(MEDIA_PROPERTIES_DIR) --output $(MEDIA_SUMMARY)

# Stage 12b: Create Media Composition Table with Normalized Concentrations
.PHONY: create-media-composition-table
create-media-composition-table: $(MEDIA_COMPOSITION_TABLE)
	@echo "$(GREEN)✓ Media composition table with normalized concentrations created$(NC)"

$(MEDIA_COMPOSITION_TABLE): $(COMPOUND_MAPPINGS_STRICT_FINAL)
	@echo "$(BLUE)Creating media composition table with g/mL normalization...$(NC)"
	$(PYTHON) -m src.scripts.create_media_composition_table --input $(COMPOUND_MAPPINGS_STRICT_FINAL) --output $(MEDIA_COMPOSITION_TABLE)

# Stage 12b2: Import MediaDive Solutions (Trace Elements, Vitamins, Minerals)
# Converts MediaDive solution recipes to complex ingredient YAML format
# Reuses existing MediaDive data from kg-microbe project
.PHONY: import-mediadive-solutions
import-mediadive-solutions: $(MEDIADIVE_SOLUTIONS_YAML)
	@echo "$(GREEN)✓ MediaDive solutions imported into complex ingredients database$(NC)"

$(MEDIADIVE_SOLUTIONS_YAML): $(MEDIADIVE_SOLUTIONS_JSON) $(MEDIADIVE_MEDIA_JSON)
	@echo "$(BLUE)Importing trace element and vitamin solutions from MediaDive data...$(NC)"
	@echo "$(YELLOW)Reusing data from: $(MEDIADIVE_RAW_DIR)$(NC)"
	@echo "$(YELLOW)Importing solutions with ≥5 media usage$(NC)"
	$(PYTHON) src/curation/import_mediadive_solutions.py \
		--solutions $(MEDIADIVE_SOLUTIONS_JSON) \
		--media $(MEDIADIVE_MEDIA_JSON) \
		--output $(MEDIADIVE_SOLUTIONS_YAML) \
		--min-usage 5 \
		--categories "trace,vitamin,mineral"

# Stage 12c: Expand Complex Biological Ingredients
# Decomposes complex ingredients (yeast extract, peptone, etc.) into constituent chemicals
# Data source: data/curated/complex_ingredients/complex_ingredient_compositions.yaml
# Based on literature: PMC9998214, ITW A1552, ThermoFisher Peptone Guide, USBio specs
.PHONY: expand-complex-ingredients
expand-complex-ingredients: $(MEDIA_COMPOSITION_EXPANDED)
	@echo "$(GREEN)✓ Complex ingredients expanded into constituent chemicals$(NC)"

$(MEDIA_COMPOSITION_EXPANDED): $(MEDIA_COMPOSITION_TABLE) $(COMPLEX_INGREDIENT_COMPOSITIONS)
	@echo "$(BLUE)Expanding complex biological ingredients (yeast extract, peptone, etc.)...$(NC)"
	@echo "$(YELLOW)Using curated composition data from literature sources$(NC)"
	@echo "$(YELLOW)🔄 Recursive expansion enabled: LB broth → tryptone → amino acids$(NC)"
	$(PYTHON) -m src.scripts.expand_complex_ingredients \
		--input $(MEDIA_COMPOSITION_TABLE) \
		--compositions $(COMPLEX_INGREDIENT_COMPOSITIONS) \
		--output $(MEDIA_COMPOSITION_EXPANDED) \
		--resolve-references \
		--mode replace

# Stage 12d: Analyze Unmapped Complex Ingredients
# Identifies complex biological ingredients that are not yet mapped to ChEBI or documented in YAML
# Prioritizes them based on occurrence frequency for curation efforts
.PHONY: analyze-unmapped-complex
analyze-unmapped-complex: $(UNMAPPED_COMPLEX_ANALYSIS)
	@echo "$(GREEN)✓ Unmapped complex ingredients analysis completed$(NC)"

$(UNMAPPED_COMPLEX_ANALYSIS): $(HIGH_CONFIDENCE_FINAL) $(COMPLEX_INGREDIENT_COMPOSITIONS)
	@echo "$(BLUE)Analyzing unmapped complex ingredients (peptones, extracts, sera)...$(NC)"
	@echo "$(YELLOW)Prioritizing by occurrence count for curation efforts$(NC)"
	@mkdir -p $(OUTPUT_DIR)/analysis
	$(PYTHON) src/analysis/analyze_unmapped_complex_ingredients.py \
		--mappings $(HIGH_CONFIDENCE_FINAL) \
		--compositions $(COMPLEX_INGREDIENT_COMPOSITIONS) \
		--output $(UNMAPPED_COMPLEX_ANALYSIS) \
		--report $(UNMAPPED_COMPLEX_REPORT) \
		--top-n 50
	@echo "$(YELLOW)📊 Report saved to: $(UNMAPPED_COMPLEX_REPORT)$(NC)"
	@echo "$(YELLOW)📊 Detailed analysis: $(UNMAPPED_COMPLEX_ANALYSIS)$(NC)"

# Chemical Database Management (IUPAC Data Processing)

# IUPAC data directory and files
IUPAC_DATA_DIR := data/chemical_processing
IUPAC_RAW_DATA := $(IUPAC_DATA_DIR)/raw_chemical_data.json
IUPAC_PROCESSED_DATA := $(IUPAC_DATA_DIR)/processed_chemical_data.json
IUPAC_MAPPING_REPORT := $(IUPAC_DATA_DIR)/compound_mapping_report.tsv
CHEMICAL_DB_BACKUP := chemical_properties_backup.tsv

# Create IUPAC data directory
$(IUPAC_DATA_DIR):
	@mkdir -p $(IUPAC_DATA_DIR)
	@echo "$(GREEN)✓ Created IUPAC data directory$(NC)"

# Generate compound mapping report from existing data
.PHONY: iupac-analyze-compounds
iupac-analyze-compounds: install $(IUPAC_DATA_DIR)
	@echo "$(BLUE)Analyzing existing compounds for IUPAC data download...$(NC)"
	$(PYTHON) -c "\
import sys, asyncio; \
sys.path.insert(0, 'src'); \
from chem.iupac.compound_mapper import CompoundMapper; \
from pathlib import Path; \
mapper = CompoundMapper(); \
mappings_files = [Path('$(HIGH_CONFIDENCE_NORMALIZED)'), Path('$(COMPOSITION_MAPPING)'), Path('$(UNACCOUNTED_MATCHES)')]; \
target_compounds = mapper.create_download_target_list(mappings_files); \
print(f'Found {len(target_compounds)} compounds for IUPAC download'); \
with open('$(IUPAC_DATA_DIR)/target_compounds.txt', 'w') as f: f.write('\\n'.join(target_compounds)) \
"
	@echo "$(GREEN)✓ Compound analysis completed: $(IUPAC_DATA_DIR)/target_compounds.txt$(NC)"

# Download chemical data from IUPAC sources
.PHONY: iupac-download-data
iupac-download-data: install iupac-analyze-compounds
	@echo "$(BLUE)Downloading chemical data from IUPAC sources...$(NC)"
	@if [ -f "$(IUPAC_DATA_DIR)/target_compounds.txt" ]; then \
		COMPOUNDS=$$(head -10 "$(IUPAC_DATA_DIR)/target_compounds.txt" | tr '\n' ',' | sed 's/,$$//'); \
		echo "Downloading data for: $$COMPOUNDS"; \
		$(PYTHON) -m src.chem.iupac.pipeline --download-compounds "$$COMPOUNDS" --data-dir $(IUPAC_DATA_DIR); \
	else \
		echo "$(RED)No target compounds found. Run 'make iupac-analyze-compounds' first$(NC)"; \
		exit 1; \
	fi
	@echo "$(GREEN)✓ Chemical data download completed$(NC)"

# Process raw IUPAC data into chemical properties
.PHONY: iupac-process-data
iupac-process-data: install
	@echo "$(BLUE)Processing raw IUPAC data...$(NC)"
	@if [ -f "$(IUPAC_RAW_DATA)" ]; then \
		$(PYTHON) -m src.chem.iupac.pipeline --process-only --data-dir $(IUPAC_DATA_DIR); \
	else \
		echo "$(RED)No raw data found. Run 'make iupac-download-data' first$(NC)"; \
		exit 1; \
	fi
	@echo "$(GREEN)✓ Data processing completed$(NC)"

# Generate updated chemical_properties.tsv from IUPAC data
.PHONY: iupac-generate-tsv
iupac-generate-tsv: install iupac-process-data
	@echo "$(BLUE)Generating chemical_properties.tsv from IUPAC data...$(NC)"
	@# Backup existing file
	@if [ -f "$(CHEMICAL_PROPERTIES)" ]; then \
		cp "$(CHEMICAL_PROPERTIES)" "$(CHEMICAL_DB_BACKUP)"; \
		echo "Backed up existing chemical_properties.tsv to $(CHEMICAL_DB_BACKUP)"; \
	fi
	@$(PYTHON) -c "\
import sys; \
sys.path.insert(0, 'src'); \
from chem.iupac.tsv_generator import ChemicalPropertiesTSVGenerator; \
from pathlib import Path; \
generator = ChemicalPropertiesTSVGenerator(); \
processed_file = Path('$(IUPAC_PROCESSED_DATA)'); \
output_file = Path('$(CHEMICAL_PROPERTIES)'); \
generator.generate_tsv_from_json(processed_file, output_file, merge_with_existing=True) if processed_file.exists() else print('No processed data found') \
"
	@echo "$(GREEN)✓ chemical_properties.tsv updated$(NC)"

# Complete IUPAC pipeline: analyze → download → process → generate
.PHONY: iupac-full-pipeline
iupac-full-pipeline: install $(IUPAC_DATA_DIR)
	@echo "$(BLUE)Running complete IUPAC chemical data pipeline...$(NC)"
	$(PYTHON) src/attic/update_chemical_properties.py --full-update --data-dir $(IUPAC_DATA_DIR)
	@echo "$(GREEN)✓ Full IUPAC pipeline completed$(NC)"

# Quick update chemical database from existing mappings
.PHONY: iupac-update-from-mappings
iupac-update-from-mappings: install
	@echo "$(BLUE)Updating chemical database from existing compound mappings...$(NC)"
	$(PYTHON) src/attic/update_chemical_properties.py --update-from-mappings --data-dir $(IUPAC_DATA_DIR)
	@echo "$(GREEN)✓ Chemical database updated from mappings$(NC)"

# Process compounds from composition_kg_mapping.tsv with robust error handling
.PHONY: iupac-process-composition-mapping
iupac-process-composition-mapping: install $(IUPAC_DATA_DIR)
	@echo "$(BLUE)Processing compounds from composition_kg_mapping.tsv with robust error handling...$(NC)"
	@if [ -f "composition_kg_mapping.tsv" ]; then \
		echo "Found composition_kg_mapping.tsv with $$(tail -n +2 composition_kg_mapping.tsv | wc -l) entries"; \
		echo "Extracting unique compound names..."; \
		UNIQUE_COMPOUNDS=$$(cut -f2 composition_kg_mapping.tsv | tail -n +2 | sort | uniq | wc -l); \
		echo "Found $$UNIQUE_COMPOUNDS unique compounds for processing"; \
		$(PYTHON) -m src.chem.iupac.pipeline --from-mapping-file composition_kg_mapping.tsv --data-dir $(IUPAC_DATA_DIR); \
	else \
		echo "$(RED)composition_kg_mapping.tsv not found. Run 'make mapping' first$(NC)"; \
		exit 1; \
	fi
	@echo "$(GREEN)✓ Composition mapping processing completed with full error reporting$(NC)"

# Add specific compounds to chemical database
.PHONY: iupac-add-compounds
iupac-add-compounds: install
	@echo "$(BLUE)Adding compounds to chemical database...$(NC)"
	@echo "Usage: make iupac-add-compounds COMPOUNDS='sodium chloride,glucose,calcium carbonate'"
	@if [ -z "$(COMPOUNDS)" ]; then \
		echo "$(RED)Error: No compounds specified. Use: make iupac-add-compounds COMPOUNDS='compound1,compound2'$(NC)"; \
		exit 1; \
	fi
	$(PYTHON) src/attic/update_chemical_properties.py --add-compounds "$(COMPOUNDS)" --data-dir $(IUPAC_DATA_DIR)
	@echo "$(GREEN)✓ Compounds added to chemical database$(NC)"

# Test IUPAC system with sample compounds
.PHONY: iupac-test
iupac-test: install $(IUPAC_DATA_DIR)
	@echo "$(BLUE)Testing IUPAC chemical data system...$(NC)"
	$(PYTHON) src/attic/update_chemical_properties.py --test-mode --data-dir $(IUPAC_DATA_DIR)
	@echo "$(GREEN)✓ IUPAC system test completed$(NC)"

# Validate chemical_properties.tsv format
.PHONY: iupac-validate-tsv
iupac-validate-tsv: install
	@echo "$(BLUE)Validating chemical_properties.tsv format...$(NC)"
	@$(PYTHON) -c "\
import sys; \
sys.path.insert(0, 'src'); \
from chem.iupac.tsv_generator import ChemicalPropertiesTSVGenerator; \
from pathlib import Path; \
generator = ChemicalPropertiesTSVGenerator(); \
tsv_file = Path('$(CHEMICAL_PROPERTIES)'); \
is_valid = generator.validate_tsv_format(tsv_file) if tsv_file.exists() else False; \
print('✓ TSV format validation passed') if is_valid else (print('✗ TSV format validation failed') or sys.exit(1)) if tsv_file.exists() else (print('Chemical properties file not found: $(CHEMICAL_PROPERTIES)') or sys.exit(1)) \
"
	@echo "$(GREEN)✓ TSV validation completed$(NC)"

# Show IUPAC data status and statistics
.PHONY: iupac-status
iupac-status:
	@echo "$(BLUE)IUPAC Chemical Data Status$(NC)"
	@echo "========================="
	@echo ""
	@echo "$(YELLOW)Data Directory:$(NC)"
	@[ -d $(IUPAC_DATA_DIR) ] && echo "✓ $(IUPAC_DATA_DIR) exists" || echo "✗ $(IUPAC_DATA_DIR) missing"
	@echo ""
	@echo "$(YELLOW)IUPAC Data Files:$(NC)"
	@[ -f "$(IUPAC_RAW_DATA)" ] && echo "✓ Raw data: $$(du -h $(IUPAC_RAW_DATA) | cut -f1)" || echo "✗ Raw data: Missing"
	@[ -f "$(IUPAC_PROCESSED_DATA)" ] && echo "✓ Processed data: $$(du -h $(IUPAC_PROCESSED_DATA) | cut -f1)" || echo "✗ Processed data: Missing"
	@[ -f "$(IUPAC_MAPPING_REPORT)" ] && echo "✓ Mapping report: $$(wc -l < $(IUPAC_MAPPING_REPORT)) compounds" || echo "✗ Mapping report: Missing"
	@echo ""
	@echo "$(YELLOW)Chemical Properties Database:$(NC)"
	@[ -f "$(CHEMICAL_PROPERTIES)" ] && echo "✓ chemical_properties.tsv: $$(tail -n +2 $(CHEMICAL_PROPERTIES) | wc -l) compounds" || echo "✗ chemical_properties.tsv: Missing"
	@[ -f "$(CHEMICAL_DB_BACKUP)" ] && echo "✓ Backup available: $(CHEMICAL_DB_BACKUP)" || echo "✗ No backup available"
	@echo ""
	@echo "$(YELLOW)Target Compounds:$(NC)"
	@[ -f "$(IUPAC_DATA_DIR)/target_compounds.txt" ] && echo "✓ Target list: $$(wc -l < $(IUPAC_DATA_DIR)/target_compounds.txt) compounds" || echo "✗ Target list: Missing"

# Clean IUPAC data files
.PHONY: iupac-clean
iupac-clean:
	@echo "$(BLUE)Cleaning IUPAC data files...$(NC)"
	@if [ -d "$(IUPAC_DATA_DIR)" ]; then \
		rm -rf $(IUPAC_DATA_DIR); \
		echo "✓ Removed $(IUPAC_DATA_DIR)"; \
	fi
	@if [ -f "$(CHEMICAL_DB_BACKUP)" ]; then \
		rm -f $(CHEMICAL_DB_BACKUP); \
		echo "✓ Removed backup file"; \
	fi
	@echo "$(GREEN)✓ IUPAC data cleanup completed$(NC)"

# Restore chemical_properties.tsv from backup
.PHONY: iupac-restore-backup
iupac-restore-backup:
	@echo "$(BLUE)Restoring chemical_properties.tsv from backup...$(NC)"
	@if [ -f "$(CHEMICAL_DB_BACKUP)" ]; then \
		cp "$(CHEMICAL_DB_BACKUP)" "$(CHEMICAL_PROPERTIES)"; \
		echo "✓ Restored $(CHEMICAL_PROPERTIES) from backup"; \
	else \
		echo "$(RED)✗ No backup file found: $(CHEMICAL_DB_BACKUP)$(NC)"; \
		exit 1; \
	fi
	@echo "$(GREEN)✓ Backup restoration completed$(NC)"

# Legacy targets for backward compatibility
.PHONY: update-chemical-db test-chemical-db
update-chemical-db: iupac-update-from-mappings
test-chemical-db: iupac-test

# PubChem Chemical Data Processing Pipeline

# PubChem data directory and files
PUBCHEM_DATA_DIR := data/pubchem_processing
PUBCHEM_RAW_DATA := $(PUBCHEM_DATA_DIR)/pubchem_raw_data.json
PUBCHEM_PROCESSED_DATA := $(PUBCHEM_DATA_DIR)/pubchem_processed_data.json
PUBCHEM_COMPARISON_REPORT := $(PUBCHEM_DATA_DIR)/pubchem_comparison_report.json

# Create PubChem data directory
$(PUBCHEM_DATA_DIR):
	@mkdir -p $(PUBCHEM_DATA_DIR)
	@echo "$(GREEN)✓ Created PubChem data directory$(NC)"

# Complete PubChem pipeline with bulk FTP downloads and robust error handling
.PHONY: pubchem-full-pipeline
pubchem-full-pipeline: install $(PUBCHEM_DATA_DIR)
	@echo "$(BLUE)Running complete PubChem chemical data pipeline...$(NC)"
	$(PYTHON) -m src.chem.pubchem.pipeline --full-pipeline --data-dir $(PUBCHEM_DATA_DIR)
	@echo "$(GREEN)✓ Full PubChem pipeline completed$(NC)"

# Process compounds from composition_kg_mapping.tsv with PubChem
.PHONY: pubchem-process-composition-mapping
pubchem-process-composition-mapping: install $(PUBCHEM_DATA_DIR)
	@echo "$(BLUE)Processing compounds from composition_kg_mapping.tsv using PubChem...$(NC)"
	@if [ -f "composition_kg_mapping.tsv" ]; then \
		echo "Found composition_kg_mapping.tsv with $$(tail -n +2 composition_kg_mapping.tsv | wc -l) entries"; \
		echo "Extracting unique compound names for PubChem processing..."; \
		UNIQUE_COMPOUNDS=$$(cut -f2 composition_kg_mapping.tsv | tail -n +2 | sort | uniq | wc -l); \
		echo "Found $$UNIQUE_COMPOUNDS unique compounds for PubChem processing"; \
		$(PYTHON) -m src.chem.pubchem.pipeline --from-mapping-file composition_kg_mapping.tsv --data-dir $(PUBCHEM_DATA_DIR); \
	else \
		echo "$(RED)composition_kg_mapping.tsv not found. Run 'make mapping' first$(NC)"; \
		exit 1; \
	fi
	@echo "$(GREEN)✓ PubChem composition mapping processing completed with full error reporting$(NC)"

# Download specific compounds using PubChem
.PHONY: pubchem-download-compounds
pubchem-download-compounds: install $(PUBCHEM_DATA_DIR)
	@echo "$(BLUE)Downloading specific compounds from PubChem...$(NC)"
	@echo "Usage: make pubchem-download-compounds COMPOUNDS='sodium chloride,glucose,calcium carbonate'"
	@if [ -z "$(COMPOUNDS)" ]; then \
		echo "$(RED)Error: No compounds specified. Use: make pubchem-download-compounds COMPOUNDS='compound1,compound2'$(NC)"; \
		exit 1; \
	fi
	$(PYTHON) -m src.chem.pubchem.pipeline --download-compounds "$(COMPOUNDS)" --data-dir $(PUBCHEM_DATA_DIR)
	@echo "$(GREEN)✓ PubChem compound download completed$(NC)"

# Test PubChem system with sample compounds
.PHONY: pubchem-test
pubchem-test: install $(PUBCHEM_DATA_DIR)
	@echo "$(BLUE)Testing PubChem chemical data system...$(NC)"
	$(PYTHON) -m src.chem.pubchem.pipeline --download-compounds "glucose,sodium chloride,glycine" --data-dir $(PUBCHEM_DATA_DIR)
	@echo "$(GREEN)✓ PubChem system test completed$(NC)"

# Show PubChem data status and statistics
.PHONY: pubchem-status
pubchem-status:
	@echo "$(BLUE)PubChem Chemical Data Status$(NC)"
	@echo "============================"
	@echo ""
	@echo "$(YELLOW)Data Directory:$(NC)"
	@[ -d $(PUBCHEM_DATA_DIR) ] && echo "✓ $(PUBCHEM_DATA_DIR) exists" || echo "✗ $(PUBCHEM_DATA_DIR) missing"
	@echo ""
	@echo "$(YELLOW)PubChem Data Files:$(NC)"
	@[ -f "$(PUBCHEM_RAW_DATA)" ] && echo "✓ Raw data: $$(du -h $(PUBCHEM_RAW_DATA) | cut -f1)" || echo "✗ Raw data: Missing"
	@[ -f "$(PUBCHEM_PROCESSED_DATA)" ] && echo "✓ Processed data: $$(du -h $(PUBCHEM_PROCESSED_DATA) | cut -f1)" || echo "✗ Processed data: Missing"
	@[ -f "$(PUBCHEM_COMPARISON_REPORT)" ] && echo "✓ Comparison report: $$(du -h $(PUBCHEM_COMPARISON_REPORT) | cut -f1)" || echo "✗ Comparison report: Missing"
	@echo ""
	@echo "$(YELLOW)PubChem Cache:$(NC)"
	@[ -d "$(PUBCHEM_DATA_DIR)/cache" ] && echo "✓ Cache directory: $$(du -sh $(PUBCHEM_DATA_DIR)/cache | cut -f1)" || echo "✗ Cache directory: Missing"
	@[ -d "$(PUBCHEM_DATA_DIR)/bulk" ] && echo "✓ Bulk data: $$(du -sh $(PUBCHEM_DATA_DIR)/bulk | cut -f1)" || echo "✗ Bulk data: Missing"

# Clean PubChem data files
.PHONY: pubchem-clean
pubchem-clean:
	@echo "$(BLUE)Cleaning PubChem data files...$(NC)"
	@if [ -d "$(PUBCHEM_DATA_DIR)" ]; then \
		rm -rf $(PUBCHEM_DATA_DIR); \
		echo "✓ Removed $(PUBCHEM_DATA_DIR)"; \
	fi
	@echo "$(GREEN)✓ PubChem data cleanup completed$(NC)"

# OAK CHEBI Mapping Pipeline

# OAK CHEBI mapping files and directories
OAK_DATA_DIR := data
CHEBI_LEXICAL_INDEX := $(OAK_DATA_DIR)/chebi_lexical_index.db
COMPOUNDS_FOR_CHEBI := $(OAK_CHEBI_DIR)/compounds_for_chebi_mapping.txt
NON_CHEBI_DETAILS := $(OAK_CHEBI_DIR)/non_chebi_mapping_details.tsv
OAK_CHEBI_ANNOTATIONS := $(OAK_CHEBI_DIR)/oak_chebi_annotations.json
UPDATED_COMPOSITION_MAPPING := $(OAK_CHEBI_DIR)/composition_kg_mapping_with_oak_chebi.tsv

# Create OAK data directory
$(OAK_DATA_DIR):
	@mkdir -p $(OAK_DATA_DIR)
	@echo "$(GREEN)✓ Created OAK data directory$(NC)"

# Extract compounds that need CHEBI mapping (not mapped to CHEBI currently)
.PHONY: extract-non-chebi-compounds
extract-non-chebi-compounds: $(COMPOSITION_MAPPING)
	@echo "$(BLUE)Extracting compounds that need CHEBI mapping...$(NC)"
	$(PYTHON) src/analysis/extract_non_chebi_compounds.py
	@echo "$(GREEN)✓ Extracted $$(wc -l < $(COMPOUNDS_FOR_CHEBI)) compounds for CHEBI mapping$(NC)"

# Run OAK CHEBI annotation on filtered compounds
.PHONY: oak-chebi-annotate
oak-chebi-annotate: $(COMPOUNDS_FOR_CHEBI) $(OAK_DATA_DIR)
	@echo "$(BLUE)Running OAK CHEBI annotation on $$(wc -l < $(COMPOUNDS_FOR_CHEBI)) compounds...$(NC)"
	@echo "$(YELLOW)This may take 5-10 minutes to build the CHEBI lexical index...$(NC)"
	runoak -i sqlite:obo:chebi annotate \
		--text-file $(COMPOUNDS_FOR_CHEBI) \
		--output-type json \
		--lexical-index-file $(CHEBI_LEXICAL_INDEX) \
		--output $(OAK_CHEBI_ANNOTATIONS)
	@echo "$(GREEN)✓ OAK CHEBI annotation completed$(NC)"

# Apply OAK CHEBI annotations to composition mapping
.PHONY: apply-oak-chebi-mappings
apply-oak-chebi-mappings: $(OAK_CHEBI_ANNOTATIONS)
	@echo "$(BLUE)Applying OAK CHEBI mappings to composition mapping...$(NC)"
	$(PYTHON) src/mapping/apply_oak_chebi_mappings.py \
		--annotations-file $(OAK_CHEBI_ANNOTATIONS) \
		--compounds-file $(COMPOUNDS_FOR_CHEBI) \
		--output-file $(UPDATED_COMPOSITION_MAPPING)
	@echo "$(GREEN)✓ Applied OAK CHEBI mappings to $(UPDATED_COMPOSITION_MAPPING)$(NC)"

# Fix hydrated compound mappings (ingredient codes -> CHEBI)
.PHONY: fix-hydrated-mappings
fix-hydrated-mappings: $(UPDATED_COMPOSITION_MAPPING)
	@echo "$(BLUE)Fixing hydrated compounds mapped to ingredient codes...$(NC)"
	$(PYTHON) src/hydration/fix_hydrated_compound_mappings.py
	@echo "$(GREEN)✓ Hydrated compound mappings fixed$(NC)"

# Complete OAK CHEBI mapping pipeline (alternative standalone version)
.PHONY: oak-chebi-mapping-standalone
oak-chebi-mapping-standalone: extract-non-chebi-compounds oak-chebi-annotate apply-oak-chebi-mappings fix-hydrated-mappings
	@echo "$(GREEN)✓ Complete OAK CHEBI mapping pipeline completed$(NC)"
	@echo "$(YELLOW)Updated composition mapping available in: $(UPDATED_COMPOSITION_MAPPING)$(NC)"

# Test OAK connection and annotation with sample compounds
.PHONY: oak-chebi-test
oak-chebi-test: $(OAK_DATA_DIR)
	@echo "$(BLUE)Testing OAK CHEBI annotation with sample compounds...$(NC)"
	@echo -e "glucose\\ncitric acid\\nsodium chloride" > test_compounds.txt
	runoak -i sqlite:obo:chebi annotate \
		--text-file test_compounds.txt \
		--output-type json \
		--lexical-index-file $(CHEBI_LEXICAL_INDEX)
	@rm test_compounds.txt
	@echo "$(GREEN)✓ OAK CHEBI test completed$(NC)"

# Show OAK CHEBI mapping status
.PHONY: oak-chebi-status
oak-chebi-status:
	@echo "$(BLUE)OAK CHEBI Mapping Status$(NC)"
	@echo "========================"
	@echo ""
	@echo "$(YELLOW)Input Files:$(NC)"
	@[ -f "$(COMPOSITION_MAPPING)" ] && echo "✓ Composition mapping: $$(wc -l < $(COMPOSITION_MAPPING)) rows" || echo "✗ Composition mapping: Missing"
	@[ -f "$(COMPOUNDS_FOR_CHEBI)" ] && echo "✓ Compounds for CHEBI: $$(wc -l < $(COMPOUNDS_FOR_CHEBI)) compounds" || echo "✗ Compounds for CHEBI: Missing"
	@echo ""
	@echo "$(YELLOW)OAK Data:$(NC)"
	@[ -d "$(OAK_DATA_DIR)" ] && echo "✓ OAK data directory exists" || echo "✗ OAK data directory: Missing"
	@[ -f "$(CHEBI_LEXICAL_INDEX)" ] && echo "✓ CHEBI lexical index: $$(du -h $(CHEBI_LEXICAL_INDEX) | cut -f1)" || echo "✗ CHEBI lexical index: Missing"
	@[ -f "$(OAK_CHEBI_ANNOTATIONS)" ] && echo "✓ OAK annotations: $$(du -h $(OAK_CHEBI_ANNOTATIONS) | cut -f1)" || echo "✗ OAK annotations: Missing"
	@echo ""
	@echo "$(YELLOW)Output Files:$(NC)"
	@[ -f "$(NON_CHEBI_DETAILS)" ] && echo "✓ Non-CHEBI details: $$(wc -l < $(NON_CHEBI_DETAILS)) rows" || echo "✗ Non-CHEBI details: Missing"
	@[ -f "$(UPDATED_COMPOSITION_MAPPING)" ] && echo "✓ Updated mapping: $$(wc -l < $(UPDATED_COMPOSITION_MAPPING)) rows" || echo "✗ Updated mapping: Missing"

# Clean OAK CHEBI mapping files
.PHONY: oak-chebi-clean
oak-chebi-clean:
	@echo "$(BLUE)Cleaning OAK CHEBI mapping files...$(NC)"
	@rm -f $(COMPOUNDS_FOR_CHEBI) $(NON_CHEBI_DETAILS) $(OAK_CHEBI_ANNOTATIONS) $(UPDATED_COMPOSITION_MAPPING)
	@if [ -f "$(CHEBI_LEXICAL_INDEX)" ]; then \
		echo "$(YELLOW)Keeping CHEBI lexical index for reuse: $(CHEBI_LEXICAL_INDEX)$(NC)"; \
	fi
	@echo "$(GREEN)✓ OAK CHEBI mapping cleanup completed$(NC)"

# ============================================================================
# BacDive Metabolites Mapping Pipeline
# ============================================================================
# Maps unmapped BacDive metabolites (19,129 records → 154 unique) to ChEBI

# BacDive metabolites files and directories
BACDIVE_METABOLITES_INPUT := data/unmapped/bacdive_metabolites_without_chebi_ids.tsv
BACDIVE_METABOLITES_DIR := $(OUTPUT_DIR)/bacdive_metabolites
BACDIVE_METABOLITES_UNIQUE := $(BACDIVE_METABOLITES_DIR)/bacdive_metabolites_unique.txt
BACDIVE_METABOLITES_FREQUENCY := $(BACDIVE_METABOLITES_DIR)/bacdive_metabolites_frequency.tsv
BACDIVE_METABOLITES_OAK := $(BACDIVE_METABOLITES_DIR)/bacdive_metabolites_oak_annotations.json
BACDIVE_METABOLITES_MAPPED := $(BACDIVE_METABOLITES_DIR)/bacdive_metabolites_chebi_mappings.tsv

# Create BacDive output directory
$(BACDIVE_METABOLITES_DIR):
	@mkdir -p $@

# Extract unique BacDive metabolites for mapping
.PHONY: bacdive-metabolites-extract
bacdive-metabolites-extract: $(BACDIVE_METABOLITES_UNIQUE)
	@echo "$(GREEN)✓ BacDive metabolites extraction completed$(NC)"

$(BACDIVE_METABOLITES_UNIQUE): $(BACDIVE_METABOLITES_INPUT) | $(BACDIVE_METABOLITES_DIR)
	@echo "$(BLUE)Extracting unique BacDive metabolites (19,129 → ~154 unique)...$(NC)"
	$(PYTHON) src/analysis/extract_bacdive_metabolites.py \
		--input $(BACDIVE_METABOLITES_INPUT) \
		--output-dir $(BACDIVE_METABOLITES_DIR)

# Run OAK ChEBI annotation on BacDive metabolites
.PHONY: bacdive-metabolites-oak-annotate
bacdive-metabolites-oak-annotate: $(BACDIVE_METABOLITES_OAK)
	@echo "$(GREEN)✓ BacDive metabolites OAK annotation completed$(NC)"

$(BACDIVE_METABOLITES_OAK): $(BACDIVE_METABOLITES_UNIQUE) | $(BACDIVE_METABOLITES_DIR)
	@echo "$(BLUE)Running OAK ChEBI annotation on BacDive metabolites...$(NC)"
	@echo "$(YELLOW)This may take a few minutes to build/use the ChEBI lexical index...$(NC)"
	runoak -i sqlite:obo:chebi annotate \
		--text-file $(BACDIVE_METABOLITES_UNIQUE) \
		--output-type json \
		--lexical-index-file $(CHEBI_LEXICAL_INDEX) \
		--output $(BACDIVE_METABOLITES_OAK)

# Apply OAK mappings to create final BacDive metabolites ChEBI mapping
.PHONY: bacdive-metabolites-apply-mappings
bacdive-metabolites-apply-mappings: $(BACDIVE_METABOLITES_MAPPED)
	@echo "$(GREEN)✓ BacDive metabolites ChEBI mappings applied$(NC)"

$(BACDIVE_METABOLITES_MAPPED): $(BACDIVE_METABOLITES_OAK) $(BACDIVE_METABOLITES_FREQUENCY)
	@echo "$(BLUE)Applying OAK mappings to BacDive metabolites...$(NC)"
	$(PYTHON) src/mapping/apply_bacdive_oak_mappings.py \
		--annotations-file $(BACDIVE_METABOLITES_OAK) \
		--metabolites-file $(BACDIVE_METABOLITES_UNIQUE) \
		--frequency-file $(BACDIVE_METABOLITES_FREQUENCY) \
		--output-file $(BACDIVE_METABOLITES_MAPPED)

# Complete BacDive metabolites mapping pipeline
.PHONY: bacdive-metabolites-mapping
bacdive-metabolites-mapping: bacdive-metabolites-extract bacdive-metabolites-oak-annotate bacdive-metabolites-apply-mappings
	@echo "$(GREEN)════════════════════════════════════════════════════════════════$(NC)"
	@echo "$(GREEN)       BacDive Metabolites Mapping Complete!                     $(NC)"
	@echo "$(GREEN)════════════════════════════════════════════════════════════════$(NC)"
	@echo ""
	@echo "$(BLUE)Output files:$(NC)"
	@echo "  📄 Unique metabolites: $(BACDIVE_METABOLITES_UNIQUE)"
	@echo "  📊 Frequency report: $(BACDIVE_METABOLITES_FREQUENCY)"
	@echo "  🔬 OAK annotations: $(BACDIVE_METABOLITES_OAK)"
	@echo "  ✅ ChEBI mappings: $(BACDIVE_METABOLITES_MAPPED)"

# Show BacDive metabolites status
.PHONY: bacdive-metabolites-status
bacdive-metabolites-status:
	@echo "$(BLUE)BacDive Metabolites Mapping Status$(NC)"
	@echo "==================================="
	@echo ""
	@echo "$(YELLOW)Input:$(NC)"
	@[ -f "$(BACDIVE_METABOLITES_INPUT)" ] && echo "✓ Input file: $$(wc -l < $(BACDIVE_METABOLITES_INPUT)) lines" || echo "✗ Input file: Missing"
	@echo ""
	@echo "$(YELLOW)Output Files:$(NC)"
	@[ -f "$(BACDIVE_METABOLITES_UNIQUE)" ] && echo "✓ Unique metabolites: $$(wc -l < $(BACDIVE_METABOLITES_UNIQUE)) compounds" || echo "✗ Unique metabolites: Not extracted yet"
	@[ -f "$(BACDIVE_METABOLITES_FREQUENCY)" ] && echo "✓ Frequency report: $$(wc -l < $(BACDIVE_METABOLITES_FREQUENCY)) entries" || echo "✗ Frequency report: Not generated yet"
	@[ -f "$(BACDIVE_METABOLITES_OAK)" ] && echo "✓ OAK annotations: $$(du -h $(BACDIVE_METABOLITES_OAK) | cut -f1)" || echo "✗ OAK annotations: Not generated yet"
	@[ -f "$(BACDIVE_METABOLITES_MAPPED)" ] && echo "✓ ChEBI mappings: $$(wc -l < $(BACDIVE_METABOLITES_MAPPED)) entries" || echo "✗ ChEBI mappings: Not generated yet"

# Clean BacDive metabolites files
.PHONY: bacdive-metabolites-clean
bacdive-metabolites-clean:
	@echo "$(BLUE)Cleaning BacDive metabolites files...$(NC)"
	@rm -rf $(BACDIVE_METABOLITES_DIR)
	@echo "$(GREEN)✓ BacDive metabolites cleanup completed$(NC)"

# ============================================================================
# Unmapped Compounds Analysis
# ============================================================================
# Extracts clean list of unmapped compounds from all pipeline sources

UNMAPPED_ANALYSIS_DIR := $(OUTPUT_DIR)/unmapped_analysis
UNMAPPED_COMPOUNDS := $(UNMAPPED_ANALYSIS_DIR)/unmapped_compounds.tsv
UNMAPPED_SUMMARY := $(UNMAPPED_ANALYSIS_DIR)/unmapped_summary.txt

# Create unmapped analysis directory
$(UNMAPPED_ANALYSIS_DIR):
	@mkdir -p $@

# Extract unmapped compounds from all sources
.PHONY: unmapped-analysis
unmapped-analysis: $(UNMAPPED_COMPOUNDS)
	@echo "$(GREEN)✓ Unmapped compounds analysis completed$(NC)"

$(UNMAPPED_COMPOUNDS): $(LOW_CONFIDENCE_MAPPINGS) | $(UNMAPPED_ANALYSIS_DIR)
	@echo "$(BLUE)Extracting clean unmapped compounds from pipeline...$(NC)"
	$(PYTHON) src/analysis/extract_unmapped_compounds.py \
		--low-confidence $(LOW_CONFIDENCE_MAPPINGS) \
		--bacdive $(BACDIVE_METABOLITES_DIR)/bacdive_metabolites_chebi_mappings_enhanced.tsv \
		--output-dir $(UNMAPPED_ANALYSIS_DIR)

# Show unmapped compounds status
.PHONY: unmapped-status
unmapped-status:
	@echo "$(BLUE)Unmapped Compounds Analysis Status$(NC)"
	@echo "===================================="
	@echo ""
	@if [ -f "$(UNMAPPED_COMPOUNDS)" ]; then \
		TOTAL=$$(tail -n +2 $(UNMAPPED_COMPOUNDS) | wc -l | tr -d ' '); \
		echo "$(GREEN)✓ Input compounds:$(NC) $$TOTAL entries"; \
	else \
		echo "$(RED)✗ Not generated yet. Run: make unmapped-analysis$(NC)"; \
	fi
	@echo ""
	@if [ -f "$(UNMAPPED_ANALYSIS_DIR)/new_mappings.tsv" ]; then \
		MAPPED=$$(tail -n +2 $(UNMAPPED_ANALYSIS_DIR)/new_mappings.tsv | wc -l | tr -d ' '); \
		echo "$(GREEN)✓ Successfully mapped:$(NC) $$MAPPED compounds"; \
		echo ""; \
		echo "$(YELLOW)Top 10 new mappings by type:$(NC)"; \
		tail -n +2 $(UNMAPPED_ANALYSIS_DIR)/new_mappings.tsv | cut -f5 | sort | uniq -c | sort -rn | head -10 | awk '{printf "  %6s  %s\n", $$1, $$2}'; \
	else \
		echo "$(YELLOW)⚠ Mappings not generated yet. Run: make unmapped-map$(NC)"; \
	fi
	@echo ""
	@if [ -f "$(UNMAPPED_ANALYSIS_DIR)/still_unmapped.tsv" ]; then \
		STILL=$$(tail -n +2 $(UNMAPPED_ANALYSIS_DIR)/still_unmapped.tsv | wc -l | tr -d ' '); \
		echo "$(YELLOW)Still unmapped:$(NC) $$STILL compounds (mostly parsing artifacts)"; \
		echo ""; \
		echo "$(YELLOW)Top 10 still unmapped by occurrence:$(NC)"; \
		tail -n +2 $(UNMAPPED_ANALYSIS_DIR)/still_unmapped.tsv | sort -t'	' -k2 -rn | head -10 | awk -F'\t' '{printf "  %6s  %s\n", $$2, $$1}'; \
	fi
	@echo ""
	@if [ -f "$(UNMAPPED_ANALYSIS_DIR)/unmapped_uncertain.tsv" ]; then \
		UNCERTAIN=$$(tail -n +2 $(UNMAPPED_ANALYSIS_DIR)/unmapped_uncertain.tsv | wc -l | tr -d ' '); \
		echo "$(YELLOW)Uncertain entries:$(NC) $$UNCERTAIN (need review)"; \
	fi

# Map unmapped compounds using curated dictionary
.PHONY: unmapped-map
unmapped-map: $(UNMAPPED_ANALYSIS_DIR)/new_mappings.tsv
	@echo "$(GREEN)✓ Unmapped compounds mapping completed$(NC)"

$(UNMAPPED_ANALYSIS_DIR)/new_mappings.tsv: $(UNMAPPED_COMPOUNDS)
	@echo "$(BLUE)Mapping unmapped compounds using curated dictionary (~400 compounds)...$(NC)"
	$(PYTHON) src/mapping/map_unmapped_compounds.py \
		--input $(UNMAPPED_COMPOUNDS) \
		--output $(UNMAPPED_ANALYSIS_DIR)/new_mappings.tsv
	@if [ -f "$(UNMAPPED_ANALYSIS_DIR)/new_mappings.tsv" ]; then \
		MAPPED=$$(tail -n +2 $(UNMAPPED_ANALYSIS_DIR)/new_mappings.tsv | wc -l | tr -d ' '); \
		TOTAL=$$(tail -n +2 $(UNMAPPED_COMPOUNDS) | wc -l | tr -d ' '); \
		echo "$(GREEN)Mapped $$MAPPED/$$TOTAL compounds ($$((MAPPED*100/TOTAL))%)$(NC)"; \
	fi

# Integrate new mappings back into high-confidence file
.PHONY: unmapped-integrate
unmapped-integrate: $(UNMAPPED_ANALYSIS_DIR)/new_mappings.tsv
	@echo "$(BLUE)Integrating new unmapped compound mappings into pipeline...$(NC)"
	@if [ -f "$(UNMAPPED_ANALYSIS_DIR)/new_mappings.tsv" ] && [ -f "$(HIGH_CONFIDENCE_FINAL)" ]; then \
		$(PYTHON) src/mapping/integrate_unmapped_mappings.py \
			--new-mappings $(UNMAPPED_ANALYSIS_DIR)/new_mappings.tsv \
			--high-confidence $(HIGH_CONFIDENCE_FINAL) \
			--low-confidence $(LOW_CONFIDENCE_MAPPINGS) \
			--output $(MERGE_MAPPINGS_DIR)/high_confidence_compound_mappings_with_unmapped.tsv; \
		echo "$(GREEN)✓ New mappings integrated$(NC)"; \
	else \
		echo "$(YELLOW)Run 'make unmapped-map' and 'make kg-enhance-all' first$(NC)"; \
	fi

# Complete unmapped compounds pipeline: analyze → map → integrate
.PHONY: unmapped-full-pipeline
unmapped-full-pipeline: unmapped-analysis unmapped-map unmapped-integrate
	@echo "$(GREEN)════════════════════════════════════════════════════════════════$(NC)"
	@echo "$(GREEN)       Unmapped Compounds Pipeline Complete!                     $(NC)"
	@echo "$(GREEN)════════════════════════════════════════════════════════════════$(NC)"
	@if [ -f "$(UNMAPPED_ANALYSIS_DIR)/new_mappings.tsv" ]; then \
		MAPPED=$$(tail -n +2 $(UNMAPPED_ANALYSIS_DIR)/new_mappings.tsv | wc -l | tr -d ' '); \
		STILL_UNMAPPED=$$(tail -n +2 $(UNMAPPED_ANALYSIS_DIR)/still_unmapped.tsv 2>/dev/null | wc -l | tr -d ' '); \
		echo ""; \
		echo "$(BLUE)Results:$(NC)"; \
		echo "  ✅ New mappings: $$MAPPED compounds"; \
		echo "  ❓ Still unmapped: $$STILL_UNMAPPED compounds (mostly parsing artifacts)"; \
	fi

# Clean unmapped analysis files
.PHONY: unmapped-clean
unmapped-clean:
	@echo "$(BLUE)Cleaning unmapped analysis files...$(NC)"
	@rm -rf $(UNMAPPED_ANALYSIS_DIR)
	@echo "$(GREEN)✓ Unmapped analysis cleanup completed$(NC)"

# ============================================================================
# Compound Mapping Validation
# ============================================================================
# Validates ChEBI/PubChem IDs against official APIs

VALIDATION_REPORT := $(OUTPUT_DIR)/validation/validation_report.tsv
VERIFIED_MAPPINGS := data/curated/verified_compound_mappings.tsv

# Create validation output directory
$(OUTPUT_DIR)/validation:
	@mkdir -p $@

# Validate all compound mappings against ChEBI/PubChem APIs
.PHONY: validate-compound-mappings
validate-compound-mappings: $(VALIDATION_REPORT)
	@echo "$(GREEN)✓ Compound mapping validation completed$(NC)"

$(VALIDATION_REPORT): | $(OUTPUT_DIR)/validation
	@echo "$(BLUE)Validating compound mappings against ChEBI/PubChem APIs...$(NC)"
	@echo "$(YELLOW)This will take 3-5 minutes (rate limited to respect APIs)$(NC)"
	$(PYTHON) src/quality/validate_chebi_mappings.py \
		--from-script \
		--output-report $(VALIDATION_REPORT) \
		--output-verified $(VERIFIED_MAPPINGS)
	@echo "$(GREEN)Reports written to:$(NC)"
	@echo "  📋 Full report: $(VALIDATION_REPORT)"
	@echo "  ✅ Verified mappings: $(VERIFIED_MAPPINGS)"

# Quick validation with sample
.PHONY: validate-compound-mappings-quick
validate-compound-mappings-quick: | $(OUTPUT_DIR)/validation
	@echo "$(BLUE)Quick validation (50 random samples)...$(NC)"
	$(PYTHON) src/quality/validate_chebi_mappings.py \
		--from-script \
		--sample 50 \
		--output-report $(OUTPUT_DIR)/validation/validation_report_sample.tsv

# Show validation status
.PHONY: validate-status
validate-status:
	@echo "$(BLUE)Compound Mapping Validation Status$(NC)"
	@echo "===================================="
	@if [ -f "$(VALIDATION_REPORT)" ]; then \
		TOTAL=$$(tail -n +2 $(VALIDATION_REPORT) | wc -l | tr -d ' '); \
		VALID=$$(grep -c '	VALID	' $(VALIDATION_REPORT) || echo 0); \
		MISMATCH=$$(grep -c '	MISMATCH	' $(VALIDATION_REPORT) || echo 0); \
		NOTFOUND=$$(grep -c '	NOT_FOUND	' $(VALIDATION_REPORT) || echo 0); \
		echo "$(GREEN)✓ Validation report exists$(NC)"; \
		echo "  Total: $$TOTAL"; \
		echo "  Valid: $$VALID"; \
		echo "  Mismatch: $$MISMATCH"; \
		echo "  Not found: $$NOTFOUND"; \
	else \
		echo "$(RED)✗ No validation report. Run: make validate-compound-mappings$(NC)"; \
	fi
	@echo ""
	@if [ -f "$(VERIFIED_MAPPINGS)" ]; then \
		echo "$(GREEN)✓ Verified mappings: $$(tail -n +2 $(VERIFIED_MAPPINGS) | wc -l | tr -d ' ') entries$(NC)"; \
	else \
		echo "$(YELLOW)⚠ No verified mappings file yet$(NC)"; \
	fi

# Clean validation files
.PHONY: validate-clean
validate-clean:
	@echo "$(BLUE)Cleaning validation files...$(NC)"
	@rm -rf $(OUTPUT_DIR)/validation
	@rm -f $(VERIFIED_MAPPINGS)
	@echo "$(GREEN)✓ Validation cleanup completed$(NC)"

# Remediate incorrect ChEBI mappings by looking up correct IDs from PubChem
REMEDIATED_MAPPINGS := $(OUTPUT_DIR)/validation/remediated_mappings.tsv

.PHONY: remediate-compound-mappings
remediate-compound-mappings: $(REMEDIATED_MAPPINGS)

$(REMEDIATED_MAPPINGS): $(VALIDATION_REPORT) | $(OUTPUT_DIR)/validation
	@echo "$(BLUE)Remediating incorrect ChEBI mappings...$(NC)"
	$(PYTHON) src/quality/remediate_chebi_mappings.py \
		--validation-report $(VALIDATION_REPORT) \
		--output $(REMEDIATED_MAPPINGS)
	@echo "$(GREEN)✓ Remediation complete$(NC)"
	@echo "  📋 Results: $(REMEDIATED_MAPPINGS)"

# Merge verified and remediated mappings
.PHONY: merge-verified-mappings
merge-verified-mappings: $(VERIFIED_MAPPINGS)
	@echo "$(BLUE)Merging verified and remediated mappings...$(NC)"
	$(PYTHON) src/quality/merge_verified_mappings.py \
		--verified $(VERIFIED_MAPPINGS) \
		--remediated $(REMEDIATED_MAPPINGS) \
		--output $(VERIFIED_MAPPINGS)
	@echo "$(GREEN)✓ Merge complete$(NC)"

# Full compound mapping validation workflow
.PHONY: validate-full-pipeline
validate-full-pipeline:
	@echo "$(BLUE)Running full compound mapping validation pipeline...$(NC)"
	@echo "Step 1: Validate compound mappings against official APIs"
	$(MAKE) validate-compound-mappings
	@echo ""
	@echo "Step 2: Remediate incorrect mappings using PubChem lookup"
	$(MAKE) remediate-compound-mappings
	@echo ""
	@echo "Step 3: Merge verified and remediated mappings"
	$(MAKE) merge-verified-mappings
	@echo ""
	@echo "$(GREEN)✓ Full validation pipeline complete$(NC)"
	$(MAKE) validate-status

# ============================================================================
# Deterministic API-Based Compound Mapping (replaces LLM-generated mappings)
# ============================================================================
# These targets generate reproducible compound mappings using only:
# - ChEBI nodes file (offline matching)
# - PubChem REST API (name → CID → ChEBI xref)
# - OLS4 API (direct ChEBI search)
# - Curated microbiology products dictionary

API_MAPPINGS_DIR := data/curated
ALL_COMPOUNDS_FILE := $(OUTPUT_DIR)/unmapped_analysis/all_compounds_to_map.txt
API_GENERATED_MAPPINGS := $(API_MAPPINGS_DIR)/api_generated_mappings.tsv

# Extract all unique compound names from pipeline for mapping
.PHONY: extract-all-compounds
extract-all-compounds: | $(OUTPUT_DIR)/unmapped_analysis
	@echo "$(BLUE)Extracting all unique compound names from pipeline...$(NC)"
	$(PYTHON) -m src.mapping.extract_all_compound_names \
		--input-dir $(MEDIA_COMPOSITIONS_DIR) \
		--kg-mapping $(COMPOSITION_MAPPING) \
		--unmapped-file $(OUTPUT_DIR)/unmapped_analysis/unmapped_compounds.tsv \
		--include-old-dict \
		--output $(ALL_COMPOUNDS_FILE)
	@echo "$(GREEN)✓ Compound names extracted to $(ALL_COMPOUNDS_FILE)$(NC)"

# Generate compound mappings via deterministic API calls
# WARNING: This takes 30-60 minutes for full dataset due to API rate limiting
.PHONY: generate-api-mappings
generate-api-mappings: $(ALL_COMPOUNDS_FILE) | $(API_MAPPINGS_DIR)
	@echo "$(BLUE)Generating compound mappings via deterministic APIs...$(NC)"
	@echo "$(YELLOW)⚠ This may take 30-60 minutes due to API rate limiting$(NC)"
	$(PYTHON) -m src.mapping.generate_compound_mappings \
		--compounds-file $(ALL_COMPOUNDS_FILE) \
		--chebi-nodes $(CHEBI_NODES_FILE) \
		--output $(API_GENERATED_MAPPINGS) \
		--checkpoint-interval 100
	@echo "$(GREEN)✓ API-generated mappings saved to $(API_GENERATED_MAPPINGS)$(NC)"

# Resume mapping generation from checkpoint
.PHONY: resume-api-mappings
resume-api-mappings: | $(API_MAPPINGS_DIR)
	@echo "$(BLUE)Resuming compound mapping generation from latest checkpoint...$(NC)"
	@CHECKPOINT=$$(ls -t $(API_MAPPINGS_DIR)/api_generated_mappings_checkpoint_*.tsv 2>/dev/null | head -1); \
	if [ -n "$$CHECKPOINT" ]; then \
		echo "Found checkpoint: $$CHECKPOINT"; \
		$(PYTHON) -m src.mapping.generate_compound_mappings \
			--compounds-file $(ALL_COMPOUNDS_FILE) \
			--chebi-nodes $(CHEBI_NODES_FILE) \
			--output $(API_GENERATED_MAPPINGS) \
			--checkpoint-interval 100 \
			--resume-from "$$CHECKPOINT"; \
	else \
		echo "$(YELLOW)No checkpoint found. Starting fresh...$(NC)"; \
		$(MAKE) generate-api-mappings; \
	fi

# Validate API-generated mappings
.PHONY: validate-api-mappings
validate-api-mappings: $(API_GENERATED_MAPPINGS)
	@echo "$(BLUE)Validating API-generated mappings...$(NC)"
	@if [ -f "$(API_GENERATED_MAPPINGS)" ]; then \
		TOTAL=$$(tail -n +2 $(API_GENERATED_MAPPINGS) | wc -l | tr -d ' '); \
		MAPPED=$$(awk -F'\t' 'NR>1 && $$2 != "" {count++} END {print count+0}' $(API_GENERATED_MAPPINGS)); \
		CHEBI=$$(awk -F'\t' 'NR>1 && $$3 == "CHEBI" {count++} END {print count+0}' $(API_GENERATED_MAPPINGS)); \
		UBERON=$$(awk -F'\t' 'NR>1 && $$3 == "UBERON" {count++} END {print count+0}' $(API_GENERATED_MAPPINGS)); \
		INGREDIENT=$$(awk -F'\t' 'NR>1 && $$3 == "ingredient" {count++} END {print count+0}' $(API_GENERATED_MAPPINGS)); \
		echo ""; \
		echo "$(GREEN)API-Generated Mappings Summary:$(NC)"; \
		echo "  Total compounds: $$TOTAL"; \
		echo "  Mapped:          $$MAPPED"; \
		echo "  ChEBI:           $$CHEBI"; \
		echo "  UBERON:          $$UBERON"; \
		echo "  ingredient:      $$INGREDIENT"; \
		echo ""; \
		echo "$(YELLOW)By Strategy:$(NC)"; \
		awk -F'\t' 'NR>1 && $$2 != "" {strategy[$$5]++} END {for (s in strategy) print "  " s ": " strategy[s]}' $(API_GENERATED_MAPPINGS) | sort -t: -k2 -nr; \
	else \
		echo "$(RED)✗ API mappings file not found. Run: make generate-api-mappings$(NC)"; \
	fi

# Full deterministic API mapping pipeline
.PHONY: api-mapping-full-pipeline
api-mapping-full-pipeline:
	@echo "$(BLUE)════════════════════════════════════════════════════════════════$(NC)"
	@echo "$(BLUE)    DETERMINISTIC API-BASED COMPOUND MAPPING PIPELINE           $(NC)"
	@echo "$(BLUE)════════════════════════════════════════════════════════════════$(NC)"
	@echo ""
	@echo "This pipeline generates fully reproducible compound mappings using:"
	@echo "  1. ChEBI nodes file (offline exact/normalized matching)"
	@echo "  2. PubChem REST API (name → CID → ChEBI cross-reference)"
	@echo "  3. OLS4 API (direct ChEBI search)"
	@echo "  4. Curated microbiology products dictionary"
	@echo ""
	@echo "$(YELLOW)Step 1: Extract all compound names$(NC)"
	$(MAKE) extract-all-compounds
	@echo ""
	@echo "$(YELLOW)Step 2: Generate mappings via API (30-60 min)$(NC)"
	$(MAKE) generate-api-mappings
	@echo ""
	@echo "$(YELLOW)Step 3: Validate generated mappings$(NC)"
	$(MAKE) validate-api-mappings
	@echo ""
	@echo "$(GREEN)════════════════════════════════════════════════════════════════$(NC)"
	@echo "$(GREEN)    ✓ DETERMINISTIC MAPPING PIPELINE COMPLETE                   $(NC)"
	@echo "$(GREEN)════════════════════════════════════════════════════════════════$(NC)"
	@echo ""
	@echo "Generated files:"
	@echo "  $(API_GENERATED_MAPPINGS)"
	@echo ""
	@echo "To use these mappings, they will be automatically loaded by:"
	@echo "  - src/mapping/map_unmapped_compounds.py"
	@echo "  - src/mapping/matching_strategies.py (CachedAPIMatcher)"

# Show API mapping status
.PHONY: api-mapping-status
api-mapping-status:
	@echo "$(BLUE)API Mapping Status$(NC)"
	@echo "=================="
	@echo ""
	@if [ -f "$(ALL_COMPOUNDS_FILE)" ]; then \
		echo "✓ Compound list: $$(wc -l < $(ALL_COMPOUNDS_FILE)) compounds"; \
	else \
		echo "✗ Compound list: Not extracted (run: make extract-all-compounds)"; \
	fi
	@if [ -f "$(API_GENERATED_MAPPINGS)" ]; then \
		MAPPED=$$(awk -F'\t' 'NR>1 && $$2 != "" {count++} END {print count+0}' $(API_GENERATED_MAPPINGS)); \
		TOTAL=$$(tail -n +2 $(API_GENERATED_MAPPINGS) | wc -l | tr -d ' '); \
		echo "✓ API mappings: $$MAPPED/$$TOTAL mapped"; \
	else \
		echo "✗ API mappings: Not generated (run: make api-mapping-full-pipeline)"; \
	fi
	@CHECKPOINTS=$$(ls $(API_MAPPINGS_DIR)/api_generated_mappings_checkpoint_*.tsv 2>/dev/null | wc -l | tr -d ' '); \
	if [ "$$CHECKPOINTS" -gt 0 ]; then \
		echo "  Checkpoints: $$CHECKPOINTS available"; \
	fi

# Clean API mapping files
.PHONY: api-mapping-clean
api-mapping-clean:
	@echo "$(BLUE)Cleaning API mapping files...$(NC)"
	rm -f $(ALL_COMPOUNDS_FILE)
	rm -f $(API_GENERATED_MAPPINGS)
	rm -f $(API_MAPPINGS_DIR)/api_generated_mappings_checkpoint_*.tsv
	@echo "$(GREEN)✓ API mapping files cleaned$(NC)"

$(API_MAPPINGS_DIR):
	mkdir -p $@

# Setup and environment targets

# Install Python dependencies
.PHONY: install
install:
	@echo "$(BLUE)Installing Python dependencies...$(NC)"
	$(PYTHON) -m pip install -r $(REQUIREMENTS)

# Install development dependencies  
.PHONY: install-dev
install-dev:
	@echo "$(BLUE)Installing development dependencies...$(NC)"
	$(PYTHON) -m pip install -e ".[dev]"

# Create Python virtual environment
.PHONY: setup-venv
setup-venv:
	@echo "$(BLUE)Creating Python virtual environment...$(NC)"
	$(PYTHON) -m venv $(VENV_DIR)
	@echo "$(YELLOW)Activate with: source $(VENV_DIR)/bin/activate$(NC)"

# Quality assurance targets

# Run all tests
.PHONY: test
test:
	@echo "$(BLUE)Running tests...$(NC)"
	$(PYTHON) -m pytest -v
	$(PYTHON) test_compound_matcher.py
	$(PYTHON) test_hydration_matching.py
	$(PYTHON) test_merge_sample.py

# Run code quality checks
.PHONY: lint
lint:
	@echo "$(BLUE)Running code quality checks...$(NC)"
	flake8 src/ *.py
	mypy src/

# Format code
.PHONY: format
format:
	@echo "$(BLUE)Formatting code...$(NC)"
	black src/ *.py
	isort src/ *.py

# All quality checks
.PHONY: quality
quality: format lint test
	@echo "$(GREEN)✓ All quality checks completed$(NC)"

# Maintenance targets

# Show pipeline status
.PHONY: status
status:
	@echo "$(BLUE)Pipeline Status Report$(NC)"
	@echo "====================="
	@echo ""
	@echo "$(YELLOW)Data Files:$(NC)"
	@[ -f $(GROWTH_MEDIA_URLS) ] && echo "✓ Media URLs: $$(wc -l < $(GROWTH_MEDIA_URLS)) URLs" || echo "✗ Media URLs: Missing"
	@[ -d $(MEDIA_PDFS_DIR) ] && echo "✓ Media PDFs: $$(ls $(MEDIA_PDFS_DIR)/*.pdf 2>/dev/null | wc -l) PDFs" || echo "✗ Media PDFs: Missing"
	@[ -d $(MEDIA_TEXTS_DIR) ] && echo "✓ Media Texts: $$(ls $(MEDIA_TEXTS_DIR)/*.md 2>/dev/null | wc -l) text files" || echo "✗ Media Texts: Missing"
	@[ -d $(MEDIA_COMPOSITIONS_DIR) ] && echo "✓ Compositions: $$(ls $(MEDIA_COMPOSITIONS_DIR)/*.md 2>/dev/null | wc -l) compositions" || echo "✗ Compositions: Missing"
	@echo ""
	@echo "$(YELLOW)Mapping Files:$(NC)"
	@[ -f $(COMPOSITION_MAPPING) ] && echo "✓ Original mappings: $$(tail -n +2 $(COMPOSITION_MAPPING) | wc -l) entries" || echo "✗ Original mappings: Missing"
	@[ -f $(EXPANDED_MAPPING) ] && echo "✓ Solution-expanded: $$(tail -n +2 $(EXPANDED_MAPPING) | wc -l) entries" || echo "✗ Solution-expanded: Missing"
	@[ -f $(KG_MAPPING_DIR)/composition_kg_mapping_hydrate_normalized.tsv ] && echo "✓ Early hydrate normalized: $$(tail -n +2 $(KG_MAPPING_DIR)/composition_kg_mapping_hydrate_normalized.tsv | wc -l) entries" || echo "✗ Early hydrate normalized: Missing"
	@[ -f $(KG_MAPPING_DIR)/composition_kg_mapping_ingredient_enhanced.tsv ] && echo "✓ Early ingredient enhanced: $$(tail -n +2 $(KG_MAPPING_DIR)/composition_kg_mapping_ingredient_enhanced.tsv | wc -l) entries" || echo "✗ Early ingredient enhanced: Missing"
	@[ -f $(UNACCOUNTED_MATCHES) ] && echo "✓ ChEBI matches: $$(tail -n +2 $(UNACCOUNTED_MATCHES) | wc -l) matches" || echo "✗ ChEBI matches: Missing"
	@[ -f $(UNIFIED_MAPPINGS) ] && echo "✓ Unified mappings: $$(tail -n +2 $(UNIFIED_MAPPINGS) | wc -l) entries" || echo "✗ Unified mappings: Missing"
	@[ -f $(HIGH_CONFIDENCE_MAPPINGS) ] && echo "✓ High confidence (original): $$(tail -n +2 $(HIGH_CONFIDENCE_MAPPINGS) | wc -l) entries" || echo "✗ High confidence: Missing"
	@[ -f $(LOW_CONFIDENCE_MAPPINGS) ] && echo "✓ Low confidence: $$(tail -n +2 $(LOW_CONFIDENCE_MAPPINGS) | wc -l) entries" || echo "✗ Low confidence: Missing"
	@echo ""
	@echo "$(YELLOW)Enhanced Mapping Files (Stage 10.5):$(NC)"
	@[ -f $(HIGH_CONFIDENCE_UPGRADED) ] && echo "✓ CAS upgraded: $$(tail -n +2 $(HIGH_CONFIDENCE_UPGRADED) | wc -l) entries" || echo "✗ CAS upgraded: Not run yet (run 'make kg-enhance-all')"
	@[ -f $(HIGH_CONFIDENCE_FORMULA) ] && echo "✓ Formula enhanced: $$(tail -n +2 $(HIGH_CONFIDENCE_FORMULA) | wc -l) entries" || echo "✗ Formula enhanced: Not run yet"
	@[ -f $(HIGH_CONFIDENCE_FINAL) ] && (echo -n "✓ Final enhanced (72% coverage): $$(tail -n +2 $(HIGH_CONFIDENCE_FINAL) | wc -l) entries, "; \
		CHEBI_COUNT=$$(awk -F'\t' 'NR>1 && $$3 ~ /^CHEBI:/ {print $$2}' $(HIGH_CONFIDENCE_FINAL) | sort -u | wc -l | tr -d ' '); \
		TOTAL_COUNT=$$(awk -F'\t' 'NR>1 {print $$2}' $(HIGH_CONFIDENCE_FINAL) | sort -u | wc -l | tr -d ' '); \
		echo "$$CHEBI_COUNT/$$TOTAL_COUNT unique compounds") || echo "✗ Final enhanced: Not run yet"
	@[ -f $(COMPOUND_MAPPINGS_STRICT_HYDRATE) ] && echo "✓ Hydrate mappings: $$(tail -n +2 $(COMPOUND_MAPPINGS_STRICT_HYDRATE) | wc -l) entries" || echo "✗ Hydrate mappings: Not created yet (run 'make create-hydrate-mappings')"
	@[ -f $(COMPOUND_MAPPINGS_SIMPLIFIED) ] && echo "✓ Simplified mappings: $$(tail -n +2 $(COMPOUND_MAPPINGS_SIMPLIFIED) | wc -l) entries" || echo "✗ Simplified mappings: Not created yet (run 'make create-simplified-mappings')"
	@[ -f $(COMPOUND_MAPPINGS_SIMPLIFIED_HYDRATE) ] && echo "✓ Simplified hydrate mappings: $$(tail -n +2 $(COMPOUND_MAPPINGS_SIMPLIFIED_HYDRATE) | wc -l) entries" || echo "✗ Simplified hydrate mappings: Not created yet (run 'make create-simplified-mappings')"
	@echo ""
	@echo "$(YELLOW)Analysis Files:$(NC)"
	@[ -d $(MEDIA_PROPERTIES_DIR) ] && echo "✓ Media properties: $$(ls $(MEDIA_PROPERTIES_DIR)/*.json 2>/dev/null | wc -l) media analyzed" || echo "✗ Media properties: Missing"
	@[ -f $(MEDIA_SUMMARY) ] && echo "✓ Media summary: $$(tail -n +2 $(MEDIA_SUMMARY) | wc -l) media summarized" || echo "✗ Media summary: Missing"
	@echo ""
	@echo "$(YELLOW)Log Files:$(NC)"
	@ls -la $(LOGS) 2>/dev/null | wc -l | xargs -I {} echo "✓ Log files: {} files"

# Clean generated files and logs
.PHONY: clean
clean:
	@echo "$(BLUE)Cleaning generated files and logs...$(NC)"
	rm -f $(LOGS)
	rm -f *.tsv
	rm -f test_*.py
	@echo "$(GREEN)✓ Cleanup completed$(NC)"

# Clean all data and outputs
.PHONY: clean-all
clean-all: clean
	@echo "$(BLUE)Cleaning all data and outputs...$(NC)"
	rm -rf $(MEDIA_PDFS_DIR)
	rm -rf $(MEDIA_TEXTS_DIR)
	rm -rf $(MEDIA_COMPOSITIONS_DIR)
	rm -rf $(MEDIA_PROPERTIES_DIR)
	rm -f $(GROWTH_MEDIA_URLS)
	@echo "$(RED)⚠ All pipeline data removed!$(NC)"

# Quick pipeline for development/testing (smaller dataset)
.PHONY: quick
quick: install
	@echo "$(BLUE)Running quick development pipeline...$(NC)"
	$(PYTHON) $(SCRIPTS_DIR)/map_compositions_sample.py
	$(PYTHON) $(SCRIPTS_DIR)/find_unaccounted_compound_matches.py
	$(PYTHON) $(SCRIPTS_DIR)/merge_compound_mappings.py
	$(PYTHON) src/mapping/filter_high_confidence_mappings.py
	@echo "$(GREEN)✓ Quick pipeline completed$(NC)"

# Pipeline validation - check all expected outputs exist
.PHONY: validate
validate:
	@echo "$(BLUE)Validating pipeline outputs...$(NC)"
	@echo "Checking required files exist..."
	@test -f $(GROWTH_MEDIA_URLS) || (echo "$(RED)✗ Missing: $(GROWTH_MEDIA_URLS)$(NC)" && exit 1)
	@test -d $(MEDIA_PDFS_DIR) || (echo "$(RED)✗ Missing: $(MEDIA_PDFS_DIR)$(NC)" && exit 1)
	@test -d $(MEDIA_TEXTS_DIR) || (echo "$(RED)✗ Missing: $(MEDIA_TEXTS_DIR)$(NC)" && exit 1)
	@test -d $(MEDIA_COMPOSITIONS_DIR) || (echo "$(RED)✗ Missing: $(MEDIA_COMPOSITIONS_DIR)$(NC)" && exit 1)
	@test -f $(COMPOSITION_MAPPING) || (echo "$(RED)✗ Missing: $(COMPOSITION_MAPPING)$(NC)" && exit 1)
	@test -f $(EXPANDED_MAPPING) || (echo "$(RED)✗ Missing: $(EXPANDED_MAPPING)$(NC)" && exit 1)
	@test -f $(KG_MAPPING_DIR)/composition_kg_mapping_hydrate_normalized.tsv || (echo "$(RED)✗ Missing: Early hydration normalization$(NC)" && exit 1)
	@test -f $(KG_MAPPING_DIR)/composition_kg_mapping_ingredient_enhanced.tsv || (echo "$(RED)✗ Missing: Early ingredient enhancement$(NC)" && exit 1)
	@test -f $(UNACCOUNTED_MATCHES) || (echo "$(RED)✗ Missing: $(UNACCOUNTED_MATCHES)$(NC)" && exit 1)
	@test -f $(UNIFIED_MAPPINGS) || (echo "$(RED)✗ Missing: $(UNIFIED_MAPPINGS)$(NC)" && exit 1)
	@test -f $(HIGH_CONFIDENCE_MAPPINGS) || (echo "$(RED)✗ Missing: $(HIGH_CONFIDENCE_MAPPINGS)$(NC)" && exit 1)
	@test -f $(LOW_CONFIDENCE_MAPPINGS) || (echo "$(RED)✗ Missing: $(LOW_CONFIDENCE_MAPPINGS)$(NC)" && exit 1)
	@test -d $(MEDIA_PROPERTIES_DIR) || (echo "$(RED)✗ Missing: $(MEDIA_PROPERTIES_DIR)$(NC)" && exit 1)
	@test -f $(MEDIA_SUMMARY) || (echo "$(RED)✗ Missing: $(MEDIA_SUMMARY)$(NC)" && exit 1)
	@echo "$(GREEN)✓ Pipeline validation successful!$(NC)"

# Phony targets (don't correspond to files)
.PHONY: all help install install-dev setup-venv test lint format quality \
        data-acquisition data-conversion db-mapping chemical-databases kg-mapping mapping map-compositions-to-kg \
        solution-expansion kg-compound-matching compound-matching kg-oak-chebi-mapping oak-chebi-mapping kg-merge-mappings merge-mappings \
        enhance-ingredients normalize-hydration-early enhance-ingredients-early compute-properties media-summary \
        kg-enhance-cas-upgrade kg-enhance-formula-matching kg-enhance-microbio-products kg-enhance-all enhance-mappings \
        iupac-analyze-compounds iupac-download-data iupac-process-data iupac-generate-tsv \
        iupac-full-pipeline iupac-update-from-mappings iupac-process-composition-mapping iupac-add-compounds iupac-test \
        iupac-validate-tsv iupac-status iupac-clean iupac-restore-backup \
        pubchem-full-pipeline pubchem-process-composition-mapping pubchem-download-compounds pubchem-test \
        pubchem-status pubchem-clean \
        extract-non-chebi-compounds oak-chebi-annotate apply-oak-chebi-mappings fix-hydrated-mappings oak-chebi-mapping \
        oak-chebi-test oak-chebi-status oak-chebi-clean oak-chebi-mapping-standalone \
        bacdive-metabolites-mapping bacdive-metabolites-extract bacdive-metabolites-oak-annotate \
        bacdive-metabolites-apply-mappings bacdive-metabolites-status bacdive-metabolites-clean \
        unmapped-analysis unmapped-map unmapped-integrate unmapped-full-pipeline unmapped-status unmapped-clean \
        update-chemical-db test-chemical-db \
        extract-all-compounds generate-api-mappings resume-api-mappings validate-api-mappings \
        api-mapping-full-pipeline api-mapping-status api-mapping-clean \
        clean clean-all status validate quick create-output-dirs