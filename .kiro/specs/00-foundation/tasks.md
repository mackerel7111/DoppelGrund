# Tasks: 00 Foundation

Legend: **[S]** Sonnet-class model · **[C]** cheaper model · **[H]** human. Window = hackathon hours from H0 (Sat 09:00 local).
Every task ends with `make verify-quick` passing (once the Makefile exists) and a STATUS.md log line.

- [x] 0.1 [C] Create repository skeleton (Window H0–H0.5)
  - Files: `.gitignore`, `README.md`, `LICENSE` (MIT), `pipeline/doppelgrund/__init__.py`, `pipeline/tests/__init__.py`, empty dirs from `structure.md` with `.gitkeep`
  - Keep the existing `.kiro/`, `.kiroignore`, `docs/`, `tech_stack.md` untouched.
  - Acceptance: `git status` shows the tree; `.gitignore` excludes `data/`, `web/node_modules/`, `web/dist/`, `web/public/data/*.f32|*.i16|*.u8|*.png` except `web/public/data/sample/`.
  - _Requirements: 1.1, 1.2, 1.3_

- [x] 0.2 [C] Python package and tooling (Window H0.5–H1)
  - Files: `pipeline/pyproject.toml`, `pipeline/tests/test_smoke.py`
  - Pin exact versions of every library in `tech.md` (choose current stable at H0, record in STATUS.md).
  - Acceptance: `pip install -e "pipeline[dev]"` works; `pytest pipeline/tests -q` passes; `ruff check pipeline` passes.
  - _Requirements: 3.1_
  - Depends on: 0.1

- [x] 0.3 [C] Web scaffold (Window H0.5–H1.5)
  - Files: `web/**` (Vite Vue TS template), `web/package.json`, `web/vite.config.ts`, `web/.eslintrc.cjs` or `eslint.config.js`, `web/.prettierrc`, `web/tests/smoke.test.ts`
  - Install and pin: vue, pinia, deck.gl packages, h3-js, three, three-globe, chart.js, vitest, @vue/test-utils, fast-check, eslint, prettier.
  - Acceptance: `npm run build`, `npm run lint`, `npm run test -- --run` all succeed.
  - _Requirements: 3.1_
  - Depends on: 0.1

- [x] 0.4 [C] Makefile (Window H1–H1.5)
  - Files: `Makefile`
  - Implement targets per design §3; `parity` and `bundle` may print "not yet implemented" and exit 0 until specs 02 tasks exist.
  - Acceptance: `make setup && make verify-quick` exits 0; `make lint-py FILE=pipeline/doppelgrund/__init__.py` exits 0.
  - _Requirements: 3.1, 3.2, 3.3_
  - Depends on: 0.2, 0.3

- [x] 0.5 [S] Config files and loader (Window H1–H2.5)
  - Files: `config/profiles.yaml`, `config/datasets.yaml`, `config/landmarks.yaml`, `config/known_sites.csv`, `config/ontology_crosswalk.csv`, `pipeline/doppelgrund/config.py`, `pipeline/tests/test_config.py`
  - Copy C3 verbatim into `profiles.yaml`. Create the other files with headers and the starter entries from design §2; leave unknown values empty with `verified: false`.
  - Tests: valid file loads; wrong feature order, missing lens group, lens sum ≠ 1, asymmetric matrix each raise `ConfigError`; `feature_weights("balanced")` returns terrain weights 0.0625 ×4, thermal 0.0833 ×3, cold_ice 0.0833 ×3, lith 0.25.
  - Acceptance: `make test-py` passes.
  - _Requirements: 2.1–2.6_
  - Depends on: 0.4

- [x] 0.6 [C] TypeScript contract types and manifest validation (Window H2.5–H3.5)
  - Files: `web/src/data/types.ts`, `web/src/data/config.ts`, `web/tests/config.test.ts`
  - Mirror C6 and C8 exactly (feature names as a readonly tuple type in C1 order).
  - Tests: a valid manifest passes; wrong feature order, wrong `n_hex` vs array length each throw `ManifestError`.
  - Acceptance: `make test-web` passes.
  - _Requirements: 5.1, 5.2_
  - Depends on: 0.4

- [x] 0.7 [S] Synthetic data generator (Window H2.5–H4)
  - Files: `pipeline/doppelgrund/fixtures/__init__.py`, `pipeline/doppelgrund/fixtures/synthetic.py`, `pipeline/tests/test_synthetic.py`
  - Follow design §5 and contracts C2/C6. Include a tiny `web/public/data/sample/` copy (≤ 500 hexes) committed to git for CI.
  - Tests: deterministic bytes for a fixed seed; manifest validates; array lengths match `n_hex`; NaN fraction per feature 5–15%; ≥ 6 targets; index-map pixels decode to valid rows.
  - Acceptance: `make bundle-synthetic` writes all C6 files; `make test-py` passes.
  - _Requirements: 4.1–4.4_
  - Depends on: 0.5

- [ ] 0.8 [H] Fill landmarks, known sites and crosswalk (Window H1–H6, in parallel)
  - Files: `config/landmarks.yaml`, `config/known_sites.csv`, `config/ontology_crosswalk.csv`, `config/datasets.yaml`
  - Landmarks: NASA Artemis III candidate south-polar regions (confirm current list), plus Jezero and Gale, each with source URL. Known sites: 30–50 documented analogues with references; mark `well_known=true` for sites the challenge names (Atacama, Haughton Crater, Death Valley, Antarctica, Iceland, Hawaii).
  - Crosswalk: map GLiM first-level classes, Moon and Mars geologic map units to the six classes; mark uncertain rows in `notes`.
  - Acceptance: `python -c "from doppelgrund.config import *; load_landmarks(); load_known_sites(); load_crosswalk()"` succeeds; every dataset used in stage 1 has `verified: true` or a STATUS.md TODO(verify).
  - _Requirements: 2.4, 2.6_

- [ ] 0.9 [C] CI and Pages deployment (Window H4–H5)
  - Files: `.github/workflows/ci.yml`, `.github/workflows/deploy.yml`
  - Acceptance: push to a branch runs CI green on the synthetic sample; push to `main` publishes the app (synthetic banner visible once spec 03 task 3.4 lands).
  - _Requirements: 6.1–6.3_
  - Depends on: 0.4, 0.7

- [x] 0.10 [C] Submission scaffolding docs (Window H4–H5)
  - Files: `docs/submission/ai-use-log.md`, `docs/submission/data-sources.md` (generated table stub from `datasets.yaml`)
  - Acceptance: files exist with headings; ai-use-log has a table `task | model | date | human reviewer`.
  - _Requirements: 7.2_
  - Depends on: 0.5
