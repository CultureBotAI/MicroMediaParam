# Complex Ingredients Database - Curation Priorities

**Generated**: 2024-12-17
**Database Version**: 1.1.0
**Purpose**: Prioritized list of enhancements needed for complex ingredient decomposition system

---

## Executive Summary

**Current State**:
- 28 complex ingredients documented across 4 YAML files
- 24 complex biological mixtures + 4 simple chemicals from BacDive
- 5 DSMZ solutions integrated (selenite-tungstate variants, SL-6, Wolfe's, etc.)
- 95% of documented constituents have ChEBI IDs (excellent)
- Evidence tier system established (Tier 1-5)

**Key Issues**:
- 1 missing ChEBI ID (H3BO3 in SL-6 solution)
- 5 ingredients with circular/unresolved sub-ingredient references
- 4 biological fluids with low confidence (need more specific chemicals)
- Missing constituents in several ingredients (nucleotides, minerals)

**Goal**: Achieve 100% ChEBI coverage with specific chemical constituents prioritized over general categories.

---

## Priority 1: Critical Fixes (Immediate)

### 1.1 Missing ChEBI ID - H3BO3

**Location**: `complex_ingredient_compositions.yaml` line 957
**Ingredient**: sl_6_trace_element_solution
**Issue**: H3BO3 (boric acid) listed without ChEBI ID

**Fix**:
```yaml
other_compounds:
  boric_acid:
    chebi_id: CHEBI:33118  # boric acid
    mg_per_100ml: 30.0
    original_compound_name: H3BO3
```

**Impact**: Completes ChEBI coverage for DSMZ solutions
**Effort**: 5 minutes
**Priority**: HIGH

---

## Priority 2: Low-Confidence Biological Fluids (High Impact)

### 2.1 Defibrinated Sheep Blood

**Current State**:
- Confidence: low
- Components: 3 (hemoglobin, albumin, glucose)
- Coverage: Very incomplete

**Enhancement Needed**:
Add 15-20 specific chemicals from clinical chemistry literature:

**Proteins**:
- Immunoglobulins (IgG, IgA, IgM) - ChEBI IDs available
- Transferrin (CHEBI:47019)
- Fibrinogen removed (defibrination), but add note

**Minerals** (from sheep blood clinical ranges):
- Iron (CHEBI:18248) - ~15 mg/100ml (from hemoglobin)
- Sodium (CHEBI:26708) - ~320 mg/100ml
- Potassium (CHEBI:26216) - ~450 mg/100ml (higher in RBCs)
- Calcium (CHEBI:22984) - ~10 mg/100ml
- Magnesium (CHEBI:25107) - ~2 mg/100ml
- Chloride (CHEBI:17996) - ~370 mg/100ml
- Phosphate (CHEBI:18367) - ~5 mg/100ml

**Metabolites**:
- Lactate (CHEBI:24996) - ~10 mg/100ml
- Urea (CHEBI:16199) - ~30 mg/100ml
- Cholesterol (CHEBI:16113) - ~60 mg/100ml

**Vitamins**:
- Vitamin B12 (CHEBI:176843) - trace amounts
- Folate (CHEBI:27470) - trace amounts

**Sources to Add**:
- Tier 1: Clinical chemistry reference (e.g., Tietz Fundamentals of Clinical Chemistry)
- Tier 2: Veterinary blood composition database
- Minimum 2 sources required

**Expected Result**:
- Confidence: low → **medium**
- Components: 3 → **18-20**
- ChEBI coverage: 100%

**Impact**: Sheep blood common in 5-10% agar media (Streptococcus, Haemophilus cultures)
**Effort**: 3-4 hours (literature search + YAML editing)
**Priority**: HIGH

### 2.2 Blood Serum

**Current State**:
- Confidence: low
- Components: 4 (albumin, immunoglobulins, glucose, cholesterol)

**Enhancement Needed**:
Add specific amino acids, fatty acids, and hormones:

**Amino Acids** (free amino acids in serum):
- L-alanine, L-glycine, L-glutamine, etc. (8-10 most abundant)
- Source: Proteomics databases (Tier 2)

**Lipids**:
- Specific fatty acids: palmitic acid (CHEBI:15756), oleic acid (CHEBI:16196)
- Triglycerides (general category if specific unknown)

**Minerals**:
- Same as blood but without RBC contribution (lower K, higher Na)

**Expected Result**:
- Confidence: low → **medium-low**
- Components: 4 → **15-18**

**Impact**: Used in mycoplasma cultivation (5-20% v/v)
**Effort**: 2-3 hours
**Priority**: MEDIUM

### 2.3 Rumen Fluid

**Current State**:
- Confidence: low
- Components: 3 volatile fatty acids (VFAs)

**Enhancement Needed**:
Add specific minerals and trace VFAs:

**Additional VFAs**:
- Isobutyric acid (CHEBI:16135)
- Valeric acid (CHEBI:17418)
- Isovaleric acid (CHEBI:28484)

**Minerals**:
- Sodium, potassium, calcium, magnesium, phosphate (from rumen chemistry literature)

**Note**: Microbiota composition NOT quantifiable (too variable), keep as general note

**Expected Result**:
- Confidence: low → **medium-low**
- Components: 3 → **10-12**

**Impact**: Used in anaerobic media (10-40% v/v) for rumen bacteria
**Effort**: 2 hours
**Priority**: LOW (less common than blood)

---

## Priority 3: Resolve Circular Sub-Ingredient Dependencies

### 3.1 Issue: Ingredients Referencing Other Ingredients

**Problematic Ingredients**:
1. `brain_heart_infusion` → references `proteose_peptone`
2. `nutrient_broth` → references `beef_extract`, `peptone`
3. `lb_broth` → references `tryptone`, `yeast_extract`
4. `pplo_broth` → references `peptone`
5. `pplo_broth_bbl` → references `beef_extract`, `yeast_extract`

**Problem**: Expansion script needs to recursively expand these references.

**Solution Options**:

**Option A: Expand in YAML** (Recommended)
- Calculate constituent concentrations directly in YAML
- Example: lb_broth has 40% tryptone → multiply tryptone amino acids by 0.4

**Option B: Recursive Expansion in Code**
- Enhance `expand_complex_ingredients.py` to detect and resolve references
- Track depth to prevent infinite loops

**Recommendation**: **Option B** (code enhancement)
- More flexible for future ingredients
- Keeps YAML concise
- Allows for validation of circular dependencies

**Implementation**:
- Add `--resolve-references` flag to expansion script
- Track visited ingredients to detect cycles
- Maximum recursion depth: 3 levels

**Impact**: Enables correct expansion of 5 commercial media formulations
**Effort**: 4-6 hours (code enhancement + testing)
**Priority**: HIGH

---

## Priority 4: Add Missing Constituents to Existing Ingredients

### 4.1 Peptone - Missing Nucleotides and Minerals

**Current**: Only amino acids (17)

**Add**:

**Nucleotides** (from protein digest):
- Guanosine (CHEBI:16750) - ~0.5 g/100g
- Adenosine (CHEBI:16335) - ~0.3 g/100g
- Uridine (CHEBI:16704) - ~0.2 g/100g
- Source: ThermoFisher Peptones technical guide

**Minerals**:
- Sodium (CHEBI:26708) - ~1500 mg/100g (from NaCl)
- Chloride (CHEBI:17996) - ~2000 mg/100g
- Phosphorus (CHEBI:28659) - ~800 mg/100g
- Source: BD Difco peptone specifications

**Expected Result**:
- Components: 17 → **23-25**
- Coverage improvement for media using peptone (very common)

**Impact**: Peptone used in 60%+ of microbial media
**Effort**: 1-2 hours
**Priority**: MEDIUM

### 4.2 Beef Extract - Additional Nucleotides

**Current**: 2 nucleotides (IMP, GMP)

**Add**:
- Adenosine monophosphate (CHEBI:16027) - ~50 mg/100g
- Cytidine monophosphate (CHEBI:17361) - ~30 mg/100g
- Uridine monophosphate (CHEBI:16695) - ~20 mg/100g

**Source**: Meat extract composition literature (Tier 2)

**Expected Result**:
- Nucleotides: 2 → **5**

**Impact**: Beef extract common in nutrient broth, blood agar base
**Effort**: 1 hour
**Priority**: LOW

### 4.3 Malt Extract - Missing Vitamins and Minerals

**Current**: 3 vitamins, 4 minerals

**Add**:

**Vitamins**:
- Thiamine (CHEBI:18385) - ~0.2 mg/100g
- Biotin (CHEBI:15956) - ~0.01 mg/100g
- Pantothenic acid (CHEBI:7916) - ~1.0 mg/100g

**Minerals**:
- Zinc (CHEBI:27363) - ~0.5 mg/100g
- Manganese (CHEBI:18291) - ~0.3 mg/100g
- Copper (CHEBI:28694) - ~0.1 mg/100g

**Source**: Brewing science literature (Tier 2)

**Expected Result**:
- Vitamins: 3 → **6**
- Minerals: 4 → **7**

**Impact**: Malt extract used in fungal cultivation media
**Effort**: 1 hour
**Priority**: LOW

---

## Priority 5: New High-Impact Ingredients

### 5.1 Additional BacDive Metabolites

**From**: `data/unmapped/bacdive_metabolites_without_chebi_ids.tsv`

**High-occurrence metabolites to consider** (if used as complex ingredients):
- None identified - most are simple chemicals already mapped via microbio_products

**Action**: No new complex ingredients needed from BacDive data

**Priority**: N/A

### 5.2 Additional DSMZ Solutions

**Check**: Are there other high-occurrence DSMZ solutions not yet documented?

**Method**:
```bash
# Find most common solution references
grep -o "solution:[0-9]*" pipeline_output/kg_mapping/composition_kg_mapping.tsv | \
  sort | uniq -c | sort -rn | head -20
```

**Action**: Run query to identify candidates, then add top 3-5 to YAML

**Priority**: MEDIUM (after completing Priority 1-3)

---

## Priority 6: Validation Enhancements

### 6.1 Cross-Reference Validation Script

**Create**: `src/curation/cross_validate.py`

**Functions**:
1. **Detect circular dependencies**:
   - Ingredient A → Ingredient B → Ingredient A
   - Maximum recursion depth exceeded

2. **Verify ChEBI IDs exist**:
   - Query against `merged-kg_nodes.tsv` or ChEBI OBO file
   - Flag non-existent IDs

3. **Check molecular weight consistency**:
   - Calculate MW from formula
   - Compare with ChEBI database MW
   - Flag discrepancies >1%

4. **Validate concentration units**:
   - g_per_100g for solids
   - mg_per_100ml for solutions
   - mmol_per_100ml for VFAs
   - Flag inconsistencies

**Output**: TSV report with warnings and errors

**Priority**: MEDIUM (needed before full pipeline run)

### 6.2 Confidence Scoring Enhancement

**Add to** `evidence_validator.py`:

**Confidence calculation formula**:
```python
base_confidence = {
    'Tier 1': 0.9,
    'Tier 2': 0.8,
    'Tier 3': 0.6,
    'Tier 4': 0.4,
    'Tier 5': 0.3
}

# Bonuses
source_count_bonus = min(0.1, (num_sources - 1) * 0.05)  # +0.05 per extra source, max +0.1
range_bonus = 0.05 if has_concentration_range else 0
chebi_verified_bonus = 0.05 if chebi_id_exists_in_db else 0

final_confidence = min(1.0, base_confidence + source_count_bonus + range_bonus + chebi_verified_bonus)
```

**Expected Result**:
- Objective confidence scores for all ingredients
- Enables filtering by `--min-confidence 0.6`

**Priority**: MEDIUM

---

## Implementation Roadmap

### Phase 1: Quick Wins (1 day)
1. ✅ Fix H3BO3 missing ChEBI ID (5 min)
2. Add missing constituents to peptone (1-2 hours)
3. Add nucleotides to beef extract (1 hour)
4. Add vitamins/minerals to malt extract (1 hour)
5. Run validation to confirm fixes

### Phase 2: High-Impact Enhancements (2-3 days)
1. Enhance defibrinated_sheep_blood (3-4 hours literature search + YAML editing)
2. Enhance blood_serum (2-3 hours)
3. Implement recursive sub-ingredient expansion in code (4-6 hours)
4. Test expansion with lb_broth, nutrient_broth, pplo_broth

### Phase 3: Validation Infrastructure (1-2 days)
1. Create cross-validation script (4 hours)
2. Enhance confidence scoring (2 hours)
3. Add automated validation to Makefile
4. Test with full dataset

### Phase 4: Additional Curation (as needed)
1. Identify additional high-occurrence DSMZ solutions
2. Enhance rumen_fluid (if needed)
3. Add any newly identified complex ingredients from pipeline run

### Phase 5: Pipeline Integration (1 day)
1. Move complex ingredient expansion to Stage 9 (before compound matching)
2. Test impact on ChEBI coverage
3. Generate expansion impact report

**Total Estimated Effort**: 5-7 days

---

## Success Metrics

| Metric | Current | Target | Priority Phase |
|--------|---------|--------|----------------|
| ChEBI ID coverage | 95% | **100%** | Phase 1 |
| Defibrinated sheep blood components | 3 | **18-20** | Phase 2 |
| Blood serum components | 4 | **15-18** | Phase 2 |
| Ingredients with circular refs resolved | 0/5 | **5/5** | Phase 2 |
| Peptone components | 17 | **23-25** | Phase 1 |
| Automated validation | No | **Yes** | Phase 3 |
| Confidence scoring | Manual | **Automated** | Phase 3 |
| Pipeline integration | Stage 12c (late) | **Stage 9 (early)** | Phase 5 |

---

## Files to Modify

### Phase 1-2 (Curation)
- `data/curated/complex_ingredients/complex_ingredient_compositions.yaml`
- `data/curated/complex_ingredients/biological_fluids_additions.yaml`
- `data/curated/complex_ingredients/evidence/sources.yaml` (add new sources)

### Phase 2-3 (Code Enhancement)
- `src/scripts/expand_complex_ingredients.py` (add recursive expansion)
- `src/curation/cross_validate.py` (NEW - create)
- `src/curation/evidence_validator.py` (enhance confidence scoring)

### Phase 5 (Pipeline Integration)
- `Makefile` (move expansion target, add validation target)

---

## Next Actions

**Immediate** (today):
1. Fix H3BO3 ChEBI ID
2. Start literature search for sheep blood composition
3. Review ThermoFisher Peptones guide for nucleotide content

**This Week**:
1. Complete Phase 1 (quick wins)
2. Start Phase 2 (sheep blood enhancement)
3. Design recursive expansion algorithm

**Next Week**:
1. Complete Phase 2
2. Implement Phase 3 (validation infrastructure)
3. Test with sample data
