# Tasks: 02 Scoring, ML and export

Legend: **[S]** Sonnet-class · **[C]** cheaper model · **[H]** human. Build on synthetic interim tables (`data/interim/synthetic/`) until gate G1, then re-run on real data.

- [x] 2.1 [S] Harmonisation (Window H4–H6)
  - Files: `pipeline/doppelgrund/harmonise.py`, `pipeline/tests/test_harmonise.py`
  - Tests: log1p applied only to listed features; NaN preserved; pooled MAD equals hand-computed value on a toy matrix; `s < 1e-6` → 1.0 with warning; JSON round-trip.
  - Acceptance: `make test-py`.
  - _Requirements: 1.1–1.4_
  - Depends on: 00/0.5, 00/0.7

- [x] 2.2 [S] Reference scorer (Window H5–H8)
  - Files: `pipeline/doppelgrund/scoring.py`, `pipeline/tests/test_scoring.py`
  - Implement C4 exactly. Hypothesis properties from R2.2. Benchmark 85k synthetic rows < 1 s (log time).
  - Acceptance: `make test-py`; property tests pass with ≥ 200 examples.
  - _Requirements: 2.1–2.3_
  - Depends on: 2.1

- [x] 2.3 [S] Match cards (Window H7–H9)
  - Files: `pipeline/doppelgrund/scoring.py` (add `select_cards`, `haversine_km`), `pipeline/tests/test_cards.py`
  - Tests: percentile uses linear interpolation; separation rule; tie-breaks; `no_eligible_match`; masked rows never chosen.
  - _Requirements: 3.1, 3.2_
  - Depends on: 2.2

- [x] 2.4 [S] Parity vector generator (Window H8–H9) — **unblocks spec 03 task 3.3**
  - Files: `pipeline/doppelgrund/export/parity.py`, `tests/parity/vectors.json` (generated), `pipeline/tests/test_parity_gen.py`
  - Acceptance: `python -m doppelgrund.export.parity --out tests/parity/vectors.json` writes all C7 required cases; `make test-py`.
  - _Requirements: 4.1, 4.2_
  - Depends on: 2.3

- [x] 2.5 [S] Bundle exporter + index map (Window H8–H11)
  - Files: `pipeline/doppelgrund/export/bundle.py`, `pipeline/doppelgrund/export/index_map.py`, `pipeline/tests/test_bundle.py`; update `pipeline/doppelgrund/fixtures/synthetic.py` to call these writers
  - Tests: `validate_bundle` passes on synthetic; antimeridian hex pixels appear at both image edges; size budget check.
  - Acceptance: `make bundle-synthetic` now uses the real exporter; `make test-py`.
  - _Requirements: 12.1–12.4_
  - Depends on: 2.2

- [x] 2.6 [C] GeoJSON layers (Window H9–H11)
  - Files: `pipeline/doppelgrund/export/layers.py`, `pipeline/tests/test_layers.py`
  - Inputs from config and downloaded files; each output a FeatureCollection of points with `name`, `source`, `kind`.
  - _Requirements: 12.1_
  - Depends on: 00/0.8

- [x] 2.7 [S] Domain-gap diagnostic (Window H14–H16, real data after G1; synthetic before)
  - Files: `pipeline/doppelgrund/ml/domain_gap.py`, `pipeline/tests/test_domain_gap.py`, `notebooks/06_domain_clusters.ipynb`
  - Tests: perfectly separable toy data → AUC ≈ 1 and feature flagged; identical distributions → AUC ≈ 0.5.
  - Acceptance: report written to `data/interim/ml/domain_gap.json`; separating features logged in STATUS.md.
  - _Requirements: 5.1–5.3_
  - Depends on: 2.1, 01/1.18 (G1)

- [ ] 2.8 [S] PCA + HDBSCAN + GMM (Window H16–H19)
  - Files: `pipeline/doppelgrund/ml/embed.py`, `pipeline/doppelgrund/ml/cluster.py`, `pipeline/tests/test_cluster.py`
  - Tests: three well-separated blobs recovered (ARI > 0.9); imputation only inside `clustering_matrix`; runtime guard path.
  - Acceptance: `clusters.parquet` written; cluster report table with body mix saved; ARI stability logged.
  - _Requirements: 6.1–6.4_
  - Depends on: 2.7

- [ ] 2.9 [C] Cluster-conditioned retrieval (Window H19–H20)
  - Files: `pipeline/doppelgrund/ml/retrieval.py`, `pipeline/tests/test_retrieval.py`
  - _Requirements: 7.1, 7.2_
  - Depends on: 2.8

- [x] 2.10 [S] Novelty (Window H15–H17)
  - Files: `pipeline/doppelgrund/ml/novelty.py`, `pipeline/tests/test_novelty.py`
  - Tests: distance to a site at a known offset; ring-1 flag; NaN features ignored in feat_novelty.
  - _Requirements: 9.1–9.3_
  - Depends on: 2.1, 01/1.17

- [ ] 2.11 [S] Validation + ablation (Window H18–H23) — **Gate G2: humans review recall before discovery claims**
  - Files: `pipeline/doppelgrund/validation.py`, `pipeline/tests/test_validation.py`, `notebooks/07_validation.ipynb`
  - Acceptance: `data/interim/validation/ablation.md` filled with CIs; misses listed with suspected reason; STATUS.md summary (recall@500 vs random).
  - _Requirements: 11.1–11.3_
  - Depends on: 2.2, 2.9, 01/1.17

- [ ] 2.12 [S] Weight calibration (Window H20–H24, cut if G2 is late)
  - Files: `pipeline/doppelgrund/ml/calibrate.py`, `pipeline/tests/test_calibrate.py`
  - Tests: on synthetic pairs with a planted best weighting, calibration moves toward it; KL penalty keeps weights near w0 when λ is large.
  - Acceptance: `calibrated_lenses.yaml` + LOO comparison table.
  - _Requirements: 8.1–8.3_
  - Depends on: 2.11

- [x] 2.13 [S] Ranking stability (Window H20–H24)
  - Files: `pipeline/doppelgrund/ml/stability.py`, `pipeline/tests/test_stability.py`, `notebooks/08_novelty_stability.ipynb`
  - Tests: with zero jitter, stability is 1 for the top 1% and 0 elsewhere; seeds reproduce.
  - Acceptance: stability files for every target × lens.
  - _Requirements: 10.1, 10.2_
  - Depends on: 2.2, 01/1.17

- [ ] 2.14 [C] Real bundle export (Window H24–H26) — **Gate G3: web switches to real data**
  - Files: `notebooks/09_export.ipynb`
  - Acceptance: `make bundle` succeeds; `validate_bundle` passes; `manifest.synthetic == false`; bundle size logged; app loads it locally.
  - _Requirements: 12.1–12.4_
  - Depends on: 2.5, 2.6, 2.8, 2.10, 2.13

- [ ] 2.15 [C] Notebook wrappers 05–09 (alongside)
  - Files: `notebooks/05_harmonise_score.ipynb` … `09_export.ipynb`
  - _Requirements: 1.4, 11.2, 12.1_
