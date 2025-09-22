# MicroMediaParam Pipeline Makefile
# 
# This Makefile reproduces the complete bioinformatics pipeline for processing
# microbial growth media composition data, from PDF downloads to final analysis.
#
# Pipeline stages:
# 1. Data acquisition (parse URLs, download PDFs/JSON)
# 2. Data conversion (PDFs to text, JSON to markdown)
# 3. Knowledge graph mapping (compounds to ChEBI/KEGG/PubChem)
# 4. Compound matching and merging
# 5. Hydration normalization and deduplication
# 6. Property calculation (pH, salinity, ionic strength)
# 7. Final media summary generation

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
UNACCOUNTED_MATCHES := $(COMPOUND_MATCHING_DIR)/unaccounted_compound_matches.tsv
UNIFIED_MAPPINGS := $(MERGE_MAPPINGS_DIR)/unified_compound_mappings.tsv
HIGH_CONFIDENCE_MAPPINGS := $(MERGE_MAPPINGS_DIR)/high_confidence_compound_mappings.tsv
LOW_CONFIDENCE_MAPPINGS := $(MERGE_MAPPINGS_DIR)/low_confidence_compound_mappings.tsv
INGREDIENT_ENHANCED_HIGH := $(INGREDIENT_ENHANCEMENT_DIR)/high_confidence_compound_mappings_ingredient_enhanced.tsv
INGREDIENT_ENHANCED_LOW := $(INGREDIENT_ENHANCEMENT_DIR)/low_confidence_compound_mappings_ingredient_enhanced.tsv
HIGH_CONFIDENCE_NORMALIZED := $(HYDRATE_NORMALIZATION_DIR)/high_confidence_compound_mappings_normalized.tsv
LOW_CONFIDENCE_NORMALIZED := $(HYDRATE_NORMALIZATION_DIR)/low_confidence_compound_mappings_normalized.tsv
MEDIA_SUMMARY := $(MEDIA_SUMMARY_DIR)/media_summary.tsv
CHEMICAL_PROPERTIES := $(DB_MAPPING_DIR)/chemical_properties.tsv

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
	@echo "  $(YELLOW)normalize-hydration-early$(NC)   - Step 5: 🔥 EARLY hydrate normalization for consistent base compounds"
	@echo "  $(YELLOW)enhance-ingredients-early$(NC)   - Step 6: 🔥 EARLY ingredient: → ChEBI matching with normalized compounds"
	@echo "  $(YELLOW)kg-compound-matching$(NC)        - Step 7: Enhanced compound matching using normalized base compounds"
	@echo "  $(YELLOW)kg-oak-chebi-mapping$(NC)        - Step 8: OAK CHEBI annotations with improved compound set"
	@echo "  $(YELLOW)kg-merge-mappings$(NC)           - Step 9: Merge all mapping sources with consistent hydration"
	@echo "  $(YELLOW)compute-properties$(NC)          - Step 10: Calculate pH, salinity with hydration-corrected MW"
	@echo "  $(YELLOW)media-summary$(NC)               - Step 11: Generate final media summary table"
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
all: install data-acquisition data-conversion db-mapping kg-mapping-initial normalize-hydration-early enhance-ingredients-early kg-compound-matching kg-oak-chebi-mapping kg-merge-mappings compute-properties media-summary
	@echo "$(GREEN)✓ Complete pipeline finished successfully!$(NC)"

# Create output directories
.PHONY: create-output-dirs
create-output-dirs:
	@mkdir -p $(DATA_ACQUISITION_DIR) $(DATA_CONVERSION_DIR) $(DB_MAPPING_DIR) $(KG_MAPPING_DIR) 
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

# Extract ALL compositions using comprehensive ingredient extraction
$(MEDIA_COMPOSITIONS_DIR)/.done: $(MEDIA_TEXTS_DIR)/.done
	@echo "$(BLUE)Extracting ALL chemical compositions using comprehensive multi-strategy approach...$(NC)"
	@echo "$(YELLOW)Goal: Capture ALL ingredients from media files using multiple extraction strategies$(NC)"
	$(PYTHON) extract_all_compositions.py
	@mkdir -p $(MEDIA_COMPOSITIONS_DIR) && touch $(MEDIA_COMPOSITIONS_DIR)/.done

# Stage 3: DB Mapping - Download IUPAC/PubChem & Build Chemical Properties Database (ingredient → pKa, properties)
.PHONY: db-mapping chemical-databases
db-mapping chemical-databases: $(CHEMICAL_PROPERTIES)
	@echo "$(GREEN)✓ DB mapping completed: IUPAC/PubChem downloaded, ingredient → chemical properties$(NC)"

