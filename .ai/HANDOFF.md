# Current handoff
Task: T7 complete — local replay runner, baseline variants, and fake-n8n tests.
Branch: main
Done: `src/replay/run.py` imports through the local n8n CLI, publishes then restarts the container, submits inputs sequentially in passes A/B, reads execution data through read-only SQLite, writes trace, summary, and one cost-ledger row, stops at the $0.25 cap, and unpublishes in `finally`. It starts a fresh local sink for each run. It does not use the public API or an online target. Q-7 repairs are materialized only in the gitignored separate `16643-repaired-to-run.json` file. `DIFF.md` discloses R-1 and R-2.
Tests / checks run: `python3 -m unittest discover -s tests -t . -v` — 26 tests OK. `compileall` OK. Secret grep found only known test and scanner pattern literals.
Next task: T8 — local baseline runs and baseline-only scoring.
Read first: AGENTS.md; `.ai/QUESTIONS.md` Q-1, Q-6, Q-7; `docs/ARCHITECTURE.md` §1.1, §4, §5.4–5.5; `specs/t2-rescue/plan.md` §T8; `workflows/baseline/DIFF.md`; `src/replay/run.py`.
T8 note: Run the as-published baseline as evidence only. Run repaired-to-run as the baseline scorecard phase. The scorecard stays at 100 rows after T11.
Open risk: the sink stamps `replay_input_id`, but the scorer reads `input_id` and `active_input`. Fix the scorer field before T8 scoring. Do not fix it in the T7 session.
