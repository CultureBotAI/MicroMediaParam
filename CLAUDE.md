# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MicroMediaParam is a bioinformatics pipeline for extracting, processing, and analyzing microbial growth media composition data. It's designed to parse media information from sources like MediaDive and DSMZ, convert data to structured formats, map chemical compounds to knowledge graph entities, and compute physical-chemical properties like pH and salinity.

## Development Commands

### Environment Setup
```bash
# Install dependencies using uv (recommended - modern Python package installer)
uv sync

# Or using traditional pip
pip install -r requirements.txt

# Install development dependencies
pip install -e ".[dev]"

# Or with uv
uv pip install -e ".[dev]"
```

### Code Quality
```bash
# Format code with Black
black src/ *.py

# Sort imports with isort
isort src/ *.py

# Lint with flake8
flake8 src/ *.py

# Type checking with mypy
mypy src/

# Run all quality checks
black src/ *.py && isort src/ *.py && flake8 src/ *.py && mypy src/
```

### Testing
```bash
# Run all tests (via pytest if configured)
python -m pytest

# Run specific test file
python -m pytest test_compound_matcher.py

# Run tests with verbose output
python -m pytest -v

# Note: Test files are not currently tracked in the repository.
# The Makefile includes test targets that may generate test scripts dynamically.
# Use `make test` for the complete test workflow.
```

### Pipeline Execution
```bash
# Run main pipeline scripts (installed as console scripts)
parse-media-urls
download-media-pdfs
convert-pdfs-to-text

# Or run directly from source
python src/scripts/parse_media_urls.py
python src/scripts/download_media_pdfs.py
python src/scripts/convert_pdfs_to_text.py
python src/scripts/convert_json_to_markdown.py
python src/scripts/map_compositions_to_kg.py
python src/scripts/compute_media_properties.py

# NEW: Unified mapping engine (replaces old scripts)
python -m src.mapping.unified_mapper --kg-nodes merged-kg_nodes.tsv --composition-dir media_compositions

# Or use the Makefile for complete workflows
make all                    # Run complete pipeline
make data-acquisition       # Step 1: Download media data
make data-conversion        # Step 2: Convert to structured format
make db-mapping            # Step 3: Build chemical properties DB
make kg-mapping-initial    # Step 4: Initial KG mapping
make solution-expansion    # Step 5: Expand DSMZ solution references
make compute-properties    # Step 11: Calculate pH/salinity
make media-summary         # Step 12: Generate summary
```

## Architecture

### Pipeline Structure
The project follows a modular pipeline architecture with discrete stages:

1. **Data Acquisition** (`parse_media_urls.py`, `download_media_pdfs.py`)
   - Extracts media URLs from BacDive/MediaDive JSON files using regex
   - Asynchronously downloads PDFs and JSON composition data

2. **Data Conversion** (`convert_pdfs_to_text.py`, `convert_json_to_markdown.py`)
   - Converts PDFs to markdown using MarkItDown
   - Transforms JSON compositions to structured markdown tables

3. **Knowledge Graph Mapping** (`map_compositions_*.py`)
   - Maps chemical compound names to KG entities (ChEBI, KEGG, PubChem)
   - Multiple mapping strategies: exact, fuzzy, comprehensive
   - Uses fuzzy string matching for compound name resolution

4. **Solution Expansion** (`complete_solution_expansion.py`)
   - Expands DSMZ solution references (e.g., "solution:241") into individual chemical components
   - Downloads DSMZ solution PDFs and parses chemical compositions
   - Integrates expanded components back into media mappings

5. **Property Calculation** (`compute_media_properties.py`)
   - Computes pH using Henderson-Hasselbalch equations
   - Calculates salinity and ionic strength using Davies activity coefficients
   - Handles complex chemical equilibria

6. **Analysis & Integration** (`find_unaccounted_compound_matches.py`, `merge_compound_mappings.py`)
   - Identifies unmapped compounds and suggests matches
   - Merges mapping results from different sources

### Data Flow
- **Input**: BacDive/MediaDive JSON files containing strain and media information
- **Intermediate**: PDF files, text extracts, structured compositions as markdown
- **Output**: TSV mapping files, JSON property files, comprehensive logs

