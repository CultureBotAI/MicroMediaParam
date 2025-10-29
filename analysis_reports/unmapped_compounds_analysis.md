# Unmapped Compounds Analysis Report

Comprehensive analysis of unmapped chemical compounds in the MicroMediaParam pipeline.

**Generated from**: `pipeline_output/merge_mappings/high_confidence_compound_mappings.tsv`

---

## Executive Summary

- **Total unique compounds**: 1,043
- **ChEBI mapped**: 587 (56.3%)
- **Unmapped**: 211 (20.2%)

**Improvement potential**: +115 compounds (+11.0% coverage)

**Target coverage**: 67.3% ChEBI mapped

---

## Unmapped Compound Clusters

### Complex/Buffer Solutions

**Count**: 76 compounds

**Description**: References to other solutions or complex buffers

**Mapping Strategy**: Expand solution references, parse nested compositions

**Difficulty**: `hard`

**Expected Improvement**: +30 compounds

**Examples**:

1. `Basal salts solution`
2. `L-Cysteine·HCl·H2O solution*`
3. `Metal solution (see below)`
4. `Methanol solution (see below)*`
5. `Mineral solution (see Medium No.976`
6. `Mineral solution (see Medium No.976)`
7. `MnCl2 solution see below`
8. `Phosphate buffer stock solution`
9. `Phosphates solution`
10. `Riboflavin solution (see Medium No.462)*`
11. `SL-6 trace element solution (see Medium No.167)`
12. `SOLUTION A`
13. `Salt Solution I`
14. `Selenite tungstate solution (see Medium No.431)`
15. `Selenite-Tungstate Solution:`

*... and 61 more*

---

### Animal/Biological Products

**Count**: 35 compounds

**Description**: Extracts, peptones, animal-derived products

**Mapping Strategy**: Create mapping dictionary for common microbiology products

**Difficulty**: `medium`

**Expected Improvement**: +15 compounds

**Examples**:

1. `5% defibrinated sheep blood`
2. `Beef Extract`
3. `Beef extract`
4. `Calf serum`
5. `Casamino Acid`
6. `Casamino Acids`
7. `Casamino acid`
8. `Casamino acids`
9. `Casamino acids (BD)`
10. `Casaminoacids`
11. `Clarified rumen fluid`
12. `Defibrinated Blood`
13. `Defibrinated Sheep Blood`
14. `Dung extract`
15. `Fish meat extract`

*... and 20 more*

---

### Other/Uncategorized

**Count**: 35 compounds

**Description**: Compounds not fitting other categories

**Mapping Strategy**: Manual review and case-by-case mapping

**Difficulty**: `hard`

**Expected Improvement**: +10 compounds

**Examples**:

1. `Casmino Acid`
2. `Casmino acids`
3. `Cellobiose or Cellulose MN 300`
4. `Charcoal-filtered, natural seawater`
5. `Corn steep liquor`
6. `Cysteine-HCL x H2O`
7. `Cysteine-HCl x H2O`
8. `Fe2(SO4)3 x n H2O`
9. `Ferric citrate monohydrate`
10. `Hipolypepton`
11. `L-Cysteine-HCl x H2O`
12. `L-Cystein·HCl·H2O`
13. `L-cysteine-HCl x H2O`
14. `LB broth powder`
15. `Leibovitz's L-15 medium`

*... and 20 more*

---

### Chemical Formulas with Hydrates

**Count**: 26 compounds

**Description**: Chemical formulas with hydration notation (x N H2O pattern)

**Mapping Strategy**: Strip hydration, normalize formula → ChEBI lookup

**Difficulty**: `easy`

**Expected Improvement**: +20 compounds

**Examples**:

1. `CoCl2 x 6 H2O`
2. `Cystein-HCl x 2 H2O (5% (w/v))`
3. `Fe(NH4)(SO4)2 x 12 H2O`
4. `FeCl2 x 6 H2O`
5. `K2HPO4 x 3 H2O`
6. `KH2PO4 x 7 H2O`
7. `MnSO4 x 1 H2O`
8. `MnSO4 x 2 H2O`
9. `MnSO4 x 4 H2O`
10. `MnSO4 x 5 H2O`
11. `MnSO4 x 6 H2O`
12. `MnSO4 x 7 H2O`
13. `Na2HPO4 x 12 H2O`
14. `Na2HPO4 x 2 H2O`
15. `Na2O4W x 2 H2O`

*... and 11 more*

---

### Simple Chemical Formulas

**Count**: 18 compounds

**Description**: Pure chemical formulas without hydration

**Mapping Strategy**: Direct formula lookup in ChEBI/PubChem

**Difficulty**: `easy`

**Expected Improvement**: +15 compounds

**Examples**:

1. `H3BO4`
2. `K2HSO4`
3. `K2SO4·7H2O`
4. `MnCl2·6H2O`
5. `MnCl4·4H2O`
6. `MnSO4 x 7H2O`
7. `Na2HPO4 x 2H2O`
8. `Na2HPO4 x2 H2O`
9. `Na2HPO4·2H2O`
10. `Na2HPO4·6H2O`
11. `Na2S2O3`
12. `Na2S2O4·2H2O`
13. `Na2SeO3·5H2O`
14. `Na2WO4 x 2H2O`
15. `NaH2PO4 x 2H2O`

