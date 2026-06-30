# Overall Codex Benchmark Evaluation

## Scope

This report summarizes the 13 leakage-controlled Codex benchmark runs created
for the grouped leave-one-out folds. Each fold has its own draft PR containing
the sub-agent trace, generated artifacts, and fold-level evaluation report.

The report focuses on the question: with access to the gold code and mapping,
is it clear what went wrong, and are the failures systematic?

## PR Index

| Fold | Held-out index/indices | PR | Key precision | Gold recall |
| --- | --- | --- | ---: | ---: |
| 01 | 1, 2, 3, 6, 16, 27 | https://github.com/bioepic-data/data-harmonization-eval/pull/37 | 0.364 | 0.621 |
| 02 | 15, 26 | https://github.com/bioepic-data/data-harmonization-eval/pull/27 | 0.000 | 0.000 |
| 03 | 4 | https://github.com/bioepic-data/data-harmonization-eval/pull/15 | 0.551 | 1.000 |
| 04 | 5 | https://github.com/bioepic-data/data-harmonization-eval/pull/24 | 1.000 | 0.528 |
| 05 | 7 | https://github.com/bioepic-data/data-harmonization-eval/pull/20 | 1.000 | 1.000 |
| 06 | 8 | https://github.com/bioepic-data/data-harmonization-eval/pull/26 | 0.994 | 0.994 |
| 07 | 9 | https://github.com/bioepic-data/data-harmonization-eval/pull/28 | 0.000 | 0.000 |
| 08 | 10 | https://github.com/bioepic-data/data-harmonization-eval/pull/29 | 0.000 | 0.000 |
| 09 | 17 | https://github.com/bioepic-data/data-harmonization-eval/pull/30 | 1.000 | 0.998 |
| 10 | 18 | https://github.com/bioepic-data/data-harmonization-eval/pull/32 | 0.000 | 0.000 |
| 11 | 23 | https://github.com/bioepic-data/data-harmonization-eval/pull/34 | 0.000 | 0.000 |
| 12 | 24 | https://github.com/bioepic-data/data-harmonization-eval/pull/35 | 0.559 | 1.000 |
| 13 | 25 | https://github.com/bioepic-data/data-harmonization-eval/pull/36 | 0.000 | 0.000 |

All sub-agent traces passed the targeted local no-gold path scan. No trace showed
root `data/gold`, root `data/processed`, other fold sandboxes, or held-out
`dataset_NN.py` reads under the scanned patterns.

## Big Picture

The benchmark is not measuring only whether an agent can map columns. In many
folds, the hard part is reproducing undocumented expert curation choices:
which rows, sites, treatments, files, and derived identifiers the expert decided
belong in the target. When those choices were simple and visible in the raw
files, the agents often got close. When the expert used hidden row filters,
external/implicit site policies, manuscript-derived constants, or exact
site-id canonicalization, the agents frequently produced plausible but
non-gold-equivalent outputs.

The most important result is that failures are not random. They cluster into a
small number of repeated failure modes:

1. Hidden row/site inclusion policy.
2. Site identifier canonicalization.
3. Wide-to-long parsing and replicate semantics.
4. Interval calculation policy.
5. Sentinel/QC handling and gold-data defects.
6. Literal JSON mapping mismatch despite semantically useful mappings.

## Common Failure Modes

### 1. Hidden Row Or Site Inclusion Policy

This was the most common cause of major precision/recall loss.

- Fold 03 / index 4 recovered all gold rows and all shared values, but retained
  449 extra `tb` rows. The gold code simply drops `site_id == "tb"` and hardcodes
  locations for `ph1`, `ph2`, and `sg5`. That exclusion is clear in gold code,
  but it was not discoverable from the fold-local skill instructions.
- Fold 04 / index 5 produced a high-precision subset but missed almost half the
  gold key set. The agent followed the general treatment/control guidance and
  kept control rows only; the gold for this dataset includes a broader row set.
- Fold 11 / index 23 went the other direction and over-included heavily. The
  gold filters to `Sensor.Type == "SWC"` and `Treatment == "control"`, merges
  sensor metadata, constructs composite site IDs, and derives replicates from
  sensor/location/depth. The agent output was much larger than gold.
- Fold 12 / index 24 recovered all gold rows exactly but included 2,532 extra
  keys. Gold selects only matric-potential columns matching a narrow pattern
  (`P1/P2` at 15/30/60 cm).

These are expert-label decisions, not merely transformation mechanics. The
skills contain general guidance about treatment/control and usable soil-moisture
signals, but they do not enumerate the per-dataset inclusion choices that the
gold code applies.

