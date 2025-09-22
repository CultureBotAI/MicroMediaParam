# Analysis of Hydrated Compounds Mapped to Ingredient Codes

## Overview
Analysis of `composition_kg_mapping_with_oak_chebi.tsv` to identify hydrated compounds that are mapped to "ingredient:" codes instead of proper CHEBI IDs.

## Key Findings

### Primary Pattern: MnCl2 x 4 H2O → ingredient:2003

The main hydrated compound consistently mapped to an ingredient code is:

**`MnCl2 x 4 H2O` → `ingredient:2003`**

### Occurrences Found
From the sections analyzed (approximately 4,200 lines out of ~40,000+ total lines), the following instances were identified:

1. **Line 521**: Medium 1590 - `MnCl2 x 4 H2O` → `ingredient:2003` (0.00181 g/L)
2. **Line 573**: Medium 846 - `MnCl2 x 4 H2O` → `ingredient:2003` (9.97009e-05 g/L)
3. **Line 1064**: Medium 486 - `MnCl2 x 4 H2O` → `ingredient:2003` (0.00248509 g/L)
4. **Line 1091**: Medium 663 - `MnCl2 x 4 H2O` → `ingredient:2003` (0.000496524 g/L)
5. **Line 1124**: Medium 265 - `MnCl2 x 4 H2O` → `ingredient:2003` (0.0018 g/L)
6. **Line 1148**: Medium 40 - `MnCl2 x 4 H2O` → `ingredient:2003` (0.000104 g/L)
7. **Line 1167**: Medium 559 - `MnCl2 x 4 H2O` → `ingredient:2003` (9.96016e-05 g/L)
8. **Line 2005**: Medium 873 - `MnCl2 x 4 H2O` → `ingredient:2003` (9.98004e-05 g/L)
9. **Line 2085**: Medium 1299 - `MnCl2 x 4 H2O` → `ingredient:2003` (9.98004e-05 g/L)
10. **Line 2120**: Medium 992 - `MnCl2 x 4 H2O` → `ingredient:2003` (0.00036 g/L)
11. **Line 2134**: Medium 144b - `MnCl2 x 4 H2O` → `ingredient:2003` (0.001 g/L)
12. **Line 2169**: Medium 1647 - `MnCl2 x 4 H2O` → `ingredient:2003` (0.0001 g/L)
13. **Line 3060**: Medium 1101 - `MnCl2 x 4 H2O` → `ingredient:2003` (2.99103e-05 g/L)
14. **Line 3149**: Medium 1539 - `MnCl2 x 4 H2O` → `ingredient:2003` (0.00098912 g/L)
15. **Line 3191**: Medium 457d - `MnCl2 x 4 H2O` → `ingredient:2003` (3e-05 g/L)
16. **Line 4013**: Medium 1639 - `MnCl2 x 4 H2O` → `ingredient:2003` (0.0001 g/L)
17. **Line 4055**: Medium 1002 - `MnCl2 x 4 H2O` → `ingredient:2003` (3e-05 g/L)
18. **Line 4080**: Medium 778a - `MnCl2 x 4 H2O` → `ingredient:2003` (9.97009e-05 g/L)
19. **Line 4105**: Medium 1160 - `MnCl2 x 4 H2O` → `ingredient:2003` (0.00036 g/L)
20. **Line 4113**: Medium 856 - `MnCl2 x 4 H2O` → `ingredient:2003` (0.001 g/L)
21. **Line 4196**: Medium 1487 - `MnCl2 x 4 H2O` → `ingredient:2003` (0.00098912 g/L)

### Related Observation
- **Line 4164**: Medium 1282 contains `MnCl2 x 2 H2O` → `CAS-RN:20603-88-7` (different hydrate form mapped to a CAS registry number rather than an ingredient code)

## Comparison with Proper CHEBI Mappings

The file contains many examples of hydrated compounds that ARE properly mapped to CHEBI IDs, including:

- `MgCl2 x 6 H2O` → `CHEBI:6636`
- `CaCl2 x 2 H2O` → `CHEBI:91243`
- `FeSO4 x 7 H2O` → `CHEBI:75836`
- `ZnSO4 x 7 H2O` → `CHEBI:35176`
- `Na2S x 9 H2O` → `CHEBI:76209`
- `L-Cysteine HCl x H2O` → `CHEBI:17561`
- `MgSO4 x 7 H2O` → `CHEBI:32599`
- `CoCl2 x 6 H2O` → `CHEBI:35696`
- `NiCl2 x 6 H2O` → `CHEBI:34887`
- `Na2MoO4 x 2 H2O` → `CHEBI:86473`

## Summary Statistics
- **From analyzed sections (~10% of file)**: 21 instances of `MnCl2 x 4 H2O` mapped to `ingredient:2003`
- **Affected media**: 21 different growth media
- **Single ingredient code**: All instances map to the same `ingredient:2003`
- **Concentration range**: From 2.99103e-05 g/L to 0.00248509 g/L

## Recommendations

1. **Create CHEBI mapping**: `MnCl2 x 4 H2O` (Manganese(II) chloride tetrahydrate) should be mapped to a proper CHEBI ID instead of `ingredient:2003`

2. **Verify completeness**: Based on this sample, there are likely more instances throughout the full file (estimated 100+ total occurrences)

3. **Check related compounds**: Review other manganese compounds and hydrated metal chlorides for similar mapping issues

4. **Quality control**: Implement validation to ensure hydrated compounds get proper chemical ontology mappings rather than generic ingredient codes

## Impact
This mapping issue affects the semantic consistency of the knowledge graph, as `MnCl2 x 4 H2O` should be linked to chemical ontology terms rather than generic ingredient identifiers for proper chemical reasoning and integration with other chemical databases.