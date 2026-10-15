# What we measure, and what each measurement means

A plain-language guide to the evaluation. Intended as raw material for the
Methods and Results sections, so each metric is stated together with what it
can and cannot tell you.

Code: `src/metrics/`. Outputs: `results/scored/` (one JSON per fold),
`results/tables/` (CSV), `results/figures/` (PNG).

---

## 1. What is being compared

Each of the 19 folds hides one dataset from the agent's reference material,
gives it that dataset's raw files, and asks it to harmonize them. We then
compare what the agent produced against what a domain expert produced for the
same dataset.

**The reference ("gold") is the BERDL lakehouse table**
`bervodata.watershed_sfa_soil_moisture.ddt_soil_moisture_observation` — 6.4M
rows covering all 19 datasets. It is the expert's own harmonized output, loaded
into the lakehouse, so it is a *complete* reference rather than the 49-row
snippets kept in this repo.

Three translations are applied before anything is compared, and each one would
silently corrupt the results if skipped:

| Issue | Translation |
|---|---|
| Water potential is stored in **pascals** in the lakehouse, kPa in the schema | divide by 1000 |
| `site_id` is not a column; it is embedded in `sdt_location_name` as `<dataset>__<site>` | join to `sdt_location.site_identifier` |
| Dataset IDs use `_` in this repo, `-` in the lakehouse | normalise separators before matching |

**Important caveat about the reference.** It is the same expert work the repo's
gold code produces, not an independent second opinion. So these metrics measure
*agreement with one expert*, not correctness in an absolute sense. Where the
agent and the expert disagree, the expert is treated as right by convention.

---

## 2. The primary measurement: output equivalence

The central question is simple: **did the agent produce the same table the
expert did?** The complication is deciding when two rows are "the same row".

A naive answer — match rows that agree on timestamp, site, depth and replicate —
turns out to be badly misleading. If the agent names a site `ER-WML1` where the
expert writes `ER-WML1_HERB`, *nothing* matches and the score is zero, even if
every number is correct. So we measure at four increasing levels of strictness
and report all four.

### The match ladder

| Level | Rows are "the same" when they agree on… | What it isolates |
|---|---|---|
| **L0** | nothing — we only compare distributions | unit errors, gross row-count errors |
| **L1** | timestamp + depth + replicate | whether the *values* are right, ignoring site naming |
| **L2** | L1 + site, after translating the expert's site names into the agent's vocabulary | whether site identity is recoverable |
| **L3** | timestamp + site + depth + replicate, exactly | the strict, conservative headline |

Reading the ladder is the point. A fold with **high L1 and zero L3** has correct
data under different site labels. A fold with **low L1** has genuinely wrong
values. One number cannot distinguish those; four can.

### Metrics reported at each level

- **Recall** — of the expert's rows, what fraction did the agent reproduce?
- **Precision** — of the agent's rows, what fraction correspond to an expert row?
  (Precision below 1 usually means the agent kept rows the expert filtered out.)
- **F1** — the harmonic mean, a single balance of the two.
- **Cell agreement** — among paired rows, what fraction of individual values match?
  Numbers compare within a small tolerance; text must match exactly.

### Two things deliberately kept separate from cell agreement

- **Null-mask agreement.** Agreement computed only over cells where both sides
  have a value would hide an agent writing `0` where the expert recorded
  "missing". We compare the *pattern of missingness* as its own number.
- **Gap structure.** Not how many rows are missing, but *which*. An entire
  missing site or a missing year is a systematic failure; the same number of
  rows missing at random is a different problem.

### Row pairing, and why order does not matter

Timestamps repeat across sites, so the match keys are not unique. Rows are
paired by sorting both sides deterministically and pairing the *n*-th
occurrence with the *n*-th occurrence. This makes matching well-defined for
repeated keys and makes row order irrelevant — which matters, because the
earlier pilot found that its only disagreements were ordering artifacts.

---

## 3. Automatic diagnosis: why a fold differs

A score says a fold is wrong. A diagnosis says *how*. Each fold gets a list of
findings, each carrying the evidence that triggered it.

Findings state evidence, not conclusions. "Ten sites appear in the agent output
that the reference does not have" is an observation; "the agent forgot a filter"
is a hypothesis that has to be checked against the expert's documented steps.
The detectors emit the former.

