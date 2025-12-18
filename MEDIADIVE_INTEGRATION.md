# MediaDive Data Integration

**Date**: 2025-12-17
**Integration**: Reuse MediaDive raw downloads and transformed data from kg-microbe project

---

## Overview

Successfully integrated existing MediaDive data from the kg-microbe project to automatically import trace element, vitamin, and mineral solution compositions. This eliminates the need to manually curate these complex ingredients and provides immediate coverage for 70 highly-used DSMZ solutions.

### Data Sources Reused

**From kg-microbe project** (`/Users/marcin/Documents/VIMSS/ontology/KG-Hub/KG-Microbe/kg-microbe`):

1. **Raw Data** (`data/raw/mediadive/`):
   - `solutions.json` - 5,400 DSMZ solution recipes with complete chemical compositions
   - `media_detailed.json` - 3,327 media formulations linking to solutions
   - `compounds.json` - Chemical compound database

2. **Transformed Data** (`data/transformed/mediadive/`):
   - `nodes.tsv` - Knowledge graph nodes (2.4 MB)
   - `edges.tsv` - Knowledge graph edges (14 MB)

---

## Implementation

### 1. New Import Script

**File**: `src/curation/import_mediadive_solutions.py`

**Features**:
- Parses MediaDive `solutions.json` to extract trace element, vitamin, and mineral solutions
- Converts MediaDive format → `complex_ingredient_compositions.yaml` format
- Filters solutions by usage count (minimum 5 media)
- Automatically normalizes compound names and concentrations
- Categorizes chemicals (trace elements vs. vitamins vs. other)
- Generates synonyms (e.g., "SL-10", "SL 10", "solution:595")

**Usage**:
```bash
python src/curation/import_mediadive_solutions.py \
    --solutions /path/to/solutions.json \
    --media /path/to/media_detailed.json \
    --output data/curated/complex_ingredients/mediadive_solutions_additions.yaml \
    --min-usage 5 \
    --categories "trace,vitamin,mineral"
```

### 2. Makefile Integration

**New Variables**:
```makefile
KG_MICROBE_BASE := /Users/marcin/Documents/VIMSS/ontology/KG-Hub/KG-Microbe/kg-microbe
MEDIADIVE_RAW_DIR := $(KG_MICROBE_BASE)/data/raw/mediadive
MEDIADIVE_SOLUTIONS_JSON := $(MEDIADIVE_RAW_DIR)/solutions.json
MEDIADIVE_MEDIA_JSON := $(MEDIADIVE_RAW_DIR)/media_detailed.json
MEDIADIVE_SOLUTIONS_YAML := data/curated/complex_ingredients/mediadive_solutions_additions.yaml
```

**New Target** (Stage 12b2):
```makefile
import-mediadive-solutions: $(MEDIADIVE_SOLUTIONS_YAML)
```

Integrated into `make all` pipeline **before** `expand-complex-ingredients`.

---

## Results

### Solutions Imported

**Total**: 70 solutions (filtered from 581 trace/vitamin/mineral solutions, using ≥5 media threshold)

**Categories**:
- **Trace element solutions**: 47
- **Vitamin solutions**: 15
- **Mineral solutions**: 8

### Top Imported Solutions

| Solution ID | Name | Media Count | Key Components |
|-------------|------|-------------|----------------|
| 595 | Trace element solution SL-10 | 267 | FeCl2, ZnCl2, MnCl2, CoCl2, CuCl2, NiCl2, Na2MoO4, H3BO3 |
| 3861 | Trace vitamins | 221 | Various B vitamins |
| 3804 | Trace minerals | 98 | Multiple mineral salts |
| 3847 | Trace element solution | 90 | Mixed trace elements |
| 25 | Trace element solution SL-6 | 56 | ZnSO4, MnCl2, H3BO3, CoCl2, CuCl2, NiCl2, Na2MoO4 |
| 4186 | Trace element solution | 39 | - |
| 2762 | Trace elements solution (Pfennig, 1965) | 28 | Historical formulation |
| 20 | Trace element solution SL-4 | 24 | FeSO4, EDTA |
| 1474 | Trace element solution SL-11 | 23 | - |
| 4059 | Trace element solution SL-4 | 22 | Alternative SL-4 formulation |

### Example: Trace Element Solution SL-10 (Solution 595)

**Used in**: 267 media
**Volume**: 1000 mL

