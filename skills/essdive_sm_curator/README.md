# ESS-DIVE Soil Moisture Dataset Curator

## Overview

This skill automates the scientific data curation workflow for ESS-DIVE soil moisture datasets, acting as an intelligent data curator that prepares inputs for the harmonization pipeline.

## Purpose

Reduces human intervention in the dataset evaluation and preparation process by:

1. **Automated retrieval**: Fetches package metadata from ESS-DIVE API or local cache
2. **Intelligent file classification**: Identifies data payloads vs metadata vs documentation
3. **Scientific interpretation**: Detects experimental manipulations, infers time series patterns
4. **Location extraction**: Resolves site coordinates from multiple sources
5. **Quality pre-screening**: Applies exclusion criteria before harmonization
6. **Structured output**: Prepares complete input bundles for harmonization skill

## Workflow Integration

```
┌─────────────────────────────────────────────────────────────────┐
│                    User provides DOI list                       │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              essdive_sm_curator skill                           │
│  • Retrieve metadata (API or cache)                             │
│  • Download & inspect files                                     │
│  • Classify files (payload/metadata/docs)                       │
│  • Extract column headers & previews                            │
│  • Resolve site coordinates                                     │
│  • Detect experimental manipulations                            │
│  • Infer time series vs discrete sampling                       │
│  • Apply exclusion criteria                                     │
│  • Prepare structured output bundles                            │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              Human review (supervisor role)                     │
│  • Review inclusion/exclusion recommendations                   │
│  • Resolve flagged ambiguities                                  │
│  • Approve batch for harmonization                              │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│          wfsfa_sm_harmonization skill (per dataset)             │
│  • Generate Python harmonization code                           │
│  • Generate JSON mapping entry                                  │
│  • Document transformations                                     │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              Human QC (quality control role)                    │
│  • Verify harmonization code correctness                        │
│  • Run code to generate harmonized outputs                      │
│  • Validate against schema                                      │
└─────────────────────────────────────────────────────────────────┘
```

## Input Formats

The curator accepts flexible input formats:

**Single DOI:**
```
doi:10.15485/1660962
```

**Single package ID:**
```
ess-dive-beca0be9bb38ece-20250516T122010234
```

**Multiple (any format):**
```
doi:10.15485/1660962
doi:10.15485/2566877
doi:10.15485/XXXXXX
```

Or:
```
doi:10.15485/1660962, doi:10.15485/2566877, doi:10.15485/XXXXXX
```

Or mixed:
```
- doi:10.15485/1660962
- ess-dive-abc123-20250101T000000
```

## Decision Categories

### AUTO-INCLUDE
Dataset passes all screening criteria:
- Contains direct soil moisture observations (VWC/GWC/water potential)
- Machine-readable data files identified
- No experimental manipulation detected
- Location resolvable (or flagged with qc_flag)

**Action**: Prepare for harmonization

### AUTO-EXCLUDE
Dataset fails mandatory criteria:
- No soil moisture variables found
- Modeled/derived data only (not direct observations)
- No machine-readable data files
- Superseded by newer version

**Action**: Document exclusion reason, skip harmonization

### FLAG FOR REVIEW
Dataset has ambiguities requiring human judgment:
- Experimental manipulation detected (treatment vs control unclear)
- Multiple potential payload files (unclear prioritization)
- Unusual file structure or units
- Missing critical metadata

**Action**: Request operator decision before proceeding

## Output Bundle Structure

For each dataset, the curator produces:

```json
{
  "package_id": "...",
  "doi": "...",
  "curator_decision": "INCLUDE | EXCLUDE | FLAG_FOR_REVIEW",
  "exclusion_reason": "..." | null,
  "data_payload_files": [{
    "filename": "...",
    "columns": [...],
    "row_count_estimate": N,
    "column_preview": "..."
  }],
  "location_metadata_files": [...],
  "readme_content": "...",
  "location_resolution": {
    "source": "...",
    "qc_flag_recommendation": null | "g1" | "g2",
    "site_coordinates": [...]
  },
  "time_series_inference": {
    "is_timeseries": true | false,
    "interval_min": N | null,
    "reasoning": "..."
  },
  "experimental_context": {
    "manipulation_detected": true | false,
    "manipulation_type": "..." | null,
    "recommendation": "..."
  },
  "similar_dataset_reference": {
    "index": N,
    "reason": "..."
  },
  "open_questions": [...]
}
```

