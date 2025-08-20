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

# Pipeline input/output directories
MEDIA_PDFS_DIR := media_pdfs
MEDIA_TEXTS_DIR := media_texts
MEDIA_COMPOSITIONS_DIR := media_compositions
MEDIA_PROPERTIES_DIR := media_properties

# Key pipeline files
GROWTH_MEDIA_URLS := growth_media_urls.txt
COMPOSITION_MAPPING := composition_kg_mapping.tsv
UNACCOUNTED_MATCHES := unaccounted_compound_matches.tsv
UNIFIED_MAPPINGS := unified_compound_mappings.tsv
HIGH_CONFIDENCE_MAPPINGS := high_confidence_compound_mappings.tsv
LOW_CONFIDENCE_MAPPINGS := low_confidence_compound_mappings.tsv
HIGH_CONFIDENCE_NORMALIZED := high_confidence_compound_mappings_normalized.tsv
LOW_CONFIDENCE_NORMALIZED := low_confidence_compound_mappings_normalized.tsv
MEDIA_SUMMARY := media_summary.tsv
CHEMICAL_PROPERTIES := chemical_properties.tsv

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
	@echo "$(GREEN)Main Pipeline Targets:$(NC)"
	@echo "  $(YELLOW)all$(NC)                    - Run complete pipeline from start to finish"
	@echo "  $(YELLOW)data-acquisition$(NC)       - Download media PDFs and JSON data"
	@echo "  $(YELLOW)data-conversion$(NC)        - Convert PDFs to text and JSON to markdown"
	@echo "  $(YELLOW)mapping$(NC)                - Map compounds to knowledge graph entities"
	@echo "  $(YELLOW)map-compositions-to-kg$(NC)  - Run specific composition to KG mapping script"
	@echo "  $(YELLOW)compound-matching$(NC)      - Find matches for unaccounted compounds"
	@echo "  $(YELLOW)merge-mappings$(NC)         - Merge mapping results from different sources"
	@echo "  $(YELLOW)enhance-ingredients$(NC)     - Match ingredient: entries to ChEBI IDs"
	@echo "  $(YELLOW)normalize-hydration$(NC)     - Normalize hydrated forms and remove duplicates"
	@echo "  $(YELLOW)compute-properties$(NC)     - Calculate pH, salinity, and ionic strength"
	@echo "  $(YELLOW)media-summary$(NC)          - Generate final media summary table"
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
all: install data-acquisition data-conversion mapping compound-matching merge-mappings enhance-ingredients normalize-hydration compute-properties media-summary
	@echo "$(GREEN)✓ Complete pipeline finished successfully!$(NC)"

# Pipeline stage targets

# Stage 1: Data Acquisition
.PHONY: data-acquisition
data-acquisition: $(GROWTH_MEDIA_URLS) $(MEDIA_PDFS_DIR)/.done
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

# Convert JSON compositions to markdown tables
$(MEDIA_COMPOSITIONS_DIR)/.done: $(MEDIA_PDFS_DIR)/.done
	@echo "$(BLUE)Converting JSON compositions to markdown...$(NC)"
	$(PYTHON) $(SCRIPTS_DIR)/convert_json_to_markdown.py
	@mkdir -p $(MEDIA_COMPOSITIONS_DIR) && touch $(MEDIA_COMPOSITIONS_DIR)/.done

# Stage 3: Knowledge Graph Mapping
.PHONY: mapping
mapping: $(COMPOSITION_MAPPING)
	@echo "$(GREEN)✓ Knowledge graph mapping completed$(NC)"

# Specific target for the main mapping script
.PHONY: map-compositions-to-kg
map-compositions-to-kg: $(COMPOSITION_MAPPING)
	@echo "$(GREEN)✓ Composition to KG mapping completed$(NC)"

# Map compounds to KG entities (ChEBI, KEGG, PubChem)
$(COMPOSITION_MAPPING): $(MEDIA_COMPOSITIONS_DIR)/.done
	@echo "$(BLUE)Mapping compounds to knowledge graph entities...$(NC)"
	$(PYTHON) $(SCRIPTS_DIR)/map_compositions_to_kg.py

# Stage 4: Compound Matching
.PHONY: compound-matching
compound-matching: $(UNACCOUNTED_MATCHES)
	@echo "$(GREEN)✓ Compound matching completed$(NC)"