# Download chemical data from IUPAC and PubChem sources and build properties database (maximize ingredients with pKa values)
$(CHEMICAL_PROPERTIES): $(MEDIA_COMPOSITIONS_DIR)/.done
	@echo "$(BLUE)DB Mapping: Building ingredient → chemical properties database...$(NC)"
	@echo "$(YELLOW)Goal: Maximize ingredients with pKa and molecular properties$(NC)"
	@echo "$(YELLOW)Phase 1: DOWNLOADING IUPAC chemical data (test compounds + processing)...$(NC)"
	$(PYTHON) -m src.chem.iupac.pipeline --download-compounds "glucose,sodium chloride,glycine,citric acid,potassium phosphate" --data-dir $(IUPAC_DATA_DIR) || echo "$(YELLOW)IUPAC download/processing completed with warnings$(NC)"
	@echo "$(YELLOW)Phase 2: DOWNLOADING PubChem chemical data (5 reference compounds)...$(NC)"
	$(PYTHON) -m src.chem.pubchem.pipeline --download-compounds "glucose,sodium chloride,glycine,citric acid,potassium phosphate" --data-dir $(PUBCHEM_DATA_DIR) || echo "$(YELLOW)PubChem download/processing completed with warnings$(NC)"
	@echo "$(YELLOW)Phase 3: Generating unified chemical properties database from downloaded data...$(NC)"
	@if [ ! -f "$(CHEMICAL_PROPERTIES)" ]; then \
		echo "Creating initial chemical_properties.tsv from IUPAC data..."; \
		$(PYTHON) -c "import sys; sys.path.insert(0, 'src'); from chem.iupac.tsv_generator import ChemicalPropertiesTSVGenerator; from pathlib import Path; generator = ChemicalPropertiesTSVGenerator(); processed_file = Path('$(IUPAC_PROCESSED_DATA)'); output_file = Path('$(CHEMICAL_PROPERTIES)'); generator.generate_tsv_from_json(processed_file, output_file, merge_with_existing=True) if processed_file.exists() else print('No IUPAC processed data found')"; \
	fi
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

# Stage 5: EARLY Hydration Normalization - Fix hydrate inconsistencies BEFORE advanced matching
.PHONY: normalize-hydration-early
normalize-hydration-early: $(KG_MAPPING_DIR)/composition_kg_mapping_hydrate_normalized.tsv
	@echo "$(GREEN)✓ EARLY hydration normalization completed: consistent base compounds for all downstream steps$(NC)"

# Apply enhanced hydrate normalization to initial KG mapping (critical optimization)
$(KG_MAPPING_DIR)/composition_kg_mapping_hydrate_normalized.tsv: $(COMPOSITION_MAPPING)
	@echo "$(BLUE)🔥 EARLY Hydration Normalization: Fixing hydrate inconsistencies BEFORE advanced matching...$(NC)"
	@echo "$(YELLOW)CRITICAL: This normalizes CaCl2 x 2 H2O & CaCl2 x 6 H2O → same base ChEBI but correct MW$(NC)"
	$(PYTHON) normalize_hydration_enhanced.py --input-high $(COMPOSITION_MAPPING) --output-suffix _hydrate_normalized

# Stage 6: EARLY Ingredient Enhancement - Convert ingredient: codes AFTER hydrate normalization
.PHONY: enhance-ingredients-early
enhance-ingredients-early: $(KG_MAPPING_DIR)/composition_kg_mapping_ingredient_enhanced.tsv
	@echo "$(GREEN)✓ EARLY ingredient enhancement completed: ingredient: codes → ChEBI IDs with normalized compounds$(NC)"

# Apply ingredient enhancement to hydrate-normalized mapping (uses better base compounds)
$(KG_MAPPING_DIR)/composition_kg_mapping_ingredient_enhanced.tsv: $(KG_MAPPING_DIR)/composition_kg_mapping_hydrate_normalized.tsv
	@echo "$(BLUE)🔥 EARLY Ingredient Enhancement: Converting ingredient: codes using normalized compounds...$(NC)"
	@echo "$(YELLOW)ADVANTAGE: Works with hydrate-corrected base compounds for better ChEBI matching$(NC)"
	$(PYTHON) enhance_ingredient_matching.py --input-high $(KG_MAPPING_DIR)/composition_kg_mapping_hydrate_normalized.tsv --output-suffix _ingredient_enhanced
	@mv $(KG_MAPPING_DIR)/composition_kg_mapping_hydrate_normalized_ingredient_enhanced.tsv $(KG_MAPPING_DIR)/composition_kg_mapping_ingredient_enhanced.tsv

