---
name: earth-engine-features
description: Compute per-hexagon Earth features with Google Earth Engine (reduceRegions over H3 cells, latitude-band batching, Export.table.toDrive, retries, quotas). Use whenever a task touches doppelgrund/earth/*, Earth Engine, MODIS, Copernicus DEM, MCD12Q1, TerraClimate, ASTER GED, zonal statistics, EE exports or EE errors such as "Computation timed out", "User memory limit exceeded" or "Too many concurrent aggregations".
---

# Earth Engine feature extraction

## Before you start
1. Confirm `ee.Initialize(project=os.environ["DOPPELGRUND_EE_PROJECT"])` works. If not, stop: auth is a human task (01/1.2).
2. Read dataset keys from `config/datasets.yaml` via `doppelgrund.config.require_dataset`. Never type collection IDs in code.
3. Check the dataset catalogue page for band names, scale factors and date coverage; record anything surprising in `docs/STATUS.md` under TODO(verify).

## Pattern
1. Build one `ee.Image` per product with all bands for that product (terrain, thermal, mask, climate, aster).
2. Convert the hex table to an `ee.FeatureCollection` **per latitude band** (≤ 10° tall) with property `h3`. Split antimeridian cells into MultiPolygons (`geodesic=False`).
3. `image.reduceRegions(collection=fc, reducer=..., scale=<product scale>, tileScale=4)`.
4. `ee.batch.Export.table.toDrive(collection=result, description=f"doppelgrund_{product}_{band}", folder="doppelgrund_exports", fileFormat="CSV", selectors=["h3", *bands])`, then `.start()`.
5. Record the task id and state in `data/interim/ee_jobs.json`. Resume = skip bands whose CSV already exists in the Drive folder.

## Reducers
- Slope: `ee.Reducer.percentile([50, 90])` → columns `slope_p50`, `slope_p90` (rename to contract names after export).
- Elevation spread: `ee.Reducer.stdDev()`.
- Fractions (binary images such as `slope < 10`): `ee.Reducer.mean()`.
- Combine with `.combine(other, sharedInputs=False)` and band-specific selection, or run one export per reducer type if combining gets confusing.

## Scales
terrain 470 m (after `reduceResolution(mean)` + `reproject`), LST 1000 m, land cover/NDVI 500 m, climate native, ASTER 500 m.

## When things fail
| Error | Fix in order |
|---|---|
| Computation timed out | tileScale 4 → 8 → 16; then split the band in two |
| User memory limit exceeded | raise tileScale; reduce bands per export |
| Too many concurrent aggregations | lower parallel exports (max ~3 running), wait |
| Empty values for many hexes | check mask/date filter; check `scale`; check polygon winding (`[lng, lat]` order) |

## Checks before marking done
- Row count per band equals hexes in that band.
- Value ranges plausible (slope 0–60°, LST 180–340 K, fractions 0–1).
- Missing stays empty/NaN after CSV load; never fill with 0.
- Write provenance (dataset key, id, scale, years, tileScale, date run).
