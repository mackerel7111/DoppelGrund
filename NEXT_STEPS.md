# Next steps

## How the "model" works (no ONNX, no weights file)
- Classical ML only (ADR-0002); static site, no backend (ADR-0001).
- Offline (Python): harmonise features, PCA + GMM/HDBSCAN clusters, novelty, stability, calibrated weights. Output is a data bundle (~15 MB, budget 40 MB).
- Live (browser, `web/src/engine/scoring.ts`): per feature `k = exp(-0.5 z²)`, `z = |target - hex| / s`; lithology by Hellinger distance; weighted mean over 4 groups (terrain, thermal, cold_ice, composition) gives S (0-100) for ~82k hexes in ~150 ms.
- "Deploying the model" = swapping the synthetic bundle for the real one.

## Phase A: deploy now (synthetic data, banner shown)
1. Commit all changes. Must include `config/ne_land.geojson` and `config/textures/` (CI's `make bundle-synthetic` reads them), `web/public/story/`, `Doppel_StoryBoard/`, new components and tests, `docs/research/`, `notebooks/`.
2. Push `main` to `mackerel7111/DoppelGrund` (repo must be public for free Pages).
3. Settings → Pages → Source: **GitHub Actions** (one-time, manual).
4. `.github/workflows/deploy.yml` builds and publishes to `https://mackerel7111.github.io/DoppelGrund/`.

## Phase B: real bundle
Currently `pipeline/doppelgrund/` has only `config.py` and fixtures; `harmonise.py`, `scoring.py`, `ml/`, `validation.py`, `export/` do not exist (spec 02).
1. Build `harmonise.py`, `scoring.py` (Python reference), `validation.py` (rediscovery vs baselines: random, terrain-only, unweighted, profile-weighted).
2. Run on `data/raw/`; record baseline rediscovery numbers.
3. Implement `doppelgrund.export.bundle`, make `make bundle` real.
4. Commit the real bundle (un-ignore a real-bundle path; ~15 MB each regeneration, so do it sparingly). Remove `make bundle-synthetic` from `deploy.yml`. Banner should key off `manifest.synthetic`.

## Innovation additions (judge by rediscovery, so after Phase B step 1)
| # | Idea | Cost |
|---|---|---|
| 1 | **Analogue portfolio**: greedy set-cover of top matches, "visit these 3-5 Earth sites to cover most Moon/Mars targets". Browser-only, buildable on synthetic data now. | Low |
| 2 | **Scale ablation**: terrain is already harmonised to ~470 m on all bodies (C1); compare 470 m vs native-resolution matching on the rediscovery metric. | Low-medium |
| 3a | **Learned tolerances**: extend `calibrate()` to weights + 10 tolerance multipliers, report leave-one-out. No web change (`s` comes from the manifest). | Low |
| 3b | **Within-group Mahalanobis**: touches `scoring.py`, `scoring.ts`, parity vectors, missing-feature handling. Only if 3a helps. | Medium-high |
| 4 | "Novel and reachable": accessibility layer (new dataset). | Medium |
| 5 | "Where the analogy breaks": per-match note on what Earth cannot reproduce (vacuum, radiation, regolith). | Low |

## Pitch
Not a new algorithm: the first interactive, validated, open tool that searches the whole Earth for analogues of Moon/Mars targets, including untested places. Headline result to aim for: N of M known analogues recovered in top-k vs random.

## Order
A (now) → Phase B step 1-2 → #2 and #3a → #1 (any time) → B step 3-4 → 3b if warranted.
