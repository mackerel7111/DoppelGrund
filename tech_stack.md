# DoppelGrund — Tech Stack, Build Plan and Orchestration

**Project:** Global Analogue Discovery Engine · **Event:** NASA Space Apps Challenge 2026 · **Challenge:** "Identify Earth Locations that Analog the Permanent Moon Base Locations and Mars"
**Build window:** Saturday 14 – Sunday 15 November 2026 (local event time) · **IDE:** Kiro (spec-driven, Sonnet-class + cheaper models)
**Status:** build may start now (orchestrator decision, 2026-10-30). H0 (Sat 14 Nov, 09:00 local) remains the start of the official event clock.

This file is the orchestrator's manual. It tells you what we build, with what, in which order, by whom (human or which model), how quality is enforced, and how we win on the judging criteria. Details live in:

| Need | File |
|---|---|
| Science (features, harmonisation, scoring rationale) | `docs/plan/Global_Analogue_Discovery_Engine_Plan.md` |
| Always-on agent context | `.kiro/steering/product.md`, `tech.md`, `structure.md`, `agent-rules.md` |
| Conditional agent context | `.kiro/steering/science-invariants.md`, `data-contracts.md`, `python-pipeline.md`, `frontend.md` |
| Executable plans | `.kiro/specs/00-foundation` … `04-submission` (`requirements.md`, `design.md`, `tasks.md`) |
| Automation and guardrails | `.kiro/hooks/*.json`, `.kiro/hooks/scripts/guard_writes.py` |
| On-demand procedures | `.kiro/skills/*/SKILL.md` |
| Live coordination | `docs/STATUS.md`, `docs/decisions/ADR-*.md` |

---

## 1. Context and constraints

| Constraint | Consequence for the plan |
|---|---|
| Hackathon is ~2 days; code may be written before H0 (orchestrator decision) | Plans, specs, contracts, steering, skills, hooks and config schemas are ready; build tasks can start immediately |
| Submission and judging guides arrive 13 Nov | Task 04/4.1 reconciles formats and deadline the evening before H0 |
| Free compute (Colab/Kaggle CPU, Earth Engine non-commercial) | Classical methods; Earth Engine does raster reduction server-side; tables are tens of MB |
| Mixed model fleet (Sonnet + cheaper) | Every task has a tier, explicit files, fixed contracts, acceptance commands and guardrail hooks |
| Earth Engine exports take hours | Exports are the critical path: first batch running by H3, all submitted by H6 |
| Demo-day risk (network, servers) | Static-first app, no backend, offline build on the demo laptop |
| Team of up to 6 (check the rules) | Five workstreams mapped to specs; one orchestrator |

**Scope decision for 48 h (orchestrator call):** in scope = global stage-1 grid, scoring, per-dimension cards, novelty, stability, rediscovery validation, 2D app, 3D dual globes as stretch, submission pack. **Out of scope** for the event (post-hackathon roadmap): stage-2 high-resolution refinement, Mars dust lens, arbitrary-click targets on Mars if disc-grid compute runs late.

---

## 2. Business case (what judges and stakeholders buy)

### 2.1 Problem
Analogue research clusters in a handful of famous sites (the challenge itself names Atacama, Haughton Crater, Death Valley, Antarctica, Iceland, Hawaii). Site choice is often ad hoc, and the reasons a site fails as an analogue are rarely quantified. Artemis-era south-polar base regions and Mars landing sites need many more, better-characterised analogues for different purposes.

### 2.2 Solution and value proposition
| User | Pain | DoppelGrund gives |
|---|---|---|
| Mission and analogue planners | Few candidates, unclear trade-offs | Ranked candidates per dimension for a chosen Moon/Mars region, with coverage, stability and divergence |
| Researchers | Hard to compare sites quantitatively | Reproducible, unit-bearing features and a validated similarity method |
| Educators and public (Sarawak and beyond) | Space feels distant | Interactive "find the Moon on Earth" with honest science |
| Judges | Need validity and novelty | Rediscovery recall vs random, unstudied high scorers, explicit limitations |

### 2.3 Differentiators
Whole-Earth systematic search (not a curated list) · per-dimension "best match" instead of a single twin · divergence as a first-class output · validation by rediscovery with confidence intervals · runs free and offline.

