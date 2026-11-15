# Data sources

Rewritten 2026-11-15 from what the pipeline code actually reads (`pipeline/doppelgrund/real.py`,
`export/bundle.py`) and from `config/datasets.yaml`. `config/datasets.yaml` is human-owned: an agent does
not fill its values or set `verified: true`, so licence, citation and version are copied only where the YAML
already has them and are otherwise `TODO(verify)`. Only rows marked `verified: true` may be quoted without a
caveat. Every other row is a draft for a human to confirm against the catalogue page.

**What the current web bundle is:** real data, not synthetic (`manifest.synthetic = false`), but a **partial
fast-mode** build: a 1-in-20 sample of Earth hexagons, and for Earth an overview-level DEM (470 m) and MODIS
MOD11A2-only thermal (the manifest `resolution` field records this). The MOD21 and 30 m DEM rows below describe
the full-resolution mode and are NOT what the current bundle used for Earth terrain and thermal.

## Earth (hexagon features)

| Feature group | Dataset as used by the code | Provider, access | How used | Licence and citation (as recorded) | YAML key | Verified |
|---|---|---|---|---|---|---|
| Terrain | `COPERNICUS/DEM/GLO30_2024_1` | Copernicus DEM GLO-30, via Earth Engine | slope p50 and p90, relief, share of slope below 10° (averaged with NASADEM where both exist) | TODO(verify) | `earth_dem` (empty) | no |
| Terrain | `NASA/NASADEM_HGT/001`, band `elevation` (SRTM, Feb 2000) | NASA JPL and USGS (LP DAAC), via Earth Engine | same; stops near ±60°, so poleward only GLO-30 (TODO(verify) the limit) | NASA-produced data may be used for any purpose without prior permission. NASA JPL (2020), doi:10.5067/MEaSUREs/NASADEM/NASADEM_HGT.001 | `earth_dem_nasadem` | no |
| Thermal | `MODIS/061/MOD11A2` (Terra, 8-day, about 10:30 and 22:30) | NASA LP DAAC, via Earth Engine | mean temperature, day-night range, annual range, share of samples below 0 °C. Used alone in fast mode | TODO(verify) | `earth_lst_terra` (empty) | no |
| Thermal | `MODIS/061/MOD21A1D`, `MOD21A1N`, band `LST_1KM` (Terra, daily) | NASA LP DAAC, via Earth Engine | fused with MOD11A2 only where MOD21 is valid on at least 50% of days (full-resolution mode only) | No restrictions on use, sale or redistribution. Citation TODO(verify) | `earth_lst_mod21_day`, `earth_lst_mod21_night` | no |
| Thermal cross-check | SMAP enhanced L3 freeze/thaw `SPL3FTP_E` v004 | NSIDC DAAC, via NASA Earthdata | cross-check of `frac_below_0C` only, never fused (6 a.m. and 6 p.m. overpass) | Free Earthdata Login, citation required. Xu et al. (2023), doi:10.5067/NQLCDOZJYAKX | `earth_smap_ft` | no |
| Cold and ice | Permafrost probability, Obu et al. 2018, `UiO_PEX_PERPROB_5.0` (Northern Hemisphere, 2000 to 2016) | PANGAEA download | permafrost extent; NaN south of the map | Obu et al. (2018). Licence TODO(verify) | `earth_permafrost` | no |
| Cold and ice | `IDAHO_EPSCOR/TERRACLIMATE` (precipitation and PET, 2010 to 2020) | via Earth Engine | aridity index (P/PET) | TODO(verify) | `earth_climate` (empty) | no |
| Composition | GLiM, Hartmann and Moosdorf (2012), 0.5° grid | AWI EPIC download | first-level classes mapped to six lithology classes through a crosswalk. The crosswalk in `real.py` is a proposal; `config/ontology_crosswalk.csv` is human-owned and unverified | Hartmann and Moosdorf (2012). Licence TODO(verify) | `earth_glim` | no |
| Subsurface | `config/earth_lava_tubes.csv`, 6 hand-listed lava tubes (Iceland x3, Tenerife, Jeju, Oregon); karst excluded | own list, coordinates read from Wikipedia | `pit_cave_density_per_1000km2`, positive-only (NaN elsewhere, never 0) | n/a. Coordinates unverified | `earth_caves` | no |
| Mask | `MODIS/061/MCD12Q1` (land cover), `MODIS/061/MOD13A2` (NDVI) | NASA LP DAAC, via Earth Engine | barren-plus-ice share and NDVI decide the mask applied before ranking (not scored) | TODO(verify) | `earth_landcover`, `earth_ndvi` (empty) | no |
| Auxiliary | `NASA/ASTER_GED/AG100_003` | NASA, via Earth Engine | a placeholder mafic index, not scored (marked UNVERIFIED in the code) | TODO(verify) | `earth_aster_ged` (empty) | no |
| Layer, tag | Smithsonian GVP Volcanoes of the World, Holocene (WFS, 1,214 points, fetched 2026-11-14) | Smithsonian Institution GVP | map layer and the volcanic tag; never scored | Licence TODO(verify). Global Volcanism Program, Volcanoes of the World | `earth_volcanoes` | no |
| Layer | `config/sarawak_caves.csv`, 2 hand-listed Sarawak karst caves (Deer Cave, Niah) | own list, Wikipedia coordinates | display layer only; never scored, never presented as a lava-tube analogue | citation TODO(verify) | `earth_sarawak_caves` | no |
| Land mask, basemap | Natural Earth 1:110m land (`config/ne_land.geojson`) | Natural Earth | land hexagons and the 2D basemap | Public domain. Made with Natural Earth. Free vector and raster map data @ naturalearthdata.com | `earth_land` | **yes** |