### 2. Site Identifier Canonicalization

Several near-row-count matches scored as zero keyed overlap because site IDs did
not match gold exactly.

- Fold 08 / index 10 had the same row count as gold, but zero keyed overlap. The
  gold parses site IDs as `PLM1`, `PLM2`, `PLM3` from data column names and only
  uses `ER-*` identifiers in the location lookup. An agent that emits `ER-PLM1`
  style site IDs is scientifically understandable but fails literal key
  matching.
- Fold 10 / index 18 also had a similar row count but zero keyed overlap. Gold
  constructs `site_id` from `Field_Site`, `Plot`, and `Topographic_Position`
  with exact underscore/string behavior.
- Fold 13 / index 25 had a close row count but zero keyed overlap, consistent
  with a site/depth/replicate canonicalization mismatch rather than a simple
  missing-file problem.

The current benchmark key is strict: `datetime_UTC`, `site_id`, `depth_m`, and
`replicate` must match. That is appropriate for target equivalence, but it means
minor-looking naming differences dominate the score.

### 3. Wide-To-Long And Replicate Semantics

Many datasets encode site, depth, variable type, and replicate in column names.
The agents often found the right payload files but missed the exact expert
interpretation of those encodings.

Examples:

- Fold 01 combines several wide micromet datasets. It achieved only 36% key
  precision and 62% gold recall across the cluster. The gold code contains
  dataset-specific parsing rules for file-derived site IDs, depth suffixes,
  replicate counters, sentinel cleanup, and pivoting VWC/SWP into a single row.
- Fold 06 / index 8 did well overall, with roughly 99.4% precision and recall,
  but remaining mismatches were concentrated in values and a small number of
  keys, consistent with subtle parsing/QC differences.
- Fold 09 / index 17 was very strong: 100% key precision and 99.8% recall.
  This suggests the agent can reproduce wide-to-long transforms when the naming
  pattern and inclusion rule are learnable from exemplars and raw headers.

### 4. Interval Policy

The skill instructions recommend sorting and computing intervals within a
site/depth stream. That is usually scientifically cleaner. Gold does not always
do that.

The clearest example is fold 05 / index 7. The agent matched all rows and all
non-interval values, but differed in six `interval_min` cells. Gold computes a
raw sequential timestamp difference across the input file. At depth transitions
that creates large negative intervals. The agent grouped by depth, so it avoided
those negative wraparound values. This is a gold-equivalence failure but arguably
not a scientific failure.

This pattern matters because interval calculation is simultaneously:

- an executable-output metric,
- a semantic curation choice,
- and in some gold modules, a place where questionable values are preserved.

### 5. Sentinel Values And Gold-Data Defects

Gold sentinel handling is inconsistent across datasets. Some modules explicitly
clean sentinel values:

- index 1 cleans `-9999`;
- index 8 cleans `-9999`;
- index 9 cleans `-9999`;
- index 16 cleans `9999` and `-9999`.

But the benchmark also includes known gold-data issues, including sentinel
values incorrectly retained in some gold outputs. In those cases an agent that
does the scientifically right thing and drops sentinel values can be penalized,
while an agent that imitates gold literally would preserve bad data.

This should be split out in future scoring:

- **gold-equivalence score**: did the agent reproduce the current expert output?
- **data-quality score**: did the agent avoid known bad values, impossible
  intervals, and invalid observations?

At present, the benchmark mostly reports gold equivalence, so it cannot
distinguish "agent error" from "agent fixed a gold bug" without manual review.

### 6. Literal JSON Mapping Mismatch

JSON mapping scores were generally worse than executable behavior. Common
patterns:

- Agents often added `gravimetric_water_content` mappings because the target
  schema has `gravimetric_water_content_gH2O_gs`; several gold mapping entries
  omit this category even when the code fills the output column with nulls.
- Gold mapping `source_pattern` strings sometimes use normalized names
  (`Depth..cm.`, `Volumetric.Water.Content`) while raw files and code use names
  like `Depth (cm)` or `Volumetric Water Content`.
- Transformation prose rarely matched literally, even when the executable
  transform was correct.
- Some gold mapping entries disagree with the gold code. For example, fold 03 /
  index 4 has a datetime source-file mismatch between JSON and actual code/data.

This means literal JSON comparison should be treated as a weak proxy for
semantic mapping quality. A structured semantic scorer would be more useful
than text equality.

## Given Gold Access, Is It Clear What Went Wrong?

Mostly yes, but not always for fair reasons.

With the gold code open, most failures are explainable:

- Extra or missing rows usually trace to a visible filter or missing filter in
  `dataset_NN.py`.
