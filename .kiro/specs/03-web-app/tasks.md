# Tasks: 03 Web app

Legend: **[S]** Sonnet-class · **[C]** cheaper model · **[H]** human. Use the synthetic bundle (`make bundle-synthetic`) until gate G3.

- [x] 3.1 [C] App shell and layout (Window H4–H6)
  - Files: `web/src/App.vue`, `web/src/main.ts`, `web/src/components/StatusBar.vue`, `web/src/styles/base.css`
  - Grid layout from design §1 with placeholder panels; header controls wired to no-ops; responsive stacking below 1100 px.
  - Acceptance: `make test-web`; `npm run build`; layout visible with `make dev`.
  - _Requirements: 12.2_
  - Depends on: 00/0.6

- [x] 3.2 [S] Bundle loader (Window H5–H7)
  - Files: `web/src/data/loader.ts`, `web/tests/loader.test.ts`
  - Parallel fetch, typed-array views with length checks, `null → NaN` for targets, progress callback, typed errors.
  - Tests: loads the committed sample bundle (Node fetch shim); corrupt length throws `BundleError` naming the file.
  - _Requirements: 1.1, 1.2, 1.4_
  - Depends on: 00/0.6, 00/0.7

- [x] 3.3 [S] Engine + parity test (Window H9–H12)
  - Files: `web/src/engine/{transforms,scoring,percentile,geo,cards}.ts`, `web/tests/engine.test.ts`, `web/tests/parity.test.ts`
  - Port C4/C5 from `doppelgrund/scoring.py` line by line; float64 internally.
  - Acceptance: `make parity` passes (all cases, tolerance 1e-5; cards exact); fast-check properties pass.
  - _Requirements: 2.1, 2.2_
  - Depends on: 02/2.4

- [x] 3.4 [S] Worker, protocol and client (Window H11–H13)
  - Files: `web/src/workers/{protocol,engine.worker,client}.ts`, `web/tests/worker.test.ts`
  - `init` loads the bundle inside the worker; `rank` returns transferred buffers; latest-wins by `reqId`; synthetic banner flag returned in `ready` and shown by `App.vue`.
  - Acceptance: rank on 85k synthetic rows < 150 ms (log in STATUS.md); `make test-web`.
  - _Requirements: 3.1, 3.2, 1.3_
  - Depends on: 3.2, 3.3

- [x] 3.5 [C] Session store (Window H6–H8)
  - Files: `web/src/stores/session.ts`, `web/tests/session.test.ts`
  - Tests: `setWeight` renormalisation (including setting one weight to 1 and to 0), lens switch resets weights, label becomes "custom".
  - _Requirements: 7.2_
  - Depends on: 00/0.6

- [x] 3.6 [S] Target panel (Window H8–H12)
  - Files: `web/src/components/TargetPanel.vue`, `web/src/map/targetLayers.ts`
  - Design §4 TargetPanel. Landmark click → `selectLandmark`; optional disc snapping when `moon_*`/`mars_*` disc files exist; footprint note text (R4.4).
  - Acceptance: works with polar landmarks at −89°; manual check logged; `make test-web`.
  - _Requirements: 4.1–4.4_
  - Depends on: 3.1, 3.5

- [x] 3.7 [S] Earth map (Window H8–H13)
  - Files: `web/src/components/EarthMap.vue`, `web/src/map/earthLayers.ts`, `web/src/map/palette.ts`, `web/tests/palette.test.ts`
  - Design §4 EarthMap; colour-by switch; legend; card rings; hex click → `selectRow`.
  - Acceptance: 85k hexes render and pan smoothly (≥ 30 fps on demo laptop, logged); `make test-web`.
  - _Requirements: 5.1–5.3_
  - Depends on: 3.1, 3.5

- [x] 3.8 [C] Match cards (Window H13–H15)
  - Files: `web/src/components/MatchCards.vue`, `web/tests/MatchCards.test.ts`
  - Props: `cards: Card[]`, row metadata accessors; emits `select(row)`. Text for null cards (R6.3).
  - _Requirements: 6.1–6.3_
  - Depends on: 3.4

- [x] 3.9 [C] Lens controls (Window H12–H14)
  - Files: `web/src/components/LensControls.vue`, `web/tests/LensControls.test.ts`
  - Preset select + four labelled sliders (0–100%) bound to the store; shows "Custom" when edited.
  - _Requirements: 7.1–7.3_
  - Depends on: 3.5

- [x] 3.10 [C] Scorecard (Window H14–H17)
  - Files: `web/src/components/Scorecard.vue`, `web/src/components/FeatureTable.vue`
  - Chart.js radar of group scores; feature table with units and "not measured" for NaN; sources from `manifest.sources`.
  - _Requirements: 8.1, 8.3_
  - Depends on: 3.4

- [x] 3.11 [C] Divergence panel (Window H15–H17)
  - Files: `web/src/components/DivergencePanel.vue`, `web/src/content/divergence.ts`
  - Static + dynamic items per design §5.
  - _Requirements: 8.2_
  - Depends on: 3.10

- [x] 3.12 [C] Shortlist, novelty filter, layers (Window H16–H19)
  - Files: `web/src/components/Shortlist.vue`, `web/src/components/LayerToggles.vue`, `web/src/map/overlayLayers.ts`
  - _Requirements: 9.1–9.3_
  - Depends on: 3.7, 3.8

- [x] 3.13 [S] Interactive stability (Window H19–H22)
  - Files: `web/src/engine/prng.ts`, `web/src/engine/stability.ts`, worker handler, `web/tests/stability.test.ts`
  - Tests: seeded reproducibility; Dirichlet samples sum to 1; zero-jitter case gives 1/0 stability.
  - _Requirements: 7.3, 3.2_
  - Depends on: 3.4

- [x] 3.14 [S] Globe painter (Window H22–H25, stretch)
  - Files: `web/src/globe/painter.ts`, worker `paint` handler, `web/tests/painter.test.ts`
  - Decode index PNG once (OffscreenCanvas or `createImageBitmap` in worker) → Int32 row map; paint RGBA per metric.
  - Acceptance: paint < 150 ms (logged); test on a tiny synthetic index image.
  - _Requirements: 10.2_
  - Depends on: 3.4, 02/2.5

- [x] 3.15 [S] Globe scene (Window H24–H28, stretch)
  - Files: `web/src/globe/GlobeScene.ts`, `web/src/components/GlobeView.vue`
  - Two globes, textures, landmark points, card points, resize handling, WebGL/fps fallback (R10.4).
  - _Requirements: 10.1, 10.4_
  - Depends on: 3.14

- [x] 3.16 [S] Globe picking and arcs (Window H27–H30, stretch)
  - Files: `web/src/globe/picking.ts`, `web/src/globe/arcs.ts`
  - _Requirements: 10.3_
  - Depends on: 3.15

- [x] 3.17 [C] About & methods dialog (Window H26–H29)
  - Files: `web/src/components/AboutDialog.vue`, `web/src/content/about.md` (rendered as static text)
  - Content from `docs/submission/writeup.md` summary + honest-labelling table + validation headline.
  - _Requirements: 11.1_
  - Depends on: 04/4.2 (draft)

- [ ] 3.18 [C] Real-data switch, performance and smoke test (Window H26–H30) — after Gate G3
  - Files: `web/tests/e2e/smoke.spec.ts` (Playwright, optional), `docs/STATUS.md`
  - Load real bundle; record load time, rank time, fps; select each landmark once; verify no console errors; verify sub-path build.
  - _Requirements: 12.1–12.3, 1.3_
  - Depends on: 02/2.14, 3.4–3.12
