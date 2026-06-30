# Research Notes — Literature Survey Provenance

> Working notes from the deep literature research conducted for this manuscript
> (June 2026). This is **reference material**, not manuscript prose; it records what
> was found, how directly it relates, and how well it was verified, so that
> `01_introduction.md`, `02_background.md`, and `references.md` rest on a traceable
> basis. Verification: **[V]** fetched & confirmed; **[S]** snippet/secondary only;
> **[org]** official site.
>
> Two research streams were run: (A) the latest agentic-curation / LLM-for-data-work
> literature (2024–2026), and (B) environmental / Earth-science harmonization and
> general data-cleaning literature. Stream B fanned out over six sub-topics.

## How the literatures map onto the manuscript

A useful three-layer framing (any harmonizer reconciles all three):

1. **Information models / schemas** — record structure incl. coordinates, depth,
   timestamps: ODM2, OGC O&M / SensorThings, WaterML, Darwin Core, SoilML, and the
   ESS-DIVE reporting formats (our concrete target).
2. **Variable vocabularies** — naming the observed property: CF Standard Names
   (canonical units for soil-moisture variables), NERC P01, ENVO, AGROVOC.
3. **Unit systems** — normalizing values: UCUM, QUDT, OM, CF canonical units.

FAIR [Wilkinson-2016] is the overarching motivation; CF Standard Names + UCUM/CF
canonical units are the most on-point for our specific target variables (volumetric /
gravimetric water content, water potential).

## Most directly comparable / competing work (lead with these)

1. **Harmonia** [Santos-2025] — *the* closest system: LLM-agent harmonization-to-target
   -schema. Differentiate: ours is an **autonomous agent pair** (not interactive),
   **environmental** (not clinical), and **rigorously evaluated** (grouped LOO CV +
   blind prospective + cell-level output equivalence). **[V]**
2. **CleanAgent** [Qi-2024] — closest single-agent standardization analogue. **[V]**
3. **Dataforge** [Wang-2025] — closest on validation-loop architecture + CV-based
   evaluation. **[V]**
4. **DataSciBench** [Zhang-2025-DataSci] & **KramaBench** [KramaBench-2025] — closest
   evaluation-methodology peers; KramaBench covers environmental science and shows
   best-system end-to-end accuracy ~55%, motivating our work. **[V]**
5. **MAST / "Why Do Multi-Agent LLM Systems Fail?"** [Cemri-2025] — the reference point
   to contrast our two-agent error-propagation taxonomy and failure attribution. **[V]**

The strongest *human-baseline / analogy* anchors: **ISMN** [Dorigo-2021] (real expert
harmonization of heterogeneous in-situ soil moisture; explicitly names our
heterogeneity axes — units, depth, time zones, sampling — and documents that ingest is
still "manually, mostly by email"); **Maelstrom/Fortier** [Fortier-2017] (gold-standard
manual retrospective harmonization process from epidemiology); **OMOP/OHDSI**
[OHDSI-OMOP] (common-data-model target schema). Strongest cost/labor anchors:
**Heidorn** [Heidorn-2008] (dark data / long tail) and **Blagoderov** [Blagoderov-2012]
(quantified curation labor).

## Stream A — Agentic curation / LLM-for-data-work (2024–2026)

- **Cleaning/wrangling/prep:** CleanAgent [Qi-2024] **[V]**, Dataforge [Wang-2025]
  **[V]**, Jellyfish [Zhang-2024] **[S]**.