- Zero key overlap usually traces to site ID, depth, replicate, or timestamp
  canonicalization.
- Small value mismatches usually trace to sentinel handling, interval policy, or
  unit conversion.
- JSON mismatches usually trace to literal wording and category coverage rather
  than a totally wrong transform.

However, many gold decisions were not recoverable from the materials available
to the sub-agents:

- dropping particular sites such as `tb`;
- including only some sites from a package, for example Colorado-relevant
  locations, when that policy is not documented in the skill;
- selecting control rows in some datasets but not applying the same heuristic in
  others;
- using manuscript-derived constants such as sampling depth or date when they
  are not explicit in staged raw files;
- using an exact site-id spelling that differs from a reference location ID;
- preserving questionable gold interval/sentinel behavior.

That means some benchmark failures reflect missing task specification rather
than model inability.

## Fold-Level Interpretation

### Strong Or Nearly Strong Runs

- **Fold 05 / index 7**: Essentially correct except for six interval cells where
  the agent used grouped interval logic instead of gold's raw-order diff.
- **Fold 06 / index 8**: High precision and recall, with remaining subtle key
  and value differences.
- **Fold 09 / index 17**: High precision and recall; most transformation logic
  matched.
- **Fold 12 / index 24**: Perfect recall and exact shared-row values, but many
  extra rows because the agent included more source columns/observations than
  gold.
- **Fold 03 / index 4**: Perfect recall and exact shared values, but retained
  the undocumented `tb` site that gold drops.

### Weak Runs With Diagnostic Value

- **Fold 02 / indices 15, 26**: Cluster handling failed. Dataset 15 is especially
  brittle because gold relies on metadata/default constants and produces an
  unexpected row profile relative to agent output.
- **Fold 07 / index 9**: Row count close but zero key overlap, likely
  timestamp/site/depth/replicate canonicalization.
- **Fold 08 / index 10**: Row count exact but zero key overlap, likely site-id
  canonicalization (`PLM*` vs `ER-PLM*`) and manuscript-derived depth labels.
- **Fold 10 / index 18**: Row count close but zero key overlap, likely composite
  site-id/depth parsing.
- **Fold 11 / index 23**: Major over-inclusion; gold's exact SWC/control/sensor
  metadata logic was not reproduced.
- **Fold 13 / index 25**: Row count close but zero key overlap, likely
  canonicalization of keys.
- **Fold 01 / indices 1, 2, 3, 6, 16, 27**: Cluster-level run had moderate
  recall but low precision. The cluster combines multiple difficult wide-format
  parsers and sentinel/QC policies.

## Recommendations

1. **Separate hidden curation labels from harmonization skill.**
   Add a benchmark-visible curation contract for each holdout: include/exclude
   sites, treatments, files, sensors, and known bad rows. Without this, agents
   are guessing hidden expert choices.

2. **Score row inclusion and value transformation separately.**
   Fold 03 and fold 12 show perfect shared-row values but poor precision due to
   extra rows. This is different from wrong transformations.

3. **Add a site-id canonicalization metric.**
   Several zero-key folds likely contain useful transformed values under
   non-gold site IDs. A diagnostic scorer should align candidate site IDs or
   report canonicalization-only failures.

4. **Add a "gold defect" annotation layer.**
   Known sentinel-value and interval defects should be marked so the evaluator
   can distinguish reproducing gold from producing scientifically cleaner data.

5. **Make interval policy explicit.**
   Decide whether intervals should be raw-row diffs or grouped by
   site/depth/replicate. The current gold uses both patterns.

6. **Use semantic JSON scoring.**
   Literal comparison of prose and raw/normalized source names is too brittle.
   Score destination variable, source variable identity, unit conversion, null
   fill, and filtering semantics separately.

7. **Document external metadata permissions.**
   Some agents used or wanted package metadata for DOI/date/depth/location
   information. The benchmark should state whether ESS-DIVE API lookups are
   allowed or whether all metadata must be staged locally.

## Bottom Line

The agents often understood the basic soil-moisture harmonization task. The
largest failures were not generic inability to write pandas code; they were
failures to infer hidden gold curation policy, exact site-id canonicalization,
and idiosyncratic gold behavior. With gold access, most failures are clear.
Without gold access, several were not fairly recoverable from the fold-local
skills and raw files alone.

The benchmark is therefore useful, but it should be interpreted as a combined
test of:

- curation-policy inference,
- exact gold-code imitation,
- tabular transformation,
- and robustness to imperfect gold labels.

Those should be disentangled before using the aggregate score as a model-quality
measure.
