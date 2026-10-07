# Current handoff
Task: T9 complete — hardened intake through ledger workflow files.
Commit: `d56a569 Complete T8 repaired baseline replay`.

Done:
- `workflows/hardened/t2-hardened.json` implements H1–H7 and all required external-call error branches.
- `workflows/hardened/t2-error-handler.json` records unhandled workflow errors in the local sink.
- The intake guard checks PDF size, hashes the PDF, and checks committed content hashes before the model call.
- The workflow caps text, per-run spend at $0.25, and model calls per minute before the DeepSeek request.
- The invoice call is `deepseek-flash` from T9 on through credential `t2-deepseek`; the T8 baseline remains `gpt-4o-mini`.

Files touched:
- `workflows/hardened/t2-hardened.json` and `workflows/hardened/t2-error-handler.json`.
- `specs/t2-rescue/tasks.md`, `.ai/STATUS.md`, `.ai/REVIEW.md`, and this file.

Commands passed:
- `python3 -m unittest discover -s tests -t . -v` — 29 tests OK.
- `python3 -m compileall -q src tests` — OK.
- Required secret grep — only scanner and test literals matched.
- `python3 -m src.checks.static_checks --strict workflows/hardened/t2-hardened.json` — clean.
- `python3 -m src.checks.static_checks --strict workflows/hardened/t2-error-handler.json` — clean.

Decisions:
- Q-6 remains local only; no public API or online target was used.
- Q-7 keeps as-published execution evidence outside the scorecard.
- The scorecard stays baseline-only until T11 adds the hardened phase.

Next task: T10 — hardened validate through record, recipient allowlist, HTML escaping, normalizer check, and LLM error drill.
Open risk: T9 has no live model call; T10 must run its invalid-key error-branch drill against the fake endpoint.
