# Requirements: 00 Foundation

Scope: repository scaffold, configuration, tooling, synthetic data and CI that every other spec depends on. Executed first, at H0 on Saturday 14 November 2026.

## R1 Repository layout
**User story:** As an agent, I want a predictable repository so that every task knows where files go.
1. WHEN the repository is created THE SYSTEM SHALL contain the directories and files listed in `structure.md`.
2. THE SYSTEM SHALL ignore `data/`, `web/node_modules/`, `web/dist/` and generated bundle binaries in git, except the small synthetic sample bundle.
3. THE SYSTEM SHALL include an MIT `LICENSE` and a `README.md` stub with setup commands.

## R2 Single source of configuration
**User story:** As a scientist, I want all weights, thresholds and dataset IDs in config files so that results are reproducible and editable without code changes.
1. THE SYSTEM SHALL store features, lithology classes, compatibility matrix, lenses and parameters in `config/profiles.yaml` exactly as contract C3.
2. WHEN `doppelgrund.config.load_profiles()` reads a file whose feature list, order, groups, lens keys or matrix shape differ from C1/C3 THE SYSTEM SHALL raise `ConfigError` naming the field.
3. WHEN lens weights do not sum to 1.0 ± 1e-6 THE SYSTEM SHALL raise `ConfigError`.
4. THE SYSTEM SHALL store every dataset in `config/datasets.yaml` with `id_or_url`, `version`, `licence`, `citation`, `access` (`ee`|`download`), `verified` (bool).
5. IF a pipeline step uses a dataset with `verified: false` THEN THE SYSTEM SHALL log a warning naming the dataset.
6. THE SYSTEM SHALL provide `config/landmarks.yaml`, `config/known_sites.csv` and `config/ontology_crosswalk.csv` with documented schemas and header rows.

## R3 Make interface
1. THE SYSTEM SHALL provide every Makefile target listed in `tech.md` with the documented behaviour.
2. WHEN `make verify-quick` runs on a clean checkout after `make setup` THE SYSTEM SHALL exit 0.
3. `make lint-py FILE=x` and `make lint-web FILE=x` SHALL operate on one file and exit 0 when the file is clean after fixing.

## R4 Synthetic data fixture
**User story:** As a frontend or ML developer, I want schema-valid synthetic data on day one so that I am never blocked by the real data pipeline.
1. `make bundle-synthetic` SHALL write a complete bundle (contract C6) to `web/public/data/` with `"synthetic": true` in the manifest.
2. THE SYSTEM SHALL also write synthetic `earth_features.parquet`, `moon_discs.parquet`, `mars_discs.parquet` and `targets.parquet` (contract C2) to `data/interim/synthetic/`.
3. Synthetic data SHALL use real H3 res-4 cells (a land-like subset of ≥ 5,000 cells), physically plausible value ranges, ~10% NaN per feature, some all-NaN rows, masked rows and at least 6 targets across both bodies.
4. Output SHALL be byte-identical across runs for the same seed.

## R5 TypeScript contract types
1. `web/src/data/types.ts` SHALL define types for manifest, bundle arrays, targets, cards and worker messages matching C6 and C8.
2. `web/src/data/config.ts` SHALL validate a loaded manifest (feature count/order, array lengths) and throw a typed error on mismatch.

## R6 CI and deployment
1. WHEN code is pushed to any branch THE SYSTEM SHALL run `make verify` in GitHub Actions.
2. WHEN code is pushed to `main` THE SYSTEM SHALL build the web app and publish `web/dist` (including the current bundle) to GitHub Pages.
3. IF the bundle in `web/public/data/` is synthetic THEN the deployed app SHALL show a visible "synthetic data" banner.

## R7 Orchestration documents
1. THE SYSTEM SHALL keep `docs/STATUS.md` (format in `agent-rules.md`) and ADRs under `docs/decisions/`.
2. THE SYSTEM SHALL keep `docs/submission/ai-use-log.md` recording which model built which task (for any AI-use disclosure the submission guide may require).
