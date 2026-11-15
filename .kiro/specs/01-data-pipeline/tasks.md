# Tasks: 01 Data pipeline

Legend: **[S]** Sonnet-class · **[C]** cheaper model · **[H]** human. Notebooks are thin wrappers created in 1.19.

> **Status note, 2026-11-15 (housekeeping).** The boxes below were never ticked because the pipeline was built as
> one module, `pipeline/doppelgrund/real.py` (plus `caves.py`, `smap.py`, `earth/download.py`, `earth/modis.py`,
> `earth/terrain.py`), not as the per-task files named here. `planetary/` and `qa/` are empty packages. Boxes stay
> unticked where the named files and tests do not exist; where the work exists in `real.py` this table says so.
>
> | Task | Where it stands |
> |---|---|
> | 1.1 tiling | H3 res-4 land cells from `select_land_cells` (`fixtures/synthetic.py`, 81,772 cells); no `tiling.py`, no `hex_cells.parquet`, no tiling test |
> | 1.2 EE auth | done (the stride-20 and stride-4 runs use it) |
> | 1.3 batch runner | in `real.py` `earth_remote`: batches of 25, resume, shards, threads, split on timeout or memory limit; no `--dry-run`, no job-state file, no `ee_client.py`/`batch.py` |
> | 1.4, 1.5, 1.6, 1.8 EE terrain, thermal, climate, mask | in `real.py` (normal and `--fast` modes); no `terrain_ee`/`thermal_ee` tests, plausibility ranges not logged |
> | 1.4b slope cross-check | partial: Plan B ETOPO terrain (`earth/terrain.py`, 7 tests) and an old-vs-new Earth Engine comparison after the cos(latitude) fix; no `planetary/terrain.py slope_deg` and no analytic cross-check test |
> | 1.6, 1.7 permafrost, GLiM | `real.py` `earth_local` (centre sampling); no `localzonal.py` zonal means; crosswalk is a proposal, `config/ontology_crosswalk.csv` unverified |
> | 1.9 process tags | tag columns written by `real.py`; no `tags.py` and no test |
> | 1.10 assemble Earth | `earth_table_real`; per-feature NaN fractions not logged here |
> | 1.11-1.16 planetary | Fibonacci discs (3,000 per body), terrain, Diviner thermal, lithology in `real.py`; none of the named modules exist |
> | 1.17 targets | `targets_real` builds 13 landmarks; `known_site_hexes.parquet` is not written (novelty uses `known_sites.csv` directly) |
> | **1.18 QA report (Gate G1)** | **not built**: `qa/` is empty; a human has not reviewed maps of the real tables |
> | 1.19 notebooks | existing notebooks are `01_datasets_features`, `02_harmonisation`, `03_ee_shard`, not the 01-03 named here |

- [ ] 1.1 [S] H3 land tiling (Window H1–H3)
  - Files: `pipeline/doppelgrund/tiling.py`, `pipeline/tests/test_tiling.py`, `notebooks/01_tiling.ipynb` (minimal cell calling `build_hex_cells`)
  - Tests: antimeridian cell splits into valid parts with total area ≈ unsplit area (±1%); a known ocean cell has `land_frac == 0`; known desert cell `> 0.9`.
  - Acceptance: `make test-py`; running the notebook writes `data/interim/hex_cells.parquet` with 80k–90k rows (record the count in STATUS.md).
  - _Requirements: 1.1–1.3_
  - Depends on: 00/0.5

- [x] 1.2 [H] Earth Engine project and auth (Window H0–H1)
  - Register/confirm the non-commercial Cloud project, run `earthengine authenticate` (local) or Colab auth, set `DOPPELGRUND_EE_PROJECT`.
  - Acceptance: `python -c "import ee; ee.Initialize(project='$DOPPELGRUND_EE_PROJECT'); print(ee.Number(1).getInfo())"` prints 1.
  - _Requirements: 8.1_

- [ ] 1.3 [S] EE client and batch runner (Window H1.5–H3)
  - Files: `pipeline/doppelgrund/earth/ee_client.py`, `pipeline/doppelgrund/earth/batch.py`, `pipeline/tests/test_batch.py` (pure-Python parts only; EE calls marked `@pytest.mark.ee`)
  - Implement band planning, submission, job-state file, resume, retry ladder (R8.3).
  - Acceptance: `make test-py`; dry run (`--dry-run`) prints the batch plan; one tiny real batch (a 2°×2° box) completes on EE.
  - _Requirements: 8.1–8.3_
  - Depends on: 1.1, 1.2

