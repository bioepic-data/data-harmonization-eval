# Background and Related Work

> **Status:** Drafted from the literature research pass (see `research_notes.md` for
> per-source verification status). Author-year keys resolve in `references.md`.
> Sources flagged "snippet-only" there should be confirmed before submission.

This work sits at the intersection of three literatures: (1) environmental and
Earth-science **data harmonization** practice and the standards it targets; (2) the
classical computer-science literature on **data cleaning, schema matching, and
integration**; and (3) the rapidly moving frontier of **LLM agents for data work**.
We review each in turn and then position our contribution.

## 1. Harmonization in environmental and Earth science

### 1.1 The problem and its cost

Reusing observational environmental data requires reconciling deep heterogeneity in
how the same quantity is recorded. For soil moisture specifically, the same physical
property appears as volumetric water content (% or m³ m⁻³), gravimetric water content
(g g⁻¹), or matric/water potential (kPa, MPa, bar, or pF); converting between
gravimetric and volumetric bases requires a bulk-density value that source datasets
frequently omit [NIDIS-2024; CEOS-SM]. The canonical community effort, the
International Soil Moisture Network (ISMN), addresses this by converting all soil
moisture to volumetric m³ m⁻³ and resampling all series to an hourly UTC reference,
applying automated quality flags rather than deleting suspect values
[Dorigo-2011; Dorigo-2021; Dorigo-2013]. Tellingly for the motivation of this paper,
the ISMN reports that data ingest from providers is still performed "either manually
(mostly by email) or is automated, depending on the degree of automation at the data
provider side" [Dorigo-2021] — i.e., the schema/unit mapping itself remains
substantially manual, with automation largely confined to downstream QC.

The same pattern holds across networks. AmeriFlux BASE [Chu-2023] and the FLUXNET2015
ONEFlux pipeline [Pastorello-2020] standardize variable names and units across
hundreds of sites, but only through purpose-built, community-engineered processing
infrastructure. Cosmic-ray neutron networks (COSMOS-UK [Cooper-2021],
COSMOS-Europe [Bogena-2022]) require multi-stage, network-specific correction chains
and harmonized calibration to produce comparable products, and even within a single
"standardized" network (e.g., NEON soil water content [NEON-DP1]) changes in
calibration method over time introduce step discontinuities that complicate reuse.

This curation burden is an instance of a general phenomenon. Qualitative study of
analysts finds data wrangling and integration to be a dominant, painful bottleneck
[Kandel-2012], and the widely repeated claim that practitioners spend 50–80% of their
time on data preparation traces to a *New York Times* article attributed only to
"interviews and expert estimates" [Lohr-2014] and a small industry survey
[CrowdFlower-2016]; the figure's weak provenance is itself documented [Dodds-2020],
so we cite it as illustrative rather than established. More rigorously, Heidorn's
"dark data in the long tail of science" frames the core risk: the heterogeneous,
hand-curated data of many small projects — exactly the kind harmonized here — is the
most expensive to integrate and the most likely to be lost [Heidorn-2008], and
quantified digitization-labor studies show curation cost is dominated by skilled human
time [Blagoderov-2012].

### 1.2 The standards being targeted

Harmonization is harmonization *toward* something. The datasets in this study come
from the DOE **ESS-DIVE** repository [ESS-DIVE], whose team has developed a family of
community **reporting formats** — the product of reviewing 112 existing standards and
iterating with 247 representatives from 128 institutions — spanning CSV file structure,
file-level metadata, hydrologic monitoring, location metadata, and sample identifiers
[Crystal-Ornelas-2022; Velliquette-2021-CSV; Goldman-2021; Damerow-2021]. Notably,
ESS-DIVE has **no dedicated soil-moisture reporting format**, which is part of what
motivates an automated mapping to a project-defined target schema. The ground-truth
data derive from the Watershed Function SFA and its East River, Colorado community
observatory [Hubbard-2018; Varadharajan-2022], a multiscale hydro-biogeochemical
testbed whose sensor and sample datasets exhibit precisely the file-, unit-, and
coordinate-level heterogeneity our agents must resolve.

