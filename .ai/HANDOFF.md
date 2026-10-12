# Current handoff
Task: T8a complete — scorer fix and baseline re-score.
Commits: `4f0b22c` (ARCHITECTURE §6 amendment, Q-8) and the T8a commit after it.

Done:
- `src/score/score.py`: pass comes from `replay_pass` (fallback `pass`, never a default "A"); `write_count` follows §4.3;
  `retry_storm` counts failed attempts only; a workflow cap no longer fires `unbounded_spend`.
- `tests/test_score.py`: 4 new tests with real sink stamps. Each one fails on the old scorer and passes on the new one.
- `evals/scorecard.csv`: re-scored from `baseline-local-20261007T060333Z-nogit`. No n8n run, no model call. 50 rows, same header.

Code counts, before → after (baseline, 50 inputs):
- duplicate_write 3 → 48 (each invoice is written in pass A and again in pass B).
- lineitem_mismatch 46 → 2; lineitem_ok 4 → 46 (pass B rows no longer leak into pass A).
- retry_storm 31 → 0 (the baseline has no retries; line-item appends are writes).
- silent_drop 1 → 3 (t2-003, t2-017: pass-A sink fault, no error row; t2-039).
- validate_skip 0 → 2 (the two doc_foots=false invoices were written).
- field_wrong 49 → 47, schema_miss 19 → 18; field counts drop by 1–2 because t2-003/t2-017 have no pass-A row.
- Unchanged: audit_gap 50, tax_ok 0/50, clean documents 0/50.

Commands passed:
- `python3 -m unittest discover -s tests -t .` — 33 tests OK.
- `python3 -m compileall -q src tests` — OK.
- Secret grep — only `src/checks/static_checks.py` and `tests/test_static_checks.py` (pattern literals).

Next task: T10 — hardened validate through record (plan.md §T9/T10).
Read first: AGENTS.md; ARCHITECTURE §3.1–3.5, §6; QUESTIONS Q-8; `workflows/hardened/t2-hardened.json`.
Do not change: frozen contracts, `docs/DECISIONS.md`, baseline files, `evals/scorecard.csv` (T11 re-scores).
Open questions: Q-8 — DeepSeek prices, exact model id, and whether the baseline is re-run on DeepSeek. Q-8 blocks T11, not T10.
Open gaps: `evals/findings.md` § Trace notes does not exist (T8 human step). 6+ commits on `main` are not pushed.