- [ ] 1.4 [S] Terrain image and export (Window H3–H4, then exports run unattended)
  - Files: `pipeline/doppelgrund/earth/terrain.py`, `pipeline/tests/test_terrain_ee.py` (`@pytest.mark.ee`)
  - Follow design §2–§3. Submit all terrain batches immediately after the tiny-box check passes.
  - Acceptance: ≥ 1 full latitude band exported with plausible values (slope p50 0–40°); STATUS.md records batch count and ETA.
  - _Requirements: 2.1, 2.3_
  - Depends on: 1.3

- [ ] 1.4b [S] Slope algorithm cross-check (Window H4–H6)
  - Files: `pipeline/doppelgrund/planetary/terrain.py` (implement `slope_deg`), `pipeline/tests/test_slope_crosscheck.py`
  - Build a synthetic DEM (tilted plane + Gaussian hills) at 470 m; compute slope with numpy `slope_deg` and with the EE path on the same array uploaded as an `ee.Image` constant grid (or compare against analytic slope of the plane). p50 difference ≤ 0.5°.
  - Acceptance: test passes (EE portion `@pytest.mark.ee`, run manually and log result).
  - _Requirements: 2.2, 13.3_
  - Depends on: 1.4

- [ ] 1.5 [S] Thermal image and export (Window H3–H5)
  - Files: `pipeline/doppelgrund/earth/thermal.py`, `pipeline/tests/test_thermal_ee.py` (`@pytest.mark.ee`)
  - Acceptance: one band exported; lst_mean 200–330 K; diurnal ≥ 0 for > 95% of hexes; batches submitted.
  - _Requirements: 3.1–3.3_
  - Depends on: 1.3

- [ ] 1.6 [S] Climate (aridity) and permafrost (Window H4–H6)
  - Files: `pipeline/doppelgrund/earth/cold.py`, `pipeline/doppelgrund/localzonal.py`, `pipeline/tests/test_localzonal.py`
  - Climate via EE export; permafrost via local raster (resample to ~5 km first if memory is tight).
  - Tests: `zonal_mean` on a synthetic raster with known values; nodata becomes NaN.
  - Acceptance: aridity exported for one band; permafrost NaN for all southern-hemisphere hexes.
  - _Requirements: 4.1, 4.2_
  - Depends on: 1.3, 00/0.8 (datasets verified)

- [ ] 1.7 [S] GLiM lithology fractions (Window H4–H6)
  - Files: `pipeline/doppelgrund/earth/composition.py`, `pipeline/tests/test_composition.py`
  - Uses `localzonal.zonal_class_fractions` with crosswalk source `glim`.
  - Tests: synthetic class raster → expected fractions; unmapped hex → all NaN; fractions sum to 1 when mapped.
  - Acceptance: `make test-py`; Earth lith table written.
  - _Requirements: 5.1, 5.2_
  - Depends on: 00/0.8 (crosswalk)

- [ ] 1.8 [C] Mask, NDVI and ASTER exports (Window H5–H6)
  - Files: `pipeline/doppelgrund/earth/mask.py`
  - Acceptance: batches submitted; one band shows `barren_frac` high over Sahara/Atacama test hexes.
  - _Requirements: 5.3, 6.1_
  - Depends on: 1.3

- [ ] 1.9 [C] Process tags (Window H6–H7)
  - Files: `pipeline/doppelgrund/earth/tags.py`, `pipeline/tests/test_tags.py`
  - Tests: volcano point inside a cell and in ring-1 both set the tag; thresholds from R7.
  - _Requirements: 7.1–7.3_
  - Depends on: 1.1

- [ ] 1.10 [C] Assemble Earth features (Window H10–H14, when exports finish)
  - Files: `pipeline/doppelgrund/earth/assemble.py`, `pipeline/tests/test_assemble.py`, `notebooks/02_earth_features.ipynb`
  - Join all parts on `h3`, enforce C2 column order and dtypes, write provenance.
  - Tests: missing part → NaN columns, never zeros; column order equals C2.
  - Acceptance: `data/interim/earth_features.parquet` exists; NaN fraction per feature logged in STATUS.md.
  - _Requirements: 13.2_
  - Depends on: 1.4–1.9