### 2.4 Judging map (2025 criteria; confirm 2026 on 13 Nov)
| Criterion | Our evidence | Owner |
|---|---|---|
| Impact | Unstudied candidates for Artemis south-polar regions and Mars sites; open, reproducible, $0 to run | Pitch lead |
| Creativity | Per-dimension cards, dual-globe target-to-Earth view, novelty index | Frontend lead |
| Validity | Physical harmonisation, recall@k vs random with bootstrap CIs, stability, coverage | ML lead |
| Relevance | Every challenge objective mapped (`product.md`) | Orchestrator |
| Presentation | 30 s story, live app, clean visuals, real numbers | Pitch lead |

### 2.5 Metrics we will report (all produced by the pipeline)
recall@100/500/1000 vs random (k/N) with 95% CIs · median percentile rank of known sites · number of novel candidates with stability ≥ 0.8, coverage ≥ 0.8 and ≥ 300 km from any known site · coverage distribution · app load/rank time.

### 2.6 Cost
| Item | Cost |
|---|---|
| Earth Engine (non-commercial), Colab/Kaggle free tiers, GitHub + Pages | $0 |
| Open datasets (NASA, USGS, PANGAEA, Smithsonian, Natural Earth) | $0 (citation required) |
| Kiro | Existing plan credits; budget in §8.6 |

### 2.7 Sustainability and roadmap
MIT licence; config-driven (new datasets and lenses without code changes); reproducible pipeline. Roadmap after the event: stage-2 refinement (H3 res 6–7), Mars surface-temperature source, Mars dust lens, community-submitted targets, field-validation partnerships (including Sarawak institutions).

---

## 3. Architecture

```
            OFFLINE (Colab / laptop, Python package `doppelgrund`)                      ONLINE (static site)
┌──────────────────────────────────────────────────────────────────┐      ┌──────────────────────────────┐
│ Earth Engine ── reduceRegions per H3 hex ──┐                     │      │ Browser                      │
│ Local rasters (GLiM, permafrost) ──────────┼─> earth_features    │      │  loader.ts ─ fetch bundle    │
│ PDS/USGS rasters (LOLA, Diviner, MOLA) ────┼─> moon/mars_discs   │      │  engine.worker.ts            │
│ Geologic maps + crosswalk ─────────────────┘   targets           │      │   ├ scoreAll (C4, parity)    │
│        │                                                         │      │   ├ selectCards (C5)         │
│        ▼                                                         │      │   ├ stability (MC)           │
│ harmonise ─> scoring (reference) ─> ML (domain gap, PCA,         │ ───> │   └ paint (globe texture)    │
│ HDBSCAN/GMM, calibration, novelty, stability) ─> validation      │bundle│  Vue + Pinia UI              │
│        │                                                         │ (C6) │   ├ deck.gl 2D (Earth, body) │
│        ▼                                                         │      │   └ three-globe 3D (stretch) │
│ export: bundle (C6) + parity vectors (C7)                        │      └──────────────────────────────┘
└──────────────────────────────────────────────────────────────────┘
```
Decisions: ADR-0001 static-first, ADR-0002 classical ML only, ADR-0003 three-globe for 3D (confirm at H0; CesiumJS fallback if someone already knows it).

**Why contracts first:** parallel agents (and cheaper models) only stay consistent if every interface is fixed before code exists. Contracts C1–C8 in `.kiro/steering/data-contracts.md` define features, tables, config, the scoring formula, card selection, the bundle, parity vectors and the worker protocol. Agents may not change them; humans can.

---

## 4. Technology stack

