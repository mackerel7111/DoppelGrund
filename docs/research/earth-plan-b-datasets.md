# Plan B: Earth features from downloadable files (no Earth Engine)

Written 2026-11-14 in case the Earth Engine extraction cannot be finished. Nothing here is wired into
`real.py` yet and nothing has been downloaded. **Verified** = read from the provider's catalogue or a
HEAD request today. **TODO(verify)** = from memory or untested.

## Dataset list

| Feature group | Dataset | Access | Size for our use | Status |
|---|---|---|---|---|
| Terrain (`slope_p50/p90`, `relief_std`, `frac_slope_lt_10deg`) | NOAA **ETOPO 2022**, 15 arc-second, `surface` GeoTIFF tiles (15 x 15 degree) | HTTP, **no login** | about 33 MB per tile; 288 tiles in all, roughly 5 GB for the land tiles | Tile URL and size verified (below). Land source mix **TODO(verify)**: use the `15s_surface_sid_gtif` source-ID tiles to see which input fills each pixel |
| Thermal (`lst_mean_K`, `diurnal_range_K`, `annual_range_K`, `frac_below_0C`) | MODIS Terra **MOD11C2 V061**, 8-day, 0.05 degree CMG | NASA Earthdata login (free) | 460 granules for 2010-2019 at 58 MB = **27 GB** (2015-2019 only: 13 GB) | Collection, 460 granules and sizes verified in CMR |
| Barren / snow-ice share | MODIS **MCD12C1 V061**, yearly land cover, 0.05 degree CMG (percent per class) | Earthdata login | 1.19 GB per year; use one or a few years (class shares barely change) | Verified; years to use are a choice |
| NDVI (mask) | MODIS Terra **MOD13C2 V061**, monthly, 0.05 degree CMG | Earthdata login | 98 MB per month; 120 months = 11.8 GB; 12 months = 1.2 GB | Verified in CMR |
| Aridity (`aridity_index`) | CGIAR **Global Aridity Index v3.1**, annual (`Global-AI_ET0__annual_v3_1.zip`) | figshare, **no login**, CC BY 4.0 | 646 MB | Verified via the figshare API (DOI 10.6084/m9.figshare.7504448.v7) |
| Permafrost, lithology | Obu 2018 and GLiM | already local | - | no change |
| `aster_mafic_idx` | not replaced | - | - | An unscored, unverified placeholder index; leave NaN |

Totals: **about 21 GB** with the reduced windows below, **about 61 GB** with the full 2010-2019 windows.
Both fit the disk (958 GB free).

Verified URLs and sizes:
- ETOPO tile: `https://www.ngdc.noaa.gov/mgg/global/relief/ETOPO2022/data/15s/15s_surface_elev_gtif/ETOPO_2022_v1_15s_N30E000_surface.tif` (HTTP 200, 33,088,066 bytes). The `thredds/fileServer` path for GeoTIFF returned 404; use the `mgg/global` path.
- MODIS: NASA CMR collections `C2565788893-LPCLOUD` (MOD11C2), `C2484078896-LPCLOUD` (MCD12C1), `C2565788914-LPCLOUD` (MOD13C2). Files are HDF4 under `data.lpdaac.earthdatacloud.nasa.gov`.
- HDF4 reading on this machine: a `pyhdf` Windows wheel exists for Python 3.12 (`pyhdf-0.11.7-cp312-cp312-win_amd64`). **Reading a real MODIS CMG file is untested.**

## What changes scientifically (to decide before using it)
1. **Terrain** moves from GLO-30 + NASADEM (approved plan) to ETOPO. At 15 arc-seconds it matches the
   ~470 m baseline of invariant 4, but its land inputs must be checked and slope must be computed in metres
   (grid spacing shrinks with latitude).
2. **Thermal** is MOD11C2 alone, so the MOD21 fusion is dropped. This is the same product as the old
   baseline, still Terra and still overpass-matched (invariant 6 holds). `frac_below_0C` uses 8-day
   composites counting day and night separately, as in the fixed code. The 0.05 degree grid (about 5.6 km)
   is coarser than 1 km, but a hex is about 42 km across, so a hex still holds about 7 x 7 pixels.
3. **Cover and NDVI** at 0.05 degrees instead of 500 m / 1 km; the mask rule is unchanged.
4. **Aridity** covers 1970-2000 climate, not 2010-2019 like the TerraClimate version.
5. **Reduced windows** (2015-2019 thermal, one year of NDVI and land cover) cut the download by two thirds
   but change the stated period; record whatever is used in `config/datasets.yaml`.

Rejected: WorldClim air temperature (not skin temperature, 1970-2000, no distribution of samples) and ESA
WorldCover (10 m, hundreds of GB).

## Work to do if this becomes the plan
- Download helpers with checksums and resume (ETOPO and figshare need no login; MODIS needs `earthaccess`
  plus an Earthdata login in the environment or `~/.netrc`).
- `earth_local()` already shows the per-hex sampling pattern; add a pixel-to-hex index built once per grid and
  per-hex statistics with `numpy.bincount`.
- Expected effort: a day of work, mostly validating each product against the 5 probe hexes from the Earth
  Engine run (`sahara`, `atacama`, `himalaya`, `arctic_70N`, `antarctica`).

## Terrain check against Earth Engine (2026-11-14, 5 probe hexes)
`doppelgrund.earth.terrain` (ETOPO 15 arc-second, Horn slope in metres with east-west spacing scaled by
cos(latitude)) takes 0.2 s for the 5 hexes (about an hour for all 81,772 on one core).

| Hex | slope p50 ETOPO / Earth Engine | slope p90 | relief std m | share < 10 deg |
|---|---|---|---|---|
| Sahara | 0.46 / 0.47 | 1.29 / 1.22 | 36.4 / 36.4 | 1.00 / 1.00 |
| Atacama | 3.38 / 3.19 | 7.50 / 6.93 | 378 / 375 | 0.97 / 0.98 |
| Himalaya | 6.48 / 6.06 | 14.9 / 13.9 | 240 / 240 | 0.70 / 0.74 |
| Antarctica | 0.21 / 0.11 | 0.52 / 0.32 | 33.1 / 33.0 | 1.00 / 1.00 |
| 70 N | **13.0 / 0.002** | **28.5 / 9.8** | 198 / 153 | **0.37 / 0.90** |

Mid-latitudes agree within about 7% on slope (ETOPO steeper) and within 1% on relief. At 70 N the two
disagree completely. The Earth Engine slope is the biased one: `earth_remote()` divides the east-west
gradient by the equatorial pixel size (its own `ponytail` comment says poleward slopes are biased), so
it underestimates slope by a factor cos(latitude), 0.34 at 70 N and 0.86 at 30 N. That also explains why
ETOPO reads about 7% steeper in the Himalaya hex. The Plan B calculation is the physically correct one.
Limits still open: pixels below sea level are dropped as ocean (so inland depressions are missing), and
the 70 N median of 13 degrees has not been checked against an independent source.

