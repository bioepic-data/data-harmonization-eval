# Expert soil-moisture harmonizer (modular)

This is the expert harmonization "gold" code, refactored from a single
1200-line monolith into a small package: one shared library plus one module
per dataset.

```
harmonize_sm/
├── common.py        # Context (mapping JSON + dsid/ds_path/read_ds_csv),
│                    # pure helpers, location dedup + CSV writer
├── dataset_01.py    # one harmonize(ctx) -> DatasetResult per dataset
├── dataset_02.py
├── ...              # indices 1-10, 15-18, 23-27 (the 19 expert datasets)
├── dataset_27.py
├── datasets.py      # registry: {index -> harmonize fn}
└── run.py           # driver with --holdout
```

## Why it's split this way

Each dataset block in the old monolith only appended to shared accumulators and
the sole cross-block dependency was the reference dataset (index 0, never a
hold-out target). So each block is independent and becomes a self-contained
`harmonize(ctx)` that *returns* its harmonized frame + location frame(s) instead
of mutating globals. The bodies are verbatim copies of the monolith — only the
wiring changed — so the harmonized outputs are identical.

## Running

```bash
# Full run (writes per-dataset CSVs + location_data_harmonized.csv)
python run.py

# Leave-one-cluster-out: just don't run the held-out datasets
python run.py --holdout 1,2,3,6,16,27     # cluster_1 "sg_ph_micromet"
```

## Grouped leave-one-cluster-out

This split is what makes grouped LOO trivial and is why the old cell-splicer
(`ablate_monolith`) is no longer needed:

- **Executable** (regenerate exemplar outputs without the held-out datasets):
  `run.py --holdout ...` — the held-out modules simply aren't run.
- **Code context** (show the agent held-out-free reference code): feed
  `common.py` plus the kept `dataset_NN.py` files.

The harness wraps both via `src/folds/expert_harmonizer.py`
(`run`, `kept_module_paths`, `assemble_source`). Requesting a hold-out that has
no module (the reference dataset 0, or the excluded datasets 11-14 / 19-22) is
rejected, so there is no coupling to `config/cv_folds.yaml`.
