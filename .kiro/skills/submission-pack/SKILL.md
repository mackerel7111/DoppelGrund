---
name: submission-pack
description: Produce NASA Space Apps 2026 submission materials for DoppelGrund (project summary, write-up, demo script, slides, data-source citations, AI-use log, judging checklist) from real pipeline outputs. Use whenever writing or editing anything in docs/submission/, the README, the About dialog text, pitch wording, or when asked about judging criteria, deadlines or demo format.
---

# Submission pack

## Ground rules
- Every number must come from a file under `data/interim/` or the bundle; cite the file path in a comment next to it in the markdown source.
- Use the claims discipline: "model-defined similarity", never "qualified site", "twin" or "probability of being an analogue".
- Honest labelling: scoring = numerical method; PCA/GMM/HDBSCAN = unsupervised ML; calibration = weakly supervised; novelty/stability = statistics. No neural networks were used.
- Formats and limits follow the official 2026 guides (task 04/4.1). Until then use defaults: summary ≤ 150 words, demo ≤ 30 s, slides ≤ 7.

## Structure of the summary (≤ 150 words)
Problem (1 sentence) → approach (2) → headline validation number (1) → discovery (1–2, with caveat) → why it matters (1).

## Writing discoveries
For each candidate: location (lat/lon), target and lens, S, coverage, stability, km to nearest known site, top matching features, top gaps in physical units, and what fieldwork could test. Always include the divergence items.

## Data sources table
Columns: dataset, provider/agency, version, licence, citation, how used. Generate from `config/datasets.yaml`; only `verified: true` entries are listed without a caveat.

## AI-use log
Table: task id, model, date, human reviewer, notes. Keep it current; disclose it if the guide requires.

## Sarawak framing
Caves (Mulu, Niah) → subsurface biology, extremophiles, cave-robotics logistics, education. Lava tubes (Hawaii, Iceland, Canary Islands, Jeju, Lava Beds) → structural analogue for lunar pits. Never present karst caves as structural lava-tube analogues.
