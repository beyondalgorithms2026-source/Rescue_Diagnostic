# Current handoff
Task: T4 complete — 50 deterministic synthetic invoice fixtures.
Branch: main
Done: `src/fixtures/make_inputs.py` generates all six buckets, the four declared sink faults, 50 gold records, 50 PDFs, and the frozen manifest. T4 is ticked.
Tests / checks run: `python3 -m unittest discover -s tests -t . -v` — 13 tests passed; `python3 -m compileall -q src tests` — passed. The required grep found only literal test patterns in `src/checks/static_checks.py` and `tests/test_static_checks.py`. The strict check cannot read the T9 workflow because it does not exist yet.
Next task: T5 — local append-only sink and `.env.example`.
Read first: AGENTS.md; `.ai/STATUS.md`; `docs/DECISIONS.md`; `docs/ARCHITECTURE.md`; `specs/t2-rescue/tasks.md`; `specs/t2-rescue/plan.md` §T5.
Do not change: architecture contracts, docs/DECISIONS.md, or tasks beyond T5.
Open risk: n8n extraction of one generated PDF is still a T6 smoke test.
Targets: local only. T4 did not call n8n or APIs.