# Stage 7: Enhanced KG Compound Matching - Uses normalized base compounds for better matching
.PHONY: kg-compound-matching compound-matching
kg-compound-matching compound-matching: $(UNACCOUNTED_MATCHES)
	@echo "$(GREEN)✓ Enhanced KG compound matching completed: additional ChEBI matches using normalized compounds$(NC)"

# Find ChEBI matches for ingredients using enhanced composition mapping (better base compounds)
$(UNACCOUNTED_MATCHES): $(KG_MAPPING_DIR)/composition_kg_mapping_ingredient_enhanced.tsv
	@echo "$(BLUE)Enhanced KG Compound Matching: Finding ChEBI matches using normalized/enhanced compounds...$(NC)"
	@echo "$(YELLOW)ADVANTAGE: Uses hydrate-normalized + ingredient-enhanced compounds for better matching$(NC)"
	@echo "$(YELLOW)Note: Using enhanced composition mapping as input for better compound coverage$(NC)"
	$(PYTHON) $(SCRIPTS_DIR)/find_unaccounted_compound_matches.py --output $(UNACCOUNTED_MATCHES)

# Stage 8: Enhanced KG OAK CHEBI Mapping - Advanced ChEBI mapping with normalized compounds
.PHONY: kg-oak-chebi-mapping oak-chebi-mapping
kg-oak-chebi-mapping oak-chebi-mapping: $(UPDATED_COMPOSITION_MAPPING)
	@echo "$(GREEN)✓ Enhanced KG OAK CHEBI mapping completed: ontology annotations using normalized compounds$(NC)"

# Enhanced KG mapping with OAK CHEBI annotations using normalized/enhanced compounds (maximize ChEBI coverage)
$(UPDATED_COMPOSITION_MAPPING): $(UNACCOUNTED_MATCHES) $(KG_MAPPING_DIR)/composition_kg_mapping_ingredient_enhanced.tsv
	@echo "$(BLUE)KG OAK CHEBI Mapping: ingredient → ChEBI with ontology annotations...$(NC)"
	@echo "$(YELLOW)Goal: Maximize ChEBI coverage using ontology-based matching$(NC)"
	@echo "$(YELLOW)Extracting ingredients needing CHEBI mapping...$(NC)"
	$(PYTHON) extract_non_chebi_compounds.py || echo "$(YELLOW)Using existing compound list$(NC)"
	@if [ -f "$(COMPOUNDS_FOR_CHEBI)" ] && [ -s "$(COMPOUNDS_FOR_CHEBI)" ]; then \
		echo "$(YELLOW)Running OAK CHEBI annotation on $$(wc -l < $(COMPOUNDS_FOR_CHEBI)) ingredients...$(NC)"; \
		echo "$(YELLOW)This may take 5-10 minutes to build the CHEBI lexical index...$(NC)"; \
		runoak -i sqlite:obo:chebi annotate --text-file $(COMPOUNDS_FOR_CHEBI) --output-type json --lexical-index-file $(CHEBI_LEXICAL_INDEX) --output $(OAK_CHEBI_ANNOTATIONS) || echo "$(YELLOW)OAK annotation completed with warnings$(NC)"; \
		echo "$(YELLOW)Applying OAK CHEBI mappings...$(NC)"; \
		$(PYTHON) apply_oak_chebi_mappings.py --annotations-file $(OAK_CHEBI_ANNOTATIONS) --compounds-file $(COMPOUNDS_FOR_CHEBI) --output-file $(UPDATED_COMPOSITION_MAPPING) || cp $(COMPOSITION_MAPPING) $(UPDATED_COMPOSITION_MAPPING); \
		echo "$(YELLOW)Fixing hydrated ingredient mappings...$(NC)"; \
		$(PYTHON) fix_hydrated_compound_mappings.py || echo "$(YELLOW)Hydrated compound fixing completed with warnings$(NC)"; \
	else \
		echo "$(YELLOW)No ingredients need CHEBI mapping, using original composition mapping$(NC)"; \
		cp $(COMPOSITION_MAPPING) $(UPDATED_COMPOSITION_MAPPING); \
	fi

# Stage 9: Enhanced KG Merge Mappings - Consolidate all mapping sources with normalized compounds
.PHONY: kg-merge-mappings merge-mappings
kg-merge-mappings merge-mappings: $(UNIFIED_MAPPINGS) $(HIGH_CONFIDENCE_MAPPINGS) $(LOW_CONFIDENCE_MAPPINGS)
	@echo "$(GREEN)✓ Enhanced KG mapping merge completed: unified ingredient → ChEBI mappings with consistent hydration$(NC)"