# Find ChEBI matches for unaccounted compounds
$(UNACCOUNTED_MATCHES): $(COMPOSITION_MAPPING)
	@echo "$(BLUE)Finding matches for unaccounted compounds...$(NC)"
	$(PYTHON) $(SCRIPTS_DIR)/find_unaccounted_compound_matches.py

# Stage 5: Merge Mappings
.PHONY: merge-mappings
merge-mappings: $(UNIFIED_MAPPINGS) $(HIGH_CONFIDENCE_MAPPINGS) $(LOW_CONFIDENCE_MAPPINGS)
	@echo "$(GREEN)✓ Mapping merge completed$(NC)"

# Create unified mapping from original + ChEBI matches
$(UNIFIED_MAPPINGS): $(COMPOSITION_MAPPING) $(UNACCOUNTED_MATCHES)
	@echo "$(BLUE)Merging compound mappings...$(NC)"
	$(PYTHON) $(SCRIPTS_DIR)/merge_compound_mappings.py

# Filter for high and low confidence mappings
$(HIGH_CONFIDENCE_MAPPINGS) $(LOW_CONFIDENCE_MAPPINGS): $(UNIFIED_MAPPINGS)
	@echo "$(BLUE)Filtering mappings by confidence level...$(NC)"
	$(PYTHON) filter_high_confidence_mappings.py

# Stage 6: Ingredient Enhancement
INGREDIENT_ENHANCED_HIGH := high_confidence_compound_mappings_normalized_ingredient_enhanced.tsv
INGREDIENT_ENHANCED_LOW := low_confidence_compound_mappings_normalized_ingredient_enhanced.tsv

.PHONY: enhance-ingredients
enhance-ingredients: $(INGREDIENT_ENHANCED_HIGH) $(INGREDIENT_ENHANCED_LOW)
	@echo "$(GREEN)✓ Ingredient ChEBI matching completed$(NC)"

# Match ingredient: entries to ChEBI IDs including hydrates
$(INGREDIENT_ENHANCED_HIGH) $(INGREDIENT_ENHANCED_LOW): $(HIGH_CONFIDENCE_MAPPINGS) $(LOW_CONFIDENCE_MAPPINGS)
	@echo "$(BLUE)Enhancing ingredient: entries with ChEBI matching...$(NC)"
	$(PYTHON) enhance_ingredient_matching.py

# Stage 7: Hydration Normalization
.PHONY: normalize-hydration
normalize-hydration: $(HIGH_CONFIDENCE_NORMALIZED) $(LOW_CONFIDENCE_NORMALIZED)
	@echo "$(GREEN)✓ Hydration normalization completed$(NC)"

# Normalize hydrated forms and remove duplicates
$(HIGH_CONFIDENCE_NORMALIZED) $(LOW_CONFIDENCE_NORMALIZED): $(INGREDIENT_ENHANCED_HIGH) $(INGREDIENT_ENHANCED_LOW)
	@echo "$(BLUE)Normalizing hydrated forms and removing duplicates...$(NC)"
	$(PYTHON) normalize_hydration_forms.py --input-high $(INGREDIENT_ENHANCED_HIGH) --input-low $(INGREDIENT_ENHANCED_LOW)

# Stage 8: Property Calculation
.PHONY: compute-properties
compute-properties: $(MEDIA_PROPERTIES_DIR)/.done
	@echo "$(GREEN)✓ Media properties calculation completed$(NC)"

# Calculate pH, salinity, ionic strength for each medium
$(MEDIA_PROPERTIES_DIR)/.done: $(HIGH_CONFIDENCE_NORMALIZED) $(CHEMICAL_PROPERTIES)
	@echo "$(BLUE)Computing media properties (pH, salinity, ionic strength)...$(NC)"
	@bash $(SCRIPTS_DIR)/media_properties.sh
	@mkdir -p $(MEDIA_PROPERTIES_DIR) && touch $(MEDIA_PROPERTIES_DIR)/.done

# Stage 9: Final Summary
.PHONY: media-summary
media-summary: $(MEDIA_SUMMARY)
	@echo "$(GREEN)✓ Media summary generation completed$(NC)"

# Generate comprehensive media summary table
$(MEDIA_SUMMARY): $(MEDIA_PROPERTIES_DIR)/.done $(HIGH_CONFIDENCE_NORMALIZED)
	@echo "$(BLUE)Creating comprehensive media summary...$(NC)"
	$(PYTHON) create_media_summary.py

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
        data-acquisition data-conversion mapping map-compositions-to-kg compound-matching merge-mappings \
        enhance-ingredients normalize-hydration compute-properties media-summary \
        clean clean-all status validate quick