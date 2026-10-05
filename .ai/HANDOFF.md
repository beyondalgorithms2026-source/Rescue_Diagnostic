# Current handoff
Task: T5 complete — local append-only HTTP sink.
Branch: main
Done: `src/sink/server.py` implements authenticated append, lookup, ledger, replay control, fault injection, request logging, and row stamps. `.env.example` lists the frozen variable names. T5 is ticked.
Tests / checks run: `python3 -m unittest discover -s tests -t . -v` — 17 tests passed, including an ephemeral-port sink test. `python3 -m compileall -q src tests` and the required secret grep were run.
Next task: T6 — baseline workflow fetch and documented swaps.
Read first: AGENTS.md; `.ai/STATUS.md`; `docs/DECISIONS.md`; `docs/ARCHITECTURE.md`; `specs/t2-rescue/tasks.md`; `specs/t2-rescue/plan.md` §T6.
Do not change: architecture contracts, docs/DECISIONS.md, or tasks beyond T6.
Open risk: T1 scorer attribution checks `input_id` or `active_input`, while architecture §3.4 requires sink stamp `replay_input_id`. Resolve before T8 scoring.
Push: `v0.3.0` is a local T4 tag. Automatic approval review rejected pushing to `origin` until the destination and payload are explicitly approved. The existing staged `.ai/QUESTIONS.md` change was not included.
Targets: local only. T5 tests used an ephemeral loopback port.
