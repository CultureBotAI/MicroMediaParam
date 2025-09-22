# METPO ChEBI Annotation Summary

## Overview
Successfully downloaded and processed the METPO (Microbial Environmental Traits and Phenotype Ontology) spreadsheet from Google Drive and attempted ChEBI annotation using OAK (Ontology Access Kit).

## Data Summary
- **Source**: Google Sheets URL with GID 355012485
- **Total labels extracted**: 232 unique terms
- **ChEBI annotations generated**: 2,796 matches

## Key Results

### Downloaded METPO Terms
The METPO sheet contains primarily phenotypic and metabolic trait terms rather than specific chemical compounds:

**Examples of METPO terms:**
- phenotype
- metabolic trait  
- oxygen preference
- aerobic/anaerobic
- nitrogen-fixing
- sulfur-oxidizing
- temperature preference
- pH preference
- salt tolerance

### ChEBI Annotation Results
- **Annotation rate**: 0.0% for meaningful matches
- **Issue**: Most matches are partial string matches (1-3 characters) rather than full term matches
- **Reason**: METPO terms describe microbial phenotypes/traits, while ChEBI focuses on chemical entities

### Example Annotations Found
- "label" → CHEBI:35209 (exact match)
- Partial matches for amino acid abbreviations (Phe, Met, etc.)
- Single character matches (L, P, etc.) which are not meaningful

## Analysis

### Why Low Match Rate?
1. **Ontology Mismatch**: METPO focuses on microbial phenotypes/traits while ChEBI covers chemical entities
2. **Term Types**: METPO contains descriptive phenotypic terms vs. ChEBI's chemical compound names
3. **Scope Difference**: 
   - METPO: "nitrogen-fixing", "aerobic", "thermophilic"
   - ChEBI: "glucose", "sodium chloride", "phosphate"

### Chemical-Related Terms in METPO
Some METPO terms do reference chemical processes:
- Nitrogen compound respiration
- Sulfur oxidation/reduction
- Iron oxidation/reduction  
- Carbon monoxide oxidation
- Sulfur disproportionation

However, these are process descriptions rather than specific chemical entities.

## Output Files Generated

1. **metpo_sheet.csv** - Raw downloaded Google Sheet data
2. **metpo_labels.txt** - Extracted unique labels (232 terms)
3. **metpo_chebi_annotations.tsv** - OAK annotation results (2,796 entries)
4. **metpo_annotated_labels.tsv** - Final merged results

## Recommendations

For better chemical entity annotation of METPO terms:

1. **Use Multiple Ontologies**: Combine ChEBI with:
   - GO (Gene Ontology) for biological processes
   - ENVO (Environmental Ontology) for environmental terms
   - PATO (Phenotype and Trait Ontology) for qualities

2. **Term Preprocessing**: Extract chemical entities from process descriptions
   - "nitrogen-fixing" → "nitrogen"
   - "sulfur oxidation" → "sulfur", "oxidation"

3. **Alternative Approaches**:
   - Use specialized microbiology ontologies
   - Apply NER (Named Entity Recognition) for chemical extraction
   - Map to KEGG pathways for metabolic processes

## Technical Notes

- **OAK Version**: Successfully used sqlite:obo:chebi backend
- **Processing Time**: ~3 minutes for full annotation
- **ChEBI Database**: ~701MB download completed successfully
- **Command Used**: `runoak -i sqlite:obo:chebi annotate --text-file labels.txt --output results.tsv --output-type tsv`

## Conclusion

The script successfully demonstrates the workflow for downloading Google Sheets data and performing ontology annotation with OAK. However, the semantic mismatch between METPO (phenotypic terms) and ChEBI (chemical entities) results in limited meaningful annotations. Future work should consider multi-ontology approaches or preprocessing to extract chemical entities from phenotypic descriptions.