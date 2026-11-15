# Data sources

Stub generated from the keys in `config/datasets.yaml` (2026-10-30). Entries marked `no` have no values yet:
humans fill them in task 00/0.8. `earth_land` and `textures` were filled and checked against their source pages (2026-10-30). Only `verified: true` entries may be listed without a caveat.

| key | dataset | provider/agency | version | licence | citation | how used | verified |
|---|---|---|---|---|---|---|---|
| earth_dem | TODO(verify) | | | | | Earth terrain (slope, relief) | no |
| earth_lst_terra | TODO(verify) | | | | | Earth thermal | no |
| earth_land | Natural Earth 1:110m land polygons (`config/ne_land.geojson`) | Natural Earth | 1:110m physical vectors | Public domain | Made with Natural Earth. Free vector and raster map data @ naturalearthdata.com. | Land mask and basemap; land cells and `layers/land.geojson` of the synthetic land-coverage bundle | yes |
| earth_ndvi | TODO(verify) | | | | | Earth vegetation mask | no |
| earth_aster_ged | TODO(verify) | | | | | Earth auxiliary (mafic index, not scored) | no |
| earth_climate | TODO(verify) | | | | | Earth aridity index | no |
| earth_glim | TODO(verify) | | | | | Earth lithology | no |
| earth_permafrost | TODO(verify) | | | | | Earth permafrost probability | no |
| earth_volcanoes | Smithsonian GVP Volcanoes of the World, Holocene volcanoes (WFS GeoJSON, 1,214 points, fetched 2026-11-14) | Smithsonian Institution GVP | live database, version not stated | TODO(verify) | Global Volcanism Program, Volcanoes of the World | Map layer (and the volcanic tag source): `layers/volcanoes.geojson` | no |
| earth_sarawak_caves | `config/sarawak_caves.csv`, 2 hand-listed Sarawak karst caves (Deer Cave, Niah), Wikipedia coordinates | own list | 2026-11-14 | n/a | TODO(verify) | Display layer only (`layers/sarawak_caves.geojson`, kind karst_cave); never scored and never presented as a lava-tube analogue | no |
| earth_dem_nasadem | NASADEM Merged DEM Global 1 arc second (`NASA/NASADEM_HGT/001`, band `elevation`, SRTM Feb 2000) | NASA JPL / USGS (LP DAAC), via Earth Engine | 001 | NASA data, any purpose without prior permission | NASA JPL (2020), doi:10.5067/MEaSUREs/NASADEM/NASADEM_HGT.001 | Earth terrain: averaged with Copernicus GLO-30 where both exist, else the one that does (likely GLO-30 only poleward of ~60 deg, TODO(verify)) | no |
| earth_lst_mod21_day / earth_lst_mod21_night | MODIS Terra MOD21A1D / MOD21A1N daily LST and 3-band emissivity, 1 km (`MODIS/061/MOD21A1D`, `MODIS/061/MOD21A1N`, band `LST_1KM`) | NASA LP DAAC, via Earth Engine | 061 | No restrictions on use, sale or redistribution | TODO(verify) | Earth thermal: fused with MOD11A2 (Terra, same overpass) for lst_mean_K, diurnal_range_K, annual_range_K, frac_below_0C, but only where MOD21 is valid on >= 50% of days (sparse polar records are clear-sky/summer-biased; MOD11A2 alone there) | no |
| earth_smap_ft | SMAP enhanced L3 freeze/thaw state `SPL3FTP_E`, HDF5 | NSIDC DAAC, via NASA Earthdata | 004 | Free Earthdata Login; citation required, no licence named | Xu et al. (2023), doi:10.5067/NQLCDOZJYAKX | Cross-check only against `frac_below_0C` (`doppelgrund.smap`); 6 a.m./6 p.m. overpass, soil freeze/thaw, from 2015: never fused into a feature | no |
| earth_caves | `config/earth_lava_tubes.csv`, 6 hand-listed lava tubes (Iceland x3, Tenerife, Jeju, Oregon); karst excluded | own list, coordinates read from Wikipedia | 2026-11-14 | n/a | TODO(verify) | `pit_cave_density_per_1000km2` per hex, positive-only: NaN where no listed tube, never 0; coordinates unverified | no |
| mars_caves | none | | | | | Mars stays NaN until a catalogue has been read and its false-positive rate judged | no |
| earth_land | TODO(verify) | | | | | Land mask and basemap | no |
| moon_dem_stage1 | TODO(verify) | | | | | Moon terrain (stage 1) | no |
| moon_dem_stage2 | TODO(verify) | | | | | Moon terrain (stage 2, stretch) | no |
| moon_diviner | TODO(verify) | | | | | Moon thermal and cold fraction | no |
| moon_geology | TODO(verify) | | | | | Moon lithology | no |
| moon_pits | LROC lunar pit catalogue (`LUNAR_PIT_LOCATIONS.CSV`, 278 pits, cp1252) | NASA / ASU LROC team (PDS) | updated 2021-03-09 | not stated | Wagner and Robinson (2021), LPSC 52 #2530 | `pit_cave_density_per_1000km2` per Moon disc, positive-only; 'Uncertain' pits dropped (266 used); no survey-coverage statement, so no zeros | no |
| mars_dem | TODO(verify) | | | | | Mars terrain | no |
| mars_geology | TODO(verify) | | | | | Mars lithology | no |
| mars_tes_ti | TODO(verify) | | | | | Mars thermal (open item) | no |
| textures (earth) | Blue Marble Next Generation, August 2004, topography and bathymetry, 5400x2700 (`world.topo.bathy.200408.3x5400x2700.jpg`) | NASA Earth Observatory | 2004 | NASA imagery, generally not copyrighted; credit NASA Earth Observatory | NASA Earth Observatory (Reto Stockli, NASA/GSFC), Blue Marble: Next Generation | Earth basemap texture (4096x2048, display only) | yes |
| textures (moon) | CGI Moon Kit, LROC WAC colour map, 2K JPG (`lroc_color_2k.jpg`), SVS 4720 | NASA Scientific Visualization Studio | 2025 version | NASA reproduction guidelines; the SVS page states no separate licence; credit NASA's Scientific Visualization Studio | NASA's Scientific Visualization Studio; Ernie Wright (USRA), Noah Petro (NASA/GSFC); LROC WAC Color Mosaic, Arizona State University | Moon basemap texture (2048x1024, unmodified copy, display only; "optimized for aesthetics, not science") | yes |
| textures (mars) | Mars Viking Colorized Global Mosaic 232 m, MDIM 2.1 (1 km JPG derivative `mars_viking_mdim21_clrmosaic_1km.jpg`) | USGS Astrogeology Science Center (NASA Ames) | MDIM 2.1, 2009-02-02 | Public domain, no use constraints | USGS Astrogeology Science Center, Mars Colorized Viking Mosaic (MDIM 2.1), originator NASA Ames | Mars basemap texture (4096x2048, display only) | yes |

The current web bundle is synthetic (`manifest.synthetic = true`): no value shown in the app comes from these datasets yet.

## Intro storyboard images

Served from `web/public/story/`.

- `earth.webp`: "The Earth seen from Apollo 17" (NASA, AS17-148-22727, public domain), via Wikimedia Commons: https://upload.wikimedia.org/wikipedia/commons/9/97/The_Earth_seen_from_Apollo_17.jpg. Cropped to the disc, outside-circle pixels made transparent.
- The other 8 images (`space`, `moon-surface`, `mars-surface`, `telescope`, `moon`, `mars`, `doppel`, `doppel-confused`): `Doppel_StoryBoard/` assets supplied by the team. Source and licence TODO(verify).