*... and 3 more*

---

### Commercial/Proprietary Products

**Count**: 14 compounds

**Description**: Brand-name commercial products (Bacto, Difco, etc.)

**Mapping Strategy**: Research equivalents, create manual mapping table

**Difficulty**: `medium`

**Expected Improvement**: +10 compounds

**Examples**:

1. `Bacto Soytone`
2. `Bacto beef extract`
3. `Bacto-Tryptone`
4. `Difco Marine Broth 2216`
5. `Difco marine broth (Difco 2216)`
6. `Difco marine broth (Difco2216)`
7. `Fastidious Anaerobe Basal Broth (OXOID)`
8. `Isovitalex`
9. `Leptospira Enrichment EMJH`
10. `PPLO Broth`
11. `PPLO broth`
12. `PPLO-Broth`
13. `Peptone (Oxoid)`
14. `Sigma Sea salts`

---

### Vitamin References

**Count**: 7 compounds

**Description**: Vitamin solutions and references

**Mapping Strategy**: Expand vitamin references to specific compounds

**Difficulty**: `medium`

**Expected Improvement**: +5 compounds

**Examples**:

1. `Trace vitamin (see Medium No.197)`
2. `Trace vitamins (See Medium No.197)`
3. `Trace vitamins (see Medium No.197)`
4. `Trace vitamins (see Medium No.197)*`
5. `Trace vitamins(see Medium No.197)`
6. `Trace vitamins* (see Medium No. 197)`
7. `Trace vitamins* (see Medium No.197)`

---

## CAS-RN to ChEBI Upgrade Opportunity

**Current CAS-RN mappings**: 191 unique compounds

**Upgrade potential**: ~120 compounds (63% success rate)

**Strategy**: Cross-reference CAS-RN numbers with ChEBI database

**Sample CAS-RN mappings**:

1. `tryptone` → `CAS-RN:84843-69-6`
2. `yeast extract` → `CAS-RN:8013-01-2`
3. `soy peptone` → `CAS-RN:91079-46-8`
4. `peptone` → `CAS-RN:73049-73-7`
5. `sodium bicarbonate` → `CAS-RN:144-55-8`
6. `Malt extract` → `CAS-RN:8002-48-0`
7. `Yeast extract` → `CAS-RN:8013-01-2`
8. `NaNO3` → `CAS-RN:7631-99-4`
9. `K2CrO4` → `CAS-RN:7789-00-6`
10. `MnCl2·4H2O` → `CAS-RN:20603-88-7`
11. `Na2MoO4·2H2O` → `CAS-RN:10102-40-6`
12. `Na2SiO3.9H2O` → `CAS-RN:13517-24-3`
13. `Fe2(SO4)3 x X H2O` → `CAS-RN:15244-10-7`
14. `MgSO4 x 7 H2O` → `CAS-RN:10034-99-8`
15. `Na2SiO3 x 9 H20` → `CAS-RN:13517-24-3`
16. `Na2S2O3 x 5H2O` → `CAS-RN:10102-17-7`
17. `Yeast extract` → `CAS-RN:8013-01-2`
18. `NaS2O3` → `CAS-RN:7772-98-7`
19. `MnCl2 x 4 H2O` → `CAS-RN:20603-88-7`
20. `Tryptone` → `CAS-RN:84843-69-6`

---

## Implementation Roadmap

### Quick Wins (Easy, High Impact)

- **Chemical Formulas with Hydrates**: +20 compounds
  - Strategy: Strip hydration, normalize formula → ChEBI lookup
- **Simple Chemical Formulas**: +15 compounds
  - Strategy: Direct formula lookup in ChEBI/PubChem

### Medium Effort (Medium Impact)

- **Animal/Biological Products**: +15 compounds
  - Strategy: Create mapping dictionary for common microbiology products
- **Commercial/Proprietary Products**: +10 compounds
  - Strategy: Research equivalents, create manual mapping table
- **Vitamin References**: +5 compounds
  - Strategy: Expand vitamin references to specific compounds
- **Malformed/Incomplete Entries**: +10 compounds
  - Strategy: Clean prefixes, parse structured text

### High Effort (Variable Impact)

- **Complex/Buffer Solutions**: +30 compounds
  - Strategy: Expand solution references, parse nested compositions
- **Other/Uncategorized**: +10 compounds
  - Strategy: Manual review and case-by-case mapping

### Not Feasible

- **Media Names/Codes**: 0 compounds
  - Reason: These are not true chemical compounds

---

## Recommended Next Steps

1. **Implement CAS-to-ChEBI upgrader** - Highest ROI, +120 compounds
2. **Implement formula matcher** - Handle hydrated formulas, +20 compounds
3. **Create microbiology products dictionary** - Map common products, +15 compounds
4. **Enhance solution expansion** - Resolve complex references, +30 compounds
5. **Manual review remaining clusters** - Case-by-case analysis