| Layer | Choice | Why | Rejected |
|---|---|---|---|
| Language (offline) | Python 3.11+ | Geo + ML ecosystem; Colab default | R, Julia |
| Raster reduction | Google Earth Engine Python API | Hosts MODIS, Copernicus DEM, land cover, climate; no terabyte downloads | AppEEARS (fallback only) |
| Local rasters | rasterio, pyproj, numpy | Windowed reads, reprojection on non-Earth spheres via `+R` | GDAL CLI scripting |
| Vector/geo | geopandas, shapely 2, h3 v4 | Land fraction, antimeridian splits, hex topology | — |
| ML | scikit-learn (PCA, GMM, HDBSCAN, HistGradientBoosting), scipy (differential_evolution) | CPU, fast, explainable | Any neural network (ADR-0002) |
| Storage | Parquet (pyarrow) + JSON sidecars | Typed, compact, column order enforced | CSV for interim |
| Testing (py) | pytest, hypothesis | Property tests guard invariants for cheaper models | — |
| Frontend | Vue 3, Vite, TypeScript strict, Pinia | Matches plan; fast builds | React (fine, but plan says Vue) |
| 2D maps | deck.gl (MapView, OrthographicView, H3HexagonLayer, BitmapLayer) | Native H3, GPU, offline (Natural Earth land, no tiles) | MapLibre tiles (network) |
| 3D | three.js + three-globe | Any-body textured globes, arcs, light | CesiumJS (heavier; fallback), deck.gl GlobeView (experimental, Earth-only) |
| Browser H3 | h3-js v4 | Picking, boundaries | — |
| Charts | Chart.js | Radar + bar, small | ECharts |
| Testing (web) | Vitest, fast-check, @vue/test-utils, Playwright (optional) | Parity + properties | — |
| Quality | ruff, ESLint, Prettier | Auto-fix via hooks | — |
| CI/CD | GitHub Actions → GitHub Pages | Free, static | Vercel/Netlify (fine alternatives) |
| Orchestration | Kiro specs, steering, hooks, skills | Spec-driven multi-model build | — |

**Environment variables:** `DOPPELGRUND_EE_PROJECT` (Earth Engine Cloud project), `DOPPELGRUND_BASE` (web base path for Pages), `DOPPELGRUND_ALLOW_PROTECTED` (temporary override of the write guard; humans only).

**Shell:** hooks use POSIX shell syntax and `python3`. On Windows, run Kiro inside WSL or Git Bash, or edit the hook commands.

---

## 5. Data plan (summary; authoritative list = `config/datasets.yaml`)

| Group | Earth (per hex) | Moon (per disc) | Mars (per disc) |
|---|---|---|---|
| Terrain | Copernicus GLO-30 → ~470 m, Horn slope | LOLA LDEM_64 (~474 m) | MOLA 463 m |
| Thermal | MOD11A2 Terra day/night 2010–2019 | Diviner local-time bins 10.5 h / 22.5 h | **Gap**: no verified source yet → NaN, flagged |
| Cold/ice | Obu 2018 permafrost (NH), TerraClimate P/PET, LST < 0 °C share | Diviner < 0 °C share; aridity 0 by definition | aridity 0 by definition |
| Composition | GLiM (gridded) via crosswalk | USGS Unified Geologic Map of the Moon via crosswalk | USGS global geologic map of Mars via crosswalk |
| Mask (Earth only) | MCD12Q1 barren + snow/ice, MOD13A2 NDVI | — | — |
| Tags/layers | GVP volcanoes; known sites; lava tubes; Sarawak caves | Lunar Pit Atlas | — |
| Basemaps | Earth, Moon, Mars equirectangular textures (verify licence) | | |

Every entry starts `verified: false` and must be confirmed against the challenge Resources tab or catalogue page (task 00/0.8). Sizes: everything downloaded is small except LOLA 118 m (~8 GB, stage 2 only, not used in the event) and MOLA 463 m (~2 GB).

**Known scientific gaps to state openly:** Mars thermal (open), polar coverage limits of some Diviner products, Northern-Hemisphere-only permafrost, no Antarctic ASTER (auxiliary only), lithology crosswalk is the weakest harmonised dimension.

---

## 6. Repository, environments and data locations

- Layout: `.kiro/steering/structure.md`.
- **Local:** `make setup`; Python venv; Node LTS; `earthengine authenticate` once.
- **Colab:** clone repo, `%pip install -e pipeline[ee]`, mount Drive; mirror `data/interim/` to `Drive/doppelgrund/interim/`; EE exports land in `Drive/doppelgrund_exports/`.
- **Git:** trunk-based on `main` with small commits; CI on every push; tag `demo-freeze` at code freeze.
- **Never in git:** credentials, `data/`, real bundle binaries (published only through the Pages artifact).

---

## 7. Kiro setup

### 7.1 Install
1. Copy this folder into the new repo root at H0 (or keep it as the repo from the start: planning files only).
2. Open the repo in Kiro. Check the **Agent Steering & Skills** panel lists 8 steering files and 5 skills, and the **Agent Hooks** panel lists the hooks below.
3. Confirm the workspace uses steering and skills by asking: "Which steering files are active?" (always-included ones should appear).