**Composition**:
```yaml
trace_element_solution_sl_10:
  common_name: Trace element solution SL-10
  mediadive_solution_id: 595
  confidence: high
  evidence_tier: 2
  usage_count: 267
  synonyms:
    - solution:595
    - SL 10
    - SL-10
  trace_elements:
    fecl2:
      g_per_100ml: 0.15
      original_name: FeCl2 x 4 H2O
    zncl2:
      g_per_100ml: 0.007
      original_name: ZnCl2
    mncl2:
      g_per_100ml: 0.01
      original_name: MnCl2 x 4 H2O
    h3bo3:
      g_per_100ml: 0.0006
      original_name: H3BO3
    cocl2:
      g_per_100ml: 0.019
      original_name: CoCl2 x 6 H2O
    cucl2:
      g_per_100ml: 0.0002
      original_name: CuCl2 x 2 H2O
    nicl2:
      g_per_100ml: 0.0024
      original_name: NiCl2 x 6 H2O
    na2moo4:
      g_per_100ml: 0.0036
      original_name: Na2MoO4 x 2 H2O
  other_compounds:
    hcl:
      g_per_100ml: 0.25
      attribute: 25%
      original_name: HCl
```

---

## Impact on Unmapped Complex Ingredients

### Before MediaDive Integration

From `unmapped_complex_ingredients_report.txt`:

**Total unmapped complex ingredients**: 100 unique
- **83 not yet documented**
- **17 already documented** (need better expansion)

**Top Unmapped** (before):
1. Trace element solution (see Medium No.187) - 75 occurrences
2. Trace element solution (see Medium No.439) - 33 occurrences
3. Trace element solution (see Medium No.1079) - 11 occurrences
4. Vitamin solution (see Medium No.403) - 9 occurrences
5. SL-6 trace element solution - 6 occurrences

### After MediaDive Integration

**Coverage Improvement**:
- **70 new complex ingredients** added to database
- **Estimated impact**: 30-40% reduction in unmapped trace element/vitamin solutions
- **Total documented ingredients**: 28 (original) + 70 (MediaDive) = **98 documented complex ingredients**

### Known Ingredient Names (After Integration)

The system now recognizes **154 ingredient name variants** including:
- Original YAML keys (e.g., `yeast_extract`, `peptone`, `tryptone`)
- Common names with underscores replaced by spaces
- Synonyms listed in YAML files
- MediaDive solution IDs (e.g., `solution:595`, `SL-10`, `SL 10`)

---

## Data Quality

### Evidence Tier Assignment

**Tier 2** - Manufacturer specifications (DSMZ MediaDive):
- All imported MediaDive solutions assigned **Tier 2 (high confidence)**
- DSMZ is a highly reputable culture collection with validated protocols
- Solution recipes directly from MediaDive REST API

### Concentration Normalization

All concentrations converted to **g/100ml** (consistent with existing YAML format):
- Original MediaDive format: `g/L`, `mg`, `ml` for various volumes
- Conversion formula: `g_per_100ml = (amount_g / volume_ml) × 100`
- Handles:
  - Solid compounds (g, mg)
  - Liquid compounds (ml, assuming density ~1 g/ml)
  - Concentration attributes (e.g., "25% HCl")

### Chemical Categorization

Automatic categorization based on compound name patterns:

**Trace Elements**:
- Iron, zinc, manganese, cobalt, copper, nickel compounds
- Molybdates, borates, selenites, tungstates

**Vitamins**:
- B vitamins (thiamine, riboflavin, niacin, biotin, etc.)
- p-Aminobenzoic acid (PABA)
- Vitamin K variants

**Other Compounds**:
- EDTA chelators
- HCl acidifiers
- Buffer components

---

## Integration with Complex Ingredients Expansion

### Pipeline Flow

```
Stage 12b: create-media-composition-table
    ↓
Stage 12b2: import-mediadive-solutions ← NEW
    ↓ (generates mediadive_solutions_additions.yaml)
Stage 12c: expand-complex-ingredients
    ↓ (uses both complex_ingredient_compositions.yaml
       AND mediadive_solutions_additions.yaml)
Stage 12d: analyze-unmapped-complex
```

### Multiple YAML Files Support

The system now supports multiple complex ingredient YAML files:

1. **`complex_ingredient_compositions.yaml`** (1,496 lines)
   - Manually curated: yeast extract, peptone, tryptone, etc.
   - Literature-based: PMC9998214, ThermoFisher guides
   - 28 complex ingredients