More broadly, environmental data interoperability is served by a stack of information
models, vocabularies, and unit systems that any harmonizer implicitly reconciles:
information models such as ODM2 [Horsburgh-2016], CUAHSI WaterML/HydroShare
[CUAHSI-HIS], OGC Observations & Measurements / SensorThings [OGC-SensorThings], and
the SOSA/SSN ontology [Janowicz-2019]; variable vocabularies such as the CF Standard
Names (which provide canonical identifiers and units for soil-moisture variables)
[CF-Conventions], the NERC vocabulary server [NERC-NVS], ENVO [Buttigieg-2013], and
AGROVOC [AGROVOC]; and unit ontologies such as UCUM [UCUM], QUDT [QUDT], and OM
[Rijgersberg-2013]. All of this is underwritten by the FAIR principles
[Wilkinson-2016], whose interoperability and reusability tenets are, in effect, a
statement of the harmonization problem. Comparable common-schema efforts in adjacent
fields — Darwin Core in biodiversity [Wieczorek-2012], OMOP/OHDSI in health
[OHDSI-OMOP], the Maelstrom guidelines for retrospective cohort harmonization
[Fortier-2017], and large ecological syntheses such as plant-trait harmonization
[Schneider-2020] and BioTIME [Dornelas-2018] — establish both the importance of the
task and the predominantly manual, expert-driven way it is done today.

### 1.3 Specific heterogeneity hazards

