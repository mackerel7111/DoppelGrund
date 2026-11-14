---
name: rediscovery-validation
description: Run and interpret the rediscovery validation (recall@k, median percentile rank, MRR, bootstrap CIs, ablation table) that decides whether DoppelGrund results are credible and which ML components are kept. Use for doppelgrund/validation.py, notebooks/07_validation.ipynb, known_sites.csv, weight calibration checks, ablations, or when writing the results section.
---

# Rediscovery validation

## Inputs
- `config/known_sites.csv` (documented sites with `documented_target_id` and `dimension`).
- `known_site_hexes.parquet` (site → hex). A hit counts if the site hex **or its first ring** is in the top-k.
- Lens per site: map `dimension` → lens (`terrain|landing` → landing_mobility, `cold|ice|volatiles` → cold_volatiles, `geology|mineralogy` → geology_minerals, else balanced). Record the mapping in the report.

## Metrics
recall@k for k ∈ {100, 500, 1000}; median percentile rank; MRR. Baselines: random (k/N exactly), terrain-only, unweighted. Paired bootstrap over sites (2,000 resamples, seed from config) for every method minus profile-weighted baseline.

## Decision rule
Keep an ML component only if its CI for improvement excludes zero. Otherwise report it as an exploration. Write the table to `data/interim/validation/ablation.{csv,md}`.

## Interpreting misses
For each site outside the top 1,000: list its coverage, the features with the largest gaps, and whether the cause is data (NaN, resolution), weights, or a genuinely different environment. Never tune weights by hand to rescue a single site.

## Bias guard
Known sites are famous sites. Report calibrated and hand-set results side by side; the novelty gate is never tuned on validation sites.

## Gate G2
Post the headline (recall@500 vs random, number of sites, CI) in `docs/STATUS.md`. Discovery claims in the write-up are allowed only after a human signs off G2.
