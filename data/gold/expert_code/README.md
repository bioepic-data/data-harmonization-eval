# Soil Moisture Data Harmonization

Modular harmonization scripts for ESS-DIVE soil moisture datasets from the WFSFA (Watershed Function SFA).

## Structure

```
notebooks/harmonize_sm/
├── README.md              # This file
├── common.py              # Shared library (Context, helpers, deduplication)
├── datasets.py            # Registry mapping indices to functions
├── run.py                 # Main orchestrator
└── dataset_XX.py × 19     # Individual dataset processors
```

## Architecture

This harmonization system is organized into independent, composable modules:

- **`common.py`**: Shared library containing:
  - `Context` class for read-only configuration and data access
  - Helper functions for date parsing, coordinate conversion, etc.
  - Cross-dataset location deduplication using Union-Find algorithm
  - Output writer

- **`datasets.py`**: Registry explicitly listing which datasets are included (19 total)

- **`run.py`**: Orchestrator that loads context, runs datasets, and writes outputs

- **`dataset_XX.py`**: One module per dataset, each with a `harmonize(ctx)` function

### Why Modular?

**Prevents ID mismatches**: Each dataset's `harmonize()` function returns a `DatasetResult` that couples the dataset_id with its data from the start, preventing the issue where manual edits could cause dataset IDs to become misaligned with their data.

**Enables cross-validation**: Individual datasets can be held out via the `--holdout` flag, enabling leave-one-cluster-out evaluation without code manipulation.

**Improves maintainability**: Each dataset is 80-120 lines and independently testable.

## Running

### Basic Usage

```bash
cd notebooks/harmonize_sm
python run.py
```

This will:
1. Load all 19 datasets
2. Harmonize each dataset to common schema
3. Perform cross-dataset location deduplication
4. Write outputs to `data/processed/harmonized_output_local/`

### With Holdout (Cross-Validation)

Hold out specific datasets for evaluation:

```bash
# Hold out dataset 5
python run.py --holdout 5

# Hold out multiple datasets
python run.py --holdout 5,10,15
```

### Custom Paths

```bash
python run.py \
  --base-dir /path/to/input/data \
  --out-dir /path/to/output \
  --mapping /path/to/mapping.json
```

### Smoke Test (No Write)

Test harmonization without writing outputs:

```bash
python run.py --no-write
```

## Outputs

### Per-Dataset Files (19 files)

Each dataset produces one harmonized CSV file:

```
{dataset_identifier}_harmonized.csv
```

**Columns:**
- `datetime_UTC`: Timestamp in UTC (ISO 8601)
- `site_id`: Site identifier
- `depth_m`: Sensor depth in meters
- `replicate`: Replicate number (for multiple sensors at same location/depth)
- `is_timeseries`: Boolean indicating if data is timeseries or snapshot
- `volumetric_water_content_m3_m3`: VWC in m³/m³ (0-1 range)
- `gravimetric_water_content_gH2O_gs`: Gravimetric water content in g H₂O / g soil
- `water_potential_kPa`: Soil water potential in kPa

### Location File (1 file)

Cross-dataset deduplicated location metadata:

```
location_data_harmonized_with_uuid.csv
```

**Key columns:**
- `harmonized_location_uuid`: UUID grouping sites at same location
- `site_id`: Original site identifier
- `source_dataset_id`: Which dataset this site came from
- `latitude`, `longitude`: Original coordinates
- `latitude_harmonized`, `longitude_harmonized`: Centroid of UUID group
- `qc_flag`: Quality control flag (`g2` = missing coordinates)

**Deduplication logic:**
- Sites within 5 meters are considered same location
- Sites with identical `site_id` across datasets are linked
- UUID assigned to each unique location group

## Datasets Included

19 datasets from ESS-DIVE (datasets 1-10, 15-18, 23-27):

| Index | Dataset ID | DOI |
|-------|------------|-----|
| 1 | ess-dive-beca0be9bb38ece-20250516T122010234 | 10.15485/2566877 |
| 2 | ess-dive-9fd65df885a8e87-20250715T064942543 | 10.15485/1646477 |
| 3 | ess-dive-4c1829de1b8a2ec-20260220T045039633 | 10.15485/2998779 |
| 4 | ess-dive-6c7085e9c544cc6-20250424T164534831 | 10.15485/2561511 |
| 5 | ess-dive-8ac2940c708a515-20230504T210140482233 | 10.15485/1842907 |
| 6 | ess-dive-18e91eb74405882-20241017T173226640 | 10.15485/1909712 |
| 7 | ess-dive-38e901ec3d7bd24-20230504T211548257225 | 10.15485/1660455 |
| 8 | ess-dive-61a0ecd70856892-20230808T205724993 | 10.15485/1958210 |
| 9 | ess-dive-460e696d8210ed3-20260309T155937802 | 10.15485/3013006 |
| 10 | ess-dive-01092fc392bc46d-20240819T143818677 | 10.15485/2322567 |
| 15 | ess-dive-987726ef1235abc-20230504T210342929747 | 10.15485/1648526 |
| 16 | ess-dive-b3d271f19a94e8d-20260114T204512119 | 10.15485/2319813 |
| 17 | ess-dive-f782da867133296-20230504T211008637996 | 10.15485/1660961 |
| 18 | ess-dive-c37aaf9ed6d4c0d-20230504T205923265966 | 10.15485/1660960 |
| 23 | ess-dive-a99be52b7a6114c-20230504T210134503379 | 10.15485/1660964 |
| 24 | ess-dive-daa156d2129c471-20250716T160748658 | 10.15485/2425313 |
| 25 | ess-dive-b924878d23c9dd7-20250214T163427929 | 10.15485/2478518 |
| 26 | ess-dive-e67ab1151ebc525-20230929T190307767 | 10.15485/1997364 |
| 27 | ess-dive-be919d7d5d42c94-20240130T205332180 | 10.15485/2228953 |

Datasets 11-14 and 19-22 are excluded as specified in the mapping JSON.

## Development

### Adding a New Dataset

1. Add index to `DATASET_INDICES` in `datasets.py`
2. Create `dataset_XX.py` with `harmonize(ctx)` function
3. Return `DatasetResult(dataset_id, harmonized_data, location_data)`

### Testing Individual Datasets

```python
from common import Context
from dataset_05 import harmonize

ctx = Context.load(
    mapping_path="../../data/processed/harmonized_soil_moisture_data/sm_data_harmonization_mapping.json",
    base_dir="../../data/intermediate/ess-dive_wfsfa_soil_datasets"
)

result = harmonize(ctx)
print(f"Rows: {len(result.harmonized_data)}")
print(f"Sites: {result.location_data['site_id'].nunique()}")
```

### Running Unit Tests

```bash
# From project root
pytest tests/test_harmonized_data.py -v
```

## Validation

To verify outputs match the original monolithic script:

```bash
# Run modular version
python notebooks/harmonize_sm/run.py

# Compare with existing outputs
diff -r data/processed/harmonized_output_local/ data/processed/harmonized_output_backup/
```

Outputs should be identical (modulo floating point precision and row ordering within equivalent groups).
