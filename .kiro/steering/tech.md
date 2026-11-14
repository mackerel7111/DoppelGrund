---
inclusion: always
---
# Tech stack and commands

## Fixed decisions (do not substitute or add alternatives)
| Layer | Choice |
|---|---|
| Offline compute | Python 3.11+ (Google Colab CPU or laptop) + Google Earth Engine Python API |
| Python libraries | numpy, pandas, pyarrow, scipy, scikit-learn (>=1.3, provides HDBSCAN), h3 (v4 API), rasterio, geopandas, shapely (2.x), pyproj, Pillow, earthengine-api, pyyaml, pytest, hypothesis, ruff |
| Frontend | Vue 3 + Vite + TypeScript (strict) + Pinia |
| 2D maps | deck.gl: `MapView` + `H3HexagonLayer` + `GeoJsonLayer` (Natural Earth land as basemap) for Earth; `OrthographicView` + `BitmapLayer` (equirectangular mosaic) for Moon/Mars. No tile servers |
| 3D (stretch) | three + three-globe: two globes in one three.js scene, arcs between them |
| H3 in browser | h3-js v4 (`latLngToCell`, `cellToBoundary`, `cellToLatLng`) |
| Charts | Chart.js (radar and bar on the scorecard) |
| Tests | pytest + hypothesis; Vitest + fast-check; Playwright smoke test (optional) |
| Lint/format | ruff (lint + format); ESLint + Prettier |
| Hosting | Static: GitHub Pages via GitHub Actions; a local `vite preview` copy on the demo laptop |
| Backend | None |

Pin exact versions in `pyproject.toml` and `web/package-lock.json` when the repo is created (H0). Do not upgrade during the hackathon.

## Commands (the Makefile is the interface: run make targets, not raw tools)
| Command | Does |
|---|---|
| `make setup` | Create Python env, `pip install -e pipeline[dev]`, `npm ci` in `web/` |
| `make lint` / `make fmt` | ruff + eslint/prettier on everything |
| `make lint-py FILE=<path>` | ruff check --fix + ruff format on one file |
| `make lint-web FILE=<path>` | eslint --fix + prettier on one file |
| `make test-py` | pytest (unit tests, excludes `-m slow` and `-m ee`) |
| `make test-web` | vitest run |
| `make parity` | Regenerate `tests/parity/vectors.json` from Python, then run the TS parity test |
| `make verify-quick` | lint + test-py + test-web (must stay green) |
| `make verify` | verify-quick + parity + web build |
| `make bundle-synthetic` | Write a schema-valid synthetic bundle to `web/public/data/` |
| `make bundle` | Export the real bundle from `data/interim/` to `web/public/data/` |
| `make dev` / `make build` / `make preview` | Vite dev server / production build / serve the build |

## Hard constraints
- No torch, tensorflow, keras, jax or any neural-network library.
- No server code, no runtime calls to external hosts. The app loads only same-origin static files.
- Bundle arrays are little-endian float32 with NaN preserved (see `data-contracts.md`).
- Python logic lives in the `doppelgrund` package under `pipeline/`. Notebooks only import `doppelgrund`, call functions, plot and save.
- Earth Engine credentials never enter the repo.
