# Tasks: 04 Submission and pitch

Legend: **[S]** Sonnet-class · **[C]** cheaper model · **[H]** human.

- [ ] 4.1 [H] Reconcile with official guides (13 Nov evening, before H0)
  - Read the 2026 Project Submission Guide and Judging and Awards Guide; note required fields, demo format/length limits, deadlines (local time), AI-use rules.
  - Acceptance: STATUS.md "Now" section lists the submission deadline and required artefacts; this spec's defaults updated by a human if they differ.
  - _Requirements: 1.1, 3.1_

- [ ] 4.2 [C] Write-up skeleton and data sources (Window H10–H14)
  - Files: `docs/submission/writeup.md`, `docs/submission/data-sources.md`
  - Skeleton headings from R4.1; data sources generated from `config/datasets.yaml` (dataset, provider, citation, licence, how used).
  - _Requirements: 1.2, 4.1_

- [ ] 4.3 [S] Methods section (Window H20–H26)
  - Files: `docs/submission/writeup.md`
  - Explain harmonisation, scoring formula, cards, ML with honest labels, novelty, stability. Pull numbers only from `data/interim/**` outputs.
  - _Requirements: 2.2, 4.1, 4.2_
  - Depends on: 02/2.11

- [ ] 4.4 [S] Results, discoveries and limitations (Window H26–H31) — after Gate G2
  - Files: `docs/submission/writeup.md`, `docs/submission/summary.md`
  - Pick 2–3 stable novel candidates (stability ≥ 0.8, coverage ≥ 0.8, geo novelty ≥ gate); describe what matches and what does not.
  - _Requirements: 2.1, 2.3, 2.4, 4.2_
  - Depends on: 02/2.11, 02/2.13, 4.3

- [ ] 4.5 [C] Judging checklist (Window H30–H31)
  - Files: `docs/submission/judging-checklist.md`
  - _Requirements: 5.1_
  - Depends on: 4.4

- [ ] 4.6 [C] Slides (Window H30–H33)
  - Files: `docs/submission/slides.md` (export to the format the guide wants)
  - _Requirements: 3.1, 6.1_
  - Depends on: 4.4

- [ ] 4.7 [H] Demo recording + backup (Window H32–H35, after code freeze)
  - Record per `demo-script.md`; keep a backup recording and an offline build on the demo laptop.
  - _Requirements: 3.1–3.3_
  - Depends on: 03/3.18

- [ ] 4.8 [H] Submit (Window H35–H37, ≥ 2 h before the deadline)
  - Fill the project page, upload/link demo, repo, live app; final AI-use log; screenshot the confirmation.
  - _Requirements: 1.1–1.4, 2.1–2.5_
  - Depends on: 4.5, 4.6, 4.7