- [ ] 1.11 [C] Planetary lattice and sample (Window H3–H4)
  - Files: `pipeline/doppelgrund/planetary/lattice.py`, `pipeline/tests/test_lattice.py`
  - Tests: disc count within 2% of `4πR²/area`; nearest-neighbour spacing roughly uniform (CV < 0.1); deterministic sample.
  - _Requirements: 9.1, 9.2_
  - Depends on: 00/0.5

- [ ] 1.12 [S] Planetary raster I/O (Window H4–H7)
  - Files: `pipeline/doppelgrund/planetary/rasterio_io.py`, `pipeline/tests/test_rasterio_io.py`
  - Tests: synthetic equirectangular raster on a sphere; reprojected window around (0,0), (60,120) and (−88,0) reproduces a known analytic surface within tolerance; longitude wrap at ±180 works.
  - _Requirements: 10.1, 10.5_
  - Depends on: 1.11

- [ ] 1.13 [S] Moon terrain features (Window H7–H10)
  - Files: `pipeline/doppelgrund/planetary/terrain.py` (add `terrain_features`), `pipeline/doppelgrund/planetary/targets.py` (`build_disc_table` terrain part), `notebooks/03_planetary_features.ipynb`
  - Acceptance: Moon sample discs computed; p50 slope distribution plausible (mostly < 15°); runtime per disc logged.
  - _Requirements: 10.1_
  - Depends on: 1.4b, 1.12, 00/0.8 (moon_dem verified)

- [ ] 1.14 [S] Moon thermal from Diviner (Window H7–H12)
  - Files: `pipeline/doppelgrund/planetary/thermal.py`, `pipeline/tests/test_thermal_planetary.py`
  - First inspect and record the product structure in STATUS.md. Apply R10.2–R10.3 and degraded mode §8.
  - Acceptance: equatorial disc diurnal_range_K of order 10² K; polar coverage gaps produce NaN plus a coverage note.
  - _Requirements: 10.2, 10.3, 10.5, 14.2_
  - Depends on: 1.12

- [ ] 1.15 [S] Mars terrain features (Window H10–H13)
  - Files: `pipeline/doppelgrund/planetary/targets.py` (Mars path)
  - Acceptance: Mars sample discs computed; thermal columns NaN (R11.2).
  - _Requirements: 11.1–11.3_
  - Depends on: 1.13

- [ ] 1.16 [S] Planetary composition (Window H10–H14)
  - Files: `pipeline/doppelgrund/planetary/composition.py`, `pipeline/tests/test_planetary_composition.py`
  - Tests: synthetic two-unit map, disc straddling the boundary → area-weighted fractions.
  - Acceptance: lith columns filled for Moon and Mars discs where maps exist.
  - _Requirements: 10.4, 11.3_
  - Depends on: 1.12, 00/0.8 (crosswalk)

- [ ] 1.17 [C] Targets and known-site hexes (Window H13–H15)
  - Files: `pipeline/doppelgrund/planetary/targets.py` (`build_targets`), `pipeline/tests/test_targets.py`
  - Acceptance: `targets.parquet` has one row per landmark; `known_site_hexes.parquet` maps each known site to its hex.
  - _Requirements: 12.1, 12.2_
  - Depends on: 1.13–1.16, 1.10

- [ ] 1.18 [C] QA report (Window H14–H16) — **Gate G1: human reviews maps before spec 02 uses real data**
  - Files: `pipeline/doppelgrund/qa/report.py`, `notebooks/04_qa.ipynb`
  - Acceptance: `data/interim/qa/report.html` renders maps and histograms; any out-of-range feature listed at the top.
  - _Requirements: 13.1_
  - Depends on: 1.10, 1.17

- [ ] 1.19 [C] Notebook wrappers 01–03 (Window alongside the tasks above)
  - Files: `notebooks/01_tiling.ipynb`, `notebooks/02_earth_features.ipynb`, `notebooks/03_planetary_features.ipynb`
  - Each notebook: install, config, call `doppelgrund` functions, save outputs, show a small map. No logic beyond ~10 lines per cell.
  - _Requirements: 13.2_
