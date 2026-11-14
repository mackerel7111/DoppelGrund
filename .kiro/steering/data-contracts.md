---
inclusion: fileMatch
fileMatchPattern: ["pipeline/doppelgrund/**/*.py", "web/src/data/**/*.ts", "web/src/engine/**/*.ts", "web/src/workers/**/*.ts", "tests/parity/**", "config/*.yaml"]
---
# Data contracts v1 (humans change these; agents never do)

## C1. Feature registry
Order is fixed: index = column in every `*_features.f32` file and every feature list.

| idx | name | group | unit | transform | Earth | Moon | Mars |
|---|---|---|---|---|---|---|---|
| 0 | slope_p50_deg | terrain | deg | none | GLO-30 and NASADEM (mean where both exist, else the one that does), resampled to ~470 m | LOLA LDEM_64 (~474 m) | MOLA 463 m |
| 1 | slope_p90_deg | terrain | deg | none | same | same | same |
| 2 | relief_std_m | terrain | m | log1p | std of elevation in footprint | same | same |
| 3 | frac_slope_lt_10deg | terrain | fraction | none | share of pixels with slope < 10° | same | same |
| 4 | lst_mean_K | thermal | K | none | mean of MOD11A2 and MOD21A1D/N day/night means (Terra, 10:30/22:30), 2010–2019; mean where both exist, else the one that does | Diviner mean of 10.5 h and 22.5 h bins | NaN (open item) |
| 5 | diurnal_range_K | thermal | K | none | same fusion of mean(day − night) | Diviner T(10.5 h) − T(22.5 h) | NaN |
| 6 | annual_range_K | thermal | K | none | max − min of the fused monthly mean LST | NaN | NaN |
| 7 | frac_below_0C | cold_ice | fraction | none | share of valid LST samples < 273.15 K, averaged over MOD11A2 and MOD21A1D/N | share of Diviner local-time bins < 273.15 K | NaN |
| 8 | permafrost_prob | cold_ice | fraction | none | Obu et al. 2018 (N. Hemisphere), else NaN | NaN | NaN |
| 9 | aridity_index | cold_ice | ratio | log1p | TerraClimate P / PET | 0.0 by definition | 0.0 by definition |
| 10 | pit_cave_density_per_1000km2 | subsurface | per_1000km2 | log1p | catalogued lava tubes / caves per 1000 km² of the hex; 0 only where a systematic survey covers the hex, else NaN | LROC lunar pit catalogue per 1000 km² of the disc; 0 only inside the survey coverage, else NaN | NaN (no catalogue) |

The value counts **catalogued** features (a prior), never detections; absence from a catalogue is not absence of caves. Earth sources and the survey-coverage rule are human-supplied (`config/datasets.yaml`: `earth_caves`, `moon_pits`; TODO(verify)). SMAP freeze/thaw is not part of any feature unless a human approves an exception to science-invariant 6.

**Lithology vector `lith`** (6 values, order fixed): `[mafic_volcanic, felsic_feldspathic, carbonate, siliciclastic, evaporite, ice]`. Fractions of the footprint's *mapped* area, summing to 1. All NaN if nothing in the footprint is mapped. Counts as **one** feature in group `composition`. Group order is fixed: `terrain, thermal, cold_ice, composition, subsurface` (composition keeps index 3, `subsurface` is index 4).

**Earth-only auxiliary columns (never scored):** `barren_frac`, `snow_ice_frac`, `ndvi_mean`, `aster_mafic_idx`, `land_frac`, `vf_dem`, `vf_lst`, `vf_lith` (valid fractions).

## C2. Parquet tables (`data/interim/`)
| File | Key | Columns |
|---|---|---|
| `hex_cells.parquet` | `h3` (str) | `lat`, `lng` (float64 centroid), `land_frac` (f32), `crosses_antimeridian` (bool) |
| `earth_features.parquet` | `h3` | C1 features (f32), `lith_<class>` ×6 (f32), Earth-only aux (f32), `tag_volcanic`, `tag_periglacial`, `tag_evaporitic` (bool), `lat`, `lng` |
| `moon_discs.parquet`, `mars_discs.parquet` | `disc_id` (int32) | `lat`, `lon` (float64, lon in [-180, 180)), C1 features, `lith_<class>` ×6, `vf_dem` |
| `targets.parquet` | `target_id` (str) | `name`, `body` (moon\|mars), `lat`, `lon`, C1 features, `lith_<class>` ×6 |
| `known_site_hexes.parquet` | `site_id` (str) | `h3`, `name`, `documented_target_id`, `dimension`, `well_known` (bool), C1 features, `lith_<class>` ×6 |
| `scaler.json` | — | `{"features":[{"name","median","s"}...], "fitted_on":{"earth":n,"moon":n,"mars":n}}` (values on the transformed scale) |
| `clusters.parquet` | `row_key` (`earth:<h3>`, `moon:<id>`, `mars:<id>`) | `hdb_label` (int16, −1 = noise), `gmm_label` (int16), `gmm_maxprob` (f32) |
| `novelty.parquet` | `h3` | `geo_novelty_km` (f32), `feat_novelty` (f32), `known_site_flag` (bool) |
| `stability/<target>__<lens>.parquet` | `h3` | `stability` (f32 in [0,1]) |

