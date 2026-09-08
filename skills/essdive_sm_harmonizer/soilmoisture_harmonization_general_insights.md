# General Insights

There are a few things that make harmonization challenging. Below I describe ten key challenges for future harmonizers.

1. Payload discovery is harder than format conversion. The main challenge is deciding which files actually contain the measurement payload versus documentation, QA exports, or derived summaries. These details are often not clearly described in metadata, and current reporting standards for file-level metadata (flmd) and data dictionaries (dd) do not document an explicit link between column names and the files in which they appear. 

2. “Soil moisture” is semantically ambiguous across datasets. Observation columns may represent direct observations of variables such as volumetric water content or soil matric potential, but they are often named or described in different ways. Occasionally observation columns report modeled estimates, borehole moisture profiles, responses to experimental manipulation such as warming, or derived moisture indices and not direct measurements of soil moisture. Variable selection in most cases requires interpretation by a subject matter expert. Relatedly, units are reported in a lot of different places. In some packages, units are noted in variable names, but in others they're in ancillary tables or package metadata. 

3. Variable validity is context-dependent. A column named like `moisture_*` may be invalid for inclusion depending on depth domain, measurement method, or whether it is a manipulation metric. Rule-based extraction alone is insufficient.

4. Time-series inference is often implicit. Most datasets do not explicitly label records as time series. One may need to infer this from timestamp regularity, sensor metadata, or repeated site-depth observations.

5. Geospatial metadata is fragmented across sources. Coordinates may appear in payload files, ancillary files, package metadata, publications, or project-level reference packages (e.g., Varadharajan et al. 2020 for the SFA). Robust harmonization of location data often requires intensive manual search. Automating this would require a hierarchical fallback strategy.

6. Non-standard site identifiers create record linkage problems. The same physical location on Earth sometimes appear in multiple datasets with different site IDs. Occasionally site identifiers are reused inconsistently. Proximity + name similarity + provenance constraints are needed to assign stable cross-dataset UUIDs.

7. Decisions about inclusion and exclusion for candidate datasets require explicit documentation. Without written reasons in script comments or mapping JSON, downstream users cannot audit why a package was excluded (duplicate, superseded, non-observational, missing required fields, etc.). Good provenance for these kinds of decisions is crucial.

8. Most datasets describe methods only cursorily and the vast majority do not report information about the measurement device. In most cases, variable names and metadata make it clear that a measurement represents volumetric water content or gravimetric water content or matric potential. However, in very few cases do we have information about nominal measurement uncertainty, calibration methods, representative volume, or device-specific assumptions or their satisfaction criteria. When the device itself is not reported, we can't even look up this information externally. 

9. Most datasets lack records of sensor replacement or relocation, so we really have to rely on the 1:1 match between observations and location identifiers. For the most part it will not be possible to attribute measurement discontinuity or drift to replacement or relocation events.

10. I would expect some tasks to be especially difficult for an LLM. These include interpreting experiment semantics (e.g., warming manipulations), identifying authoritative location sources, recognizing superseded package versions, and deciding whether a measurement is validly harmonizable to the target schema.
