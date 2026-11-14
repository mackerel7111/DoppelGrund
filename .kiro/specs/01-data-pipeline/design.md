# Design: 01 Data pipeline

## 1. Module map and signatures
```python
# doppelgrund/tiling.py
def all_cells(res: int = 4) -> list[str]
def cell_polygon(cell: str) -> shapely.Polygon | shapely.MultiPolygon   # split at antimeridian
def land_fraction(cells: list[str], land: gpd.GeoDataFrame) -> pd.Series  # equal-area CRS (EPSG:6933)
def build_hex_cells(land_path: Path, land_frac_min: float) -> pd.DataFrame  # C2 hex_cells

# doppelgrund/localzonal.py  (local rasters without Earth Engine)
def child_points(cells: list[str], child_res: int = 6) -> pd.DataFrame        # cell, lat, lng (49 per res-4 cell)
def sample_raster(path: Path, lat: np.ndarray, lng: np.ndarray, band: int = 1) -> np.ndarray  # NaN for nodata
def zonal_mean(cells, path, child_res=6) -> pd.Series
def zonal_class_fractions(cells, path, crosswalk: pd.DataFrame, source: str, child_res=6) -> pd.DataFrame  # lith_* cols

# doppelgrund/earth/ee_client.py
def init_ee(project: str | None = None) -> None          # reads DOPPELGRUND_EE_PROJECT
def to_ee_feature_collection(hex_df: pd.DataFrame) -> "ee.FeatureCollection"  # property h3

# doppelgrund/earth/batch.py
@dataclass class Batch: name: str; lat_min: float; lat_max: float; product: str
def plan_batches(hex_df, band_deg: float = 10.0, products=("terrain", "thermal", "mask", "climate", "aster")) -> list[Batch]
def submit(batch: Batch, image: "ee.Image", reducer: "ee.Reducer", scale: float, tile_scale: int, drive_folder: str) -> str  # task id
def poll(jobs_path: Path) -> dict
def collect(drive_dir: Path, product: str) -> pd.DataFrame   # concat exported CSVs, dedupe on h3

# doppelgrund/earth/terrain.py | thermal.py | cold.py | composition.py | mask.py
def terrain_image(cfg) -> "ee.Image"       # bands: slope (deg), elev (m), lt10 (0/1)
def terrain_reducer() -> "ee.Reducer"      # percentile([50,90]) on slope, stdDev on elev, mean on lt10
def thermal_image(cfg) -> "ee.Image"       # bands: lst_mean_K, diurnal_range_K, annual_range_K, below0_frac
def climate_image(cfg) -> "ee.Image"       # band: aridity_index
def mask_image(cfg) -> "ee.Image"          # bands: barren_frac, snow_ice_frac, ndvi_mean
def aster_image(cfg) -> "ee.Image"         # band: aster_mafic_idx
def permafrost_local(cells, path) -> pd.Series
def glim_local(cells, path, crosswalk) -> pd.DataFrame

# doppelgrund/earth/tags.py
def volcanic_tag(cells, volcanoes: pd.DataFrame) -> pd.Series   # within cell or ring-1 (h3.grid_disk(cell, 1))
def derived_tags(df) -> pd.DataFrame

# doppelgrund/earth/assemble.py
def assemble_earth(hex_df, parts: list[pd.DataFrame]) -> pd.DataFrame   # C2 earth_features, column order fixed
def write_with_provenance(df, path, datasets: list[str], params: dict) -> None

# doppelgrund/planetary/lattice.py
BODY_RADIUS_KM = {"moon": 1737.4, "mars": 3389.5}
def fibonacci_lattice(body: str, footprint_area_km2: float) -> pd.DataFrame   # disc_id, lat, lon
def sample_discs(lattice, n: int, seed: int, must_include: list[tuple[float, float]]) -> pd.DataFrame

# doppelgrund/planetary/rasterio_io.py
def body_crs(body: str) -> str                   # "+proj=longlat +R=<m> +no_defs"
def aeqd_crs(body: str, lat: float, lon: float) -> str
def read_disc_window(path, body, lat, lon, radius_km, res_m=470.0) -> tuple[np.ndarray, float]  # (grid in AEQD, pixel size m), NaN outside data
def disc_mask(shape, res_m, radius_km) -> np.ndarray

# doppelgrund/planetary/terrain.py
def slope_deg(dem: np.ndarray, res_m: float) -> np.ndarray       # THE shared algorithm (see §3)
def terrain_features(dem, res_m, radius_km) -> dict[str, float]

# doppelgrund/planetary/thermal.py
def diviner_features(lat, lon, products: "DivinerProducts") -> dict[str, float]

# doppelgrund/planetary/composition.py
def map_unit_fractions(lat, lon, radius_km, geomap: gpd.GeoDataFrame, crosswalk, source) -> dict[str, float]

# doppelgrund/planetary/targets.py
def build_disc_table(body: str, discs: pd.DataFrame, cfg) -> pd.DataFrame
def build_targets(landmarks: pd.DataFrame, cfg) -> pd.DataFrame
```