### Key Directories
- `src/scripts/` - Main pipeline scripts (21 scripts)
- `src/analysis/` - Chemical analysis tools (7 scripts)
- `src/mapping/` - Knowledge graph mapping tools (11 scripts)
- `src/hydration/` - Hydration state processing (4 scripts)
- `src/quality/` - Quality control and validation (8 scripts)
- `src/tools/` - Utility scripts including solution expansion (12 scripts)
- `src/chem/iupac/` - IUPAC chemical data processing
- `src/chem/pubchem/` - PubChem integration
- `src/attic/` - Legacy and experimental scripts (34 scripts)
- `pipeline_output/` - Organized output by pipeline stage (created by Makefile)
  - `data_acquisition/` - Downloaded PDFs and JSON data
  - `data_conversion/` - Converted markdown and compositions
  - `db_mapping/` - Chemical properties database
  - `kg_mapping/` - Knowledge graph mappings
  - `solution_expansion/` - Expanded DSMZ solutions
  - `compound_matching/` - Compound match results
  - `merge_mappings/` - Unified mappings
  - `property_calculation/` - Media properties (pH, salinity)
  - `media_summary/` - Final summary tables

### Technology Stack
- **Async Processing**: `aiohttp`/`aiofiles` for concurrent downloads
- **Document Processing**: `MarkItDown` for PDF conversion, `BeautifulSoup4` for HTML parsing
- **Scientific Computing**: `numpy`/`sympy` for chemical calculations
- **Fuzzy Matching**: `fuzzywuzzy` for compound name matching
- **Build System**: Modern Python packaging with Hatchling
- **Package Management**: `uv` for fast, modern dependency management (lock file: `uv.lock`)

## Development Notes

### Code Style
- Black formatting (88 character line length)
- isort for import organization (black profile)
- Type hints required (`mypy` with `disallow_untyped_defs`)
- Python 3.10+ required

### Testing Approach
- Unit tests for compound matching logic
- Property calculation validation tests
- Sample data merging tests
- Run `make test` for full test suite (includes pytest and individual test scripts)
- Test scripts may be generated dynamically during pipeline execution

### Chemical Data Processing
- Compound names are mapped to multiple databases (ChEBI, KEGG, PubChem)
- pH calculations handle complex buffer systems and ionic interactions
- Salinity computation uses Davies equation for activity coefficients
- Missing or ambiguous compounds are logged for manual review

### Hydration State Handling
- Critical optimization: Early hydration normalization (Stage 6) ensures consistent base compounds
- Example: "CaCl2 x 2 H2O" and "CaCl2 x 6 H2O" both map to same base ChEBI but maintain correct molecular weights
- Hydration patterns: `6-hydrate`, `6H2O`, `x H2O`, `·6H2O`
- Molecular weight calculation includes water molecules: `MW_hydrated = MW_base + (n × 18.015)`

### DSMZ Solution Expansion
- Solution references like "solution:241" are expanded into individual chemical components
- Downloads solution PDFs from DSMZ MediaDive REST API
- Parses compositions using specialized parsers
- Adjusts concentrations based on solution usage ratios
- Generates comprehensive expansion reports

### Performance Considerations
- Large-scale processing (1000+ media compositions, 23,181 chemical entries)
- Asynchronous downloads to handle network I/O efficiently
- Chunked file processing for memory management with large JSON files
- Extensive logging for debugging pipeline issues

### Output Formats
- TSV files for knowledge graph integration
- JSON for structured property data
- Comprehensive logs for each processing stage
- Markdown tables for human-readable compositions

### Mapping Strategies
The pipeline uses two complementary mapping approaches:

1. **DB Mapping** (ingredient → pKa, properties)
   - Downloads IUPAC/PubChem data for chemical properties
   - Goal: Maximize pKa coverage for pH/salinity calculations
   - Stored in `chemical_properties.tsv`

2. **KG Mapping** (ingredient → ChEBI/KEGG/PubChem IDs)
   - Maps ingredients to knowledge graph entities
   - Goal: Maximize ChEBI coverage for semantic analysis
   - Multiple strategies: exact matching, fuzzy matching, OAK ontology-based matching
   - Output: `composition_kg_mapping.tsv` and variants

