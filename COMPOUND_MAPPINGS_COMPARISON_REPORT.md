# Compound Mappings Comparison Report

## Files Compared

### Baseline (Previous Version)
- **File**: `pipeline_output/merge_mappings/compound_mappings_strict_final_BASELINE.tsv`
- **Size**: 3.2 MB
- **Date**: Dec 17, 2024 20:54
- **Total Entries**: 17,658 (+ 1 header = 17,659 lines)
- **Columns**: 36

### Current (New Pipeline Output)
- **File**: `pipeline_output/merge_mappings/compound_mappings_strict_final.tsv`
- **Size**: 3.2 MB
- **Date**: Dec 18, 2024 00:11
- **Total Entries**: 17,658 (+ 1 header = 17,659 lines)
- **Columns**: 36

### Hydrate-Enhanced (New Feature)
- **File**: `pipeline_output/merge_mappings/compound_mappings_strict_final_hydrate.tsv`
- **Size**: 3.3 MB
- **Date**: Dec 18, 2024 00:16
- **Total Entries**: 17,658 (+ 1 header = 17,659 lines)
- **Columns**: 39 (3 additional columns)

---

## Baseline vs Current: ID Distribution

| ID Type | BASELINE | CURRENT | Change |
|---------|----------|---------|--------|
| **CHEBI** | 14,526 | 14,526 | 0 |
| **PubChem** | 884 | 885 | +1 |
| **CAS-RN** | 1,176 | 1,176 | 0 |
| **ingredient** | 971 | 970 | -1 |
| **FOODON** | 26 | 26 | 0 |
| **UBERON** | 28 | 28 | 0 |
| **KEGG** | 21 | 21 | 0 |
| **medium** | 20 | 20 | 0 |
| **Unmapped** | 4 | 4 | 0 |
| **Other** | 2 | 2 | 0 |

### Semantic ID Coverage

| Metric | BASELINE | CURRENT | Change |
|--------|----------|---------|--------|
| **Total Semantic IDs** | 15,465 | 15,465 | 0 |
| **Coverage %** | 87.6% | 87.6% | 0 |

### Unique Compounds

| Metric | BASELINE | CURRENT |
|--------|----------|---------|
| **ChEBI-mapped** | 686 | 686 |
| **Total unique** | 1,047 | 1,047 |
| **ChEBI coverage** | 65.5% | 65.5% |

---

## Key Difference: BASELINE vs CURRENT

**Only 1 entry changed:**

| Field | BASELINE | CURRENT |
|-------|----------|---------|
| Medium | dsmz_973_composition | dsmz_973_composition |
| Compound | Na2Se3 x 5 H2O | Na2Se3 x 5 H2O |
| **mapped ID** | **ingredient:870** | **PUBCHEM.COMPOUND:24934.0** |

**Impact:**
- One ingredient code was upgraded to a PubChem ID
- This represents a semantic mapping improvement (PubChem > generic ingredient code)
- However, this could also represent a regression if the ingredient code was manually curated

**Note**: The pipeline appears stable with minimal drift from baseline.

---

## Hydrate-Enhanced Version: New Features

### Additional Columns (3 total)

1. **hydrated_chebi_id** - ChEBI ID specifically for the hydrated form
2. **hydrated_chebi_label** - ChEBI label for the hydrated form
3. **hydrate_mapping_source** - Source/method used for hydrate mapping

### Hydrate Mapping Statistics

| Metric | Value |
|--------|-------|
| **Total entries** | 17,658 |
| **Entries with hydrated ChEBI IDs** | 1,130 |
| **Hydrate coverage** | 6.4% |

### What This Means

The hydrate-enhanced file provides:

1. **Dual Mapping**: For hydrated compounds, both base and hydrated ChEBI IDs are provided
   - Example: `MgCl2 x 6 H2O`
     - `mapped`: Base compound mapping (if available)
     - `base_chebi_id`: CHEBI ID for MgCl2 (anhydrous)
     - `hydrated_chebi_id`: CHEBI ID for MgCl2·6H2O (hexahydrate)

2. **Improved Specificity**: 1,130 hydrated compounds now have precise ChEBI IDs matching their hydration state

3. **Source Tracking**: The mapping source is documented for reproducibility

---

## File Size Comparison

| File | Size | Size Increase |
|------|------|---------------|
| BASELINE | 3.2 MB | - |
| CURRENT | 3.2 MB | 0 KB |
| HYDRATE | 3.3 MB | +100 KB |

The hydrate file is 3% larger due to the additional columns and hydrate-specific metadata.

---

## Recommendations

### 1. Verify Na2Se3 Mapping Change

The change from `ingredient:870` to `PUBCHEM.COMPOUND:24934.0` should be reviewed:
- **Action**: Check if PubChem 24934 correctly represents Na2Se3 x 5 H2O
- **Verify**: Whether ingredient:870 was a manual curation that should be preserved

### 2. Use Hydrate File for Downstream Analysis

For media property calculations and semantic analysis:
- **Use**: `compound_mappings_strict_final_hydrate.tsv`
- **Benefit**: More accurate molecular weights and ChEBI mappings for 1,130 hydrated compounds
- **Impact**: Better pH, salinity, and ionic strength calculations

### 3. Monitor Pipeline Stability

The current pipeline shows excellent stability:
- **Observation**: Only 1 entry changed out of 17,658
- **Confidence**: High reproducibility
- **Action**: Continue monitoring for unexpected changes

---

## Summary

✅ **BASELINE → CURRENT**: Highly stable, only 1 mapping changed
✅ **CURRENT → HYDRATE**: 1,130 compounds enhanced with hydrate-specific ChEBI IDs
✅ **Overall Quality**: 87.6% semantic coverage maintained
✅ **Recommendation**: Adopt hydrate-enhanced file for improved chemical accuracy

**Generated**: 2025-12-18
