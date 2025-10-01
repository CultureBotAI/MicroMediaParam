# Unmapped Compounds Enhancement Report

## Summary

Enhanced chemical compound mapping coverage by identifying systematic patterns in unmapped compounds and creating targeted mappings.

## Results

- **Original unmapped compounds:** 7,366 out of 26,991 entries (27.3%)
- **Newly mapped compounds:** 2,720 
- **Remaining unmapped:** 4,646 (17.2%)
- **Coverage improvement:** +36.9% reduction in unmapped compounds

## Enhancement Breakdown

### 1. Chemical Formula Mappings (1,146 compounds)
Direct mapping of chemical formulas to ChEBI IDs:

**Top formulas mapped:**
- `KH2PO4` → CHEBI:63036 (potassium dihydrogen phosphate) - **1,019 occurrences**
- `CoCl2·6H2O` → CHEBI:35701 (cobalt chloride hexahydrate) - **81 occurrences**
- `Na2HPO4·12H2O` → CHEBI:32149 (disodium hydrogen phosphate)
- `K2HPO4·3H2O` → CHEBI:32588 (dipotassium hydrogen phosphate)
- `CaCl2 x 2H2O` → CHEBI:3312 (calcium chloride)

**Additional formulas:** NH4Cl, Na2HPO4, NaH2PO4, MgSO4, FeCl2, FeCl3, CuSO4, ZnSO4, MnSO4, MnCl2, NiCl2, H3BO3, Na2S, Na2CO3, NaHCO3, K2SO4

### 2. Common Name Variations (1,320 compounds)
Mapped compound name variations and brand-specific ingredients:

**Complex ingredients:**
- Yeast extract (all brands) → CAS-RN:8013-01-2 - **256+ occurrences**
- Trypticase peptone (BD BBL/BD-BBL) → ingredient:trypticase_peptone - **75+ occurrences**
- Bacto peptone (BD-Difco) → ingredient:bacto_peptone - **42+ occurrences**
- Tryptone (various brands) → ingredient:tryptone - **67+ occurrences**
- Casamino acids (various brands) → ingredient:casamino_acids - **41+ occurrences**
- Casitone → ingredient:casitone
- Phytone peptone → ingredient:phytone_peptone
- Meat peptone → ingredient:meat_peptone

**Sodium salts:**
- `Na-acetate` → CHEBI:32954 (sodium acetate) - **118 occurrences**
- `Na-pyruvate` → CHEBI:140345 (sodium pyruvate) - **47 occurrences**
- `Na-formate` → CHEBI:62955 (sodium formate) - **25 occurrences**
- `Na-lactate` → CHEBI:32398 (sodium lactate)

**Other compounds:**
- `Soluble starch` → CHEBI:28017 (starch) - **68 occurrences**
- `Thiamine-HCl` → CHEBI:532454 (thiamine hydrochloride)
- `EDTA·2Na` → CHEBI:64734 (EDTA disodium salt)

### 3. Hydrate Pattern Resolution (254 compounds)
Resolved hydrate variations by stripping water molecules and mapping to base compound:

**Patterns handled:**
- `x H2O` - `L-Cysteine HCl x H2O` → CHEBI:17561 - **207 occurrences**
- `·nH2O` - `CoCl2·6H2O` → CHEBI:35701
- `xH2O` - `MnSO4·xH2O` (variable hydration)
- `x nH2O` - `Thiamine-HCl x 2 H2O` → CHEBI:532454 - **35 occurrences**

## Remaining Unmapped Compounds (Top 20)

The following compounds remain unmapped and require manual curation or additional data sources:

1. **Solution references:** `5% Na2S·9H2O solution` (133), solution references, vitamin/trace element solutions
2. **Metadata entries:** `Final volume: 1000 ml` (32), `Revision: 001` (33), `Approved: 30APR20` (31)
3. **Complex solutions:** `8% NaHCO3solution*` (84), `FeCl2solution (see Medium No.187)` (74)
4. **Variable hydrates:** `MnSO4·xH2O` (51) - uncertain number of water molecules
5. **Cysteine with multiple dots:** `L-Cysteine·HCl·H2O` (108), `5% L-Cysteine·HCl·H2O solution` (49)
6. **Reference solutions:** `Trace element solution (see below)` (57), `Vitamin solution (see below)` (39)
7. **Proprietary media:** `QF 09` (36), `Sea salts (Sigma)` (19)
8. **Commercial extracts:** `Beef extract (BD-Difco)` (19), `10% Yeast extract solution` (24)

## Implementation

Created `enhance_unmapped_compounds.py` which:
1. Loads composition mapping TSV
2. Identifies unmapped compounds (empty `mapped` column)
3. Applies three mapping strategies sequentially:
   - Direct chemical formula lookup
   - Common name variation matching
   - Hydrate pattern stripping + base compound lookup
4. Writes enhanced mapping to `composition_kg_mapping_enhanced.tsv`
5. Generates comprehensive statistics

## Usage

```bash
python enhance_unmapped_compounds.py
```

**Input:** `composition_kg_mapping.tsv` (26,991 rows)  
**Output:** `composition_kg_mapping_enhanced.tsv` (26,991 rows with 2,720 additional mappings)  
**Log:** `enhance_unmapped_compounds.log`

## Next Steps

1. **Solution expansion:** Parse and expand solution references (e.g., "5% Na2S·9H2O solution" → Na2S with concentration)
2. **Metadata cleanup:** Filter out non-chemical entries (Final volume, Revision, Approved)
3. **Manual curation:** Create mappings for remaining high-frequency unmapped compounds
4. **Multi-dot hydrates:** Special handling for `L-Cysteine·HCl·H2O` patterns
5. **Commercial extracts:** Map proprietary media components to generic equivalents or ingredient codes

## Files Modified

- **Created:** `enhance_unmapped_compounds.py` - Enhancement script
- **Created:** `composition_kg_mapping_enhanced.tsv` - Enhanced mapping output
- **Created:** `enhance_unmapped_compounds.log` - Processing log

## Impact

This enhancement increases the overall mapping coverage from **72.7% to 82.8%**, a significant improvement that will enable more accurate downstream analysis including pH calculations, salinity measurements, and knowledge graph integration.