The transformations our harmonizer must get right are exactly those with a long
history of silent, costly error. Unit mismatches are a classic failure mode in
quantitative science — the loss of NASA's Mars Climate Orbiter to a
pound-force-seconds vs. newton-seconds mismatch being the canonical example
[Mars-Orbiter] — motivating machine-actionable unit systems and conversion libraries
(UCUM, QUDT, OM, Pint) that surface dimensional errors rather than hiding them
[UCUM; QUDT; Rijgersberg-2013; Pint]; in soil science the volumetric–gravimetric
conversion's dependence on bulk density makes this especially treacherous
[Dorigo-2021]. Coordinate-reference heterogeneity (mixed UTM zones, datum
differences, axis order) is handled in software by PROJ/EPSG [PROJ], and automated
geocoordinate cleaning of biodiversity records shows such errors are pervasive at
scale — CoordinateCleaner flagged ~3.6% of ~91M GBIF plant records, including
systematic coordinate-conversion artifacts [Zizka-2019]. Time-zone and UTC conversion
of sensor time series is a frequent multi-hour error source absent explicit ISO-8601
offsets [ISO-8601], depth conventions differ across sources (standardized depth
intervals such as GlobalSoilMap's being one response [Poggio-2021]), and the
reshaping between wide and long ("tidy") table layouts is itself a recognized,
error-prone operation [Wickham-2014]. Finally, distinguishing genuinely observational
data from experimentally manipulated data (warming, irrigation) is a scientific
judgment with direct downstream consequences: experimental and observational studies
can yield *opposite* directional responses, so naively pooling them confounds any
synthesis [Yue-2017] — a distinction our curator must make explicitly.

### 1.4 Gold standards and benchmarks

Evaluating automated harmonization against expert ground truth follows an established
paradigm: schema-matching, ontology-alignment, and entity-resolution work is scored
against expert-curated reference alignments using precision, recall, and F-measure
[OAEI]. The data-management community has built benchmarks for adjacent tasks —
error detection [Abedjan-2016], the impact of cleaning on downstream ML (CleanML)
[CleanML-2021], controlled error injection with known ground truth (BART)
[Arocena-2015], entity matching (DeepMatcher, WDC Products)
[Mudgal-2018; Peeters-2024], and semantic-type / table-to-KG interpretation
(Sherlock, SemTab) [Hulsebos-2019; SemTab]. Most directly, recent benchmarks for
*LLM agents* on data-science and data-engineering tasks — DSBench [Jing-2024],
InfiAgent-DABench [Hu-2024], and KramaBench [KramaBench-2025] — report that current
agents fall well short of expert performance (e.g., the best DSBench agent solves
~34% of data-analysis tasks). These results both motivate our study and frame our
methodological choice to benchmark against a real expert-harmonized corpus with
execution-grounded agreement metrics.

## 2. Data cleaning, schema matching, and integration

Our harmonizer is, in classical terms, a system that performs schema matching, value
transformation, and entity/record reconciliation, then emits a transformation
program. Each has a deep literature. Interactive cleaning and wrangling systems —
Potter's Wheel [Raman-2001], Wrangler/Trifacta [Kandel-2011], and OpenRefine
[OpenRefine] — established the value of generating reusable, inspectable
transformation scripts rather than one-off manual edits, and are the conceptual
ancestors of an agent that writes auditable harmonization code. Schema matching has a
canonical taxonomy [Rahm-2001] revisited a decade later [Bernstein-2011]; data
quality and constraint-based repair are surveyed in [Ilyas-2019] and exemplified by
HoloClean's probabilistic-inference approach [Rekatsinas-2017]; and entity resolution
descends from the Fellegi–Sunter model [Fellegi-1969] through managed pipelines such
as Magellan [Konda-2016]. Programming-by-example synthesis of transformations, from
FlashFill onward [Gulwani-2011], is the direct precursor to LLM code generation for
data wrangling.

The transition to learned and then foundation-model methods is recent and rapid: DITTO
brought pre-trained language models to entity matching [Li-2020]; Narayan et al. showed
that a single foundation model can match or beat task-specific systems across five
cleaning/integration tasks with no fine-tuning ["Can Foundation Models Wrangle Your
Data?"] [Narayan-2022]; Table-GPT improved LLMs' tabular reasoning via table-tuning
[Li-2023]; and empirical studies of LLM schema matching find that prompt context must
be balanced — too little or too much degrades quality [Parciak-2024]. These works
establish that LLMs are credible engines for the *sub-tasks* of harmonization;
our contribution is to evaluate a structured *agent pair* that composes them
end-to-end against executed expert ground truth.

## 3. LLM agents for data curation and harmonization

The closest contemporary work casts harmonization itself as agentic pipeline
synthesis. **Harmonia** uses LLM reasoning plus an interactive UI and a library of
harmonization primitives to map diverse datasets to a standard schema, demonstrated on
clinical data [Santos-2025]; it is the most directly comparable system, but it is
human-in-the-loop, in a different domain, and is not evaluated with cross-validation
or cell-level output equivalence. Single-agent standardization and data-engineering
systems are also emerging: CleanAgent decomposes data standardization into iterative
LLM steps [Qi-2024]; Dataforge adds grounding-validation and dual-loop optimization
with cross-validated evaluation [Wang-2025]; Jellyfish instruction-tunes local models
as universal preprocessors [Zhang-2024]; and a line of schema/entity-matching and
ETL-generation work applies LLMs to the mapping and code-generation steps
[KcMF-2024; TabulaX-2024; Prompt2DAG-2025]. On the scientific-curation side, LLMs are
being used to extract and *validate* metadata against ground truth
[MOLE-2025; DCAT-LLM-2025], directly analogous to our conformance and accuracy checks.

Three further threads shape our methodology. First, **multi-agent failure**: recent
taxonomies (MAST) catalogue how chained LLM systems fail through inter-agent
misalignment and weak verification, and emphasize the difficulty of *attributing* a
failure to the responsible agent [Cemri-2025] — exactly what our oracle-vs-end-to-end
decomposition and error-propagation taxonomy operationalize for a two-agent pipeline.
Second, **evaluation of agents on data tasks**: benchmarks such as DataSciBench
[Zhang-2025-DataSci] and KramaBench [KramaBench-2025] grapple with uncertain ground
truth and execution-based scoring, and KramaBench — which spans environmental science —
finds the best system reaches only ~55% end-to-end accuracy, underscoring that this is
an unsolved problem. Third, **the unreliability of LLM-as-judge** scoring
[JudgeReliability-2026] motivates our reliance on automated, execution-grounded
cell-level metrics with expert validation rather than model-graded outputs. Our agents
are implemented as Anthropic **Agent Skills** [AgentSkills-2025], a structured
instruction-and-tool packaging in which the in-context exemplars (the 19 expert
harmonizations) function as retrievable references.

## 4. Positioning of this work

Against this backdrop, our contribution is methodological and empirical rather than a
new system per se. Where Harmonia and CleanAgent demonstrate feasibility, and where
data-task benchmarks report aggregate success rates, we provide a **rigorous,
decomposable evaluation** of an autonomous curator–harmonizer pair on real
environmental data: an output-data-equivalence primary endpoint (executed code
compared cell-by-cell against an expert's), grouped cross-validation with a
similarity covariate to give honest generalization estimates, and a cross-agent
error-propagation taxonomy that attributes each failure to its source. To our
knowledge this is the first such evaluation in the environmental-data-harmonization
setting, and it directly addresses the verification and attribution gaps highlighted
by the multi-agent and agent-evaluation literature.