# Create unified KG mapping from enhanced + ChEBI matches
$(UNIFIED_MAPPINGS): $(UPDATED_COMPOSITION_MAPPING) $(UNACCOUNTED_MATCHES)
	@echo "$(BLUE)KG Merge Mappings: Consolidating ingredient → ChEBI mappings...$(NC)"
	@echo "$(YELLOW)Goal: Create unified high-quality ChEBI mappings$(NC)"
	$(PYTHON) $(SCRIPTS_DIR)/merge_compound_mappings.py

# Filter KG mappings by confidence level (high/low confidence ChEBI mappings)
$(HIGH_CONFIDENCE_MAPPINGS) $(LOW_CONFIDENCE_MAPPINGS): $(UNIFIED_MAPPINGS)
	@echo "$(BLUE)Filtering KG mappings by confidence level...$(NC)"
	$(PYTHON) filter_high_confidence_mappings.py

# Stage 10: Property Calculation - Using enhanced mappings with hydration-corrected MW
.PHONY: compute-properties
compute-properties: $(MEDIA_PROPERTIES_DIR)/.done
	@echo "$(GREEN)✓ Media properties calculation completed using DB mappings$(NC)"

# Calculate pH, salinity, ionic strength using enhanced mappings with hydration-corrected MW
$(MEDIA_PROPERTIES_DIR)/.done: $(HIGH_CONFIDENCE_MAPPINGS) $(CHEMICAL_PROPERTIES)
	@echo "$(BLUE)Property Calculation: Using enhanced mappings with hydration-corrected molecular weights...$(NC)"
	@echo "$(YELLOW)ADVANTAGE: Uses early hydrate normalization + ingredient enhancement for accurate calculations$(NC)"
	@echo "$(YELLOW)Using ingredient → pKa mappings from $(CHEMICAL_PROPERTIES)$(NC)"
	@mkdir -p $(MEDIA_PROPERTIES_DIR)
	$(PYTHON) $(SCRIPTS_DIR)/compute_media_properties.py --input-high $(HIGH_CONFIDENCE_MAPPINGS) --chemical-properties $(CHEMICAL_PROPERTIES) --output-dir $(MEDIA_PROPERTIES_DIR)
	@touch $(MEDIA_PROPERTIES_DIR)/.done

# Stage 11: Final Media Summary with Enhanced Mappings
.PHONY: media-summary
media-summary: $(MEDIA_SUMMARY)
	@echo "$(GREEN)✓ Enhanced media summary generation completed$(NC)"

# Generate comprehensive media summary using enhanced mappings
$(MEDIA_SUMMARY): $(MEDIA_PROPERTIES_DIR)/.done $(HIGH_CONFIDENCE_MAPPINGS)
	@echo "$(BLUE)Creating comprehensive media summary with enhanced compound mappings...$(NC)"
	@echo "$(YELLOW)ADVANTAGE: Summary includes hydrate-normalized + ingredient-enhanced data$(NC)"
	$(PYTHON) create_media_summary.py --mappings-file $(HIGH_CONFIDENCE_MAPPINGS) --properties-dir $(MEDIA_PROPERTIES_DIR) --output $(MEDIA_SUMMARY)

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
	$(PYTHON) update_chemical_properties.py --full-update --data-dir $(IUPAC_DATA_DIR)
	@echo "$(GREEN)✓ Full IUPAC pipeline completed$(NC)"

# Quick update chemical database from existing mappings
.PHONY: iupac-update-from-mappings
iupac-update-from-mappings: install
	@echo "$(BLUE)Updating chemical database from existing compound mappings...$(NC)"
	$(PYTHON) update_chemical_properties.py --update-from-mappings --data-dir $(IUPAC_DATA_DIR)
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
	$(PYTHON) update_chemical_properties.py --add-compounds "$(COMPOUNDS)" --data-dir $(IUPAC_DATA_DIR)
	@echo "$(GREEN)✓ Compounds added to chemical database$(NC)"

# Test IUPAC system with sample compounds
.PHONY: iupac-test
iupac-test: install $(IUPAC_DATA_DIR)
	@echo "$(BLUE)Testing IUPAC chemical data system...$(NC)"
	$(PYTHON) update_chemical_properties.py --test-mode --data-dir $(IUPAC_DATA_DIR)
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
	$(PYTHON) extract_non_chebi_compounds.py
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
	$(PYTHON) apply_oak_chebi_mappings.py \
		--annotations-file $(OAK_CHEBI_ANNOTATIONS) \
		--compounds-file $(COMPOUNDS_FOR_CHEBI) \
		--output-file $(UPDATED_COMPOSITION_MAPPING)
	@echo "$(GREEN)✓ Applied OAK CHEBI mappings to $(UPDATED_COMPOSITION_MAPPING)$(NC)"