| Finding | Triggered when | Usually means |
|---|---|---|
| `TZ_SHIFT` | every timestamp is off by the same whole number of hours | a timezone conversion applied, or omitted, in error |
| `ROW_INFLATION` / `ROW_DEFICIT` | agent row count differs by >5% | a filter was missed or applied too aggressively |
| `SITE_SUPERSET` | agent has sites the reference lacks | rows the expert excluded were kept |
| `SITE_MISSING` | reference has sites the agent lacks | part of the data was dropped |
| `SITE_VOCAB_COLLAPSE` | reference names extend the agent's with a qualifier | a distinction (e.g. vegetation type) was flattened |
| `UNIT_SCALE` | column medians differ by ~100, 1000 or 101.325 | percent/fraction, kPa/Pa, or bar/kPa confusion |
| `SIGN_ERROR` | water potential positive where the reference is negative | sign convention inverted |
| `NULL_INFLATION` / `NULL_DEFICIT` | missingness rate differs by >10 points | data not found, or invented/zero-filled |
| `NULL_PATTERN_MISMATCH` | nulls sit in different places on paired rows | a value substituted where the expert recorded missing |
| `DUPLICATE_KEYS` | the agent repeats a key the reference treats as unique | the row identity is wrong |
| `EMPTY_SITE_ID` | rows carry a blank site | a required field is unpopulated |
| `COORD_UNRESOLVED` | agent gives no coordinates where the reference resolves some | an available location source was not consulted |
| `QC_FLAG_MISMATCH` | provenance flags disagree with the reference | coordinate provenance misreported |
| `SYSTEMATIC_GAP` | >80% of unmatched rows fall in one site | the omission is structured, not random |

### Timezone correction, and why it is reported separately

A uniform clock offset drives every keyed score to zero while leaving all the
values perfectly correct. When a shift is detected, we re-score with it removed
and report both numbers. This answers a specific question: *how much of this
fold's failure is one systematic mistake, versus many scattered ones?*

A shift is only counted when the timestamps genuinely fail to line up as they
are **and** the candidate shift recovers most of them. Without both conditions,
one coincidentally-matching timestamp would "detect" an offset on an
already-correct fold — which it did, on four folds, until the rule was tightened.

---

## 4. Schema conformance

Does the output have the right shape? Columns present, no extras, correct order,
values inside plausible ranges (volumetric water content in 0–1, water potential
negative, depth 0–100 m), and the required fields populated.

**What we do not score: raw pandas dtypes.** A CSV file has no types — what
pandas infers on read is a property of the reader, not the agent. Scoring that
would mark every run wrong for storing a timestamp as text. Instead we score
*coercibility*: does every value parse into its intended type without loss?

Note also that the repo's `TargetSchema.is_valid()` ignores range violations, so
a volumetric water content of 95 passes it. Ranges are scored here and count
toward the verdict.

---

## 5. Sites and coordinates

The agent also emits a location table. Against `sdt_location` we measure:

- **Site set precision/recall/F1** — did it find the right sites?
- **Coordinate error** — great-circle distance per matched site, reported as
  median and as fractions within 10 m / 100 m / 1 km.
- **`qc_flag` accuracy** — the lakehouse has no `qc_flag` column, but
  `geolocation_resolution_method` records *how* each coordinate was obtained.
  Mapping that vocabulary onto `g1` (from the registry) and `g2` (unavailable)
  makes coordinate provenance scoreable.

The denominator matters: some reference sites have no coordinates at all, so the
resolvable count is smaller than the site count and is reported separately.

---

## 6. Documentation: the mapping JSON and notes

The agent documents its transformations in prose. Exact text matching is
worthless here — the pilot found 0/8 agreement on transformation wording while
the executed outputs were identical. But "does the text describe the same
operations?" is a real and answerable question.

### `unit_conversion` is not prose

Its 153 reference values collapse to **9 templates** once numerals are masked
("Divide by 1e2 to convert from cm to m"). It is parsed deterministically into
`(factor, from_unit, to_unit)` and scored exactly. No judgement required.

### `transformation` is scored as a set of steps

