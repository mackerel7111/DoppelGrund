# Requirements: 01 Data pipeline

Scope: build the Earth hex feature table, the Moon and Mars disc tables and the target table (contract C2), with provenance and QA. Long-running Earth Engine exports start as early as possible (target: first export running by H3).

## R1 Tiling
1. THE SYSTEM SHALL generate all H3 resolution-4 cells, compute each cell's land fraction against Natural Earth 10m land polygons in an equal-area projection, and keep cells with `land_frac >= params.land_frac_min`.
2. THE SYSTEM SHALL flag cells crossing the antimeridian and provide their polygon split into valid parts on either side of ±180°.
3. THE SYSTEM SHALL write `data/interim/hex_cells.parquet` (C2) and log the count (expected order of 80,000–90,000).

## R2 Earth terrain features
1. THE SYSTEM SHALL compute `slope_p50_deg`, `slope_p90_deg`, `relief_std_m` and `frac_slope_lt_10deg` per hex from Copernicus GLO-30 resampled (mean) to ~470 m before slope is computed.
2. THE SYSTEM SHALL use a slope algorithm that the planetary pipeline reproduces exactly, confirmed by a cross-check test on a shared synthetic DEM (R13.3).
3. THE SYSTEM SHALL record `vf_dem` (valid-pixel fraction) per hex.

## R3 Earth thermal features
1. THE SYSTEM SHALL compute `lst_mean_K`, `diurnal_range_K`, `annual_range_K` and `frac_below_0C` from MOD11A2 (Terra) day and night LST, years in `datasets.yaml`, scaled to kelvin.
2. `diurnal_range_K` SHALL use only pixel-composites where both day and night values are valid.
3. THE SYSTEM SHALL record `vf_lst` per hex.

## R4 Earth cold and ice features
1. THE SYSTEM SHALL compute `aridity_index` = mean annual precipitation / mean annual PET from the configured climate dataset.
2. THE SYSTEM SHALL compute `permafrost_prob` from the Obu et al. permafrost raster for Northern-Hemisphere hexes and NaN elsewhere.

## R5 Earth composition
1. THE SYSTEM SHALL compute the six `lith_<class>` fractions per hex from gridded GLiM using `config/ontology_crosswalk.csv` (source `glim`), excluding water and no-data classes from the denominator.
2. IF no part of a hex is mapped THEN all six fractions SHALL be NaN.
3. THE SYSTEM SHALL compute `aster_mafic_idx` (auxiliary, not scored) where ASTER GED covers.

## R6 Earth mask and auxiliary
1. THE SYSTEM SHALL compute `barren_frac`, `snow_ice_frac` (MCD12Q1 LC_Type1 classes from config, years in config) and `ndvi_mean` (MOD13A2) per hex.
2. Mask rule (applied later in export): keep a hex if `barren_frac + snow_ice_frac >= mask.barren_plus_ice_min` OR `ndvi_mean <= mask.ndvi_max`.

## R7 Process tags
1. `tag_volcanic` SHALL be true if a Holocene volcano lies within the hex or its first ring.
2. `tag_periglacial` SHALL be true if `permafrost_prob >= 0.5` or `frac_below_0C >= 0.5`.
3. `tag_evaporitic` SHALL be true if `lith_evaporite >= 0.1`.

## R8 Earth Engine execution
1. THE SYSTEM SHALL run Earth Engine reductions in batches (latitude bands of ≤ 10°), export each batch as a table to Drive, and resume by skipping batches whose export file already exists.
2. THE SYSTEM SHALL record per-batch status (submitted, running, done, failed) in `data/interim/ee_jobs.json`.
3. IF a batch fails THEN THE SYSTEM SHALL retry it once with a larger `tileScale`, then split it in two.

## R9 Planetary sampling
1. THE SYSTEM SHALL generate a near-equal-area lattice (Fibonacci sphere) of disc centres for the Moon and Mars with spacing that matches the footprint area (~21,400 Moon, ~81,600 Mars).
2. THE SYSTEM SHALL draw a deterministic sample of `n_sample` (default 8,000) discs per body for clustering, plus every disc nearest to a landmark.

## R10 Moon features
1. THE SYSTEM SHALL compute the four terrain features per disc by reprojecting a window of the stage-1 DEM to a disc-centred azimuthal equidistant grid at ~470 m on the lunar sphere, then applying the shared slope algorithm, masked to the 23.7 km disc.
2. THE SYSTEM SHALL compute `lst_mean_K`, `diurnal_range_K` and `frac_below_0C` from Diviner local-time products at 10.5 h and 22.5 h (and all bins for `frac_below_0C`).
3. `annual_range_K` and `permafrost_prob` SHALL be NaN; `aridity_index` SHALL be 0.0.
4. THE SYSTEM SHALL compute `lith_<class>` from the lunar geologic map via the crosswalk.
5. IF a disc lies poleward of a product's coverage THEN the feature SHALL be NaN and the target table SHALL carry a coverage note.

## R11 Mars features
1. Terrain as R10.1 using MOLA 463 m on the Mars sphere.
2. Thermal features SHALL be NaN unless a verified Mars surface-temperature source is added to `datasets.yaml` (open item).
3. `permafrost_prob` NaN; `aridity_index` 0.0; `lith_<class>` from the Mars geologic map via the crosswalk.

## R12 Targets
1. THE SYSTEM SHALL compute features for every landmark in `config/landmarks.yaml` with the same disc method and write `targets.parquet`.
2. THE SYSTEM SHALL compute the same features for the hex containing each known site (for validation and novelty).

## R13 QA and provenance
1. THE SYSTEM SHALL produce `data/interim/qa/report.html` with a global map per feature, histograms per body, NaN fraction per feature and min/max checks against plausible ranges.
2. Every output table SHALL be accompanied by a `<name>.provenance.json` listing datasets (key, id, version), parameters and code git hash.
3. A test SHALL compute slope on the same synthetic DEM through the Earth path and the planetary path and agree within 0.5° at p50.

## R14 Fallbacks
1. IF the Earth Engine terrain export is not complete by H14 THEN the pipeline SHALL support a degraded mode using a coarser DEM resampling (~1 km) for unfinished bands, flagged in provenance.
2. IF Diviner products cannot be read by H18 THEN Moon thermal features SHALL be NaN and the UI SHALL state that thermal is unavailable for Moon targets.
