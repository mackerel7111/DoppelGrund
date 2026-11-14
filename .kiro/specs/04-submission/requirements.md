# Requirements: 04 Submission and pitch

Scope: everything judges see. Formats are provisional until the 2026 Project Submission Guide and Judging and Awards Guide are released on 13 November 2026; task 4.1 reconciles this spec with them.

## R1 Compliance
1. THE TEAM SHALL reconcile this spec with the official 2026 submission and judging guides on 13 November and record differences in `docs/STATUS.md`.
2. The project SHALL use NASA open data as a primary source and list every dataset with citation and licence.
3. THE TEAM SHALL record AI assistance (Kiro, models, which tasks) in `docs/submission/ai-use-log.md` and disclose it if the guide requires.
4. No project code or data processing SHALL predate the hackathon start; the git history begins at H0.

## R2 Project page content
1. A summary (≤ 150 words) that states the problem, approach, headline result and why it matters.
2. A "How it works" section: features, scoring, ML (honest labels), validation, novelty, divergence.
3. A "Results" section with numbers produced by the pipeline (recall@k vs random, number of stable novel candidates, coverage), never placeholders.
4. A "Limitations" section (data gaps, proxies, resolution, unmatchable conditions).
5. Links: live app, repository, demo video/slides, data sources.

## R3 Demo
1. A recorded demo (default ≤ 30 s unless the guide says otherwise) plus a slide deck (default ≤ 7 slides) are prepared; whichever the guide requires is submitted.
2. The demo SHALL show: pick a Moon landmark → per-dimension cards → open a novel candidate's scorecard and divergence panel → change a lens → (if built) 3D globes.
3. A backup screen recording and an offline local build SHALL exist on the demo laptop.

## R4 Write-up
1. `docs/submission/writeup.md` (≈ 2–4 pages) SHALL cover motivation, data, harmonisation, scoring, ML, validation (ablation table), discoveries with caveats, limitations, future work.
2. Claims SHALL follow the plan's claims discipline: scores are model-defined similarity, not qualification or twin probability.

## R5 Judging alignment
1. A checklist SHALL map each judging criterion to concrete evidence in the app, write-up or demo.

## R6 Local story
1. The materials SHALL include the Sarawak framing (caves for subsurface biology and exploration robotics; lava tubes are the structural analogue) without overclaiming.