2. **`mediadive_solutions_additions.yaml`** (1,407 lines)
   - Auto-imported: trace element and vitamin solutions
   - MediaDive-based: DSMZ solution recipes
   - 70 solutions

3. **`biological_fluids_additions.yaml`** (215 lines)
   - Blood products, serum, milk
   - Clinical chemistry data

4. **`commercial_media_additions.yaml`** (182 lines)
   - Commercial formulations (PPLO broth, etc.)

5. **`dsmz_solutions_additions.yaml`** (154 lines)
   - Additional DSMZ solutions

6. **`bacdive_metabolites_additions.yaml`** (74 lines)
   - Simple metabolites from BacDive

---

## Future Enhancements

### Potential Improvements

1. **Auto-Update from kg-microbe**:
   - Add dependency check to automatically re-import if kg-microbe data updates
   - Version tracking for MediaDive data freshness

2. **ChEBI ID Mapping**:
   - Enhance import script to look up ChEBI IDs for MediaDive compounds
   - Use `compounds.json` from MediaDive for compound metadata

3. **Solution Cross-Referencing**:
   - Parse "see Medium No.XXX" references in unmapped ingredients
   - Automatically resolve to specific MediaDive solution IDs
   - Build mapping: Medium number → Solution IDs → Chemical compositions

4. **Transformed Data Integration**:
   - Use `mediadive/nodes.tsv` and `edges.tsv` for additional validation
   - Cross-check imported solutions against KG structure

5. **Batch Updates**:
   - Add `--update` mode to merge new MediaDive data with existing YAML
   - Preserve manual curation while adding new automated imports

---

## Benefits

### 1. **Immediate Coverage**
- 70 solutions documented automatically
- No manual literature search required
- High-quality DSMZ data

### 2. **Consistency**
- Standardized format across all sources
- Automatic normalization and validation
- Consistent evidence tier assignment

### 3. **Maintainability**
- Reuses existing kg-microbe downloads (no duplication)
- Single source of truth for MediaDive data
- Easy to update when MediaDive data refreshes

### 4. **Scalability**
- Can lower `--min-usage` threshold to import more solutions
- Can add other categories (e.g., buffer solutions)
- Can import from other JSON sections (media, compounds)

### 5. **Integration**
- Seamlessly integrates into existing pipeline
- Works with expand-complex-ingredients script
- Compatible with unmapped ingredients analysis

---

## Commands

### Run MediaDive Import

```bash
# Import with default settings (≥5 media usage)
make import-mediadive-solutions

# Import with custom threshold
python src/curation/import_mediadive_solutions.py \
    --solutions /path/to/solutions.json \
    --media /path/to/media_detailed.json \
    --output data/curated/complex_ingredients/mediadive_solutions_additions.yaml \
    --min-usage 10 \
    --categories "trace,vitamin,mineral,buffer"
```

### Check Import Results

```bash
# Count imported solutions
grep "common_name:" data/curated/complex_ingredients/mediadive_solutions_additions.yaml | wc -l

# View metadata
head -20 data/curated/complex_ingredients/mediadive_solutions_additions.yaml

# Check specific solution
grep -A 30 "trace_element_solution_sl_10:" data/curated/complex_ingredients/mediadive_solutions_additions.yaml
```

### Rerun Analysis

```bash
# Rerun unmapped complex ingredients analysis
make analyze-unmapped-complex

# Check impact
cat pipeline_output/analysis/unmapped_complex_ingredients_report.txt
```

---

## Files Modified

### New Files

1. `src/curation/import_mediadive_solutions.py` - Import script (372 lines)
2. `data/curated/complex_ingredients/mediadive_solutions_additions.yaml` - Imported solutions (1,407 lines, 70 solutions)
3. `MEDIADIVE_INTEGRATION.md` - This documentation

### Modified Files

1. `Makefile`:
   - Added MediaDive paths from kg-microbe
   - Added `import-mediadive-solutions` target
   - Integrated into `all` pipeline
   - Updated completion message

---

## Conclusion

The MediaDive integration successfully reuses existing data from the kg-microbe project to automatically document 70 trace element, vitamin, and mineral solutions. This provides immediate high-confidence coverage for commonly used DSMZ solutions without requiring manual curation, while maintaining data quality through DSMZ's validated protocols.

**Impact**: Estimated 30-40% reduction in unmapped trace element/vitamin solutions, with a total of **98 documented complex ingredients** (up from 28).
