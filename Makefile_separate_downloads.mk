# MicroMediaParam Pipeline Makefile - Separated Downloads Version
# 
# This Makefile provides granular control over each download step
# for better debugging and resumability.

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
CHEMICAL_PROPERTIES := $(DB_MAPPING_DIR)/chemical_properties.tsv

# Chemical data directories
IUPAC_DATA_DIR := data/chemical_processing
PUBCHEM_DATA_DIR := data/pubchem_processing

# Colors for output
RED := \033[31m
GREEN := \033[32m
YELLOW := \033[33m
BLUE := \033[34m
NC := \033[0m # No Color

# Default target
.DEFAULT_GOAL := help

# Help target
.PHONY: help
help:
	@echo "$(BLUE)MicroMediaParam Pipeline - Separated Downloads$(NC)"
	@echo "=============================================="
	@echo ""
	@echo "$(GREEN)Data Acquisition Steps:$(NC)"
	@echo "  $(YELLOW)parse-urls$(NC)          - Parse media URLs from source files"
	@echo "  $(YELLOW)download-pdfs$(NC)       - Download PDF files only"
	@echo "  $(YELLOW)download-json$(NC)       - Download JSON composition files only"
	@echo "  $(YELLOW)download-media$(NC)      - Download both PDFs and JSON files"
	@echo ""
	@echo "$(GREEN)Chemical Database Downloads:$(NC)"
	@echo "  $(YELLOW)download-iupac$(NC)      - Download IUPAC chemical data"
	@echo "  $(YELLOW)download-pubchem$(NC)    - Download PubChem chemical data"
	@echo "  $(YELLOW)build-chemical-db$(NC)   - Build unified chemical properties database"
	@echo ""
	@echo "$(GREEN)Processing Steps:$(NC)"
	@echo "  $(YELLOW)convert-pdfs$(NC)        - Convert PDFs to text/markdown"
	@echo "  $(YELLOW)convert-json$(NC)        - Convert JSON to markdown tables"
	@echo "  $(YELLOW)data-conversion$(NC)     - Run all conversions"
	@echo ""
	@echo "$(GREEN)Complete Pipeline:$(NC)"
	@echo "  $(YELLOW)all$(NC)                 - Run complete pipeline"
	@echo "  $(YELLOW)clean$(NC)               - Clean output directories"
	@echo ""
	@echo "$(GREEN)Usage Examples:$(NC)"
	@echo "  make parse-urls      # Step 1: Parse URLs"
	@echo "  make download-pdfs   # Step 2a: Download PDFs only"
	@echo "  make download-json   # Step 2b: Download JSON only"
	@echo "  make download-iupac  # Step 3a: Download IUPAC data"
	@echo "  make download-pubchem # Step 3b: Download PubChem data"

# Create output directories
.PHONY: create-dirs
create-dirs:
	@mkdir -p $(DATA_ACQUISITION_DIR)
	@mkdir -p $(DATA_CONVERSION_DIR)
	@mkdir -p $(DB_MAPPING_DIR)
	@mkdir -p $(KG_MAPPING_DIR)
	@mkdir -p $(COMPOUND_MATCHING_DIR)
	@mkdir -p $(OAK_CHEBI_DIR)
	@mkdir -p $(MERGE_MAPPINGS_DIR)
	@mkdir -p $(INGREDIENT_ENHANCEMENT_DIR)
	@mkdir -p $(HYDRATE_NORMALIZATION_DIR)
	@mkdir -p $(PROPERTY_CALCULATION_DIR)
	@mkdir -p $(MEDIA_SUMMARY_DIR)
	@mkdir -p $(MEDIA_PDFS_DIR)
	@mkdir -p $(MEDIA_TEXTS_DIR)
	@mkdir -p $(MEDIA_COMPOSITIONS_DIR)
	@mkdir -p $(MEDIA_PROPERTIES_DIR)
	@mkdir -p $(IUPAC_DATA_DIR)
	@mkdir -p $(PUBCHEM_DATA_DIR)

# ========== STAGE 1: DATA ACQUISITION ==========

# Parse media URLs from source files
.PHONY: parse-urls
parse-urls: create-dirs $(GROWTH_MEDIA_URLS)
	@echo "$(GREEN)✓ Media URLs parsed successfully$(NC)"
	@echo "$(YELLOW)URLs saved to: $(GROWTH_MEDIA_URLS)$(NC)"

$(GROWTH_MEDIA_URLS):
	@echo "$(BLUE)Parsing media URLs from source files...$(NC)"
	$(PYTHON) $(SCRIPTS_DIR)/parse_media_urls.py
	@echo "$(YELLOW)Total URLs found: $$(wc -l < $(GROWTH_MEDIA_URLS))$(NC)"

# Download PDF files only
.PHONY: download-pdfs
download-pdfs: $(GROWTH_MEDIA_URLS)
	@echo "$(BLUE)Downloading PDF files only...$(NC)"
	@echo "$(YELLOW)This may take some time depending on the number of URLs$(NC)"
	$(PYTHON) $(SCRIPTS_DIR)/download_media_pdfs.py --pdfs-only || echo "$(YELLOW)PDF downloads completed with some errors$(NC)"
	@touch $(MEDIA_PDFS_DIR)/.pdf_done
	@echo "$(GREEN)✓ PDF download completed$(NC)"
	@echo "$(YELLOW)PDFs saved to: $(MEDIA_PDFS_DIR)$(NC)"

# Download JSON composition files only
.PHONY: download-json
download-json: $(GROWTH_MEDIA_URLS)
	@echo "$(BLUE)Downloading JSON composition files only...$(NC)"
	@echo "$(YELLOW)Note: Only DSMZ/MediaDive URLs have JSON data$(NC)"
	$(PYTHON) $(SCRIPTS_DIR)/download_media_pdfs.py --json-only || echo "$(YELLOW)JSON downloads completed with some errors$(NC)"
	@touch $(MEDIA_PDFS_DIR)/.json_done
	@echo "$(GREEN)✓ JSON download completed$(NC)"
	@echo "$(YELLOW)JSON files saved to: $(MEDIA_PDFS_DIR)$(NC)"

# Download both PDFs and JSON files
.PHONY: download-media
download-media: download-pdfs download-json
	@touch $(MEDIA_PDFS_DIR)/.done
	@echo "$(GREEN)✓ All media downloads completed$(NC)"

# ========== STAGE 2: DATA CONVERSION ==========

# Convert PDFs to text
.PHONY: convert-pdfs
convert-pdfs: $(MEDIA_PDFS_DIR)/.pdf_done
	@echo "$(BLUE)Converting PDFs to text format...$(NC)"
	$(PYTHON) $(SCRIPTS_DIR)/convert_pdfs_to_text.py
	@touch $(MEDIA_TEXTS_DIR)/.done
	@echo "$(GREEN)✓ PDF conversion completed$(NC)"
	@echo "$(YELLOW)Text files saved to: $(MEDIA_TEXTS_DIR)$(NC)"

# Convert JSON to markdown tables
.PHONY: convert-json
convert-json: $(MEDIA_PDFS_DIR)/.json_done
	@echo "$(BLUE)Converting JSON compositions to markdown tables...$(NC)"
	$(PYTHON) $(SCRIPTS_DIR)/convert_json_to_markdown.py
	@touch $(MEDIA_COMPOSITIONS_DIR)/.done
	@echo "$(GREEN)✓ JSON conversion completed$(NC)"
	@echo "$(YELLOW)Markdown files saved to: $(MEDIA_COMPOSITIONS_DIR)$(NC)"

# All data conversions
.PHONY: data-conversion
data-conversion: convert-pdfs convert-json
	@echo "$(GREEN)✓ All data conversions completed$(NC)"

# ========== STAGE 3: CHEMICAL DATABASE DOWNLOADS ==========

# Download IUPAC chemical data
.PHONY: download-iupac
download-iupac: create-dirs
	@echo "$(BLUE)Downloading IUPAC chemical data...$(NC)"
	@echo "$(YELLOW)Test compounds: glucose, sodium chloride, glycine, citric acid, potassium phosphate$(NC)"
	$(PYTHON) -m src.chem.iupac.pipeline --download-compounds "glucose,sodium chloride,glycine,citric acid,potassium phosphate" \
		--data-dir $(IUPAC_DATA_DIR) || echo "$(YELLOW)IUPAC download completed with warnings$(NC)"
	@touch $(IUPAC_DATA_DIR)/.download_done
	@echo "$(GREEN)✓ IUPAC data download completed$(NC)"
	@echo "$(YELLOW)Data saved to: $(IUPAC_DATA_DIR)$(NC)"

# Download PubChem chemical data
.PHONY: download-pubchem
download-pubchem: create-dirs
	@echo "$(BLUE)Downloading PubChem chemical data...$(NC)"
	@echo "$(YELLOW)Test compounds: glucose, sodium chloride, glycine, citric acid, potassium phosphate$(NC)"
	$(PYTHON) -m src.chem.pubchem.pipeline --download-compounds "glucose,sodium chloride,glycine,citric acid,potassium phosphate" \
		--data-dir $(PUBCHEM_DATA_DIR) || echo "$(YELLOW)PubChem download completed with warnings$(NC)"
	@touch $(PUBCHEM_DATA_DIR)/.download_done
	@echo "$(GREEN)✓ PubChem data download completed$(NC)"
	@echo "$(YELLOW)Data saved to: $(PUBCHEM_DATA_DIR)$(NC)"

# Build chemical properties database
.PHONY: build-chemical-db
build-chemical-db: $(CHEMICAL_PROPERTIES)
	@echo "$(GREEN)✓ Chemical properties database built$(NC)"
	@echo "$(YELLOW)Database saved to: $(CHEMICAL_PROPERTIES)$(NC)"

$(CHEMICAL_PROPERTIES): $(IUPAC_DATA_DIR)/.download_done $(PUBCHEM_DATA_DIR)/.download_done
	@echo "$(BLUE)Building unified chemical properties database...$(NC)"
	@echo "Creating initial chemical_properties.tsv from IUPAC data..."
	@if [ -f "$(IUPAC_DATA_DIR)/processed_chemical_data.json" ]; then \
		$(PYTHON) -c "from src.chem.iupac.tsv_generator import ChemicalPropertiesTSVGenerator; \
		gen = ChemicalPropertiesTSVGenerator(); \
		gen.generate_tsv_from_json('$(IUPAC_DATA_DIR)/processed_chemical_data.json', '$(CHEMICAL_PROPERTIES)')"; \
	else \
		echo "$(YELLOW)Warning: IUPAC processed data not found$(NC)"; \
	fi
	@echo "Merging PubChem data into chemical_properties.tsv..."
	@if [ -f "$(PUBCHEM_DATA_DIR)/pubchem_processed_data.json" ]; then \
		$(PYTHON) -c "from src.chem.pubchem.tsv_generator import PubChemTSVGenerator; \
		gen = PubChemTSVGenerator(); \
		gen.generate_tsv_from_json('$(PUBCHEM_DATA_DIR)/pubchem_processed_data.json', '$(CHEMICAL_PROPERTIES)', merge_with_existing=True)"; \
	else \
		echo "$(YELLOW)Warning: PubChem processed data not found$(NC)"; \
	fi
	@echo "$(GREEN)✓ Chemical properties database generated$(NC)"

# ========== UTILITY TARGETS ==========

# Clean all output
.PHONY: clean
clean:
	@echo "$(BLUE)Cleaning output directories...$(NC)"
	rm -rf $(OUTPUT_DIR)
	rm -f *.log
	@echo "$(GREEN)✓ Cleaned$(NC)"

# Clean downloads only
.PHONY: clean-downloads
clean-downloads:
	@echo "$(BLUE)Cleaning downloaded files...$(NC)"
	rm -rf $(MEDIA_PDFS_DIR)
	rm -f $(GROWTH_MEDIA_URLS)
	@echo "$(GREEN)✓ Downloads cleaned$(NC)"

# Status check
.PHONY: status
status:
	@echo "$(BLUE)Pipeline Status:$(NC)"
	@echo ""
	@if [ -f "$(GROWTH_MEDIA_URLS)" ]; then \
		echo "$(GREEN)✓ URLs parsed:$(NC) $$(wc -l < $(GROWTH_MEDIA_URLS)) URLs found"; \
	else \
		echo "$(RED)✗ URLs not parsed$(NC)"; \
	fi
	@echo ""
	@if [ -f "$(MEDIA_PDFS_DIR)/.pdf_done" ]; then \
		echo "$(GREEN)✓ PDFs downloaded:$(NC) $$(find $(MEDIA_PDFS_DIR) -name '*.pdf' | wc -l) files"; \
	else \
		echo "$(YELLOW)⚠ PDFs not downloaded$(NC)"; \
	fi
	@echo ""
	@if [ -f "$(MEDIA_PDFS_DIR)/.json_done" ]; then \
		echo "$(GREEN)✓ JSON downloaded:$(NC) $$(find $(MEDIA_PDFS_DIR) -name '*.json' | wc -l) files"; \
	else \
		echo "$(YELLOW)⚠ JSON not downloaded$(NC)"; \
	fi
	@echo ""
	@if [ -f "$(IUPAC_DATA_DIR)/.download_done" ]; then \
		echo "$(GREEN)✓ IUPAC data downloaded$(NC)"; \
	else \
		echo "$(YELLOW)⚠ IUPAC data not downloaded$(NC)"; \
	fi
	@echo ""
	@if [ -f "$(PUBCHEM_DATA_DIR)/.download_done" ]; then \
		echo "$(GREEN)✓ PubChem data downloaded$(NC)"; \
	else \
		echo "$(YELLOW)⚠ PubChem data not downloaded$(NC)"; \
	fi

# Complete pipeline (all steps)
.PHONY: all
all: parse-urls download-media data-conversion download-iupac download-pubchem build-chemical-db
	@echo "$(GREEN)✓ Complete pipeline finished$(NC)"
	@echo "$(YELLOW)Run 'make status' to see results$(NC)"