### Unified Mapping Architecture (October 2025)

**New modular architecture** consolidates 7 legacy scripts into clean, maintainable system:

**Core Components:**
- `src/mapping/compound_normalizer.py` - Handles name normalization (hydrates, stereochemistry, etc.)
- `src/mapping/matching_strategies.py` - Strategy pattern for different matching approaches
- `src/mapping/unified_mapper.py` - Main mapping engine with all strategies

**Specialized Matchers:**
- `src/mapping/formula_matcher.py` - Hydrated chemical formulas (e.g., "CoCl2 x 6 H2O")
- `src/mapping/cas_to_chebi_upgrader.py` - Upgrades CAS-RN → ChEBI (+120 compounds)
- `src/mapping/microbio_products.py` - Curated biological products (tryptone, yeast extract, etc.)

**Analysis Tools:**
- `src/analysis/analyze_unmapped_compounds.py` - Identifies patterns in unmapped compounds

**Legacy Scripts Archived:**
- 6 duplicate scripts moved to `src/attic/legacy_mapping_scripts/`
- Main `map_compositions_to_kg.py` kept for backwards compatibility

**Usage:**
```bash
# Analyze unmapped compounds
python3 src/analysis/analyze_unmapped_compounds.py

# Upgrade CAS-RN to ChEBI (highest ROI: +120 compounds)
python3 src/mapping/cas_to_chebi_upgrader.py \
    --chebi-file chebi_nodes.tsv \
    --input high_confidence_compound_mappings.tsv \
    --output high_confidence_compound_mappings_upgraded.tsv

# Use unified mapper for new mappings
python3 -m src.mapping.unified_mapper \
    --kg-nodes merged-kg_nodes.tsv \
    --composition-dir media_compositions \
    --fuzzy-threshold 85
```

**See `IMPLEMENTATION_SUMMARY.md` for complete documentation.**

### Mapping Enhancement Deployment (October 28, 2025) ✅

**Successfully deployed** three specialized mapping strategies, achieving **+16% coverage gain** (56% → 72%):

**Deployment Workflow:**
```bash
# 1. Upgrade CAS-RN to ChEBI (+94 compounds)
python3 src/mapping/cas_to_chebi_upgrader.py \
    --chebi-file chebi_nodes.tsv \
    --input high_confidence_compound_mappings.tsv \
    --output high_confidence_compound_mappings_upgraded.tsv

# 2. Apply formula matching for hydrated compounds (+56 compounds)
python3 src/mapping/apply_formula_matching.py \
    --chebi-file chebi_nodes.tsv \
    --input high_confidence_compound_mappings_upgraded.tsv \
    --output high_confidence_compound_mappings_formula_enhanced.tsv

# 3. Apply microbiology products dictionary (+21 semantic IDs)
python3 src/mapping/apply_microbio_products.py \
    --input high_confidence_compound_mappings_formula_enhanced.tsv \
    --output high_confidence_compound_mappings_final.tsv
```

**Results:**
- Total improvement: +171 compounds with semantic IDs
- ChEBI coverage: 754/1,047 (72%)
- UBERON (anatomical): 4/1,047
- Formula matcher: 73.6% success rate (exceeded projections by 150%!)

**See `DEPLOYMENT_REPORT.md` for complete deployment details.**

### Pipeline Optimization Flow
The Makefile implements an optimized pipeline sequence:

1. Early hydration normalization (Stage 6) - Fixes hydrate inconsistencies BEFORE advanced matching
2. Early ingredient enhancement (Stage 7) - Converts ingredient codes using normalized compounds
3. Enhanced compound matching (Stage 8) - Uses normalized base compounds for better ChEBI matches
4. OAK CHEBI mapping (Stage 9) - Ontology-based annotations with improved compound set
5. Merge mappings (Stage 10) - Creates final high/low confidence mappings
6. Property calculation (Stage 11) - Uses hydration-corrected molecular weights
7. Media summary (Stage 12) - Final comprehensive dataset

This ordering ensures downstream steps work with clean, consistent compound data.

