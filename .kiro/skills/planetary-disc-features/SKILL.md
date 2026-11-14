---
name: planetary-disc-features
description: Compute Moon and Mars features over equal-area discs (LOLA, MOLA, Diviner, geologic maps) with rasterio/pyproj, including reprojection to disc-centred azimuthal equidistant grids, polar handling, longitude wrap and the shared Horn slope. Use for any task in doppelgrund/planetary/*, Fibonacci lattices, PDS .IMG/.LBL products, USGS Astropedia GeoTIFFs, lunar or Martian slope, Diviner temperatures or planetary lithology.
---

# Planetary disc features

## Geometry
- Sphere radii: Moon 1737.4 km, Mars 3389.5 km. Footprint radius 23.7 km (area ≈ one H3 res-4 hex).
- Source CRS: `+proj=longlat +R=<metres> +no_defs`. Disc CRS: `+proj=aeqd +lat_0=<lat> +lon_0=<lon> +R=<metres> +units=m`.
- Output grid: square, pixel 470 m, half-width = radius + 2 pixels. Mask pixels with centre distance > radius.

## Reading products safely
1. Open with rasterio. If it is a PDS3 `.IMG` with a `.LBL`, read `SCALING_FACTOR`, `OFFSET`, units and map projection from the label. Never hardcode them.
2. Read only a source window around the disc (pad ≥ 1°). Near ±180° longitude, read two windows and concatenate. Poleward of ±80°, read a full-longitude strip.
3. Reproject with `rasterio.warp.reproject` (bilinear for DEM, nearest for categorical).
4. Convert nodata to NaN immediately.

## Terrain
Use `doppelgrund.planetary.terrain.slope_deg(dem, res_m)` (Horn 3×3, NaN-propagating). Statistics on pixels inside the disc: `slope_p50_deg`, `slope_p90_deg`, `relief_std_m` (std of elevation), `frac_slope_lt_10deg`. Require ≥ 50% valid pixels, otherwise NaN.

## Diviner (Moon thermal)
1. First, print the product inventory (files, shapes, local-time axis, units) and paste a summary into STATUS.md.
2. Use local-time bins centred at 10.5 h and 22.5 h for `lst_mean_K` and `diurnal_range_K`; all bins for `frac_below_0C`.
3. Outside product coverage → NaN + a coverage note for targets.

## Composition
Intersect geologic-map polygons with the disc in AEQD, take area fractions per unit, map through `config/ontology_crosswalk.csv` (source `moon_ugm` or `mars_tanaka2014`), renormalise over mapped classes. Unmapped → all NaN.

## Tests to write
Analytic surfaces (plane with known slope, paraboloid) placed at the equator, 60° latitude and −88° latitude must give slopes within 0.5° of truth after reprojection; a disc straddling ±180° must match the same disc shifted to 0°.

## Performance
Log seconds per disc. If > 0.2 s, cache reprojected windows per 5° tile or reduce the sample size; never reduce the resolution silently.
