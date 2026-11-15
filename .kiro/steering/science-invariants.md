---
inclusion: fileMatch
fileMatchPattern: ["pipeline/doppelgrund/**/*.py", "web/src/engine/**/*.ts", "web/src/workers/**/*.ts", "notebooks/**/*.ipynb"]
---
# Science invariants (violating any of these is a bug)

1. **NaN means missing.** Never fill missing values with 0, a mean or a sentinel in feature tables, the bundle or the scorer. Imputation is allowed **only** inside clustering (`doppelgrund/ml/cluster.py`) and must be recorded.
2. **Units in names.** Every feature column carries its unit (`_deg`, `_m`, `_K`, `frac_`, `_prob`, `_index`). Temperatures are kelvin. Distances are kilometres.
3. **Pooled scaling only.** Medians and tolerances `s_f` (MAD) are fitted on pooled Earth + Moon + Mars rows. Never fit a scaler per body.
4. **Same algorithm, same baseline.** Slope and roughness use the same algorithm and ~470 m ground sampling on every body in stage 1. Never compute slope on a geographic (lat/lon) grid without metric pixel spacing.
5. **Same footprint area.** Earth = H3 res-4 hex (~1,770 km²). Moon/Mars = disc of radius 23.7 km on the body's sphere (Moon R = 1737.4 km, Mars R = 3389.5 km).
6. **Overpass-matched thermal.** Earth uses MODIS Terra (≈10:30 / 22:30 local solar time). The Moon uses Diviner local-time bins at 10.5 h and 22.5 h. Report the remaining gap in kelvin. Other Earth thermal products may be fused only if they are Terra products at the same overpass (e.g. MOD21A1D/N, MOD11A2). Aqua, VIIRS, ECOSTRESS and SMAP (6 h / 18 h) are not overpass-matched; using one needs an explicit human exception recorded in `docs/STATUS.md`.
7. **Definitions, not guesses.** Planetary `aridity_index` is 0.0 by definition (no precipitation), documented in `config/profiles.yaml`. Anything else without data is NaN. The one allowed zero from a catalogue is `pit_cave_density_per_1000km2 = 0` inside an area a systematic survey covers; outside survey coverage a catalogue with no entry is NaN, never 0.
8. **Unmatchable stays unscored.** Gravity, vacuum/atmosphere, radiation and permanent-shadow illumination never enter a score. They appear only in the divergence panel.
9. **Barrenness is a mask.** It filters Earth hexes before ranking. It is never a scored or clustering feature.
10. **Coverage is always reported** next to every score. Ranking requires `coverage >= params.coverage_floor`.
11. **Determinism.** Every stochastic step uses `params.seed`. Re-running a notebook reproduces the same outputs.
12. **Alignment for clustering only.** Any Earth-to-planet alignment (e.g. CORAL) is allowed for clustering experiments only, never for reported gaps or scores.
13. **Python is the reference.** `doppelgrund/scoring.py` defines scoring; TypeScript must match it within 1e-5 on `tests/parity/vectors.json`.