- **Schema/entity matching, ETL gen:** Harmonia [Santos-2025] **[V]**, KcMF
  [KcMF-2024] **[S]**, TabulaX [TabulaX-2024] **[S]**, Prompt2DAG [Prompt2DAG-2025]
  **[S]**, plus a large entity-matching line (Peeters & Bizer, AnyMatch, "Match,
  Compare, or Select?") — context only.
- **Multi-agent / error propagation:** MAST [Cemri-2025] **[V]**; also PEAR (planner→
  executor robustness) and a 2026 failure-*attribution* benchmark — both directly
  relevant to attributing curator-vs-harmonizer error (snippet-only; verify before
  citing).
- **Code-gen / PBE lineage:** FlashFill [Gulwani-2011], Table-GPT [Li-2023] **[V]**,
  "Can Foundation Models Wrangle Your Data?" [Narayan-2022] **[V]** — the key prior
  work showing a single FM matches task-specific cleaning systems.
- **Evaluation methodology:** DataSciBench [Zhang-2025-DataSci] **[V]** (uncertain
  ground truth; Task–Function–Code scoring of execution outcomes — informs our
  output-equivalence design), KramaBench [KramaBench-2025] **[V]**, DSBench [Jing-2024]
  **[V]**, InfiAgent-DABench [Hu-2024] **[S]**. LLM-as-judge reliability papers
  (snippet-only) justify our preference for automated cell-level metrics over a model
  judge.
- **Skills / structured prompting:** Anthropic Agent Skills [AgentSkills-2025] — cite
  the primary Anthropic engineering blog / agentskills.io at submission (current
  coverage is secondary tech-press).
- **Scientific curation with LLMs:** MOLE [MOLE-2025] **[V]** (extract-then-validate-
  against-GT, mirrors our conformance checks), DCAT metadata extraction [DCAT-LLM-2025]
  **[S]** (few-shot > zero-shot — supports exemplar value).

**Caveat:** several 2026 arXiv IDs (26xx.xxxxx) are consistent with the current date
but were captured from search snippets only; confirm author/title/venue before final
citation. The single most directly comparable paper is **Harmonia** [Santos-2025].

## Stream B — Environmental harmonization & data cleaning

### B1 Soil-moisture networks (how harmonization is done today)
ISMN [Dorigo-2011; Dorigo-2021; Dorigo-2013], AmeriFlux BASE [Chu-2023], FLUXNET/
ONEFlux [Pastorello-2020], COSMOS-UK [Cooper-2021], COSMOS-Europe [Bogena-2022], NEON
[NEON-DP1]. Consistent theme: harmonization relies on agreed reporting formats +
substantial manual/semi-automated ingest, with automation mostly confined to
downstream QC — the gap our agent pair targets. ISMN converts all SM to volumetric
m³/m³, resamples to hourly UTC, flags rather than deletes; notably does **not**
harmonize depth.

### B2 ESS-DIVE & WFSFA (our data source and target standards)
Repository [ESS-DIVE]; flagship reporting-formats paper [Crystal-Ornelas-2022] (11
formats; reviewed 112 standards; 247 reps / 128 institutions); CSV format
[Velliquette-2021-CSV], FLMD, hydrologic monitoring [Goldman-2021], location metadata,
sample IDs/IGSN [Damerow-2021]; standards-development process [Crystal-Ornelas-2021].
Ground truth from the East River testbed [Hubbard-2018; Varadharajan-2022]. **Key fact
for motivation: ESS-DIVE has no dedicated soil-moisture reporting format.**

### B3 Ontologies / FAIR / units
FAIR [Wilkinson-2016]; ODM2 [Horsburgh-2016]; CUAHSI/WaterML [CUAHSI-HIS]; OGC O&M/
SensorThings [OGC-SensorThings]; SOSA/SSN [Janowicz-2019]; ENVO [Buttigieg-2013] (note:
C. J. Mungall — the project lead — is a co-author); AGROVOC [AGROVOC]; CF Conventions
[CF-Conventions]; NERC NVS [NERC-NVS]; UCUM [UCUM]; QUDT [QUDT]; OM [Rijgersberg-2013];
Darwin Core [Wieczorek-2012].

### B4 Classical data cleaning / matching (CS)
Potter's Wheel [Raman-2001], Wrangler/Trifacta [Kandel-2011], OpenRefine [OpenRefine];
schema-matching surveys [Rahm-2001; Bernstein-2011]; data quality [Ilyas-2019];
HoloClean [Rekatsinas-2017]; record linkage [Fellegi-1969]; Magellan [Konda-2016].
LLM era: DITTO [Li-2020], "Can FMs Wrangle Your Data?" [Narayan-2022], Table-GPT
[Li-2023], LLM schema matching [Parciak-2024] (context balance matters).
**"80% of time on data prep" provenance:** traces to a 2014 NYT piece [Lohr-2014]
attributed only to "interviews and expert estimates" — no rigorous primary source;
cite [CrowdFlower-2016] (small n) and especially [Kandel-2012] (peer-reviewed
qualitative) instead, and note the critique [Dodds-2020].

### B5 Provenance, reproducibility, cost/labor
PROV-O [PROV-O], RO-Crate [RO-Crate-2022] (+ Workflow Run Crate 2024); reproducible-
pipeline provenance (Ursprung, PVLDB 2020). Cost/labor: long-tail dark data
[Heidorn-2008], digitization labor [Blagoderov-2012]. Cross-domain harmonization
analogies: Maelstrom [Fortier-2017] (retrospective vs prospective — mirrors our
Phase A/B split), OMOP/OHDSI [OHDSI-OMOP], ecology (trait data [Schneider-2020],
BioTIME [Dornelas-2018]).

### B6 Heterogeneity hazards & benchmarks
Unit mismatch: Mars Climate Orbiter [Mars-Orbiter]; UCUM/Pint [UCUM; Pint]. CRS:
PROJ/EPSG [PROJ], CoordinateCleaner [Zizka-2019] (~3.6% of 91M GBIF records flagged).
Time: ISO 8601 [ISO-8601]. Reshaping: Tidy Data [Wickham-2014]. Depth: SoilGrids/
GlobalSoilMap intervals [Poggio-2021]. Observational-vs-manipulated confound:
[Yue-2017] (experimental and observational responses can have *opposite* sign).
Benchmarks: error detection [Abedjan-2016], CleanML [CleanML-2021], BART [Arocena-2015],
DeepMatcher [Mudgal-2018], WDC Products [Peeters-2024], Sherlock [Hulsebos-2019],
SemTab [SemTab]; LLM-agent data benchmarks DSBench [Jing-2024], InfiAgent-DABench
[Hu-2024], KramaBench [KramaBench-2025]; expert-gold-standard / reference-alignment
evaluation paradigm [OAEI].

## Outstanding verification TODOs before submission

- Confirm DOIs / author order for snippet-only **[S]** entries, especially older works
  ([Fellegi-1969], [Dorigo-2011], [Dorigo-2013]) and all 2026 arXiv preprints
  ([JudgeReliability-2026] and the failure-attribution benchmark).
- Replace the secondary Agent Skills citation with Anthropic's primary source.
- Verify ESS-DIVE reporting-format dataset author lists/years on the OSTI DOI landing
  pages (several have v1/v2 releases).
- ODM2 [Horsburgh-2016] full text was publisher-blocked; DOI corroborated — confirm.
