# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MicroMediaParam is a bioinformatics pipeline for extracting, processing, and analyzing microbial growth media composition data from BacDive/MediaDive and DSMZ sources. It maps chemical compounds to knowledge graph entities (ChEBI, KEGG, PubChem) and computes physical-chemical properties (pH, salinity).

**Dataset**: 23,181 chemical entries from 1,807 microbial growth media with 72% ChEBI coverage.

## Development Commands

```bash
# Environment (prefer uv)
uv sync                                    # Install dependencies
uv pip install -e ".[dev]"                 # Install dev dependencies

# Code quality
black src/ *.py && isort src/ *.py         # Format
flake8 src/ *.py && mypy src/              # Lint and type check

# Testing
make test                                   # Full test suite
python -m pytest -v                        # Pytest only

# Pipeline execution
make all                                   # Complete pipeline (30-60 min)
make status                                # Check pipeline status
make validate                              # Verify outputs
```

## Pipeline Architecture

The Makefile orchestrates a 12-stage pipeline. Run `make help` for all targets.

### Key Stages

| Stage | Target | Description |
|-------|--------|-------------|
| 1 | `data-acquisition` | Download PDFs/JSON from MediaDive/DSMZ |
| 2 | `data-conversion` | Convert PDFs to markdown, extract compositions |
| 3 | `db-mapping` | Build chemical properties DB (ingredient → pKa) |
| 4 | `kg-mapping-initial` | Initial ChEBI/KEGG/PubChem mapping |
| 5 | `solution-expansion` | Expand "solution:241" → individual chemicals |
| 6 | `normalize-hydration-early` | Normalize hydrates BEFORE matching |
| 7 | `enhance-ingredients-early` | Convert ingredient codes → ChEBI |
| 8-10 | `kg-compound-matching` | OAK ChEBI + fuzzy matching + merge |
| 10.5 | `kg-enhance-all` | CAS→ChEBI + formula + microbio products (+16%) |
| 11 | `compute-properties` | Calculate pH, salinity, ionic strength |
| 12 | `media-summary` | Generate final summary table |

### Two Mapping Strategies

1. **DB Mapping** (ingredient → pKa, properties): For pH/salinity calculations
2. **KG Mapping** (ingredient → ChEBI IDs): For semantic analysis

## Source Code Structure

```
src/
├── scripts/     # Main pipeline scripts (parse, download, convert, map, compute)
├── mapping/     # KG mapping: unified_mapper.py, formula_matcher.py, cas_to_chebi_upgrader.py
├── hydration/   # Hydrate normalization: normalize_hydration_enhanced.py
├── analysis/    # Chemical analysis: extract_non_chebi_compounds.py
├── quality/     # Validation: calculate_molecular_weights.py, fix_*.py
├── tools/       # Utilities: complete_solution_expansion.py
├── chem/        # IUPAC and PubChem integration
└── attic/       # Legacy scripts (archived)
```

### Key Output Files

- `pipeline_output/kg_mapping/composition_kg_mapping.tsv` - Initial mappings
- `pipeline_output/solution_expansion/composition_kg_mapping_expanded_solutions.tsv` - After solution expansion
- `pipeline_output/merge_mappings/high_confidence_compound_mappings.tsv` - Final high-quality mappings
- `pipeline_output/merge_mappings/high_confidence_compound_mappings_final.tsv` - After all enhancements (72% ChEBI)
- `pipeline_output/db_mapping/chemical_properties.tsv` - pKa and molecular properties

## Critical Implementation Details

### Hydration State Handling

Hydration normalization happens EARLY (Stage 6) to ensure consistent base compounds:
- "CaCl2 x 2 H2O" and "CaCl2 x 6 H2O" → same base ChEBI, different molecular weights
- Patterns: `6-hydrate`, `6H2O`, `x H2O`, `·6H2O`
- MW calculation: `MW_hydrated = MW_base + (n × 18.015)`

### DSMZ Solution Expansion

Solution references (e.g., "solution:241") are expanded into individual chemicals by:
1. Downloading solution PDFs from DSMZ MediaDive REST API
2. Parsing compositions with `src/tools/enhanced_solution_parser.py`
3. Adjusting concentrations based on solution usage ratios

### Mapping Enhancement Pipeline (Stage 10.5)

Three strategies achieve +16% coverage gain (56% → 72%):
1. `cas_to_chebi_upgrader.py` - CAS-RN → ChEBI (+94 compounds)
2. `apply_formula_matching.py` - Hydrated formulas (+56 compounds)
3. `apply_microbio_products.py` - Biological products (+21 semantic IDs)

### Unified Mapping Architecture

Core components in `src/mapping/`:
- `compound_normalizer.py` - Name normalization (hydrates, stereochemistry)
- `matching_strategies.py` - Strategy pattern for different approaches
- `unified_mapper.py` - Main mapping engine
- `formula_matcher.py` - Hydrated chemical formulas
- `microbio_products.py` - Curated biological products dictionary

### BacDive Metabolites Mapping

Additional unmapped chemicals from `data/unmapped/bacdive_metabolites_without_chebi_ids.tsv`:
- **19,129 records → 154 unique metabolites** (optimized for processing)
- Top metabolites: Potassium 5-ketogluconate (7,610), Potassium 2-ketogluconate (6,705), casein (1,585)
- Pipeline: `make bacdive-metabolites-mapping` (extract → OAK annotate → apply)
- Output: `pipeline_output/bacdive_metabolites/bacdive_metabolites_chebi_mappings.tsv`

## Common Workflows

```bash
# Debug a specific stage
make status                               # See what's present
make solution-expansion                   # Run just that stage
cat *.log                                 # Check logs

# Work with OAK ChEBI mappings
make oak-chebi-status                     # Check status
make kg-oak-chebi-mapping                 # Run full OAK pipeline

# Map BacDive metabolites (19k records → 154 unique)
make bacdive-metabolites-status           # Check status
make bacdive-metabolites-mapping          # Full pipeline

# Quick iteration
make quick                                # Smaller dataset for testing

# Chemical database updates
make iupac-status && make pubchem-status  # Check database status
make db-mapping                           # Rebuild properties DB

# Run individual mapping enhancements
python3 src/mapping/cas_to_chebi_upgrader.py --chebi-file chebi_nodes.tsv --input input.tsv --output output.tsv
python3 -m src.mapping.unified_mapper --kg-nodes merged-kg_nodes.tsv --composition-dir media_compositions
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `make validate` fails | Run `make status` to see what's missing; pipeline creates files in `pipeline_output/kg_mapping/` not separate directories |
| Missing ChEBI matches | File only created if unmapped compounds exist; check `make oak-chebi-status` |
| Property calculation fails | Verify `chemical_properties.tsv` exists; check `compute_media_properties.log` |
| Stage fails | Check previous stage completed; review stage log; run `make status` |

## Code Style

- Python 3.10+, Black (88 chars), isort (black profile)
- Type hints required (`mypy --disallow_untyped_defs`)
- Async I/O: `aiohttp`/`aiofiles` for downloads
- Document processing: MarkItDown for PDFs, BeautifulSoup4 for HTML
