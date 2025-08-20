# IUPAC Chemical Data Processing Module

This module provides automated tools for downloading and processing chemical data from authoritative sources (IUPAC, NIST, ChEBI, PubChem) to generate `chemical_properties.tsv` files for the MicroMediaParam pipeline.

## Features

- **Automated Data Download**: Download chemical properties from multiple sources
- **Intelligent Compound Mapping**: Map compound names to standardized chemical names
- **Property Extraction**: Extract pKa values, solubility, molecular weights, and ion charges
- **TSV Generation**: Generate `chemical_properties.tsv` in the correct format
- **Pipeline Integration**: Seamlessly integrate with existing MicroMediaParam workflow

## Quick Start

### Update Chemical Database

```bash
# Update chemical properties from existing compound mappings
python update_chemical_properties.py --update-from-mappings

# Add specific compounds
python update_chemical_properties.py --add-compounds "sodium chloride,glucose,calcium carbonate"

# Test mode (no downloads)
python update_chemical_properties.py --test-mode
```

### Using Makefile

```bash
# Update chemical database via Makefile
make update-chemical-db

# Test chemical database update
make test-chemical-db
```

## Module Components

### 1. Data Downloader (`data_downloader.py`)

Downloads chemical data from multiple sources:

- **PubChem REST API**: Molecular formulas, weights, identifiers
- **ChEBI Database**: Chemical ontology data
- **NIST Chemistry WebBook**: Thermodynamic properties
- **Manual Curation**: High-quality literature data

```python
from src.chem.iupac import IUPACDataDownloader

async with IUPACDataDownloader() as downloader:
    data = await downloader.download_all_sources(["glucose", "sodium chloride"])
    await downloader.save_raw_data(data)
```

### 2. Property Extractor (`property_extractor.py`)

Processes raw data to extract chemical properties:

- **pKa Estimation**: Based on functional groups and known values
- **Ion Charge Determination**: Parse formulas to identify ions
- **Solubility Estimation**: Pattern-based solubility prediction
- **Molecular Weight**: From formula or database lookup

```python
from src.chem.iupac import ChemicalPropertyExtractor

extractor = ChemicalPropertyExtractor()
processed_compounds = extractor.process_raw_data(raw_data_file)
```

### 3. TSV Generator (`tsv_generator.py`)

Generates `chemical_properties.tsv` files:

- **Format Validation**: Ensures compatibility with `compute_media_properties.py`
- **Data Merging**: Merge new data with existing TSV files
- **Quality Control**: Validate data types and ranges

```python
from src.chem.iupac import ChemicalPropertiesTSVGenerator

generator = ChemicalPropertiesTSVGenerator()
generator.generate_tsv_from_processed_data(compounds, "chemical_properties.tsv")
```

### 4. Compound Mapper (`compound_mapper.py`)

Maps compound names to standardized forms:

- **Name Normalization**: Remove hydration states, stereochemistry
- **Synonym Recognition**: Handle common name variations
- **Fuzzy Matching**: Match similar compound names
- **Exclusion Filtering**: Filter out complex mixtures

```python
from src.chem.iupac import CompoundMapper

mapper = CompoundMapper()
standard_name = mapper.map_to_standard_name("CaCl2 x 2 H2O")  # → "calcium chloride"
```

### 5. Complete Pipeline (`pipeline.py`)

Orchestrates the entire process:

```python
from src.chem.iupac import ChemicalDataPipeline

pipeline = ChemicalDataPipeline()
await pipeline.run_full_pipeline()  # Complete automation
```

## Configuration

Configuration is managed in `config.py`:

```python
from src.chem.iupac.config import get_config

config = get_config()
priority_compounds = config['priority_compounds']
api_settings = config['api']
```

## Data Flow

```
1. Compound Analysis
   ├── Extract compounds from mapping files
   ├── Normalize compound names
   └── Create download target list

2. Data Download
   ├── PubChem API calls
   ├── ChEBI database queries
   └── NIST data lookup

3. Property Extraction
   ├── Parse molecular formulas
   ├── Estimate pKa values
   ├── Determine ion charges
   └── Calculate solubilities

4. TSV Generation
   ├── Format data for compute_media_properties.py
   ├── Merge with existing data
   └── Validate output format
```

## Output Format

The generated `chemical_properties.tsv` has the following columns:

| Column | Description | Example |
|--------|-------------|---------|
| `compound_name` | Normalized compound identifier | `nacl` |
| `molecular_weight` | Molecular weight in g/mol | `58.44` |
| `pka_values` | Comma-separated pKa values | `2.15,7.20,12.35` |
| `charge_states` | Possible charge states | `-1,0,1,2` |
| `ion_charges` | Ion charges as ion:charge pairs | `Na+:1,Cl-:-1` |
| `solubility_g_per_L` | Solubility in g/L at 20°C | `360.0` |
| `activity_coefficient` | Activity coefficient | `1.0` |
| `description` | Human-readable name | `Sodium chloride` |

## Integration with MicroMediaParam

This module integrates seamlessly with the existing pipeline:

1. **Compound Discovery**: Analyzes existing mapping files to find compounds needing chemical data
2. **Automated Updates**: Downloads and processes new chemical data
3. **Format Compatibility**: Generates TSV files compatible with `compute_media_properties.py`
4. **Quality Assurance**: Validates data to ensure reliable pH/salinity calculations

## Error Handling

The module includes robust error handling:

- **Rate Limiting**: Respects API rate limits
- **Network Failures**: Graceful handling of network issues
- **Data Validation**: Validates all chemical property data
- **Fallback Mechanisms**: Uses manual curation when APIs fail

## Extending the Module

To add new data sources:

1. **Add API Configuration**: Update `config.py` with new API details
2. **Implement Downloader**: Add new download method to `data_downloader.py`
3. **Update Property Extraction**: Extend extraction logic if needed
4. **Test Integration**: Ensure new data integrates properly

## Dependencies

- `aiohttp` - Async HTTP requests
- `aiofiles` - Async file operations
- `pandas` - Data manipulation
- `fuzzywuzzy` - Fuzzy string matching
- `numpy` - Numerical operations

## Examples

### Basic Usage

```python
# Simple compound addition
python update_chemical_properties.py --add-compounds "potassium phosphate,magnesium sulfate"

# Update from existing mappings
python update_chemical_properties.py --update-from-mappings

# Full pipeline with all priority compounds
python update_chemical_properties.py --full-update
```

### Advanced Usage

```python
from src.chem.iupac import ChemicalDataPipeline

# Custom pipeline with specific mapping files
pipeline = ChemicalDataPipeline()
mapping_files = ["my_compounds.tsv", "additional_compounds.tsv"]
await pipeline.run_full_pipeline(mapping_files)
```

## Troubleshooting

### Common Issues

1. **Network Timeouts**: Increase timeout values in `config.py`
2. **API Rate Limits**: Adjust rate limiting delays
3. **Missing Dependencies**: Run `pip install -r requirements.txt`
4. **Format Errors**: Check TSV file format with validation tools

### Logging

Enable detailed logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Validation

Validate generated TSV files:

```python
from src.chem.iupac import ChemicalPropertiesTSVGenerator

generator = ChemicalPropertiesTSVGenerator()
is_valid = generator.validate_tsv_format("chemical_properties.tsv")
```

## Contributing

To contribute to this module:

1. Follow the existing code structure
2. Add comprehensive error handling
3. Include unit tests for new functionality
4. Update documentation for new features
5. Validate compatibility with the main pipeline