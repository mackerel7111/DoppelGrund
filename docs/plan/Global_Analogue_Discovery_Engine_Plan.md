# Global Analogue Discovery Engine

### Scoring every land tile on Earth against a Moon or Mars landmark, then showing where each Earth match is strongest and where it fails

**Consolidated plan (v2).** This file merges the former `project.md` (overall plan) and `ML_comp.md` (Colab-scale ML plan), and records the updated interface design. Where the two old files disagreed on ML detail, the ML plan won.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [What Changed](#2-what-changed)
3. [Scope: What Is Scored, Tagged, Curated or Excluded](#3-scope-what-is-scored-tagged-curated-or-excluded)
4. [Covering Earth With Hexagons](#4-covering-earth-with-hexagons)
5. [Datasets](#5-datasets)
6. [Features and Harmonisation](#6-features-and-harmonisation)
7. [What the ML Actually Sees](#7-what-the-ml-actually-sees)
8. [Matching Engine](#8-matching-engine)
9. [Machine Learning Layer](#9-machine-learning-layer)
10. [Validation by Rediscovery](#10-validation-by-rediscovery)
11. [Mission Lenses (Profiles)](#11-mission-lenses-profiles)
12. [Product and User Experience](#12-product-and-user-experience)
13. [Divergence Panel and Confidence](#13-divergence-panel-and-confidence)
14. [Caves, Lava Tubes and the Sarawak Story](#14-caves-lava-tubes-and-the-sarawak-story)
15. [Implementation Architecture and Colab Engineering](#15-implementation-architecture-and-colab-engineering)
16. [Execution Plan and Priorities](#16-execution-plan-and-priorities)
17. [Evaluation Metrics](#17-evaluation-metrics)
18. [Risks and Mitigations](#18-risks-and-mitigations)
19. [Pitch Framing](#19-pitch-framing)
20. [Open Items to Verify](#20-open-items-to-verify)
21. [Sources](#21-sources)

---

## 1. Project Overview

Terrestrial analogues are places on Earth that share selected conditions with the Moon or Mars. They are used to test hardware, train crews and develop science methods before missions fly. Most analogue work uses a small set of well-known sites, such as the Atacama, Antarctica's Dry Valleys, Iceland, Hawaii and Devon Island.

This project builds a **systematic, whole-Earth search** instead. It tiles all of Earth's land into hexagonal cells, computes a physical feature table for every cell from global datasets, and scores each cell against a user-selected Moon or Mars landmark. The user picks a landmark on a Moon or Mars view and the app returns Earth matches, each labelled by the dimension in which it is strongest, together with per-feature gaps that show exactly where each analogy breaks down. A novelty view surfaces high-similarity places nobody has studied.

**One-sentence pitch:** *Pick a place on the Moon or Mars, and we score every land tile on Earth against it, show which matches are strongest for terrain, temperature, ice or geology, flag the ones nobody has studied, and are honest about where each one fails.*

### Design principles

- **Discovery over rediscovery.** Famous sites are a validation set, not the product.
- **Physical quantities, not raw pixels.** Everything compared is a derived, unit-bearing measurement.
- **Honest about gaps.** Missing data stays missing. Unmatchable conditions (gravity, vacuum, radiation) are reported, never hidden by scaling.
- **Lens-driven, not mission-locked.** An analogue need not match everything. The user sees the best match per dimension by default and can apply a mission lens to re-weight.
- **Explainable and reproducible.** Every ranking can be regenerated from features, weights, method and version.
- **Classical and inspectable.** Scoring is a formula, clustering is unsupervised, and every number on screen can be traced to a feature and a source.

### Plain-language mental model

Every place (an Earth hex, a Moon disc, a Mars disc) becomes a **fingerprint of about 20 numbers**: slope, temperature, ground-ice indicators, rock type and so on. All datasets, whatever their original file format, are reduced to those columns. Everything after that is maths on a table.

---

## 2. What Changed

### 2.1 Compared with the original plan

| Topic | Original plan | Current plan |
|---|---|---|
| Search space | 100-200 hand-picked regions, mostly famous sites | Every land tile on Earth (H3 grid) |
| Headline result | "Best Earth twin for this Moon location" | Best Earth matches **per dimension** for a chosen landmark, plus a novelty list of unstudied high scorers |
| Similarity metric | Weighted cosine similarity | Per-feature tolerance-kernel similarity in physical units, aggregated with weights |
| Thermal handling | Normalised away by independent scaling | Compared on a shared scale with overpass-matched local times; the gap is reported in kelvin and flagged |
| Roughness and slope | Single pixel window | Matched physical baselines across datasets |
| ML | Optional neural embedding | PCA, joint clustering, weight calibration, novelty index, ranking stability |
| Validation | Informal agreement with documented studies | Formal rediscovery test, recall@k on 30-50 known analogues |
| Dimensions | Hardware-test focus | Hardware plus science: terrain, thermal, cold/ice and composition scored; others tagged or curated |
| Mars | Minor | First-class target alongside the Moon |
| Caves | Mulu and Niah as habitat candidates | Lava-tube catalogue for structure; Sarawak caves for subsurface biology and exploration logistics |
| Mission selection | Mandatory mission dropdown | Optional mission lens. Default shows best matches per dimension |
| UI | Two synchronised globes first | Two-panel target-to-Earth interface in 2D first; 3D dual globes as an upgrade of the same interaction |

### 2.2 Decisions made while merging the two files

| Issue | Resolution |
|---|---|
| Terrain baseline: `project.md` said 30 m vs 118 m, ML plan said ~470 m | **Stage 1 uses a matched ~470 m baseline** (LOLA LDEM ~474 m, MOLA ~463 m). Stage 2 uses ~30 m (Earth) against ~118 m (Moon) |
| Dust and wind listed as core in `project.md` | The ML plan dropped the datasets (MERRA-2, SMAP are login-gated or heavy). **Mars dust lens is an optional stretch**, not a core dimension |
| Soil moisture (SMAP) and EMIT spectroscopy in `project.md` | Dropped. Cold/ice uses permafrost, cold-ground fraction and aridity. Composition uses GLiM and ASTER GED |
| Barrenness had a profile weight | Barrenness is now a **mask**, not a scored feature or clustering feature |
| Rock/regolith proxy had a profile weight | No Earth-side rock-abundance feature exists in the stage-1 matrix. Its weight was reassigned (see Section 11) |
| Process tags had a profile weight | Tags are labels only. They are displayed and can break ties, but are not scored |
| WOKAM karst map and Earth Impact Database | Deferred pending access check. GLiM carbonate fraction stands in for karst. Impact tag deferred |
| Autoencoder items | Removed from the plan |
| Mars stage-2 refinement | The kept Mars datasets are all coarse (~460 m). Mars refinement therefore has no finer data than stage 1 unless a dataset is added. State this in the results |

---

## 3. Scope: What Is Scored, Tagged, Curated or Excluded

The challenge lists eight themed dimensions. They are not equally measurable from global data, so they are triaged.

### 3.1 Scored in the engine (four feature groups)

| Group | What is scored |
|---|---|
| **Terrain** | Slope distribution, fraction of ground below a slope threshold, relief, roughness at matched baselines |
| **Thermal** | Mean temperature, diurnal range (overpass-matched), annual range where data exist |
| **Cold and ice** | Fraction of ground below 0 °C, permafrost probability (Northern Hemisphere only), aridity |
| **Composition** | Lithology class fractions on a shared ontology, compared with a graded compatibility matrix. Mafic/silica proxies from ASTER GED where covered |

Barrenness (barren fraction, snow/ice fraction, NDVI) is applied as a **mask** before scoring and clustering.

### 3.2 Curated or indicator layers (shown, not scored)

| Dimension | Treatment |
|---|---|
| Caves, lava tubes, underground | Catalogue-based. No global detection data exists, so any lava-tube signal is a **prior** (young basalt flows), never a detection |
| Biology, extremophiles, habitability | An **extreme-environment index** (hyperaridity, cold, salinity proxies, UV) with a standing note that no global extremophile map exists |
| Landing, mobility, navigation, construction | Derived from terrain, for example the fraction of a cell below a slope threshold |

### 3.3 Process tags (labels, not feature columns)

Tags attach to results so each match states which processes it shares with the target. Launch tags come from data already in the plan: **volcanic** (Smithsonian GVP Holocene volcanoes), **periglacial** (permafrost and cold-ground fraction) and **evaporitic** (GLiM evaporite class). **Aeolian** and **impact** tags are deferred until data access is confirmed.

### 3.4 Excluded from the score

Gravity, vacuum, radiation and permanent-shadow illumination cannot be matched on Earth. They appear in the divergence panel (Section 13) and never contribute to a similarity number.

---

## 4. Covering Earth With Hexagons

### 4.1 Why H3

H3 provides a hierarchical hexagonal grid with uniform neighbour relationships and multiple resolutions. Hexes avoid the area distortion of a latitude/longitude grid and support a coarse-to-fine workflow. H3 is used as the **shared key**: every Earth dataset, in any format, is reduced to one row per hex.

### 4.2 Resolution strategy

| H3 resolution | Approx. cell area | Approx. land cells | Role |
|---|---|---|---|
| 4 | ~1,770 km² | ~85,000 | **Stage 1: global screening pass** |
| 5 | ~250 km² | ~590,000 | Only if compute allows |
| 6-7 | ~36 / ~5 km² | Top hits only | **Stage 2: refinement** |

A 1,770 km² hex can hide small, strong matches. Stage 2 re-tiles the top ~200-300 hexes at resolution 6-7 using finer data.

### 4.3 Generating the tiles

```python
import h3

# All resolution-4 cells covering the globe
cells = [c for r0 in h3.get_res0_cells() for c in h3.cell_to_children(r0, 4)]

# Keep land only: intersect with Natural Earth land polygons,
# and store the land fraction per cell (drop cells below a threshold).
```

### 4.4 Turning each data type into hex features

| Data type | Examples | Reduction per hex |
|---|---|---|
| Continuous raster | DEM, land surface temperature | Zonal statistics over the hex polygon: p10 / p50 / p90 (slope is computed first, at the matched baseline) |
| Categorical raster | Land cover, lithology | Fraction of the hex in each class |
| Coarse grid | GLiM (~0.5°), permafrost | Area-weighted lookup of overlapping cells |
| Points | Volcanoes, pits | Count per hex or distance to nearest. Feeds tags and novelty, not scored features |

### 4.5 Matching footprints: target side

H3 is an Earth grid, so the Moon and Mars use a **disc of the same physical area as the Earth hex**, centred on the landmark. A resolution-4 hex covers about 1,770 km², so the disc radius is about **23.7 km**. Footprints are defined in kilometres, never in hex indices or pixel counts, so the comparison is like-for-like. A landmark match is therefore a match to its ~47 km-wide surroundings, not to the crater or feature itself, and the interface says so.

### 4.6 Gotchas

- Cells that cross the **antimeridian** must be split or skipped.
- Store **distributions** (p10, p50, p90), not only means.
- Record the **land fraction**, **valid-pixel fraction** and **source** per feature.
- Keep stage-1 and stage-2 tables separate. Never mix resolutions in one comparison.

---

## 5. Datasets

Filter used: **free, openly downloadable (or on Earth Engine), small enough for Colab, and relevant to the scored dimensions.** Entries marked **(verify)** come from memory or have conflicting information. Re-check everything against the challenge's Resources tab before committing.

### 5.1 Earth (per hex): keep

| Dataset | Access | Resolution / size | Licence note | Feature role |
|---|---|---|---|---|
| **Copernicus GLO-30 DEM** (`COPERNICUS/DEM/GLO30`) | Earth Engine | 30 m | Free licence, except two countries (Armenia, Azerbaijan) | Slope, relief, roughness. It is a **surface** model (includes vegetation and buildings), so mask vegetated cells |
| **MODIS MOD11A2 / MYD11A2 land surface temperature** (`MODIS/061/...`) | Earth Engine | 1 km, 8-day, day + night | No restrictions on use or redistribution | Mean temperature, diurnal range, annual range, cold-ground fraction |
| **MODIS MCD12Q1 v6.1 land cover** | Earth Engine | 500 m, yearly | Open | Barrenness mask. Be cautious with 2021+ layers (known issue), so use ~2010-2019 |
| **ASTER GED AG100** (`NASA/ASTER_GED/AG100_003`) | Earth Engine | 100 m, 2000-2008, thermal IR emissivity | No restrictions | Silicate/mafic proxy. Footprint is roughly 59°S to 80°N, so **no Antarctica** |
| **GLiM lithology** | PANGAEA gridded version (tiny download, ~0.5°) | 16 first-level lithology classes | Cite Hartmann & Moosdorf (2012). **Verify licence**, since one catalogue lists it differently | Lithology class fractions per hex. The full polygon version is much heavier (use only if needed) |
| **Permafrost (Obu et al. 2018)** | PANGAEA download | 1 km, **Northern Hemisphere only** | CC-BY | Permafrost probability and ground temperature for NH hexes. Southern Hemisphere and Antarctica need the LST-based cold proxy |
| **Smithsonian GVP Holocene volcano list** | Free download (cite version) | ~1,400 points | Free, citation required | Volcanic process tag |
| **Natural Earth land polygons, H3 library** | Open data / open source | Small | **Verify** licences | Land mask and tiling |
| **TerraClimate / aridity layers** | Earth Engine | Candidate | **Verify** collection ID and licence | Aridity |

### 5.2 Moon: keep

| Dataset | Access | Resolution / size | Feature role |
|---|---|---|---|
| **LOLA global DEM** (LDEM_64 ≈ 474 m, LDEM_128 ≈ 237 m) | NASA PDS Geosciences | Global | **Stage 1 baseline** (slope, relief) |
| LOLA 118 m global DEM | USGS Astropedia | ~8 GB GeoTIFF | **Stage 2 only**, read in windows around candidates |
| LOLA polar DEMs (e.g. 20 m to 5 m) | PDS / LOLA node | Per-region | Polar targets only (e.g. Shackleton) |
| **Diviner global cumulative products** | PDS | Binned at 2 px/deg and 0.25 h of local time | **Diurnal range at matched local times** (see 6.2). Coarse but fits hex resolution 4 |
| **Diviner rock abundance / soil temperature** (GDR_L3, GHRM) | PDS | GHRM 128 px/deg, **70°S-70°N only** | Moon-only diagnostic (no Earth equivalent). **Polar targets need separate polar products** |
| **Clementine FeO map** | USGS Astropedia | 1 km, ~133 MB | Mafic proxy. The listed file is a **colour-binned** product, so look for a quantitative version **(verify)** |
| **Lunar Pit Atlas** | LROC shapefile | ~281 pits | Curated layer only (not a scored feature) |

### 5.3 Mars: keep

| Dataset | Access | Resolution / size | Feature role |
|---|---|---|---|
| **MOLA MEGDR DEM** | USGS (463 m, ~2 GB) or PDS (4-128 px/deg tiles) | Global | Slope, relief |
| **TES thermal inertia (Putzig & Mellon)** | PSI / PDS | ~20 px/deg, ~50 MB, filled by interpolation (mask provided) | Thermal-inertia proxy. **Use the mask** to avoid interpolated pixels |
| **TES albedo** | PDS | 8 px/deg, small | Context |
| **TES mineral maps** | TES archive | Global | Composition proxy |

### 5.4 Dropped or deferred (and why)

| Dataset | Decision | Reason |
|---|---|---|
| THEMIS global thermal inertia (100 m) | Drop | Single tiles are ~2.5 GB. Use TES (coarse) instead |
| LOLA / SLDEM2015 full-resolution global | Defer | Stage-2 windows only |
| Diviner raw radiance records | Drop | Billions of measurements. Use gridded products |
| LROC NAC imagery, HiRISE, CTX, CRISM | Drop | Far too large for Colab, and not needed for screening |
| EMIT spectroscopy | Drop | Patchy coverage and heavy |
| MERRA-2 dust, SMAP soil moisture | Drop | Login-gated or heavy. Only served the Mars dust lens, now an optional stretch |
| WOKAM karst map | Defer **(verify access)** | Not confirmed open. Use GLiM carbonate fraction as a proxy |
| Earth Impact Database | Defer **(verify access)** | Not confirmed open. Can be added as a tag later |

### 5.5 Access and size summary

| Route | Used for | Notes |
|---|---|---|
| **Google Earth Engine** (Python API in Colab) | Copernicus DEM, MODIS, ASTER | Server-side. Nothing large is downloaded. Free for non-commercial use, but **confirm eligibility and project registration** |
| **Direct download** | GLiM, permafrost (PANGAEA); LOLA, Diviner, MOLA (PDS, USGS Astropedia); TES (PSI/PDS); GVP list; Pit Atlas | Small except LOLA 118 m (~8 GB, windowed reads) and MOLA (~2 GB) |
| **Final feature tables** | Everything downstream | Tens of MB in `float32` Parquet |

---

## 6. Features and Harmonisation

Harmonisation is the single most important correctness step. File format stops mattering once each dataset is reduced to hex or disc features. The hard part is making the numbers **mean the same thing** on every body.

### 6.1 Rules

1. **Compare derived physical quantities, never raw pixels.** Examples: slope in degrees at a stated baseline; temperature in kelvin.
2. **Match spatial baseline before computing slope or roughness.** Slope depends on pixel size. Resample the Earth DEM to the planetary DEM's resolution first (~470 m in stage 1) and use the **same algorithm** (Horn 3×3) on all bodies.
3. **Define thermal terms carefully** (see 6.2). Report the remaining gap in kelvin. Never let scaling make it appear matched.
4. **Map geology onto a small shared ontology**: mafic volcanic, felsic/feldspathic, carbonate, siliciclastic, evaporite, ice. Use a **graded compatibility matrix** (or Hellinger distance on class fractions), not integer codes, so no false ordering is imposed. This is the weakest harmonised dimension, so document assumptions.
5. **Use one shared reference scale per feature.** Set each feature's tolerance `s_f` from the **pooled** Earth + Moon + Mars distribution (median absolute deviation) so no variable dominates. Never scale each body to its own range.
6. **Treat missing data as missing.** Use NaN, not zero. Score only features present on both sides, renormalise weights, and report coverage.
7. **Keep unmatchable conditions out of the score.** Gravity, vacuum, radiation and permanent-shadow illumination go to the divergence panel.
8. **Record uncertainty and provenance** with every feature value: source, version, native resolution, date range and valid-pixel fraction.

### 6.2 Overpass-matched thermal range

MODIS gives skin temperatures near fixed local overpass times (about 10:30 and 22:30 for Terra). Diviner's cumulative products are binned by local time, so sample the Moon at the **same local-time bins** and compute `diurnal_range_K` the same way. The lunar full-cycle range is hundreds of kelvin and no terrestrial surface reaches it, so the remaining gap is reported in kelvin and flagged, never hidden.

### 6.3 Final feature matrix (target ~18-22 columns)

| Group | Features | Notes |
|---|---|---|
| Terrain | `slope_p50`, `slope_p90`, `relief_std`, `frac_slope_lt_10deg` | All at a **matched ~470 m baseline** in stage 1 |
| Thermal | `lst_mean_K`, `diurnal_range_K` (overpass-matched), `annual_range_K` | `annual_range` is NaN on the Moon, so coverage handles it |
| Cold and ice | `frac_below_0C`, `permafrost_prob` (NH only), `aridity` | Qualitative "cold, dry, ice-bearing" |
| Composition | Lithology class fractions on the shared ontology; mafic/silica index where ASTER GED covers | Graded compatibility matrix |
| Barrenness (mask) | `barren_frac`, `snow_ice_frac`, `ndvi_mean` | **Mask**, not a clustering or scoring feature |
| Tags (not features) | Volcanic, periglacial, evaporitic (aeolian and impact deferred) | Attached to results only |

### 6.4 Preprocessing steps

1. **Mask first.** Keep Earth hexes that pass a barrenness rule (for example `barren_frac` above a threshold or low `ndvi_mean`). This removes forests and wet tropics, which are poor airless-body analogues, and shrinks compute. The threshold is a documented, adjustable parameter.
2. **Transform skewed variables** (`relief_std`, `diurnal_range_K` if heavy-tailed) with `log1p` or a similar monotone transform, applied identically to all bodies.
3. **Pooled robust scaling.** Fit a median/MAD scaler on the pooled Earth + Moon + Mars rows, never one scaler per body.
4. **Clip outliers** at roughly the 0.5th and 99.5th pooled percentiles for clustering. Keep unclipped values for the gap report.
5. **Missing data.** For scoring, keep NaN and renormalise weights. For clustering, keep rows with at least ~80% feature coverage and median-impute the rest, and record this.

```python
# Sketch: pooled robust scaling and tolerances (untested)
import numpy as np
from sklearn.preprocessing import RobustScaler

X_pool = np.vstack([X_earth, X_moon, X_mars])          # NaN allowed
scaler = RobustScaler(quantile_range=(25, 75)).fit(X_pool)
s_f = np.nanmedian(np.abs(X_pool - np.nanmedian(X_pool, axis=0)), axis=0)  # MAD tolerances
s_f = np.where(s_f < 1e-6, 1.0, s_f)
```

---

## 7. What the ML Actually Sees

| Quantity | Approx. size | Source |
|---|---|---|
| Earth hexes (res 4, land) | ~85,000, fewer after the barrenness mask | H3 + Natural Earth |
| Moon discs | ~5,000-10,000 sampled (not exhaustive) | Equal-area sampling |
| Mars discs | ~5,000-10,000 sampled | Equal-area sampling |
| Features per row | ~18-22 | Section 6.3 |
| Table size | Tens of MB | `float32` |

**Why only a few thousand Moon and Mars discs for clustering:** the Moon would give about 21,000 such discs and Mars about 81,000. A few thousand is enough to define planetary regimes and keeps compute small. Preloaded landmarks are always computed explicitly. If arbitrary-click targets are supported (Section 12.2), the full disc grids can be precomputed too, which is still only tens of MB.

---

## 8. Matching Engine

### 8.1 Baseline scoring

This replaces cosine similarity, which on positive, normalised features scores almost everything above 0.9 and ignores magnitude.

$$
S=\frac{\sum_{f} w_f \cdot k\!\left(\dfrac{|x_{t,f}-x_{e,f}|}{s_f}\right)}{\sum_{f} w_f},
\qquad k(z)=\exp\!\left(-\tfrac{z^2}{2}\right)
$$

- Sum over features **present on both sides** only.
- `w_f` are weights; `s_f` are tolerances from the pooled distribution.
- For distribution-valued features (such as slope), compare percentiles or use a 1-D Wasserstein distance.
- For lithology fractions, use the graded compatibility matrix or Hellinger distance.

```python
import numpy as np

def score(X_earth, x_target, w, s):
    """X_earth: (N,F) with NaN; x_target: (F,); w,s: (F,). Returns S, coverage."""
    z = np.abs(X_earth - x_target) / s
    k = np.exp(-0.5 * z**2)
    valid = ~np.isnan(z)
    num = np.nansum(w * k, axis=1)
    den = (w * valid).sum(axis=1)
    S = np.where(den > 0, num / den, np.nan)
    return S, den / w.sum()
```

This is the **reference every other method must beat**.

### 8.2 Group scores

Weights are set at **group level** (terrain, thermal, cold/ice, composition) and split equally across the features present in each group, unless overridden in `profiles.yaml`. The same formula restricted to one group's features gives a **group score** `S_terrain`, `S_thermal`, `S_cold`, `S_comp`. The overall `S` is the weighted combination.

### 8.3 Outputs per hex

- Overall similarity `S` (0-100 model-defined index, **not** a probability of being a true twin)
- Four group scores, plus per-feature similarity and per-feature gap in physical units
- **Coverage** = weight covered / total weight
- Process tags shared with the target
- Novelty (Section 9.7) and stability (Section 9.8)

### 8.4 Ranking rules

- A candidate with high `S` but low coverage must not automatically outrank a well-characterised candidate. Rankings display `S` alongside coverage, and a coverage floor is applied.
- The barrenness mask is applied before ranking.
- The engine never forces famous sites into the results.

### 8.5 Selecting the "best match per dimension" cards

The default interface returns one card per dimension. To stop a top-terrain match from being poor on everything else, a card is chosen as follows:

1. Start from hexes that pass the barrenness mask and the coverage floor.
2. Keep only hexes whose **overall** `S` is above a documented threshold (for example the top few percent overall; a parameter to tune).
3. Within that set, rank by the group score for the card's dimension.
4. Pick the best hex, and enforce a minimum geographic separation between cards so they do not all land on neighbouring hexes.

Every card shows overall `S`, coverage, stability and novelty alongside its dimension score, so a dimension label can never oversell a weak overall match.

---

## 9. Machine Learning Layer

All components are classical and run on **CPU**. The heavy raster work happens server-side in Earth Engine, so no GPU is needed anywhere.

```text
 Parquet feature tables (Earth hexes, Moon discs, Mars discs)
                         |
                         v
   [9.1] Preprocess: mask, transform, pooled robust scaling, missing data
                         |
          +--------------+---------------+
          v                              v
 [8.1] Baseline scorer           [9.2] Domain-gap diagnostic
 (tolerance kernels)             (can Earth be told from Moon/Mars?)
          |                              |
          |                              v
          |                    [9.3] Embedding: PCA
          |                              |
          |                              v
          |                    [9.4] Joint clustering (HDBSCAN, GMM)
          |                              |
          +----------> [9.5] Cluster-conditioned retrieval <----+
                                   |
        [9.6] Weight calibration (weak supervision, leave-one-site-out)
                                   |
        [9.7] Novelty index      [9.8] Ranking stability (Monte Carlo)
                                   |
                         [10] Validation by rediscovery
```

### Honest labelling for the write-up

| Component | What it is |
|---|---|
| Tolerance-kernel scoring, kNN retrieval | Numerical method, **not** a trained model |
| PCA, GMM, HDBSCAN | Unsupervised machine learning |
| Domain-gap classifier | Diagnostic only, not part of the product |
| Weight calibration | Weakly supervised learning on a very small set of known pairs |
| Novelty, stability | Statistical analysis built on the above |

### 9.1 Preprocessing

See Section 6.4.

### 9.2 Domain-gap diagnostic (do this before trusting any clustering)

**Risk:** Earth and planetary rows differ systematically, so a clustering might simply separate "Earth" from "Moon/Mars" instead of grouping by terrain.

**Test:** train a classifier to tell Earth rows from planetary rows. If it succeeds almost perfectly (AUC near 1), the embedding is dominated by body identity.

```python
from sklearn.ensemble import HistGradientBoostingClassifier   # handles NaN natively
from sklearn.model_selection import cross_val_score
from sklearn.metrics import roc_auc_score

y = np.r_[np.zeros(len(X_earth_s)), np.ones(len(X_plan_s))]
X = np.vstack([X_earth_s, X_plan_s])
auc = cross_val_score(HistGradientBoostingClassifier(random_state=0),
                      X, y, scoring="roc_auc", cv=5).mean()

# Per-feature separability
per_feature_auc = [roc_auc_score(y[~np.isnan(X[:, j])], X[~np.isnan(X[:, j]), j])
                   for j in range(X.shape[1])]
```

**Actions**

- Features that almost perfectly separate bodies (for example absolute temperature range) are **excluded from clustering** and handled in scoring plus the divergence panel as flagged gaps.
- Report overlap: what fraction of Earth rows lie within the planetary target's per-feature range (a simple support check). If a target has no Earth support in key features, say so.
- Optional ablation: second-order alignment (CORAL-style) of Earth to planetary features **for clustering only**. Never use it for the reported gap, since it would hide real physical differences.

### 9.3 Embedding

**PCA** keeping ~90% variance (expect roughly 6-10 components). It runs in seconds on CPU and is the operational similarity space. UMAP may be used for **visualisation only**.

### 9.4 Joint clustering (the core unsupervised step)

```python
from sklearn.decomposition import PCA
from sklearn.cluster import HDBSCAN
from sklearn.mixture import GaussianMixture

Z = PCA(n_components=0.90, random_state=0).fit_transform(X_cluster)   # imputed, pooled-scaled

hdb = HDBSCAN(min_cluster_size=100, min_samples=10).fit(Z)            # regimes + noise label (-1)

# Compare K for GMM with BIC; GMM also supports predict_proba for new targets
bics = {k: GaussianMixture(k, covariance_type="full", random_state=0).fit(Z).bic(Z)
        for k in range(6, 26, 2)}
```

This yields interpretable **analogue regimes**.

**Checks**

- **Stability:** bootstrap or subsample refits and compare labels (adjusted Rand index).
- **Interpretability:** table of per-cluster mean z-scores (for example "cold, smooth, mafic" vs "hot, rugged, carbonate").
- **Body mix:** a good analogue regime contains Earth **and** Moon/Mars members. Clusters that are 100% Earth or 100% planetary say something about overlap, not analogues.
- **Runtime:** HDBSCAN at ~10⁵ points in ≤15 dimensions should be feasible on a free Colab CPU, but **benchmark it**. Fallbacks are GMM, or fitting on a subsample and assigning the rest by nearest neighbours.

**New or arbitrary targets:** compute the target's features, apply the stored scaler and PCA, then assign a regime by GMM `predict_proba` or a kNN vote on the HDBSCAN labels in PCA space.

### 9.5 Cluster-conditioned retrieval

1. Find the target's regime.
2. Candidates = Earth hexes in that regime (or with GMM probability ≥ 0.5).
3. Rank candidates **inside** the regime by the weighted baseline score `S`, with the coverage floor.
4. If the target is labelled **noise** or has very low support, **say so** ("no Earth regime closely matches this target") and fall back to the global baseline ranking with a visible warning. Some lunar environments (for example permanently shadowed craters) may have no real Earth analogue, and that is a valid result.

### 9.6 Weight calibration by weak supervision

The default weights are guesses. The only supervision available is the small set of documented analogue pairs (Section 10).

- Parameterise group weights `w = softmax(θ)`.
- Loss: negative mean reciprocal rank (or negative recall@k) of the known sites for their documented targets.
- Regularise toward the hand-set weights `w0` (for example a KL penalty) so the result cannot drift into nonsense.
- Optimise with `scipy.optimize.differential_evolution` or random search. One evaluation scores ~40 targets against ~85k hexes, so it is fast.
- Use **leave-one-site-out** (or split-half) cross-validation. With only ~30-50 pairs, overfitting is the main danger.
- **Bias warning:** known sites are famous sites. Calibrating too hard to them teaches the model to prefer what is already famous, which fights the discovery goal. Keep the regularisation strong and report both calibrated and hand-set results.

### 9.7 Novelty index

For each shortlisted hex:

- **Geographic novelty:** minimum great-circle distance to any known analogue site (a documented list, plus the challenge's named well-studied regions).
- **Feature novelty:** distance in scaled feature space to the nearest known analogue site's hex. This separates "same terrain type, new place" from "a different type of terrain".
- **Headline list:** apply a geographic-distance gate (for example several hundred kilometres, a documented parameter), then rank by `S`, coverage and stability.

Report both novelty columns. Do not collapse them into one number without saying how.

### 9.8 Ranking stability (Monte Carlo)

The default weights and tolerances are not scientifically validated, so the ranking is stress-tested.

```python
rng = np.random.default_rng(0)
N, R = len(X_earth), 500
w0 = np.clip(w, 1e-3, None); w0 /= w0.sum()          # Dirichlet needs strictly positive weights
counts = np.zeros(N)

for _ in range(R):
    w_i = rng.dirichlet(50 * w0)                      # concentration controls how far weights wander
    s_i = s * np.exp(rng.normal(0, 0.25, size=s.shape))
    S_i, cov_i = score(X_earth, x_target, w_i, s_i)
    S_i = np.where(cov_i >= 0.6, S_i, -np.inf)        # coverage floor
    thr = np.percentile(S_i[np.isfinite(S_i)], 99)
    counts += (S_i >= thr)

stability = counts / R                                 # fraction of draws in the top 1%
```

Compute and cache this for each preloaded landmark and lens. Chunk the loop if memory is tight. Stable high scorers are credible. Unstable ones get a warning.

---

## 10. Validation by Rediscovery

### 10.1 Rediscovery set

Compile **roughly 30-50 documented analogue sites** with their documented target body and the dimension they were used for. Starter list **(verify each against the literature before using)**: Haughton Crater (Devon Island), McMurdo Dry Valleys, Atacama Desert, Hawaii volcanic sites, Cinder Lake (Arizona), Askja (Iceland), Rio Tinto (Spain), Svalbard sites. Map each to its hex plus first-ring neighbours.

### 10.2 Metrics

With ~85,000 hexes, raw top-k is hard to interpret, so report:

| Metric | Meaning |
|---|---|
| **recall@k** for k = 100, 500, 1000 | Fraction of known sites inside the top-k hexes for their target |
| **Median percentile rank** | Where known sites land in the full ranking |
| **MRR** | Mean reciprocal rank |
| **Random baseline** | `k / N`, which every method must clearly beat |
| **Negative controls** | Rainforest and heavily vegetated hexes should never rank highly |

### 10.3 Ablation table (to fill in)

| Method | recall@100 | recall@500 | recall@1000 | Median pct rank |
|---|---|---|---|---|
| Random | | | | |
| Single group (terrain only) | | | | |
| Unweighted baseline score | | | | |
| Profile-weighted baseline score | | | | |
| PCA + kNN | | | | |
| Cluster-conditioned retrieval (GMM) | | | | |
| Cluster-conditioned retrieval (HDBSCAN) | | | | |
| + calibrated weights (leave-one-site-out) | | | | |

Use paired bootstrap confidence intervals over sites. Report misses and diagnose them (data gap, resolution, weights).

### 10.4 Decision rule

An ML component is **kept only if** it improves a validation metric over the profile-weighted baseline with a confidence interval that does not cross zero. Otherwise the baseline stays and the component is described honestly as an exploration.

**Interpretation:** if known analogues rank highly for their documented targets, the method is credible and unfamiliar high scorers carry weight as discoveries. If it fails, the weights and features need revisiting before any discovery claims.

---

## 11. Mission Lenses (Profiles)

The default view uses a **Balanced** lens and shows the best match per dimension. Three optional **mission lenses** re-weight the four feature groups for people with a specific goal. Weights are **illustrative starting points to be tuned and stress-tested**, not validated defaults. They live in `profiles.yaml`.

| Lens | Terrain | Thermal | Cold and ice | Composition |
|---|---:|---:|---:|---:|
| **Balanced** (default) | 0.25 | 0.25 | 0.25 | 0.25 |
| **Surface Mobility and Landing** | 0.70 | 0.15 | 0.00 | 0.15 |
| **Cold Regions and Volatiles** | 0.15 | 0.30 | 0.45 | 0.10 |
| **Geology and Mineral Science** | 0.20 | 0.10 | 0.10 | 0.60 |

**Typical targets:** Landing and Mobility: Artemis candidate regions (Shackleton, Malapert, Haworth, de Gerlache and others), Jezero, Gale. Cold Regions: lunar south pole, Mars mid-latitude ice. Geology: Jezero, Gale, lunar highlands and maria.

**How the old weights were remapped.** Barrenness became a mask. The rock/regolith proxy weight was folded into terrain, because no Earth-side rock-abundance feature exists at stage 1. The process-tag weight became tie-breaking and display only, and the dust/wind weight was dropped with the dust lens. In the Cold Regions lens, permafrost and aridity together form the Cold and ice group (0.45), which equals the old 0.30 + 0.15.

**Sliders.** Four sliders (one per group) re-rank instantly. Stability for slider-adjusted weights is recomputed with a reduced number of draws on the backend (benchmark this), and the card shows the preset's stability, marked as such, until the new value is ready.

---

## 12. Product and User Experience

### 12.1 Core interaction

The product is a **target-to-Earth** flow:

1. **Pick a body** (Moon or Mars) and **select a landmark** on the target view.
2. The app computes (or loads) that landmark's feature fingerprint over the matched footprint.
3. The Earth view shows the **best Earth matches**, one card per dimension, plus best overall.
4. The user may apply a **mission lens** or adjust the four sliders to re-rank.
5. Selecting a match opens the scorecard.

There is no mandatory mission selection. Each result is labelled by the dimension in which it is strongest (Section 8.5), and always shown with its overall score and coverage.

### 12.2 Target selection

- **Preloaded landmarks:** Shackleton, Malapert, Haworth, de Gerlache, Jezero, Gale, plus lunar highlands, maria and crater examples. Everything is precomputed, so results are instant.
- **Arbitrary click (optional):** click any point on the Moon or Mars map. Either compute the target's features on demand over the matched footprint, or precompute the full disc grids (about 21,000 Moon and 81,000 Mars) and snap the click to the nearest disc. Polar Moon clicks outside the 70°S-70°N Diviner products need the polar products and a visible coverage note.

### 12.3 Primary views (build first)

| View | Content |
|---|---|
| **Match cards** | Best overall plus best terrain, thermal, cold/ice and composition matches, each with overall `S`, coverage, stability, novelty and shared process tags |
| **Earth similarity map** | H3 heat map coloured by `S` for the selected landmark and lens, with the cards' hexes highlighted |
| **Ranked shortlist** | Top hexes with `S`, group scores, coverage, stability, tags |
| **Novelty view** | Filter to high-similarity, far-from-known-analogue cells, with known sites shown for context |
| **Scorecard** | Per-feature comparison (radar or bar), divergence panel, data sources, stage |

### 12.4 Layout and rendering

- **Version 1 (2D, build first):** two linked panels. The left panel shows the Moon or Mars with landmarks; the right panel shows Earth with the heat map and highlighted matches. Selecting a landmark updates the right panel.
- **Version 2 (3D, polish):** the same two panels become two synchronised globes with connecting arcs from the selected landmark to its matches. No logic changes, only the renderer. The 2D version is always kept as the fallback.

### 12.5 Layers and overlays

- Barrenness mask, shown as greyed-out excluded land
- Curated lava-tube and Sarawak cave layer (Section 14)
- Extreme-environment index
- Known analogue sites (for context and novelty)

### 12.6 Stage-2 refinement

Selecting a shortlisted hex triggers (or loads precomputed) high-resolution analysis at H3 resolution 6-7 for finer features. Results are labelled "refined" and never mixed with stage-1 scores in one ranking.

### 12.7 Usability notes

- Say plainly in the interface that a match compares ~47 km-wide surroundings, not the landmark itself.
- A "no close Earth match" state is a valid, explained result (Section 9.5).
- Stage and coverage are always visible on every card.

---

## 13. Divergence Panel and Confidence

Every result shows what cannot be replicated or has not been measured.

| Factor | Treatment |
|---|---|
| Gravity | Always flagged. Not scored |
| Vacuum / atmosphere | Always flagged. Not scored |
| Radiation | Always flagged. Not scored |
| Permanent-shadow illumination | Flagged where relevant |
| Thermal extremes | Gap reported in kelvin; lunar ΔT is hundreds of kelvin and no terrestrial surface reaches it |
| Dust behaviour | Electrostatic and particle properties not captured by terrestrial proxies |
| Geology | Similar-looking surfaces can differ in cohesion, strength and mineralogy |
| Surface-model DEM | Copernicus GLO-30 includes vegetation and buildings, which can inflate roughness. Treated as screening only |
| Data gaps | No ASTER over Antarctica; permafrost map covers the Northern Hemisphere only; no finer Mars data for stage 2 |

### Confidence block

- Overall similarity `S` and the four group scores
- Per-feature similarity and gap
- Coverage of weighted features
- Ranking stability (fraction of Monte Carlo runs in the top 1%)
- Novelty (geographic and feature)
- Data sources, resolution and uncertainty
- Stage (screening or refined)

> The score supports **preliminary** site selection. It is not a qualification result or a probability that a site is a true twin.

---

## 14. Caves, Lava Tubes and the Sarawak Story

### 14.1 Why the split

Mulu and Niah are humid, biologically active limestone karst. They are a weak structural analogue for dry basaltic lunar lava tubes, and a knowledgeable reviewer will notice. The story is therefore split by what each system genuinely supports.

### 14.2 Lava-tube structural question

Curated catalogue layer, with a young-basalt prior as a map overlay:

- Lava Beds National Monument (USA)
- Hawaii lava tubes
- Iceland lava tubes
- Canary Islands (Tenerife, La Palma)
- Jeju Island (South Korea)

Targets: Lunar Pit Atlas candidates (~281 pits), GRAIL-informed subsurface hints. The platform presents this as a **prior**, never a detection.

### 14.3 Sarawak caves: what they fit

- **Subsurface biology and extremophiles:** relevance to Mars subsurface habitability studies
- **Cave-exploration logistics and robotics:** navigation, communications, mapping and traversal in complex underground environments
- **Education and local engagement:** a memorable local entry point into global space research

### 14.4 Biology / habitability indicator

An extreme-environment index (hyperarid, cold, saline, high UV) is shown as a layer, with a standing note that no global extremophile map exists. Sarawak caves appear as a curated showcase tied to this layer.

---

## 15. Implementation Architecture and Colab Engineering

### 15.1 Compute reality

| Platform | What it gives (free) | Implication |
|---|---|---|
| **Google Colab (free)** | ~12 GB RAM, up to ~12 h per session, ~90 min idle timeout | Design for sessions that die. Checkpoint every stage to Drive |
| **Kaggle Notebooks** | 12 h sessions, datasets can be attached directly | Backup environment |
| **Google Earth Engine** | Free for non-commercial/research use. Python API works in Colab | Does the zonal statistics server-side. **Confirm eligibility and project registration** |

Nothing here needs a paid tier or a GPU. The Earth feature table is roughly 85,000 land hexes plus a few thousand sampled Moon and Mars cells, at ~20 `float32` features, which is tens of megabytes.

### 15.2 Design rules

1. **Precompute, then load.** Every expensive step writes a Parquet file. Later notebooks only read Parquet.
2. **Keep the feature table small.** `float32`, one row per hex, no rasters in memory.
3. **Stay CPU-first.** scikit-learn and NumPy cover everything.
4. **Stream or window big rasters.** Never load an 8 GB GeoTIFF whole.
5. **Fix seeds and pin library versions** so a restarted session reproduces the same ranking.
6. **Resume-safe.** Each notebook checks whether its output exists and skips if so.

### 15.3 Application layers

| Layer | Suggested technology | Responsibility |
|---|---|---|
| Offline feature pipeline | Python, Google Earth Engine, `h3`, `rasterio`, `numpy`, `scipy` | Tile generation, zonal statistics, harmonisation |
| Feature store | Parquet files; DuckDB or PostgreSQL / PostGIS | One row per H3 cell with quality metadata |
| Matching and ML | NumPy, scikit-learn, HDBSCAN | Scoring, group scores, clustering, novelty, stability |
| Backend API | FastAPI | Target feature lookup or computation, ranking, match-card and scorecard payloads |
| Frontend | Vue + Vite (or equivalent) | Landmark picker, match cards, sliders, shortlist, scorecard |
| Mapping | deck.gl or MapLibre for the H3 heat map and two-panel view; CesiumJS for the optional 3D globes | Rendering |
| Caching | Precomputed rankings for every preloaded landmark and lens | Fast demos |

**Principles**

- All heavy computation is **offline**. The live app reads precomputed tables and ranks in memory. Ranking 85,000 hexes against one target is a single vectorised operation.
- The matching engine is independent of the renderer, so the 2D and 3D views share one API.
- Rankings are reproducible from features, weights, method and version tags.

### 15.4 Notebook sequence

| Notebook | Purpose | Output |
|---|---|---|
| `01_tiling.ipynb` | H3 res-4 cells, land filter, antimeridian handling | `hex_cells.parquet` |
| `02_earth_features.ipynb` | Earth Engine zonal statistics in batches | `earth_features.parquet` |
| `03_planetary_features.ipynb` | Moon/Mars disc features from DEM and thermal products | `moon_features.parquet`, `mars_features.parquet` |
| `04_harmonise.ipynb` | Units, baselines, pooled scaling, tolerances | `features_harmonised.parquet`, `scaler.pkl` |
| `05_baseline_scoring.ipynb` | Tolerance-kernel scorer, group scores, lenses | Per-landmark score tables |
| `06_domain_and_clusters.ipynb` | Domain-gap test, PCA, HDBSCAN, GMM | `clusters.parquet`, `pca.pkl`, `gmm.pkl` |
| `07_validation.ipynb` | Rediscovery set, ablations, weight calibration | Results tables |
| `08_novelty_stability.ipynb` | Novelty index and Monte Carlo stability | `shortlist.parquet` |
| `09_export.ipynb` | Match cards, map layers and API-ready tables | GeoJSON/Parquet for the frontend |

### 15.5 Earth Engine batching tips (verify while building)

- Convert each H3 cell to a polygon with `[lng, lat]` ordering. Split or skip cells crossing the antimeridian.
- Process in batches (for example by latitude band) rather than one huge `reduceRegions` call. Use a larger `tileScale` if computations time out.
- For large outputs, prefer `Export.table.toDrive` and read the CSV/Parquet from Drive.
- Mosaic the GLO-30 collection and set its default projection before reducing, and apply the matched-baseline resampling before slope.
- Check your project's **noncommercial quota** in the Earth Engine console. Limits may apply **(verify)**.
- Store distributions (p10, p50, p90), not only means.

### 15.6 Session survival

- Mount Drive and write to it after every stage.
- Keep notebooks idempotent (skip if the output file exists).
- Pin versions in a `requirements.txt` (`scikit-learn>=1.3`, `h3`, `rasterio`, `geopandas`, `earthengine-api`, `pyarrow`).
- Use `float32` everywhere. Avoid holding rasters and tables in memory at once.
- Keep **one source of truth** for group weights, lenses and feature definitions in `profiles.yaml`.

### 15.7 Team split (example)

| Role | Owns |
|---|---|
| Data engineer (Earth) | Notebooks 01-02, Earth Engine batching |
| Planetary data | Notebook 03, polar and local-time handling |
| ML lead | Notebooks 04-06, 08, domain-gap diagnostic |
| Validation | Notebook 07, rediscovery set, ablation table |
| Frontend / integration | Notebook 09, API payloads, two-panel UI, match cards |

---

## 16. Execution Plan and Priorities

> **Logistics:** planning is fine now, but do not begin building the pipeline until the hackathon officially starts. Check the event dates and rules.

### 16.1 Priority order

1. Global H3 scored grid (stage 1)
2. Scoring engine, group scores, lenses and scorecard
3. Rediscovery validation and novelty map
4. Two-panel target-to-Earth interface in 2D, with match cards
5. Stage-2 refinement
6. 3D dual-globe upgrade
7. Mars dust lens (stretch)

### 16.2 Phases

**Phase 0: Preparation (before the event)**
- Finalise this plan, feature table and `profiles.yaml`
- Check the Resources tab for datasets, access and rules
- Compile the candidate list of 30-50 documented analogue sites
- Set up accounts (Earth Engine, Kaggle backup) and repository structure, with no pipeline code
- Resolve the **(verify)** items in Section 20

**Phase 1: Data foundation**
- Generate H3 res-4 land cells with land fraction
- Compute core Earth features per hex (terrain, thermal, cold/ice, composition, barrenness mask)
- Compute Moon and Mars features for preloaded landmarks over matched footprints, and the sampled disc sets for clustering
- Harmonise per Section 6 and store with provenance

**Phase 2: Scoring and validation**
- Implement tolerance-kernel scoring, group scores, coverage and the divergence panel
- Implement the Balanced default and the three lenses
- Run rediscovery validation; tune and document

**Phase 3: ML and discovery**
- Domain-gap test, PCA, joint clustering for analogue regimes
- Weight calibration with leave-one-site-out
- Novelty index and ranking stability
- Produce match-card tables and the novelty shortlist for every preloaded landmark and lens

**Phase 4: Product**
- Two-panel interface in 2D: landmark picker, match cards, map, shortlist, scorecard, sliders
- Curated caves, lava-tube and Sarawak layer
- Stage-2 refinement for top hits

**Phase 5: Polish and presentation**
- 3D dual-globe view and camera animations (if time allows)
- Performance checks on the demonstration hardware
- Demo script covering familiar, unfamiliar and missing-data cases

### 16.3 Cut order if time runs short

1. Mars dust lens
2. Stage-2 refinement
3. 3D dual-globe view (the 2D two-panel interface stays)
4. Arbitrary-click targets (preloaded landmarks stay)

**Never cut:** the global grid, the scoring, the rediscovery check, the match cards and the novelty map.

---

## 17. Evaluation Metrics

| Area | Measure |
|---|---|
| Rediscovery | recall@k, median percentile rank and MRR on documented analogue sites vs random and single-group baselines |
| Discovery | Number of high-similarity, high-stability, low-study cells, with expert plausibility notes |
| Stability | Fraction of Monte Carlo runs each shortlisted hex remains in the top 1% |
| Coverage | Weighted feature coverage per shortlisted cell |
| Discrimination | Different landmarks and lenses yield explainably different rankings, and the per-dimension cards differ meaningfully |
| Harmonisation checks | Slope and roughness reproducible across resolutions; unit tests on conversions |
| Clustering quality | Cluster coherence (adjusted Rand index under resampling), body mix, agreement with known regimes |
| Domain gap | AUC of the Earth-vs-planet classifier and the features excluded as a result |
| Performance | Load time, API latency, interaction smoothness on demo hardware |
| Usability | Task completion for selecting a landmark, reading a match card and scorecard, and finding a novel site |

---

## 18. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Compute or time for global feature extraction | Use Earth Engine `reduceRegions`; stage 1 at res 4 only; precompute; batch by latitude band |
| Coarse hexes hide small matches | Stage-2 refinement of top hits at res 6-7 |
| Clustering splits by body, not terrain | Domain-gap test, exclude separating features, report gaps instead |
| Too few known pairs to calibrate | Strong regularisation, leave-one-site-out, report hand-set weights too |
| Calibration reinforces famous-site bias | Compare calibrated vs hand-set, keep the novelty gate separate from calibration |
| Thermal and composition proxies are weak | Document each proxy, flag gaps in kelvin, never hide them by scaling |
| Surface-model DEM inflates roughness in vegetated terrain | Barrenness mask, treat roughness as screening only |
| Polar Moon targets fall outside 70°S-70°N products | Dedicated polar products and windows, state coverage clearly |
| Antarctica and Southern Hemisphere data gaps (ASTER, permafrost) | Fall back to the LST-based cold proxy and mark coverage |
| Dimension cards oversell a weak overall match | Overall-score threshold before picking a card, and always show overall `S`, coverage and stability |
| Cards cluster on neighbouring hexes | Minimum geographic separation between cards |
| No global boulder, extremophile or lava-tube detection data | Proxy or prior layers only, with explicit statements |
| Sampling bias toward famous sites | Whole-Earth grid; novelty index penalises proximity to known sites |
| Rediscovery fails | Revisit features and weights before making discovery claims; report honestly |
| Colab session loss | CPU-first design, Drive checkpoints, idempotent notebooks, Kaggle backup |
| Dataset access or licence problems | Verify in Phase 0; keep fallbacks (AppEEARS, coarse downloads) |
| Scope too large for the event | Strict priority order and cut list; 2D first |
| Over-claiming | Scores framed as model-defined similarity, not qualification or twin probability. Use the honest-labelling table for ML claims |

---

## 19. Pitch Framing

### 19.1 For challenge judges and technical reviewers

- A systematic, reproducible whole-Earth search rather than a curated list
- Physically harmonised features and tolerance-based similarity
- Real validation by rediscovery with reported recall
- Best matches per dimension, so users see *why* a place matches, not just that it does
- A novelty list of unrecognised candidates, with stability and coverage evidence
- An explicit divergence panel that says where each analogy breaks down

### 19.2 For Sarawak audiences

- Pick a place on the Moon or Mars, then discover places on Earth that nobody has studied
- Sarawak's caves as a genuine fit for subsurface biology, extremophile research and cave-exploration robotics
- Local participation in global space science, with honest scientific framing

### 19.3 Claims discipline

- Claims about reduced testing cost or mission risk are future objectives unless demonstrated by evaluation.
- Describe the method as scoring and classical unsupervised learning validated by rediscovery. Do not describe the whole system as "AI-powered".

---

## 20. Open Items to Verify

Before committing to any dataset or method, check against the challenge's Resources tab and rules:

- [ ] Event start date and when build work is allowed
- [ ] Provided or recommended datasets and any access restrictions
- [ ] Earth Engine account and Cloud project registered (non-commercial), eligibility confirmed
- [ ] Current versions, collection IDs and access routes for the datasets in Section 5
- [ ] GLiM licence
- [ ] Quantitative (not colour-binned) Clementine FeO map
- [ ] TerraClimate or other aridity collection ID and licence
- [ ] WOKAM and Earth Impact Database access (for karst and impact tags)
- [ ] Whether any finer Mars dataset is worth adding for stage 2
- [ ] Judging criteria and required deliverables
- [ ] The list of "already well-known" sites the challenge names, to feed the novelty index
- [ ] Final set of 30-50 documented analogue sites and their documented targets, with literature references
- [ ] Demonstration hardware and network constraints
- [ ] Kaggle session limits, if relying on it as backup
- [ ] `profiles.yaml` and feature definitions drafted
- [ ] Notebook skeletons and repo structure agreed (no data processing yet)

---

## 21. Sources

- [Colab free-tier limits (2026 comparison)](https://www.spheron.network/blog/google-colab-alternatives-8-gpu-clouds-compared-2026/)
- [Kaggle session limits (2026)](https://gpuperhour.com/blog/free-cloud-gpus-and-credits)
- [Earth Engine authentication and noncommercial use](https://developers.google.cn/earth-engine/guides/auth?authuser=3)
- [Earth Engine free for research and education (geemap workshop)](https://nbviewer.org/github/gee-community/geemap/blob/master/docs/workshops/City_Plus_2023.ipynb)
- [Copernicus GLO-30 DEM (Earth Engine)](https://developers.google.cn/earth-engine/datasets/catalog/COPERNICUS_DEM_GLO30?authuser=3)
- [MOD11A2 land surface temperature (Earth Engine)](https://developers-dot-devsite-v2-prod.appspot.com/earth-engine/datasets/catalog/MODIS_061_MOD11A2)
- [MYD11A2 land surface temperature (Earth Engine)](https://developers-dot-devsite-v2-prod.appspot.com/earth-engine/datasets/catalog/MODIS_061_MYD11A2)
- [MCD12Q1 v6.1 land cover (Earth Engine)](https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MCD12Q1)
- [ASTER GED AG100 (Earth Engine)](https://developers.google.com/earth-engine/datasets/catalog/NASA_ASTER_GED_AG100_003)
- [GLiM on PANGAEA](https://doi.pangaea.de/10.1594/PANGAEA.788537)
- [Obu et al. northern-hemisphere permafrost map](https://openpolar.no/Record/ftpangaea:oai:pangaea.de:doi:10.1594%2FPANGAEA.888600)
- [Global Permafrost Zonation Index (Gruber 2012)](https://climatedataguide.ucar.edu/climate-data/global-permafrost-zonation-index-map)
- [Smithsonian GVP volcano search and downloads](https://volcano.si.edu/search_volcano.cfm)
- [LOLA 118 m DEM (USGS Astropedia)](https://astrogeology.usgs.gov/search/map/moon_lro_lola_dem_118m)
- [LOLA gridded DEM products (PDS ODE)](https://ode.rsl.wustl.edu/moon/pagehelp/Content/Missions_Instruments/LRO/LOLA/GDR/GDRDEM.htm)
- [MOLA 463 m DEM (USGS Astropedia)](https://astrogeology.usgs.gov/search/map/mars_mgs_mola_dem_463m)
- [MOLA MEGDR archive (PDS)](https://pds-geosciences.wustl.edu/missions/mgs/megdr.html)
- [Diviner derived data products (PDS ODE)](https://ode.rsl.wustl.edu/moon/pagehelp/Content/Missions_Instruments/Lunar%20Reconnaissance%20Orbiter%20(LRO)/DIVINER/Derived_Data.htm)
- [Diviner GHRM mosaics (PDS ODE)](https://ode.rsl.wustl.edu/moon/pagehelp/Content/Missions_Instruments/Lunar%20Reconnaissance%20Orbiter%20(LRO)/DIVINER/GHRM.htm)
- [TES thermal inertia map (PSI)](https://se.psi.edu/inertia/ti2003.html)
- [TES products (ASU)](https://tes.mars.asu.edu/products)
- [THEMIS thermal inertia mosaic tile (USGS)](https://astrogeology.usgs.gov/search/map/themis_thermal_inertia_mosaic_quantitative_30s060e_100mpp)
- [Clementine FeO map (USGS Astropedia)](https://astrogeology.usgs.gov/search/map/Moon_Clementine_UVVIS_FeO_Color_Binned_1km)
- [Lunar Pit Atlas shapefile (LROC)](https://data.lroc.im-ldi.com/lroc/view_rdr/SHAPEFILE_LUNAR_PIT_LOCATIONS)

---

## Summary

The core innovation is a **systematic, explainable, whole-Earth analogue search**. Pick a landmark on the Moon or Mars and every land tile on Earth is scored against it. The app shows the best match for each dimension (terrain, thermal, cold and ice, composition), validates itself by rediscovering known sites, surfaces credible unrecognised candidates, and states plainly where each analogy fails.
