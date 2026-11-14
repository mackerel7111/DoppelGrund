---
inclusion: always
---
# Agent operating rules

You may be a smaller model running one task. Follow these exactly.

1. **One task.** Work on exactly one task from a `.kiro/specs/*/tasks.md`. Touch only the files listed under that task's "Files". If you need another file, stop and report.
2. **Read first.** Read `docs/STATUS.md`, the task, every requirement ID it references, and the design section it names.
3. **Contracts are law.** `data-contracts.md` and the function signatures in each `design.md` are fixed. If one looks wrong, stop and add a `CONTRACT ISSUE:` line to `docs/STATUS.md`. Never edit `requirements.md`, `design.md` or `data-contracts.md` yourself.
4. **Never invent.** Dataset IDs, URLs, coordinates, thresholds, citations and results come from `config/*.yaml|csv` or real computation. If a value is unknown, write `TODO(verify): <what>` and report it.
5. **Science invariants.** Follow `science-invariants.md` whenever you touch pipeline or engine code.
6. **Definition of done.** All acceptance commands in the task pass (at minimum `make verify-quick`), new code has tests, `docs/STATUS.md` has a new log line, and the task checkbox is ticked. Never claim done otherwise.
7. **Stuck twice.** If the same acceptance check fails twice, stop. Add a `Blocked:` entry to `docs/STATUS.md` with what you tried, and hand back.
8. **Small diffs.** No drive-by refactors, renames or reformatting of untouched code. No new dependencies unless the task says so.
9. **No secrets.** Never write credentials, tokens or keys. Earth Engine auth is interactive and local only.
10. **Large data.** Never read or write `data/raw/`. Never load files larger than ~5 MB into chat context; inspect with code (`head`, shapes, dtypes).
11. **Report format.** Finish with: files changed; commands run and their result; open issues or TODOs.

STATUS log line format:
`- [YYYY-MM-DD HH:MM] <spec>/<task-id> <done|partial|blocked> — <one-line summary> (model: <name>)`