## File Classification Logic

### Data Payload Files
- **Indicators**: `data`, `observations`, `measurements`, `sensor`, `VWC`, `moisture`
- **Structure**: CSV/TXT with timestamp + numeric measurements
- **Size**: Multiple rows (>10)

### Location Metadata Files
- **Indicators**: `site`, `location`, `coordinates`, `plot`
- **Structure**: site_id + lat/lon or easting/northing
- **Size**: Fewer rows (1-100)

### Sensor Metadata Files
- **Indicators**: `sensor`, `instrument`, `logger`, `deployment`
- **Structure**: sensor_id + depth + installation details

### Documentation
- **Indicators**: `README`, `methods`, `protocol`, `dictionary`
- **Format**: TXT, PDF, DOCX, MD

## Location Resolution Priority

1. **Location metadata file**: Dedicated site coordinate table
2. **Data payload file**: Coordinates embedded in data
3. **Package metadata**: ESS-DIVE `spatialCoverage` field
4. **README parsing**: Extract coordinates from text
5. **Varadharajan lookup**: Flag for external location registry (`qc_flag = "g1"`)
6. **Unresolvable**: Include with missing coords (`qc_flag = "g2"`)

## Experimental Manipulation Detection

### Exclusion keywords
- `warming`, `heated`, `irrigation`, `fertiliz`, `drought`, `rainout`
- `elevated CO2`, `nutrient addition`, `precipitation exclusion`

### Handling
- **Separate treatment/control**: Exclude treatment, include control
- **Mixed dataset**: Flag for review
- **Treatment only**: Exclude with reason

## Time Series Inference

### Time series indicators
- Multiple timestamps per site/depth
- Regular intervals (hourly, daily)
- Keywords: `continuous`, `logger`, `sensor`, `monitoring`
- Large file size (>1000 rows)

### Discrete sampling indicators
- Single timestamp per site/depth
- Irregular spacing
- Keywords: `campaign`, `survey`, `field campaign`
- Small file size (<500 rows)

## Example Usage

**Input:**
```
Please curate these datasets:
doi:10.15485/1660962
doi:10.15485/2566877
```

**Curator output:**
```
Retrieved metadata for 2 datasets from local cache.

Dataset 1 (doi:10.15485/1660962):
  ✓ RECOMMENDED FOR INCLUSION
  - Data files: ER_SMN1B.csv, ER_SMN3B.csv (9 files total)
  - VWC and water potential time series
  - Location source: Sensor_Location.csv (UTM coordinates)
  - Time series: Yes, hourly interval
  - Similar to dataset 1 in mapping JSON

Dataset 2 (doi:10.15485/2566877):
  ✗ RECOMMENDED FOR EXCLUSION
  - Reason: Does not contain direct soil moisture observations
  - Contains only carbon mineralization data

Summary: 1 include, 1 exclude, 0 flagged

Proceed with harmonization for Dataset 1? [yes/no]
```

**After approval:**
```
Invoking wfsfa_sm_harmonization for Dataset 1...
[Harmonization skill generates Python code and JSON mapping]
```

## Testing Strategy

Test the two-skill workflow with a mixed DOI list:

1. **Valid time series**: Should auto-include
2. **Valid discrete sampling**: Should auto-include
3. **No soil moisture data**: Should auto-exclude
4. **Modeled data**: Should auto-exclude
5. **Experimental manipulation**: Should flag for review
6. **Ambiguous structure**: Should flag for review

## Dependencies

- ESS-DIVE API access: `https://api.ess-dive.lbl.gov/`
- Local metadata cache: `data/raw_cache/ess-dive_meta/`
- Context dependencies: 
  - data/gold/sm_data_harmonization_mapping.json  # for schema reference and examples
  - data/gold/expert_code/harmonize_ess-dive_soilmoisture_data.py  # for code pattern reference
  - data/gold/harmonized_outputs/*.csv # harmonized datasets
- Python libraries: `pandas`, `requests`, `json`, `re`

## Future Enhancements

- Machine learning classification for file type detection
- Automated unit detection and conversion recommendations
- Integration with Varadharajan location registry API
- Automated similar-dataset matching based on file structure
- Batch download and local caching of data files
