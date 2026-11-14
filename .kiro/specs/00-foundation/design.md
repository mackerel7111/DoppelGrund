# Design: 00 Foundation

## 1. Python package
`pipeline/pyproject.toml` defines package `doppelgrund` (src at `pipeline/doppelgrund`), optional extras `[dev]` = pytest, hypothesis, ruff; `[ee]` = earthengine-api. Python ≥ 3.11. ruff: line length 100, rules `E,F,I,UP,B,NPY`. pytest markers: `ee`, `slow`.

### `doppelgrund/config.py`
```python
class ConfigError(ValueError): ...

@dataclass(frozen=True)
class Feature: name: str; group: str; unit: str; transform: Literal["none", "log1p"]

@dataclass(frozen=True)
class Profiles:
    version: int
    features: tuple[Feature, ...]
    lith_classes: tuple[str, ...]
    compat_matrix: np.ndarray        # (6, 6) float64
    groups: tuple[str, ...]
    lenses: dict[str, dict[str, float]]
    params: dict                      # raw dict; typed accessors below
    assumptions: tuple[str, ...]
    def feature_weights(self, lens: str | dict[str, float]) -> tuple[np.ndarray, float]:
        """Return (w_numeric[10], w_lith) using the C3 weight rule."""

EXPECTED_FEATURES: tuple[str, ...]  # C1 names in order (hardcoded copy used for validation)

def load_profiles(path: Path = REPO / "config/profiles.yaml") -> Profiles: ...
def load_datasets(path: Path = REPO / "config/datasets.yaml") -> dict[str, dict]: ...
def require_dataset(key: str) -> dict:  # logs warning if verified is false
def load_landmarks(path=...) -> pd.DataFrame  # columns: id, name, body, lat, lon, source
def load_known_sites(path=...) -> pd.DataFrame
def load_crosswalk(path=...) -> pd.DataFrame
REPO: Path  # repo root resolved from this file
```
Validation rules: features equal `EXPECTED_FEATURES` in order; groups exactly `[terrain, thermal, cold_ice, composition]`; each lens has all four groups, non-negative, sums to 1 ± 1e-6; compat matrix 6×6, symmetric, diagonal 1, values in [0,1]; required params present.

## 2. Config file schemas
`config/datasets.yaml` (keys used by code; humans fill values and flip `verified`):
```yaml
earth_dem:        {id_or_url: "COPERNICUS/DEM/GLO30", access: ee, band: DEM, version: "", licence: "", citation: "", verified: false}
earth_lst_terra:  {id_or_url: "MODIS/061/MOD11A2", access: ee, bands: [LST_Day_1km, LST_Night_1km], scale: 0.02, years: [2010, 2019], verified: false}
earth_landcover:  {id_or_url: "MODIS/061/MCD12Q1", access: ee, band: LC_Type1, years: [2010, 2019], barren_class: 16, snow_ice_class: 15, verified: false}
earth_ndvi:       {id_or_url: "MODIS/061/MOD13A2", access: ee, band: NDVI, scale: 0.0001, years: [2010, 2019], verified: false}
earth_aster_ged:  {id_or_url: "NASA/ASTER_GED/AG100_003", access: ee, verified: false}
earth_climate:    {id_or_url: "IDAHO_EPSCOR/TERRACLIMATE", access: ee, bands: [pr, pet], years: [1991, 2020], verified: false}
earth_glim:       {id_or_url: "https://doi.pangaea.de/10.1594/PANGAEA.788537", access: download, verified: false}
earth_permafrost: {id_or_url: "<Obu et al. 2018 PANGAEA record>", access: download, verified: false}
earth_volcanoes:  {id_or_url: "https://volcano.si.edu/", access: download, verified: false}
earth_land:       {id_or_url: "Natural Earth 10m land", access: download, verified: false}
moon_dem_stage1:  {id_or_url: "LOLA LDEM_64 (PDS Geosciences)", access: download, verified: false}
moon_dem_stage2:  {id_or_url: "https://astrogeology.usgs.gov/search/map/moon_lro_lola_dem_118m", access: download, verified: false}
moon_diviner:     {id_or_url: "Diviner global cumulative products (PDS)", access: download, verified: false}
moon_geology:     {id_or_url: "USGS Unified Geologic Map of the Moon", access: download, verified: false}
moon_pits:        {id_or_url: "https://data.lroc.im-ldi.com/lroc/view_rdr/SHAPEFILE_LUNAR_PIT_LOCATIONS", access: download, verified: false}
mars_dem:         {id_or_url: "https://astrogeology.usgs.gov/search/map/mars_mgs_mola_dem_463m", access: download, verified: false}
mars_geology:     {id_or_url: "USGS global geologic map of Mars (Tanaka et al. 2014)", access: download, verified: false}
mars_tes_ti:      {id_or_url: "https://se.psi.edu/inertia/ti2003.html", access: download, verified: false}
textures:         {earth: "", moon: "", mars: "", verified: false}
```
All IDs above are starting points copied from the plan; every one must be confirmed (Resources tab, catalogue page) before `verified: true`.