**Important:** The optimized pipeline does NOT create separate `*_normalized.tsv` files at the end. Instead:
- Normalization happens EARLY in `pipeline_output/kg_mapping/composition_kg_mapping_hydrate_normalized.tsv`
- Enhancement happens EARLY in `pipeline_output/kg_mapping/composition_kg_mapping_ingredient_enhanced.tsv`
- Final outputs are `high_confidence_compound_mappings.tsv` and `low_confidence_compound_mappings.tsv` which already contain normalized/enhanced data

The `validate` and `status` targets have been updated to check for this optimized structure.

## Common Development Workflows

### Running the Complete Pipeline
```bash
# Full pipeline from scratch
make clean-all  # Remove all previous outputs
make all        # Run complete pipeline (takes 30-60 minutes)
```

### Working with Chemical Databases
```bash
# Check current database status
make iupac-status
make pubchem-status

# Update chemical properties from mappings
make iupac-update-from-mappings
make db-mapping  # Or use the full DB mapping target
```

### Debugging Pipeline Stages
```bash
# Check pipeline status
make status

# Run individual stages
make data-acquisition      # Just download data
make data-conversion       # Just convert PDFs
make kg-mapping-initial    # Just create initial mappings
make solution-expansion    # Just expand DSMZ solutions
make compute-properties    # Just calculate properties

# Validate pipeline outputs
make validate
```

### Working with Solution Expansion
The DSMZ solution expansion feature is critical for converting solution references (e.g., "solution:241") into individual chemical components:

```bash
# Run complete solution expansion
make solution-expansion

# This will:
# 1. Identify all solution: references in composition mappings
# 2. Download DSMZ solution PDFs from MediaDive REST API
# 3. Parse chemical compositions from solution specifications
# 4. Expand solution references into individual chemical entries
# 5. Generate expansion report: pipeline_output/solution_expansion/dsmz_solution_expansion_report.json
```

### Working with OAK ChEBI Mappings
```bash
# Check OAK ChEBI status
make oak-chebi-status

# Run complete OAK ChEBI pipeline
make kg-oak-chebi-mapping

# Individual steps
make extract-non-chebi-compounds  # Extract unmapped compounds
make oak-chebi-annotate           # Run OAK annotation (builds lexical index)
make apply-oak-chebi-mappings     # Apply results to composition mapping
make fix-hydrated-mappings        # Fix hydration issues
```

### Quick Development Iteration
```bash
# Fast iteration with smaller dataset
make quick

# Format and lint before committing
make format
make lint
```

### Understanding Pipeline Outputs
Key output files to examine:
- `pipeline_output/kg_mapping/composition_kg_mapping.tsv` - Initial KG mappings
- `pipeline_output/solution_expansion/composition_kg_mapping_expanded_solutions.tsv` - After solution expansion
- `pipeline_output/merge_mappings/high_confidence_compound_mappings.tsv` - Final high-quality mappings
- `pipeline_output/media_summary/media_summary.tsv` - Comprehensive media summary
- `pipeline_output/db_mapping/chemical_properties.tsv` - Chemical properties database

All pipeline stages generate detailed logs (`*.log` files) for debugging.

## Troubleshooting

### Validation Errors
If `make validate` fails, check:
1. Run `make status` to see which files are actually present
2. The optimized pipeline creates files in `pipeline_output/kg_mapping/` (early stages) not in separate normalized directories
3. Final mappings are in `pipeline_output/merge_mappings/high_confidence_compound_mappings.tsv`

### Missing ChEBI Matches
If you see "✗ ChEBI matches: Missing" or 0 matches:
- This file (`unaccounted_compound_matches.tsv`) is only created if there are unmapped compounds
- Check `make oak-chebi-status` to see OAK mapping status
- The absence of this file may indicate all compounds are already mapped

### Property Calculation Issues
If property calculation fails or produces incomplete results:
1. Verify chemical properties database exists: `pipeline_output/db_mapping/chemical_properties.tsv`
2. Check that high confidence mappings exist with hydration data
3. Review `compute_media_properties.log` for specific errors
4. Common issues: missing pKa values, malformed concentration units

### Pipeline Stage Dependencies
The pipeline must run in order. If a stage fails:
1. Check the previous stage completed successfully
2. Review the stage-specific log file
3. Use `make status` to verify all upstream files exist
4. Consider running `make clean` and restarting from the failed stage