Each description is reduced to the operations it names, from a controlled
vocabulary: `JOIN`, `FILTER`, `RENAME`, `RESHAPE_WIDE_LONG`, `PARSE_DATETIME`,
`TIMEZONE`, `PARSE_FROM_COLNAME`, `ASSIGN_CONSTANT`, `DERIVE_MIDPOINT`,
`METADATA_LOOKUP`, `COORD_TRANSFORM`, `AGGREGATE`, `DEDUPE`. We then ask:

- **Step recall** — which operations the expert documented are missing from the
  agent's account? (This is the "did it omit an important step?" question.)
- **Step precision** — operations the agent claims that the expert does not.
- **Parameter completeness** — a step named without its arguments. "Convert to
  UTC" without naming the source timezone is weaker documentation than the
  expert's version, and this distinguishes them.

Three design choices worth stating in Methods:

1. **Steps are pooled per dataset, not per variable group.** In the reference, a
   filter that governs every column is recorded inside the `depth` group. A
   group-by-group comparison would miss it entirely.
2. **Reported stratified by operation type, unweighted.** `FILTER` appears just
   twice in 153 reference patterns, yet it drives the largest output errors. Any
   frequency-weighted average would make it invisible. Small cells are reported
   as counts ("1 of 2 FILTER steps recovered"), never as percentages.
3. **Recall pools the mapping text with `notes.md`; precision is attributed per
   artifact.** An agent should not be penalised for documenting a step in the
   other deliverable, but a claim made in a file is that file's claim.

### On using an LLM to read the prose

The current extractor is a **lexical** one — regular expressions over the
controlled vocabulary — applied identically to both sides so any extraction bias
is symmetric. An LLM extractor would recall more, but it must be validated first:
blind to which text is the reference, never shown the output data, run repeatedly
for self-consistency, and checked against human annotation on a subsample. An LLM
judging LLM-written text has a self-preference bias. `extract_steps()` is the
seam to swap one in once that validation exists.

---

## 7. Behaviour and context (not quality metrics)

These describe *how* a run happened. They are covariates, and must not be read
as quality:

- **Exemplar substitution** — which reference implementations the agent actually
  opened, split into in-cluster and out-of-cluster, from `audit/access_trace.tsv`.
  This observes the ablation mechanism directly rather than inferring it from
  score differences.
- **Cost, turns, duration, tokens, tool mix** — from `audit/claude-execution.json`.
  Deliberately *not* a quality metric: a cheap run that silently skips a filter
  would otherwise look efficient.
- **Process integrity** — the invigilator's verdict. Used as a **gate, not a
  score**: essentially every run is clean, so it has no power to discriminate
  between runs. It tells you a fold is admissible, not that it is good.
- **Difficulty covariates** — reference row count, number of sites, number of
  source files, number of unit conversions required, exemplar pool size. These
  exist to separate "the agent did well" from "the dataset was easy".

---

## 8. How to read the statistics

Three limits belong in any write-up of these results.

**The folds are not independent.** Six of the nineteen are the same
micrometeorology station cluster. Treating n=19 as nineteen independent
observations overstates the evidence. The pre-registered cluster bootstrap
resamples only **three** clusters, which has almost no resolution.

**There are no error bars.** Every fold is a single run. Two accidental repeat
runs showed output differing by **3.9% of rows** between identical invocations,
so run-to-run variability is a meaningful fraction of the effect being measured.
Per-fold scores are point estimates of unknown precision until a repeat batch
exists.

**The ablation contrast is confounded.** It is effectively cluster_1 (6 folds,
13 exemplars available) against cluster_3 (11 folds, 18 available) — but those
groups also differ in dataset type and intrinsic difficulty. Any ablation result
here is exploratory.

For these reasons the results report per-fold detail and effect sizes rather
than p-values, and a composite score — if quoted at all — is shown beside its
components, never instead of them.

---

## 9. Reproducing

```bash
# score every fold against the lakehouse (requires on-cluster BERDL access)
python -m src.metrics.run_all

# build tables and figures from the scored JSON
python -m src.metrics.report
```

A known-answer regression exists on fold 17 (target 23), whose defects were
established by hand before the scorer was written: 1,722,752 agent rows against
912,417 reference rows, 20 agent sites against 15, a `_HERB`/`_SHRUB` vocabulary
collapse, and ten retained sites the reference excludes. If the scorer stops
reproducing those, the scorer is wrong.
