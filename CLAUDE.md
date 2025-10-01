# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MicroMediaParam is a bioinformatics pipeline for extracting, processing, and analyzing microbial growth media composition data. It's designed to parse media information from sources like MediaDive and DSMZ, convert data to structured formats, map chemical compounds to knowledge graph entities, and compute physical-chemical properties like pH and salinity.

## Development Commands

### Environment Setup
```bash
# Install dependencies (using uv for faster installs)
uv pip install -r requirements.txt

# Or using pip
pip install -r requirements.txt

# Install development dependencies
pip install -e ".[dev]"
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
# Run all tests
python -m pytest

# Run specific test file
python -m pytest test_compound_matcher.py

# Run tests with verbose output
python -m pytest -v

# Run individual test scripts
python test_compound_matcher.py
python test_hydration_matching.py
python test_merge_sample.py
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
- `src/scripts/` - Main pipeline scripts (16 scripts)
- `src/analysis/` - Chemical analysis tools (5 scripts)
- `src/mapping/` - Knowledge graph mapping tools
- `src/hydration/` - Hydration state processing
- `src/quality/` - Quality control and validation
- `src/tools/` - Utility scripts (9 scripts)
- `src/chem/iupac/` - IUPAC chemical data processing
- `src/chem/pubchem/` - PubChem integration
- `src/attic/` - Legacy and experimental scripts (35+ scripts)
- `media_pdfs/` - Downloaded PDF documentation and JSON data
- `media_texts/` - Converted markdown from PDFs
- `media_compositions/` - Structured composition tables (1000+ media)
- `media_properties/` - Computed physical-chemical properties
- `pipeline_output/` - Organized output by pipeline stage

### Technology Stack
- **Async Processing**: `aiohttp`/`aiofiles` for concurrent downloads
- **Document Processing**: `MarkItDown` for PDF conversion, `BeautifulSoup4` for HTML parsing
- **Scientific Computing**: `numpy`/`scipy` for chemical calculations
- **Fuzzy Matching**: `fuzzywuzzy` for compound name matching
- **Build System**: Modern Python packaging with Hatchling

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
- Run `python -m pytest` for full test suite

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

### Pipeline Optimization Flow
The Makefile implements an optimized pipeline sequence:

1. Early hydration normalization (Stage 6) - Fixes hydrate inconsistencies BEFORE advanced matching
2. Early ingredient enhancement (Stage 7) - Converts ingredient codes using normalized compounds
3. Enhanced compound matching (Stage 8) - Uses normalized base compounds for better ChEBI matches
4. OAK CHEBI mapping (Stage 9) - Ontology-based annotations with improved compound set
5. Property calculation (Stage 11) - Uses hydration-corrected molecular weights

This ordering ensures downstream steps work with clean, consistent compound data.