`config/landmarks.yaml`: list of `{id, name, body, lat, lon, source, notes}`. Humans fill from authoritative sources (NASA Artemis III candidate regions; Jezero; Gale).

`config/known_sites.csv` header: `site_id,name,lat,lon,target_body,documented_target_id,dimension,reference_url,well_known`.

`config/ontology_crosswalk.csv` header: `source,unit_code,unit_name,mafic_volcanic,felsic_feldspathic,carbonate,siliciclastic,evaporite,ice,notes` (weights per row sum to 1 or all 0 = unmapped). Sources: `glim`, `moon_ugm`, `mars_tanaka2014`.

## 3. Makefile (outline)
```make
PY ?= python3
.PHONY: setup lint fmt lint-py lint-web test-py test-web parity verify-quick verify bundle-synthetic bundle dev build preview
setup:            $(PY) -m pip install -e "pipeline[dev,ee]" && cd web && npm ci
lint:             ruff check pipeline && ruff format --check pipeline && cd web && npm run lint
fmt:              ruff check --fix pipeline && ruff format pipeline && cd web && npm run format
lint-py:          ruff check --fix "$(FILE)" && ruff format "$(FILE)"
lint-web:         cd web && npx eslint --fix "$(abspath $(FILE))" && npx prettier --write "$(abspath $(FILE))"
test-py:          pytest pipeline/tests -m "not ee and not slow" -q
test-web:         cd web && npm run test -- --run
parity:           $(PY) -m doppelgrund.export.parity --out tests/parity/vectors.json && cd web && npm run test -- --run tests/parity.test.ts
verify-quick:     lint test-py test-web
verify:           verify-quick parity && cd web && npm run build
bundle-synthetic: $(PY) -m doppelgrund.fixtures.synthetic --bundle web/public/data --interim data/interim/synthetic
bundle:           $(PY) -m doppelgrund.export.bundle --interim data/interim --out web/public/data
dev / build / preview: cd web && npm run dev|build|preview
```
(Indentation with tabs in the real file.)

## 4. Web scaffold
Vite + Vue 3 + TS template, Pinia, Vitest (+ @vue/test-utils, fast-check), ESLint (vue + typescript configs) + Prettier. `vite.config.ts`: `base` from env `DOPPELGRUND_BASE` (GitHub Pages sub-path), `worker: { format: "es" }`. Dependencies added now (pinned): `deck.gl` (core, layers, geo-layers), `h3-js`, `three`, `three-globe`, `chart.js`, `pinia`.

## 5. Synthetic generator (`doppelgrund/fixtures/synthetic.py`)
```python
def make_synthetic(seed: int, n_hex: int = 6000) -> dict[str, pd.DataFrame]: ...
def write_synthetic_interim(out_dir: Path, seed: int) -> list[Path]: ...
def write_synthetic_bundle(out_dir: Path, seed: int) -> list[Path]: ...   # uses doppelgrund.export.bundle writers once they exist; until then its own minimal writer that follows C6 exactly
def main(argv=None) -> int:  # CLI: --bundle DIR --interim DIR --seed N
```
- Cells: take H3 res-4 children of a fixed list of res-0 cells covering deserts/poles/volcanic regions (deterministic), keep first `n_hex`.
- Values: slope_p50 ~ lognormal(mean ≈ 3°), p90 = p50 × U(1.5, 3); relief_std ~ lognormal(≈ 80 m); frac_slope_lt_10 = clip(1 − p50/15); lst_mean 230–320 K by latitude; diurnal 5–40 K; annual 5–60 K; frac_below_0C from lst_mean; permafrost only lat > 45°N; aridity 0.02–3; lith one-hot or two-class mixtures; mask 30% of rows.
- Moon targets: lst_mean ≈ 250 K, diurnal ≈ 250 K, annual NaN, frac_below_0C ≈ 0.5, permafrost NaN, aridity 0, lith mostly mafic or feldspathic. Mars targets: thermal NaN.
- Index map: rasterise each hex polygon (split at the antimeridian) with Pillow `ImageDraw.polygon` onto a 4096×2048 RGB image using the C6 encoding.
- Textures: plain grey placeholder JPGs (real textures replace them later).

## 6. CI (`.github/workflows/`)
- `ci.yml`: on push/PR → setup Python 3.11 + Node LTS, `make setup`, `make bundle-synthetic`, `make verify`.
- `deploy.yml`: on push to `main` → same build, then `actions/upload-pages-artifact` with `web/dist` and `actions/deploy-pages`.

## 7. Banner
`App.vue` shows "Synthetic data — not real results" when `manifest.synthetic === true` (implemented in spec 03 but required here as acceptance for R6.3 once 03 exists).
