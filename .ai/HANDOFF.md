# Current handoff
Task: T1 complete — normalizers + scorer for hand-built STUB evidence.
Branch: main
Last commit: pending focused T1 commit
Done: `src/common/norm.py` implements the §3.5 vectors and parsers; `src/score/score.py` maps baseline headers, scores stub run directories, emits the §5.6 CSV columns, and prints rollups. The stub fixture contains three inputs in baseline and hardened phases.
Tests / checks run: `python3 -m unittest discover -s tests -t . -v` — 4 tests passed; `PYTHONPYCACHEPREFIX=/private/tmp/t2-pycache python3 -m compileall -q src tests` — passed; required secret grep — clean.
Next task: T2 — `src/checks/static_checks.py`, workflow audit and secret checks.
Read first: AGENTS.md; `.ai/STATUS.md`; `docs/DECISIONS.md`; `docs/ARCHITECTURE.md`; `specs/t2-rescue/tasks.md`; `specs/t2-rescue/plan.md` §T2.
Do not change: architecture contracts, docs/DECISIONS.md, or tasks beyond the T2 checkbox.
Open questions: no T1 blockers.
Targets: local only; no n8n used for T1.
