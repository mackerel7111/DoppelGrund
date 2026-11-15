# Project Details: DoppelGrund

Draft for the Space Apps "Project Details" field. Facts come from `web/src/content/about.md`, `tech_stack.md`,
`.kiro/steering/product.md` and `docs/submission/data-sources.md`. Items marked **[if shipped]** depend on unfinished
tasks in spec 02 (2.7–2.13). Delete them if those tasks don't land.

---

## The pitch

**DoppelGrund: every alien landscape has an Earthly twin. We find it, and show you where the resemblance ends.**

Before anyone builds a base on the Moon or sets foot on Mars, they need somewhere on Earth to practice. Finding those
places is hard. The data is spread across different space agencies and archives, and many promising analog sites have
never been studied. Most analogs in use today were chosen because someone went there and thought it looked right.

## What it does

Pick a landmark on the Moon or Mars. DoppelGrund scores every land hexagon on Earth against it (about 85,000 cells of
roughly 1,770 km² each). It then shows:

- the best Earth match for each of five traits, plus the best match overall:
  - **Terrain**: slope, relief, share of flat ground
  - **Thermal**: mean surface temperature, day–night range, annual range
  - **Cold & ice**: time spent below 0 °C, permafrost, aridity
  - **Composition**: six-class rock-type mix from geologic maps
  - **Subsurface**: catalogued pits, lava tubes and caves per area
- a ranked shortlist with an overall score (0–100) and a score per trait
- how far each match is from the nearest documented analog site, so the overlooked candidates stand out
- a divergence panel that lists every gap in physical units, plus the things Earth can never reproduce: gravity,
  vacuum, radiation and permanent shadow

Mission presets (Balanced, Landing & mobility, Cold regions & volatiles, Geology & minerals) change how much each trait
counts. Moving a slider re-ranks all 85,000 hexagons right in the browser.

Interactive 2D maps and paired 3D globes (Earth beside the Moon or Mars) let you see each match next to its target.

## How it works

1. **Same fingerprint for every world.** Each Earth hexagon and each same-area disc on the Moon or Mars (radius
   23.7 km) becomes a vector of physical, unit-bearing features. We never compare pixels or how a place looks.
2. **Tolerance-kernel scoring.** For each feature, similarity = exp(−0.5·z²), where z is the gap divided by a
   tolerance fitted on Earth, Moon and Mars data together. Rock-type mixes are compared with the Hellinger distance.
   Trait scores and the overall score are weighted averages over the features measured on both sides.
3. **Missing data stays missing.** A feature that wasn't measured is shown as "not measured" and lowers the match's
   coverage score. It is never filled with zero or an average. Matches below a coverage floor are not ranked.
4. **Stability check.** We rerun the ranking with perturbed weights and tolerances. A match counts as stable only if it
   stays in the top 1% across those runs.
5. **[if shipped] Unsupervised machine learning.** PCA plus GMM/HDBSCAN clustering groups places into analog regimes. A
   domain-gap classifier checks that Earth and planetary data are actually comparable. Weights are calibrated on known
   analog pairs.
6. **Static-first.** All heavy processing runs offline in Python. The website is a static bundle of about 15 MB with
   no backend, and ranking runs in a Web Worker.

## Benefits

- **One place for scattered data.** It combines NASA, USGS, ESA/Copernicus and university datasets for three worlds
  in one harmonised feature space.
- **Answers to "where", "why" and "why not".** Every score breaks down into features, datasets and versions, and every
  gap is stated in real units (for example, "+38 K warmer at night").
- **Different analogs for different jobs.** The best terrain match for testing a rover is rarely the best thermal
  match for testing instruments. DoppelGrund shows both.
- **Finds overlooked sites.** Ranking by distance from known analog sites surfaces candidates nobody has studied.
- **Cheap and open.** It runs in any browser with no install, no account and no server costs.

## Intended impact

- **Mission and analog planners** get a defensible shortlist with evidence before spending money on fieldwork.
- **Researchers** get reproducible features, cited sources and stated gaps they can check or extend.
- **Students and the public**, including audiences in Sarawak, Malaysia, get an honest and engaging way to see how
  Earth relates to other worlds. Local karst caves at Mulu and Niah connect to subsurface biology and cave robotics.
  They are never presented as lava-tube analogs.
- **Wider effect:** more, and better-justified, analog sites. That means more places to train crews and test hardware
  before the Artemis and Mars missions.

## Validation

We validate by rediscovery: do well-documented analog sites (Haughton Crater, the McMurdo Dry Valleys, the Atacama and
others in `config/known_sites.csv`) rank highly for the targets they are known for?