### 7.2 Steering (how each file loads)
| File | Inclusion | Purpose |
|---|---|---|
| `product.md` | always | Why, users, challenge mapping, non-goals |
| `tech.md` | always | Fixed stack, make commands, hard constraints |
| `structure.md` | always | Where files go, naming |
| `agent-rules.md` | always | One-task discipline, never-invent, definition of done |
| `science-invariants.md` | fileMatch (pipeline, engine, notebooks) | NaN, units, pooled scaling, same slope algorithm |
| `data-contracts.md` | fileMatch (doppelgrund, engine, worker, parity, config) | C1–C8 |
| `python-pipeline.md` | fileMatch (pipeline, notebooks) | Python conventions |
| `frontend.md` | fileMatch (web) | Vue/deck.gl/three conventions |

Always-on files are kept short to save tokens on every interaction; big references are loaded only when relevant.

### 7.3 Specs
Five specs, executed in waves (Kiro builds a dependency graph from `tasks.md` and runs independent tasks in parallel; we also state dependencies explicitly in each task):
`00-foundation` → (`01-data-pipeline` ∥ `02-scoring-ml` on synthetic data ∥ `03-web-app` on synthetic data) → real-data switch → `04-submission`.
Requirements use EARS phrasing; designs give exact signatures; tasks give tier, window, files, tests and acceptance commands.

### 7.4 Hooks (v1 JSON in `.kiro/hooks/`)
| File | Trigger | Type | Effect |
|---|---|---|---|
| `session-start-status.json` | SessionStart | command | Prints top of `docs/STATUS.md` into context |
| `lint-on-save.json` | PostFileSave (`.py`, `web/*.ts|vue`) | command | `make lint-py` / `make lint-web` on the saved file |
| `task-gates.json` | PreTaskExec | command | **Blocks** a task (exit 2) while `make verify-quick` is red |
| `task-gates.json` | PreTaskExec / PostTaskExec | agent | Start checklist / completion checklist |
| `guard-writes.json` | PreToolUse (`write`) | command | **Blocks** agent writes to raw data, secrets, contracts, spec requirements/design, golden vectors |
| `science-review.json` | PostFileSave (science code) | agent | Short invariant review + test |
| `contract-sync.json` | PostFileSave (exporter, types, protocol, profiles) | agent | Check contract match, run `make parity` |
| `no-nn-deps.json` | PostFileSave (dependency files) | command | Flags neural-network packages |

Notes: file triggers fire only on agent edits, not on your manual edits. Agent-type hooks spend credits each time they fire; if credits run low, set `"enabled": false` on `science-review` and `contract-sync` first. Emergency bypass of the red-tree gate: set `enabled: false` on that hook, fix, re-enable.

### 7.5 Skills (`.kiro/skills/`, instruction-only)
`earth-engine-features`, `planetary-disc-features`, `scorer-parity`, `rediscovery-validation`, `submission-pack`. They activate by description or as `/skill-name` slash commands. They contain no scripts, so nothing executable ships with them.

### 7.6 `.kiroignore`
Keeps `data/`, Parquet, rasters, bundle binaries and `node_modules` out of agent context.

---

## 8. Orchestration protocol