## C3. `config/profiles.yaml`
```yaml
version: 1
features:            # exactly C1, same order
  - {name: slope_p50_deg, group: terrain, unit: deg, transform: none}
  # ... idx 1-9
  - {name: pit_cave_density_per_1000km2, group: subsurface, unit: per_1000km2, transform: log1p}   # idx 10
lith_classes: [mafic_volcanic, felsic_feldspathic, carbonate, siliciclastic, evaporite, ice]
compat_matrix:       # 6x6, symmetric, diagonal 1.0, values in [0,1]; illustrative, set by humans
  - [1.0, 0.2, 0.0, 0.1, 0.0, 0.0]
  - [0.2, 1.0, 0.0, 0.2, 0.0, 0.0]
  - [0.0, 0.0, 1.0, 0.2, 0.3, 0.0]
  - [0.1, 0.2, 0.2, 1.0, 0.2, 0.0]
  - [0.0, 0.0, 0.3, 0.2, 1.0, 0.0]
  - [0.0, 0.0, 0.0, 0.0, 0.0, 1.0]
groups: [terrain, thermal, cold_ice, composition, subsurface]
lenses:
  balanced:         {terrain: 0.225, thermal: 0.225, cold_ice: 0.225, composition: 0.225, subsurface: 0.10}
  landing_mobility: {terrain: 0.70, thermal: 0.15, cold_ice: 0.00, composition: 0.15, subsurface: 0.00}
  cold_volatiles:   {terrain: 0.15, thermal: 0.30, cold_ice: 0.45, composition: 0.10, subsurface: 0.00}
  geology_minerals: {terrain: 0.20, thermal: 0.10, cold_ice: 0.10, composition: 0.55, subsurface: 0.05}
params:
  seed: 20261114
  footprint_radius_km: 23.7
  land_frac_min: 0.3
  coverage_floor: 0.6
  card_overall_percentile: 95
  card_min_separation_km: 300
  novelty_gate_km: 300
  mask: {barren_plus_ice_min: 0.5, ndvi_max: 0.2}   # keep hex if barren+ice >= 0.5 OR ndvi <= 0.2
  stability: {draws: 500, draws_interactive: 100, dirichlet_concentration: 50, tol_log_sigma: 0.25, top_fraction: 0.01, store_top_k: 2000}
assumptions:
  - "Planetary aridity_index = 0.0 (no precipitation)."
```
**Weight rule:** `w_f = W_group / n_group`, where `n_group` = number of features in that group in the registry (terrain 4, thermal 3, cold_ice 3, composition 1, subsurface 1).

## C4. Scoring (Python reference; TypeScript must match within 1e-5)
For Earth row `e` and target `t`:
1. Transform: `x' = log1p(max(x, 0))` if `transform == log1p`, else `x' = x`. NaN stays NaN.
2. Numeric feature `f`: valid iff both `x'_t,f` and `x'_e,f` are finite. `z = |x'_t − x'_e| / s_f`; `k_f = exp(−0.5 z²)`.
3. Lithology: valid iff both vectors have finite values summing > 0. Smooth: `p = lith_e · C`, `q = lith_t · C`, then normalise each to sum 1. `k_lith = 1 − sqrt(max(0, 1 − Σ_i sqrt(p_i q_i)))` (one minus Hellinger distance).
4. `S = 100 · Σ_valid w_f k_f / Σ_valid w_f`; `coverage = Σ_valid w_f / Σ_all w_f`. If `Σ_valid w_f == 0`: `S = NaN`, `coverage = 0`.
5. Group score `S_g` = the same formula restricted to group `g` (×100); NaN if no valid feature in the group or `W_g == 0`.
6. Rows with `flags & 1` (masked) get `S = NaN` and all `S_g = NaN`; `coverage` is still computed.
7. Eligible for ranking: `S` finite and `coverage >= params.coverage_floor`.

## C5. Match cards
1. `eligible` as in C4.7. `thr = percentile(S[eligible], card_overall_percentile)` using **linear interpolation** (numpy default `method="linear"`).
2. `pool = eligible & (S >= thr)`.
3. Card `overall` = argmax `S` over `eligible` (ties → lower row index).
4. For `g` in `[terrain, thermal, cold_ice, composition, subsurface]` in that order: candidates = `pool` & `S_g` finite & great-circle distance to every already-chosen card ≥ `card_min_separation_km` (R = 6371.0088 km, haversine). Pick argmax `S_g`; ties → higher `S`, then lower row index. No candidate → card with `row = null`, `reason = "no_eligible_match"`.
5. Output list of `{kind, row, S, S_g, coverage, reason?}` in the order overall, terrain, thermal, cold_ice, composition, subsurface (6 cards).