| Metric | Result |
|---|---|
| Recall of known sites in top 100 / 500 / 1,000 vs random | TODO: fill from real run |
| Median percentile rank of known sites | TODO |
| Novel candidates (stable, well covered, ≥ 300 km from any known site) | TODO |

## Tools, languages and software

| Area | What we used |
|---|---|
| Languages | Python 3.11, TypeScript |
| Earth data processing | Google Earth Engine Python API, Google Colab |
| Geospatial | rasterio, pyproj, geopandas, shapely 2, H3 (h3 v4 / h3-js) |
| Numerics and ML | numpy, pandas, scipy, scikit-learn (PCA, GMM, HDBSCAN, gradient boosting) |
| Storage | Parquet (pyarrow), JSON |
| Frontend | Vue 3, Vite, Pinia, Web Workers |
| Maps and globes | deck.gl (H3 hexagon layers), three.js, three-globe |
| Testing | pytest, hypothesis, Vitest, fast-check |
| Quality and delivery | ruff, ESLint, Prettier, GitHub Actions, GitHub Pages |
| Build process | Kiro spec-driven development with AI coding assistants. Every task is logged in `docs/submission/ai-use-log.md`. |
| Hardware | Laptops and free cloud notebooks only. No GPU needed. |

**Neural networks:** none are used anywhere in DoppelGrund.

### Key datasets

| World | Terrain | Thermal | Composition | Subsurface |
|---|---|---|---|---|
| Earth | Copernicus GLO-30, NASADEM | MODIS MOD11A2, MOD21A1D/N | GLiM | Lava-tube list (Iceland, Tenerife, Jeju, Oregon) |
| Moon | LRO LOLA | LRO Diviner | USGS Unified Geologic Map of the Moon | LROC pit catalogue (266 pits) |
| Mars | MGS MOLA | gap: not measured yet | USGS global geologic map of Mars | none yet |

Also used: Obu et al. permafrost, TerraClimate aridity, Natural Earth land, and NASA/USGS basemap textures. Full
citations are in `docs/submission/data-sources.md`.

## How it is creative

- **Built around differences, not just matches.** Most analog tools stop at "this looks like Mars". DoppelGrund
  treats the gaps as half the result and lists them for every match.
- **One match per trait instead of one winner.** No single place on Earth is the Moon. The app admits that and shows a
  different best twin for each trait.
- **Physics, not pictures.** Everything is compared in real units like kelvin, degrees and metres, never by pixels or
  colour.
- **Novelty as a feature.** It actively looks for places nobody has studied, instead of just confirming famous ones.
- **Live re-weighting in the browser.** Changing the mission focus re-ranks the planet in real time, with no server.
- **Story first.** An illustrated intro with our mascot, Doppel, explains the idea before the data shows up.

## Factors we considered

- **Scientific honesty.** We say "model-defined similarity", never "qualified site". Every method is labelled for what
  it is: numerical scoring, unsupervised ML or statistics.
- **Things Earth can't reproduce.** Gravity, vacuum, radiation and permanent shadow are never scored and are always
  shown in the divergence panel.
- **Data gaps and bias.** Permafrost data covers only the Northern Hemisphere. Mars thermal data is still missing. Polar
  MODIS records are biased towards clear skies and summer. The cave catalogues are incomplete. All of this is shown as
  reduced coverage, never hidden.
- **Scale.** A 1,770 km² hexagon can hide small, strong matches. A finer second-stage search is future work.
- **Comparing like with like.** Earth thermal data comes from about 10:30 and 22:30 Terra passes, and Moon data uses
  Diviner bins at the same local times.
- **Accessibility and reach.** It's a static site that loads on modest hardware, uses colour scales that work in light
  and dark themes, and needs no login.
- **Cost and reproducibility.** It uses free, open datasets, fixed random seeds, a single config file for the datasets
  and pinned dependencies.
- **Local relevance.** Sarawak's caves are framed carefully as subsurface-biology and robotics testbeds, not as
  structural lava-tube analogs.

---

## Before submitting

- [ ] Fill in the validation table from the real pipeline run.
- [ ] Remove or keep the **[if shipped]** ML item, depending on spec 02 tasks 2.7–2.12.
- [ ] Confirm whether the live bundle is still synthetic. If it is, say so.
- [ ] Check the dataset rows against `verified: true` entries in `data-sources.md`.
- [ ] Check the field's character limit in the 2026 submission guide and trim if needed.
- [ ] Add the live demo URL and repo link.
