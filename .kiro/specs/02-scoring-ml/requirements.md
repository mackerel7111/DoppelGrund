# Requirements: 02 Scoring, ML and export

Scope: harmonisation, the reference scorer and match cards, parity vectors, the classical ML layer, validation, and the web bundle export. Built against synthetic data from H4, switched to real data after gate G1.

## R1 Harmonisation
1. THE SYSTEM SHALL apply each feature's transform (C1) identically to every body.
2. THE SYSTEM SHALL fit per-feature `median` and `s` (median absolute deviation) on pooled Earth (unmasked) + Moon sample + Mars sample rows, ignoring NaN, on the transformed scale.
3. IF a feature's `s < 1e-6` THEN `s` SHALL be set to 1.0 and a warning logged.
4. THE SYSTEM SHALL write `scaler.json` (C2) including row counts per body.

## R2 Reference scorer
1. `doppelgrund.scoring.score` SHALL implement contract C4 exactly, vectorised over all Earth rows.
2. Properties: S ∈ [0,100] or NaN; coverage ∈ [0,1]; identical row and target → S = 100 and coverage = 1 (when nothing is NaN); NaN never produces a finite contribution; zero-weight groups never affect S.
3. Scoring 85,000 rows SHALL take < 1 s on a laptop CPU.

## R3 Match cards
1. `doppelgrund.scoring.select_cards` SHALL implement contract C5 exactly.
2. Cards SHALL never contain masked or below-coverage rows.

## R4 Parity vectors
1. `python -m doppelgrund.export.parity` SHALL write `tests/parity/vectors.json` (C7) covering the required cases.
2. Vectors SHALL be regenerated, never hand-edited.

## R5 Domain-gap diagnostic
1. THE SYSTEM SHALL train a gradient-boosted classifier (Earth vs planetary) with 5-fold CV on a body-balanced sample and report mean ROC AUC.
2. THE SYSTEM SHALL report per-feature AUC and list features with AUC ≥ 0.95 (or ≤ 0.05) as "separating"; these are excluded from clustering.
3. THE SYSTEM SHALL report the support fraction: share of Earth rows inside each target's per-feature value (± s_f).

## R6 Embedding and clustering
1. THE SYSTEM SHALL build the clustering matrix from non-separating features + lith fractions, keeping rows with ≥ 80% coverage and median-imputing the rest (recorded).
2. THE SYSTEM SHALL fit PCA keeping 90% variance, HDBSCAN (min_cluster_size 100, min_samples 10 as defaults in config) and GMM with K chosen by BIC over 6–24. On samples under about 20,000 rows min_cluster_size is `max(10, N // 200)` instead (never above 100), so a partial run still forms clusters.
3. THE SYSTEM SHALL report per-cluster mean z-scores, body mix, and label stability (ARI over 5 subsample refits).
4. THE SYSTEM SHALL assign each target a regime (GMM predict_proba; kNN vote on HDBSCAN labels).

## R7 Cluster-conditioned retrieval
1. Candidates = Earth rows in the target's regime (or GMM prob ≥ 0.5), ranked by S with the coverage floor.
2. IF the target is HDBSCAN noise or has < 50 Earth members THEN retrieval SHALL fall back to the global ranking with flag `no_close_regime`.

## R8 Weight calibration
1. THE SYSTEM SHALL optimise lens group weights `w = softmax(θ)` to maximise MRR of known sites for their documented targets, with a KL penalty to the hand-set weights (λ configurable).
2. THE SYSTEM SHALL use leave-one-site-out evaluation and report calibrated vs hand-set metrics side by side.
3. Calibrated weights SHALL be written to `data/interim/calibrated_lenses.yaml` and never overwrite `profiles.yaml` automatically.

## R9 Novelty
1. `geo_novelty_km` = great-circle distance from hex centroid to the nearest known site.
2. `feat_novelty` = minimum scaled Euclidean distance (valid features only, divided by √(valid count)) to any known-site hex.
3. Known-site hexes and their first ring get `known_site_flag = true` (flag bit4).

## R10 Ranking stability
1. For each preloaded target × lens, THE SYSTEM SHALL run `params.stability.draws` Monte Carlo draws (Dirichlet weights around the lens; log-normal tolerance jitter) and record each row's fraction of draws in the top `top_fraction`.
2. THE SYSTEM SHALL store the top `store_top_k` rows per target × lens.

## R11 Validation
1. THE SYSTEM SHALL compute recall@k (k = 100, 500, 1000), median percentile rank and MRR for every known site with a documented target, against random (k/N), single-group (terrain only) and unweighted baselines.
2. THE SYSTEM SHALL fill the ablation table (plan §10.3) with paired bootstrap 95% CIs over sites, written to `data/interim/validation/ablation.md` and `.csv`.
3. A component SHALL be marked "kept" only if its CI for improvement over the profile-weighted baseline excludes zero.

## R12 Bundle export
1. `python -m doppelgrund.export.bundle` SHALL write every C6 file from interim tables, applying the mask rule to set flag bit0.
2. THE SYSTEM SHALL write `earth_index_4096x2048.png` by rasterising hex polygons (antimeridian-safe).
3. THE SYSTEM SHALL validate its own output against C6 (lengths, dtypes, feature order) before finishing.
4. Bundle size SHALL be within the C6 budget or the export fails with a size report.
