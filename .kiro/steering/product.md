---
inclusion: always
---
# Product: Global Analogue Discovery Engine

## One line
Pick a landmark on the Moon or Mars. DoppelGrund scores every land hexagon on Earth (H3 resolution 4, ~85,000 cells) against it, shows the best Earth match **per dimension** (terrain, thermal, cold/ice, composition, subsurface) plus best overall, flags places nobody has studied, and states plainly where each analogy fails.

## Challenge
NASA Space Apps 2026, "Identify Earth Locations that Analog the Permanent Moon Base Locations and Mars". Hackathon: 14-15 November 2026. Building may start before the event (orchestrator decision, 2026-10-30).

## How the product answers the challenge
| Challenge asks for | DoppelGrund feature |
|---|---|
| New, previously unrecognised analogues, not rediscovery | Novelty index (distance from known sites) + rediscovery validation |
| Explain what is analogous and what is not | Per-feature gaps in physical units + divergence panel |
| Different analogues for different characteristics | One match card per dimension; optional mission lenses |
| Think beyond visual similarity | Physical, unit-bearing features only, never pixels |
| Processes as well as places | Process tags (volcanic, periglacial, evaporitic) |
| Caves, lava tubes, subsurface | Scored feature `pit_cave_density_per_1000km2` (catalogued pits/caves per area, group `subsurface`) plus curated overlay layers. It is a prior from catalogues, never a detection; NaN where no survey covers the area. Never present karst caves as structural lava-tube analogues. |
| Earth's limits (gravity, vacuum, radiation) | Never scored, always shown in the divergence panel |
| Consider scale | Stage-2 refinement of top hits (stretch) |
| Maps, similarity metrics, ML | Interactive 2D/3D app, tolerance-kernel scoring, classical unsupervised ML |

## Users
1. Analogue and mission planners: want a defensible shortlist with evidence.
2. Researchers: want reproducible features, sources and gaps.
3. Hackathon judges: want validity, creativity, impact and a clear demo.
4. Public and Sarawak audiences: want an engaging, honest story.

## Principles (non-negotiable)
- Physical quantities in stated units; never raw pixels.
- Missing data stays missing (NaN), reported as coverage.
- Unmatchable conditions are flagged, never scored.
- Classical methods only, labelled honestly (scoring = numerical method; PCA/GMM/HDBSCAN = unsupervised ML; calibration = weakly supervised).
- Every number on screen traces to a feature, a dataset and a version.
- Static-first: the web app is a static site; all heavy computation is offline.

## Non-goals
Neural networks or deep learning of any kind; user accounts; a backend server; live raster processing in the browser; claims that a site is "qualified" or a "true twin".

## Judging
The 2025 criteria were Impact, Creativity, Validity, Relevance and Presentation. The 2026 Judging and Awards Guide is released on 13 November 2026: re-check then.

## Where the detail lives
- Master plan (science): `docs/plan/Global_Analogue_Discovery_Engine_Plan.md` (read only when a task needs it).
- Build plan and orchestration: `tech_stack.md`.
- Specs: `.kiro/specs/00-foundation` to `04-submission`.