## C6. Web bundle (`web/public/data/`, little-endian)
| File | Shape / type | Notes |
|---|---|---|
| `manifest.json` | JSON | see below |
| `earth_h3.txt` | N lines | row order shared by every Earth file |
| `earth_features.f32` | N×11 float32, row-major | **raw** values (untransformed), NaN preserved |
| `earth_lith.f32` | N×6 float32 | |
| `earth_latlng.f32` | N×2 float32 | `[lat, lng]` centroid |
| `earth_novelty.f32` | N×2 float32 | `[geo_novelty_km, feat_novelty]` |
| `earth_cluster.i16` | N int16 | HDBSCAN label, −1 noise |
| `earth_flags.u8` | N uint8 | bit0 masked, bit1 volcanic, bit2 periglacial, bit3 evaporitic, bit4 known-site hex |
| `targets.json` | JSON array | `{id, name, body, lat, lon, features[11], lith[6], cluster, notes, coverage_notes[]}`; NaN written as `null` |
| `stability/<target>__<lens>.json` | JSON | `{target, lens, draws, rows: [[row, frac], ...]}` top `store_top_k` |
| `moon_features.f32`, `moon_lith.f32`, `moon_latlon.f32` (+ mars) | M×11 / M×6 / M×2 | optional full disc grids for arbitrary clicks |
| `earth_index_4096x2048.png` | RGB PNG | equirectangular; pixel value = row+1 encoded `R·65536 + G·256 + B`; 0 = no hex; x=0 at lon −180, y=0 at lat +90 |
| `layers/*.geojson` | GeoJSON | `land`, `known_sites`, `lunar_pits`, `lava_tubes`, `sarawak_caves`, `volcanoes` |
| `textures/{earth,moon,mars}.jpg` | 4096×2048 or 2048×1024 | equirectangular basemaps |

`manifest.json`:
```json
{
  "contract": "doppelgrund-bundle/1",
  "created_utc": "2026-11-14T00:00:00Z",
  "synthetic": false,
  "h3_res": 4,
  "n_hex": 0,
  "features": [{"name": "slope_p50_deg", "group": "terrain", "unit": "deg", "transform": "none", "median": 0.0, "s": 1.0}],
  "lith_classes": ["mafic_volcanic", "felsic_feldspathic", "carbonate", "siliciclastic", "evaporite", "ice"],
  "compat_matrix": [[1.0]],
  "lenses": {"balanced": {"terrain": 0.25, "thermal": 0.25, "cold_ice": 0.25, "composition": 0.25}},
  "params": {},
  "files": {"h3": "earth_h3.txt", "features": "earth_features.f32"},
  "sources": [{"feature": "slope_p50_deg", "body": "earth", "dataset": "COPERNICUS/DEM/GLO30", "version": ""}]
}
```
Budget: bundle ≤ 40 MB excluding textures; textures ≤ 15 MB total.

## C7. Parity vectors (`tests/parity/vectors.json`)
```json
{"contract": "doppelgrund-parity/1",
 "cases": [{"name": "...", "earth_features": [[...11]], "earth_lith": [[...6]], "latlng": [[lat, lng]], "flags": [0],
            "target_features": [...11], "target_lith": [...6], "median": [...11], "s": [...11],
            "transforms": ["none", "..."], "compat_matrix": [[...]], "lens_weights": {"terrain": 0.25},
            "params": {"coverage_floor": 0.6, "card_overall_percentile": 95, "card_min_separation_km": 300},
            "expected": {"S": [...], "coverage": [...], "group": [[t, th, c, comp, sub]], "cards": [...]}}]}
```
NaN is encoded as `null`. Cases must include: all-valid, partial NaN, all-NaN row, masked row, zero-weight group, ties, antimeridian neighbours, identical target and row (S = 100).

## C8. Worker protocol (`web/src/workers/protocol.ts`)
| Request | Response |
|---|---|
| `{type:"init", baseUrl}` | `{type:"ready", nHex, synthetic}` or `{type:"error", message}` |
| `{type:"rank", reqId, target:{features, lith}, weights:{terrain,thermal,cold_ice,composition}}` | `{type:"ranked", reqId, S: Float32Array, coverage: Float32Array, groups: Float32Array (N×5), cards: Card[], top: Int32Array (best 200 rows)}` (buffers transferred) |
| `{type:"stability", reqId, target, weights, draws}` | `{type:"progress", reqId, done, total}` then `{type:"stability", reqId, rows:[row, frac][]}` |
| `{type:"paint", reqId, colorBy:"S"\|"novelty"\|"terrain"\|"thermal"\|"cold_ice"\|"composition"\|"subsurface", palette}` | `{type:"painted", reqId, width, height, rgba: Uint8ClampedArray}` |
Every response echoes `reqId`. The UI ignores responses whose `reqId` is older than the latest request.