# Fix hydrated compound mappings (ingredient codes -> CHEBI)
.PHONY: fix-hydrated-mappings
fix-hydrated-mappings: $(UPDATED_COMPOSITION_MAPPING)
	@echo "$(BLUE)Fixing hydrated compounds mapped to ingredient codes...$(NC)"
	$(PYTHON) fix_hydrated_compound_mappings.py
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
	@[ -f $(UNACCOUNTED_MATCHES) ] && echo "✓ ChEBI matches: $$(tail -n +2 $(UNACCOUNTED_MATCHES) | wc -l) matches" || echo "✗ ChEBI matches: Missing"
	@[ -f $(UNIFIED_MAPPINGS) ] && echo "✓ Unified mappings: $$(tail -n +2 $(UNIFIED_MAPPINGS) | wc -l) entries" || echo "✗ Unified mappings: Missing"
	@[ -f $(HIGH_CONFIDENCE_MAPPINGS) ] && echo "✓ High confidence: $$(tail -n +2 $(HIGH_CONFIDENCE_MAPPINGS) | wc -l) entries" || echo "✗ High confidence: Missing"
	@[ -f $(LOW_CONFIDENCE_MAPPINGS) ] && echo "✓ Low confidence: $$(tail -n +2 $(LOW_CONFIDENCE_MAPPINGS) | wc -l) entries" || echo "✗ Low confidence: Missing"
	@[ -f $(HIGH_CONFIDENCE_NORMALIZED) ] && echo "✓ High normalized: $$(tail -n +2 $(HIGH_CONFIDENCE_NORMALIZED) | wc -l) entries" || echo "✗ High normalized: Missing"
	@[ -f $(LOW_CONFIDENCE_NORMALIZED) ] && echo "✓ Low normalized: $$(tail -n +2 $(LOW_CONFIDENCE_NORMALIZED) | wc -l) entries" || echo "✗ Low normalized: Missing"
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
	$(PYTHON) filter_high_confidence_mappings.py
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
	@test -f $(UNACCOUNTED_MATCHES) || (echo "$(RED)✗ Missing: $(UNACCOUNTED_MATCHES)$(NC)" && exit 1)
	@test -f $(UNIFIED_MAPPINGS) || (echo "$(RED)✗ Missing: $(UNIFIED_MAPPINGS)$(NC)" && exit 1)
	@test -f $(HIGH_CONFIDENCE_NORMALIZED) || (echo "$(RED)✗ Missing: $(HIGH_CONFIDENCE_NORMALIZED)$(NC)" && exit 1)
	@test -f $(LOW_CONFIDENCE_NORMALIZED) || (echo "$(RED)✗ Missing: $(LOW_CONFIDENCE_NORMALIZED)$(NC)" && exit 1)
	@test -d $(MEDIA_PROPERTIES_DIR) || (echo "$(RED)✗ Missing: $(MEDIA_PROPERTIES_DIR)$(NC)" && exit 1)
	@test -f $(MEDIA_SUMMARY) || (echo "$(RED)✗ Missing: $(MEDIA_SUMMARY)$(NC)" && exit 1)
	@echo "$(GREEN)✓ Pipeline validation successful!$(NC)"

# Phony targets (don't correspond to files)
.PHONY: all help install install-dev setup-venv test lint format quality \
        data-acquisition data-conversion db-mapping chemical-databases kg-mapping mapping map-compositions-to-kg \
        kg-compound-matching compound-matching kg-oak-chebi-mapping oak-chebi-mapping kg-merge-mappings merge-mappings \
        enhance-ingredients normalize-hydration compute-properties media-summary \
        iupac-analyze-compounds iupac-download-data iupac-process-data iupac-generate-tsv \
        iupac-full-pipeline iupac-update-from-mappings iupac-process-composition-mapping iupac-add-compounds iupac-test \
        iupac-validate-tsv iupac-status iupac-clean iupac-restore-backup \
        pubchem-full-pipeline pubchem-process-composition-mapping pubchem-download-compounds pubchem-test \
        pubchem-status pubchem-clean \
        extract-non-chebi-compounds oak-chebi-annotate apply-oak-chebi-mappings fix-hydrated-mappings oak-chebi-mapping \
        oak-chebi-test oak-chebi-status oak-chebi-clean \
        update-chemical-db test-chemical-db \
        clean clean-all status validate quick