### 8.1 Roles (map to people; one person can hold two roles)
| Role | Owns | Specs/tasks |
|---|---|---|
| **Orchestrator** (Damian) | STATUS board, dispatch, gates, cuts, contracts | all; reviews every [S] diff on critical path |
| Earth data lead | EE auth, exports, Earth assembly | 01/1.1–1.10, 1.18 |
| Planetary lead | Moon/Mars discs, targets | 01/1.11–1.17 |
| ML lead | harmonise, scorer, ML, validation, export | 02/* |
| Frontend lead | web app, globes | 03/* (with Orchestrator) |
| Pitch lead | configs (landmarks, sites, crosswalk), submission | 00/0.8, 04/* |
With 4 people: Orchestrator+Frontend, Earth+Planetary, ML, Pitch+config.

### 8.2 Model routing
| Tier | Use for | Examples |
|---|---|---|
| **[S] Sonnet-class** | Numerics, geospatial reprojection, cross-module logic, anything with a science invariant or a contract on both sides | 0.5, 0.7, 1.1, 1.3–1.7, 1.12–1.16, 2.1–2.5, 2.7–2.13, 3.2–3.4, 3.6, 3.7, 3.13–3.16, 4.3, 4.4 |
| **[C] cheaper model** | Scaffolding, config files, UI components with typed props, GeoJSON conversion, docs, CI, notebook wrappers | 0.1–0.4, 0.6, 0.9, 0.10, 1.8–1.11, 1.17–1.19, 2.6, 2.9, 2.14, 2.15, 3.1, 3.5, 3.8–3.12, 3.17, 3.18, 4.2, 4.5, 4.6 |
| **[H] human** | Accounts, auth, dataset verification, scientific judgement (crosswalk, landmarks, known sites), gates, recording, submission | 0.8, 1.2, 4.1, 4.7, 4.8, gates G0–G4 |

**Escalation ladder:** [C] fails acceptance twice → re-run the task with [S] in a fresh session → still failing → human pairs with [S]. Any `CONTRACT ISSUE` → human decision within 30 minutes.

**Cross-model review:** after any [C] task on the critical path (0.6, 2.14, 3.5, 3.8), open a fresh [S] session: "Review the diff of task X against its requirements and data-contracts.md; list defects only."

### 8.3 Dispatch template (paste into a fresh Kiro chat, or press "Start task" in `tasks.md`)
```
Execute task <spec>/<id> from .kiro/specs/<spec>/tasks.md and nothing else.
Follow agent-rules.md. Allowed files: <copy the Files line>.
Run the acceptance commands and `make verify-quick`, append a STATUS.md log line (model: <name>), then tick the checkbox.
If anything is missing or a contract looks wrong, stop and write it under Blocked/CONTRACT ISSUE in docs/STATUS.md.
```
**Session hygiene:** one task per chat session; close it after the STATUS line. Long sessions drift and cost more.

### 8.4 Gates (human sign-off, recorded in STATUS.md)
| Gate | When | Pass criteria |
|---|---|---|
| G0 Foundation | ~H4 | `make verify-quick` green; synthetic bundle loads; CI green |
| G1 Real data QA | ~H16 | QA report maps look physically sensible; NaN shares explained; slope cross-check ≤ 0.5° |
| G2 Validation | ~H23 | recall@500 clearly above random with CI; misses explained; only then discovery claims |
| G3 Real bundle | ~H26 | `validate_bundle` passes; app loads real data < 5 s; parity green |
| G4 Code freeze | H32 | Demo path works 3× in a row offline; tag `demo-freeze` |

### 8.5 Definition of done (every task)
Acceptance commands pass · `make verify-quick` green · tests added · no contract changed · STATUS log line with model name · checkbox ticked · ai-use log row (Pitch lead batches these hourly).

### 8.6 Credit budget (Kiro)
Rough split: 55% [S] tasks on critical path, 25% [C] tasks, 10% reviews, 10% reserve for fixes. The Orchestrator checks usage at every decision point; below 30% remaining before H24 → disable agent hooks, route all remaining UI work to [C], cut 2.12 and 3.16.

---

## 9. Timeline (H0 = Sat 14 Nov 09:00 local; assumed deadline Sun 23:59 = H39 — confirm on 13 Nov)

| Hours (clock) | Earth data | Planetary | ML | Frontend | Pitch/config | Orchestrator decisions |
|---|---|---|---|---|---|---|
| H0–H1 (09–10) | 1.2 EE auth [H] | — | 0.2 [C] | 0.1, 0.3 [C] | 0.8 starts [H] | Kickoff; confirm ADR-0003 |
| H1–H3 (10–12) | 1.1 [S], 1.3 [S] | read specs + datasets | 0.4 [C], 0.5 [S] | 0.6 [C] | 0.8 | — |
| H3–H6 (12–15) | 1.4, 1.5, 1.6, 1.8 submit [S/C] | 1.11 [C], 1.12 [S] | 0.7 [S], 2.1 [S] | 3.1, 3.5 [C] | 0.8, 0.10 | **H6:** all EE batches submitted? |
| H6–H10 (15–19) | 1.4b [S], 1.7 [S], 1.9 [C] | 1.13, 1.14 [S] | 2.2, 2.3 [S] | 3.2 [S], 3.6, 3.7 [S] | 0.9 [C] | **H10:** export progress ≥ 50%? (else §8 design 01) |
| H10–H14 (19–23) | 1.10 [C] as exports land | 1.15, 1.16 [S] | 2.4, 2.5 [S], 2.6 [C] | 3.3, 3.4 [S] | 4.2 [C] | **H14:** degraded terrain mode? |
| H14–H20 (23–05) night shift | 1.18 [C] → **G1** | 1.17 [C] | 2.7, 2.10 [S] | 3.8–3.11 [C] | sleep | Half the team sleeps 23–05, the other half 05–11 |
| H20–H24 (05–09) | support ML | — | 2.8 [S], 2.9 [C], 2.11 [S] → **G2** | 3.12 [C], 3.13 [S] | 4.3 [S] | **H24:** go/no-go 3D globes |
| H24–H28 (09–13) | — | — | 2.13 [S], 2.12 [S] (cut-able), 2.14 [C] → **G3** | 3.14, 3.15 [S], 3.18 [C] | 4.3 | **H28:** cut 2.12 / 3.16 if late |
| H28–H32 (13–17) | bug fixes | bug fixes | bug fixes | 3.16 [S], 3.17 [C] | 4.4 [S] | **H32: G4 code freeze** |
| H32–H37 (17–22) | — | — | numbers for write-up | final deploy | 4.5, 4.6 [C], 4.7 [H] | Rehearse demo 3× |
| H37–H39 (22–24) | — | — | — | — | 4.8 submit [H] by H37 | Buffer |

### Cut list (in order)
1. 02/2.12 weight calibration (report hand-set lenses only)
2. 03/3.16 globe picking and arcs (keep static 3D view)
3. 03/3.14–3.15 3D globes entirely (2D only)
4. Mars disc grid for arbitrary clicks (landmarks only)
5. 02/2.8–2.9 clustering (global ranking only; state it)

**Never cut:** global grid, scorer + parity, per-dimension cards, divergence panel, rediscovery validation, novelty, honest write-up.

### Fallback ladder for data
| Trigger | Fallback |
|---|---|
| EE terrain incomplete at H14 | 1 km resampling for remaining bands, flagged |
| Diviner unreadable at H18 | Moon thermal NaN; UI says so |
| Geologic maps unavailable | lith NaN for that body; composition drops out via coverage |
| Crosswalk not ready by H10 | Earth-only lithology; planetary composition NaN |
| Real bundle fails at H26 | Demo on synthetic is **not** allowed for results; ship 2D with whatever real tables validated, and say what is missing |

---

## 10. Quality strategy

| Layer | Check | Where |
|---|---|---|
| Config | Schema validation, lens sums, matrix symmetry | 00/0.5 tests |
| Science invariants | Hypothesis properties (S range, NaN propagation, identical → 100) | 02/2.2 |
| Cross-language | Parity vectors, 1e-5 tolerance, exact cards | `make parity` |
| Geometry | Analytic surfaces at equator/60°/−88°, antimeridian | 01/1.12 |
| Harmonisation | Slope cross-check Earth vs planetary path ≤ 0.5° | 01/1.4b |
| Data QA | Maps, histograms, NaN shares, range checks | 01/1.18 (G1) |
| Validity | Rediscovery + ablation with CIs | 02/2.11 (G2) |
| Performance | Rank < 150 ms, paint < 150 ms, load < 5 s, ≥ 30 fps 2D | 03/3.4, 3.14, 3.18 |
| Guardrails | Red-tree gate, write guard, no-NN check, lint on save | hooks |

---

## 11. Deployment and demo-day operations
- `main` → GitHub Pages via `deploy.yml`; `DOPPELGRUND_BASE=/<repo>/`.
- Demo laptop: `make build && make preview` copy with the real bundle; browser cache warmed; backup screen recording on the desktop; slides exported as PDF.
- Run the demo path three times after freeze (G4). Keep a printed one-page script.
- Check projector resolution with the 1440×900 layout and the stacked fallback.

---

## 12. Risk register
| Risk | Likelihood | Impact | Mitigation | Owner |
|---|---|---|---|---|
| EE exports slow or failing | High | High | Submit by H6, band batching, retry ladder, degraded mode | Earth lead |
| Slope mismatch Earth vs planetary | Medium | High | Shared Horn algorithm, cross-check test 1.4b | Planetary lead |
| Diviner/geology formats unfamiliar | Medium | Medium | Inspection step first; fallbacks | Planetary lead |
| Cheaper model breaks contracts | Medium | High | Contracts in fileMatch steering, write guard, parity, red-tree gate, reviews | Orchestrator |
| Rediscovery fails | Medium | High | Report honestly; inspect misses; no discovery claims without G2 | ML lead |
| 3D eats time | High | Medium | Stretch only; go/no-go at H24 | Orchestrator |
| Credits run out | Medium | High | Budget §8.6, disable agent hooks, route to [C] | Orchestrator |
| Event-rule compliance (code written before H0) | Low | Severe | Orchestrator accepted this; disclose in the ai-use log and write-up if the guides require it | Orchestrator |
| Over-claiming | Medium | High | Claims discipline in skill + write-up review | Pitch lead |
| Deadline/time-zone confusion | Low | Severe | 4.1 records local deadline; submit 2 h early | Pitch lead |

---

## 13. Pre-event checklist (now → 13 Nov; planning and setup only)
- [ ] Register the team for Space Apps 2026 and a local or virtual event.
- [ ] Each member: Kiro installed and signed in; Google account with Earth Engine non-commercial access; GitHub account.
- [ ] Decide roles (§8.1) and sleep shifts.
- [ ] Read this file, `product.md`, `agent-rules.md` and your own specs end to end.
- [ ] Confirm the 3D choice (ADR-0003) based on team experience.
- [ ] Pitch lead drafts (on paper/docs, not code) the landmark list sources, the 30–50 known analogue sites with references, and the lithology crosswalk table. These become config files at H0.
- [ ] Check dataset catalogue pages and the challenge Resources tab; note anything to change in `datasets.yaml` starter entries.
- [ ] 13 Nov: read the 2026 submission and judging guides (task 04/4.1); update STATUS "Now" with the deadline.
- [ ] Code before H0 is allowed by orchestrator decision. Re-check the 2026 rules on 13 Nov (task 04/4.1) and disclose pre-event work if required.

---

## 14. Open items (TODO(verify))
| Item | Owner | Due |
|---|---|---|
| 2026 submission format, demo length, deadline, AI-use rules | Pitch | 13 Nov |
| Earth Engine collection IDs, band names, scale factors (all `datasets.yaml` EE entries) | Earth | H2 |
| GLiM licence; Obu permafrost record and value encoding | Earth | H4 |
| Diviner product structure and coverage near the poles | Planetary | H8 |
| Lunar and Mars geologic map downloads and unit codes | Planetary + Pitch | H6 |
| Mars surface-temperature source (optional; else thermal NaN) | Planetary | H12 |
| Earth Engine slope algorithm vs Horn (task 1.4b) | Planetary | H6 |
| three-globe API details (material access, coordinate helpers) | Frontend | H22 |
| Basemap texture sources and licences | Frontend | H10 |
| Artemis III candidate region list and coordinates | Pitch | H2 |

---

## 15. Task index (dispatch view)
| ID | Title | Tier | Window | Depends |
|---|---|---|---|---|
| 0.1 | Repo skeleton | C | H0–0.5 | — |
| 0.2 | Python package/tooling | C | H0.5–1 | 0.1 |
| 0.3 | Web scaffold | C | H0.5–1.5 | 0.1 |
| 0.4 | Makefile | C | H1–1.5 | 0.2, 0.3 |
| 0.5 | Config files + loader | S | H1–2.5 | 0.4 |
| 0.6 | TS contract types | C | H2.5–3.5 | 0.4 |
| 0.7 | Synthetic generator | S | H2.5–4 | 0.5 |
| 0.8 | Fill landmarks/sites/crosswalk/datasets | H | H1–6 | — |
| 0.9 | CI + Pages | C | H4–5 | 0.4, 0.7 |
| 0.10 | Submission scaffolding | C | H4–5 | 0.5 |
| 1.1 | H3 land tiling | S | H1–3 | 0.5 |
| 1.2 | EE auth | H | H0–1 | — |
| 1.3 | EE batch runner | S | H1.5–3 | 1.1, 1.2 |
| 1.4 | Terrain export | S | H3–4 | 1.3 |
| 1.4b | Slope cross-check | S | H4–6 | 1.4 |
| 1.5 | Thermal export | S | H3–5 | 1.3 |
| 1.6 | Aridity + permafrost | S | H4–6 | 1.3, 0.8 |
| 1.7 | GLiM lithology | S | H4–6 | 0.8 |
| 1.8 | Mask/NDVI/ASTER | C | H5–6 | 1.3 |
| 1.9 | Process tags | C | H6–7 | 1.1 |
| 1.10 | Assemble Earth table | C | H10–14 | 1.4–1.9 |
| 1.11 | Planetary lattice | C | H3–4 | 0.5 |
| 1.12 | Planetary raster I/O | S | H4–7 | 1.11 |
| 1.13 | Moon terrain | S | H7–10 | 1.4b, 1.12 |
| 1.14 | Moon thermal (Diviner) | S | H7–12 | 1.12 |
| 1.15 | Mars terrain | S | H10–13 | 1.13 |
| 1.16 | Planetary composition | S | H10–14 | 1.12, 0.8 |
| 1.17 | Targets + known-site hexes | C | H13–15 | 1.10, 1.13–1.16 |
| 1.18 | QA report → G1 | C | H14–16 | 1.10, 1.17 |
| 1.19 | Notebooks 01–03 | C | alongside | — |
| 2.1 | Harmonisation | S | H4–6 | 0.5, 0.7 |
| 2.2 | Reference scorer | S | H5–8 | 2.1 |
| 2.3 | Match cards | S | H7–9 | 2.2 |
| 2.4 | Parity vectors | S | H8–9 | 2.3 |
| 2.5 | Bundle exporter + index map | S | H8–11 | 2.2 |
| 2.6 | GeoJSON layers | C | H9–11 | 0.8 |
| 2.7 | Domain gap | S | H14–16 | 2.1, G1 |
| 2.8 | PCA + HDBSCAN + GMM | S | H16–19 | 2.7 |
| 2.9 | Cluster retrieval | C | H19–20 | 2.8 |
| 2.10 | Novelty | S | H15–17 | 2.1, 1.17 |
| 2.11 | Validation → G2 | S | H18–23 | 2.2, 2.9, 1.17 |
| 2.12 | Weight calibration (cut-able) | S | H20–24 | 2.11 |
| 2.13 | Ranking stability | S | H20–24 | 2.2, 1.17 |
| 2.14 | Real bundle → G3 | C | H24–26 | 2.5, 2.6, 2.8, 2.10, 2.13 |
| 2.15 | Notebooks 05–09 | C | alongside | — |
| 3.1 | App shell | C | H4–6 | 0.6 |
| 3.2 | Bundle loader | S | H5–7 | 0.6, 0.7 |
| 3.3 | Engine + parity | S | H9–12 | 2.4 |
| 3.4 | Worker + client | S | H11–13 | 3.2, 3.3 |
| 3.5 | Session store | C | H6–8 | 0.6 |
| 3.6 | Target panel | S | H8–12 | 3.1, 3.5 |
| 3.7 | Earth map | S | H8–13 | 3.1, 3.5 |
| 3.8 | Match cards UI | C | H13–15 | 3.4 |
| 3.9 | Lens controls | C | H12–14 | 3.5 |
| 3.10 | Scorecard | C | H14–17 | 3.4 |
| 3.11 | Divergence panel | C | H15–17 | 3.10 |
| 3.12 | Shortlist/novelty/layers | C | H16–19 | 3.7, 3.8 |
| 3.13 | Interactive stability | S | H19–22 | 3.4 |
| 3.14 | Globe painter (stretch) | S | H22–25 | 3.4, 2.5 |
| 3.15 | Globe scene (stretch) | S | H24–28 | 3.14 |
| 3.16 | Globe picking + arcs (stretch) | S | H27–30 | 3.15 |
| 3.17 | About dialog | C | H26–29 | 4.2 |
| 3.18 | Real-data switch + smoke | C | H26–30 | 2.14, 3.4–3.12 |
| 4.1 | Reconcile guides | H | 13 Nov | — |
| 4.2 | Write-up skeleton + sources | C | H10–14 | — |
| 4.3 | Methods | S | H20–26 | 2.11 |
| 4.4 | Results + discoveries → after G2 | S | H26–31 | 2.11, 2.13, 4.3 |
| 4.5 | Judging checklist | C | H30–31 | 4.4 |
| 4.6 | Slides | C | H30–33 | 4.4 |
| 4.7 | Demo recording | H | H32–35 | 3.18 |
| 4.8 | Submit | H | H35–37 | 4.5–4.7 |