## 2. Earth Engine recipes (verify each call while building; see skill `earth-engine-features`)
- **DEM:** `ee.ImageCollection(earth_dem).select("DEM").mosaic().setDefaultProjection(<first image projection>)`, then `.reduceResolution(ee.Reducer.mean(), maxPixels=1024).reproject(crs="EPSG:4326", scale=470)`.
- **Slope:** use the shared algorithm (§3). Preferred: implement Horn 3×3 in EE with `convolve` kernels and metric pixel spacing from `ee.Image.pixelLonLat()`. Fallback: `ee.Terrain.slope` **only if** task 1.4b shows the numpy implementation can mirror it within tolerance.
- **lt10:** `slope.lt(10)`; `frac_slope_lt_10deg` = mean over hex.
- **LST:** filter years; `LST_Day_1km × 0.02`, `LST_Night_1km × 0.02`. Per pixel: `lst_mean` = mean over all valid day and night; `diurnal` = mean of (day − night) where both valid; `annual` = max − min of 12 monthly means; `below0` = mean of (value < 273.15) over all valid samples.
- **Mask:** MCD12Q1 LC_Type1 per year → per-pixel share of years in barren class and in snow/ice class; MOD13A2 NDVI × 0.0001 mean.
- **Climate:** annual P and PET totals averaged over years; ratio. Check each band's scale factor in the catalogue.
- **Reduce:** `image.reduceRegions(collection=fc_band, reducer=..., scale=<native or 470>, tileScale=4)`; export with `ee.batch.Export.table.toDrive(..., fileFormat="CSV", selectors=[...])`.
- Scales: terrain 470 m; LST 1000 m; mask 500 m; climate native (~4.6 km); ASTER 100 m → use 500 m.

## 3. The shared slope algorithm
Horn (1981) 3×3 on a metric grid with pixel size `res_m`:
`dz/dx = ((c + 2f + i) − (a + 2d + g)) / (8·res_m)`, `dz/dy = ((g + 2h + i) − (a + 2b + c)) / (8·res_m)`, `slope = degrees(arctan(sqrt(dzdx² + dzdy²)))`. Edge pixels and any window containing NaN → NaN. Implemented once in `doppelgrund/planetary/terrain.py::slope_deg` and mirrored in EE. Task 1.4b proves agreement.

## 4. Planetary disc procedure
1. AEQD CRS centred on the disc (`+proj=aeqd +lat_0=<lat> +lon_0=<lon> +R=<m> +units=m`).
2. Output grid: square, side `2·(radius + 2·res)` at `res_m = 470`.
3. `rasterio.warp.reproject` from the source (`body_crs`, geotransform from the product label) with bilinear resampling for DEM; read only a source window around the disc (pad 1°, handle longitude wrap and polar caps by reading full-longitude strips poleward of ±80°).
4. Slope via §3, mask to radius 23.7 km, then statistics: p50, p90 of slope; std of elevation; share of slope < 10°.
5. Never trust scaling constants: read scale factor, offset and units from the product label (.LBL / GeoTIFF tags).

## 5. Diviner
Inspect the product structure first (task 1.14 starts with a notebook cell listing files, dimensions and local-time axis). Expected: maps binned at 2 px/deg and 0.25 h of local time. Use bins centred at 10.5 h and 22.5 h. For `frac_below_0C`, use all local-time bins present for that pixel. Disc value = mean over pixels whose centres fall within the disc.

## 6. Composition
- Earth: GLiM gridded (~0.5°) via `localzonal.zonal_class_fractions` with the crosswalk.
- Moon/Mars: geologic map polygons intersected with the disc (in AEQD), area-weighted unit fractions, then crosswalk to six classes and renormalise over mapped classes.

## 7. Outputs and order of work
| Output | Producer | Needed by |
|---|---|---|
| `hex_cells.parquet` | 1.1 | all Earth tasks |
| `ee_jobs.json`, Drive CSVs | 1.3–1.8 | 1.10 |
| `earth_features.parquet` (+ provenance) | 1.10 | spec 02 |
| `moon_discs.parquet`, `mars_discs.parquet` | 1.13–1.16 | spec 02 |
| `targets.parquet`, `known_site_hexes.parquet` | 1.17 | spec 02 |
| `qa/report.html` | 1.18 | humans (gate G1) |

## 8. Degraded modes (decided by the orchestrator at the listed hour)
| Hour | Condition | Action |
|---|---|---|
| H10 | < 50% of terrain batches done | Halve band width; raise tileScale; drop ASTER |
| H14 | terrain still incomplete | Run remaining bands at 1 km resampling, flag `degraded_terrain` in provenance |
| H18 | Diviner unreadable | Moon thermal = NaN; UI note |
| H20 | Moon/Mars geology unavailable | lith = NaN on that body; composition group drops out via coverage |
