# Compound Mapping Coverage Comparison

This table compares unique compound counts by mapping prefix between two mapping files.

| Prefix | Old | New | Change |
|--------|-----|-----|--------|
| **Ontology IDs** | | | |
| CHEBI | 688 | 694 | **+6** |
| UBERON | 4 | 7 | **+3** |
| FOODON | 0 | 7 | **+7** |
| KEGG | 4 | 4 | same |
| **Subtotal Ontology** | **696** | **712** | **+16** |
| | | | |
| **Database IDs** | | | |
| PubChem | 19 | 19 | same |
| CAS-RN | 153 | 153 | same |
| **Subtotal Database** | **172** | **172** | same |
| | | | |
| **References** | | | |
| medium | 19 | 19 | same |
| | | | |
| **Unmapped** | | | |
| ingredient | 156 | 140 | **-16** (improved) |
| | | | |
| **Grand Total** | **1,043** | **1,043** | same |

## Summary

- **+16** unique compounds upgraded to proper ontology IDs
- **-16** reduction in unmapped `ingredient:` compounds
- New ontology coverage: CHEBI (694), UBERON (7), FOODON (7), KEGG (4)