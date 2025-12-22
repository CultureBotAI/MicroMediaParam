# Pipeline Output ATTIC

This directory contains archived pipeline outputs that are no longer part of the current pipeline but are preserved for reference.

## Archived: 2025-12-22

### Directories Archived

1. **analysis/** (40 KB)
   - Old unmapped complex ingredients analysis
   - Files: unmapped_complex_ingredients_priority.tsv, unmapped_complex_ingredients_report.txt
   - Replaced by: `pipeline_output/unmapped_analysis/`
   - Date: Dec 17-18, 2024

2. **properties/** (20 KB)
   - Old media property calculations from initial pipeline run
   - Files: medium_1-5_properties.json
   - Replaced by: `pipeline_output/property_calculation/media_properties/`
   - Date: Sep 21, 2024

3. **validation/** (92 KB)
   - Old validation reports and remediated mappings
   - Files: validation_report.tsv, remediated_mappings.tsv
   - Replaced by: `pipeline_output/quality/` (current validation)
   - Date: Nov 24, 2024

4. **pipeline_output/** (nested duplicate)
   - Accidental nested directory created during early pipeline development
   - Empty except for old solution_expansion subdirectory
   - Date: Sep 24, 2024

## Current Active Pipeline Directories

The following directories are part of the active pipeline (as of Dec 2024):

### Core Pipeline Stages:
- `data_acquisition/` - Stage 1: Download media PDFs/JSON from MediaDive
- `data_conversion/` - Stage 2: Convert PDFs to text and extract compositions
- `db_mapping/` - Stage 3: Build chemical properties database
- `kg_mapping/` - Stage 4: Initial ChEBI/KEGG/PubChem mapping
- `solution_expansion/` - Stage 5: Expand solution references to chemicals
- `hydrate_normalization/` - Stage 6: Normalize hydrate states
- `ingredient_enhancement/` - Stage 7: Convert ingredient codes to ChEBI
- `compound_matching/` - Stage 8-10: OAK ChEBI + fuzzy matching
- `oak_chebi/` - Stage 8: OAK ChEBI mapping outputs
- `merge_mappings/` - Stage 10: Merge all mapping sources
- `property_calculation/` - Stage 11: Calculate pH, salinity, ionic strength
- `media_summary/` - Stage 12: Generate final summary table

### Enhancement Stages:
- `foodon_mapping/` - Stage 10.5c.5.7: FOODON/ENVO ontology mapping
- `bacdive_metabolites/` - BacDive metabolite ChEBI mapping
- `quality/` - Validation and quality control outputs
- `unmapped_analysis/` - Analysis of unmapped complex ingredients

## Notes

Files in this ATTIC are retained for:
- Historical reference
- Debugging previous pipeline runs
- Comparison with current pipeline outputs

These files are not used by `make all` or any current pipeline targets.

To fully remove these archived files:
```bash
rm -rf pipeline_output/ATTIC/
```

---
*Archived on: 2025-12-22*
*Archived by: Pipeline cleanup (commit 03abb01+)*