**Offline Plan B inputs** (`earth/terrain.py`, `earth/modis.py`, `earth/download.py`; not used by the current
bundle): NOAA ETOPO 2022 15 arc-second surface tiles, CGIAR aridity v3.1, MODIS MOD11C2, MOD13C2, MCD12C1 V061
through Earthdata. All TODO(verify).

## Moon (disc features, radius 23.7 km)

| Feature group | Dataset as used by the code | Provider, access | How used | Licence and citation (as recorded) | YAML key | Verified |
|---|---|---|---|---|---|---|
| Terrain | LRO LOLA `LDEM_64` global DEM (about 474 m per pixel) | NASA PDS Geosciences, download | slope, relief | TODO(verify) | `moon_dem_stage1` (empty) | no |
| Thermal, cold | LRO Diviner global cumulative averages (18 latitude bands, about 2.8 GB, sha256 in the code) | NASA PDS Geosciences, download | mean temperature, day-night range, share of samples below 0 °C, from local-time bins matched to the MODIS overpass | TODO(verify) | `moon_diviner` (empty) | no |
| Composition | Lunar Prospector GRS, FeO from the 2° elemental abundance table (`lpgrs_high1_elem_abundance_2deg.tab`) | NASA PDS Geosciences, download | lithology vector derived from FeO (`moon_lith_from_feo`, a proposal for human review) | TODO(verify) | `moon_geology` (empty) | no |
| Subsurface | LROC lunar pit catalogue `LUNAR_PIT_LOCATIONS.CSV` (278 pits, 266 used after dropping 12 typed Uncertain; updated 2021-03-09) | NASA and ASU LROC team (PDS) | `pit_cave_density_per_1000km2`, positive-only | Licence not stated; citation required. Wagner and Robinson (2021), LPSC 52, abstract 2530 | `moon_pits` | no |

## Mars (disc features, radius 23.7 km)

| Feature group | Dataset as used by the code | Provider, access | How used | Licence and citation (as recorded) | YAML key | Verified |
|---|---|---|---|---|---|---|
| Terrain | MGS MOLA DEM mosaic, 463 m | USGS Astrogeology, download | slope, relief | TODO(verify) | `mars_dem` (empty) | no |
| Composition | USGS Scientific Investigations Map 3292, global geologic map (shapefile database) | USGS, download | lithology fractions through the crosswalk | TODO(verify) | `mars_geology` (empty) | no |
| Thermal | none: Mars thermal is NaN by contract. The code also reads TES thermal inertia (`ti_nmap2003.bin`, `nmsk2003.bin`, ASU TES and an archived LASP copy) into a side column that is not a scored feature (open item) | ASU, download | not scored | TODO(verify) | `mars_tes_ti` (empty) | no |
| Subsurface | none: Mars stays NaN until a catalogue has been read and its false-positive rate judged | | | | `mars_caves` (empty, deliberate) | no |

## Basemap textures (display only)

| Body | Dataset | Provider | Licence | Citation | Verified |
|---|---|---|---|---|---|
| Earth | Blue Marble Next Generation, August 2004, topography and bathymetry, 5400x2700 (`world.topo.bathy.200408.3x5400x2700.jpg`), resized to 4096x2048 | NASA Earth Observatory | NASA imagery, generally not copyrighted; credit NASA Earth Observatory | NASA Earth Observatory (Reto Stockli, NASA/GSFC), Blue Marble: Next Generation | **yes** |
| Moon | CGI Moon Kit, LROC WAC colour map, 2K (`lroc_color_2k.jpg`), SVS 4720, 2025 version, unmodified copy ("optimized for aesthetics, not science") | NASA Scientific Visualization Studio | NASA reproduction guidelines; the SVS page states no separate licence; credit NASA's Scientific Visualization Studio | NASA's Scientific Visualization Studio; Ernie Wright (USRA), Noah Petro (NASA/GSFC); LROC WAC Color Mosaic, Arizona State University | **yes** |
| Mars | Mars Viking Colorized Global Mosaic 232 m, MDIM 2.1 (1 km JPG derivative `mars_viking_mdim21_clrmosaic_1km.jpg`), resized to 4096x2048 | USGS Astrogeology Science Center (NASA Ames) | Public domain, no use constraints | USGS Astrogeology Science Center, Mars Colorized Viking Mosaic (MDIM 2.1), originator NASA Ames | **yes** |

## Not data sources: what a reviewer should know

- The scorecard shows each feature's source from the bundle manifest, so the manifest and this table must agree.
  Fast-mode sources text for Earth terrain and thermal is written by `export/bundle.py`
  (`FAST_EARTH_SOURCES`).
- Rows 'verified: no' are expected to be confirmed by a human (task 00/0.8) before submission; the
  write-up's data section links here.
- No licence or citation in this file was written from memory: each is either copied from
  `config/datasets.yaml` or `TODO(verify)`.

## Intro storyboard images

Served from `web/public/story/`.

- `earth.webp`: "The Earth seen from Apollo 17" (NASA, AS17-148-22727, public domain), via Wikimedia Commons: https://upload.wikimedia.org/wikipedia/commons/9/97/The_Earth_seen_from_Apollo_17.jpg. Cropped to the disc, outside-circle pixels made transparent.
- The other 8 images (`space`, `moon-surface`, `mars-surface`, `telescope`, `moon`, `mars`, `doppel`, `doppel-confused`): `Doppel_StoryBoard/` assets supplied by the team. Source and licence TODO(verify).
