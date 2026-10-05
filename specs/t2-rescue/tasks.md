# Tasks — t2-rescue

One box = one Codex session = one focused commit. Dependency order. Tick the box in the same commit.
Each task's acceptance is in `plan.md` under the same id. Do not start a task whose dependencies are unticked.

- [x] **T0** Harness skeleton: AGENTS, CLAUDE, README, docs, .ai, specs, evals/README (architecture session, Opus)
- [x] **T1** `src/common/norm.py` (invoice_no_norm, vendor_norm, dedupe_key, amount/date/currency parsers) + `src/score/score.py` reading manifest, gold, and a run dir; writes the frozen scorecard columns and prints rollups. Tests use a hand-built `tests/fixtures/stub_run/` labelled STUB (3 inputs, both phases). `.gitignore`. — deps: T0
- [x] **T2** `src/checks/static_checks.py`: secret grep + workflow audit (external nodes without onError / with unbounded retries / missing timeout) → `static_checks.json`; tests with tiny inline JSON snippets. — deps: T1
- [x] **T3** `src/fixtures/pdfwriter.py` (stdlib text-only PDF) + `make_inputs.py` generating the 14 clean + 12 messy inputs, gold JSON, manifest rows. Deterministic seed. Footer invariant I-1. — deps: T1
- [x] **T4** Extend generator: 8 duplicate, 6 missing_field, 6 injection, 4 oversized; faults on 2 clean + 2 messy; full 50-row manifest; test that every gold passes schema and every PDF text contains the footer. — deps: T3
- [x] **T5** `src/sink/server.py`: append/lookup/ledger endpoints, `_replay/active`, `_replay/fault`, request log, row stamping, `X-Sink-Token` auth; `.env.example`. Tests start it on an ephemeral port. — deps: T1
- [ ] **T6** Baseline: fetch verbatim `16643-original.json` (only after Q-3 answered), produce `16643-equivalent.json` with §2.3 swaps only (incl. headerAuth + placeholders), `DIFF.md`; test asserting non-swapped nodes' `parameters` are identical; one manual smoke on the local container. Pin n8n (Q-2) in README. — deps: T2, T5, Q-2, Q-3
- [ ] **T7** `src/replay/run.py` setup + run, `--target local|online` (placeholder substitution in memory, activate/deactivate in finally, passes A/B, attribution, trace.jsonl, summary.json, cost_ledger.csv, runner cap). Tests against a fake n8n HTTP stub (no network). — deps: T5, T6
- [ ] **T8** Baseline run: local dry run (not committed), then scored run on online (Q-1, Q-6; human creates credentials + starts tunnel). Commit `evals/runs/<baseline_run_id>/`. Score baseline-only; nothing to findings yet. Human reads ≥15 traces and writes notes in `evals/findings.md` §Trace notes. — deps: T4, T7, Q-1, Q-6
- [ ] **T9** Hardened part 1: intake → extract → spend gate → ledger (H1–H7) + `t2-error-handler.json`; static checks clean. — deps: T8
- [ ] **T10** Hardened part 2: validate → decide → act (dedupe, header-as-commit) → approve → record (H8–H16), recipient allowlist, HTML escape; JS normalizer passes §3.5 vectors (test via exported code string run under `node`). LLM error-branch drill with invalid key, noted in commit message. — deps: T9
- [ ] **T11** Hardened run (local dry run, then online — same target as T8); re-score both phases into `evals/scorecard.csv`; then a third hardened pass-B-only replay against the same sink proves I-8 (0 new header rows) — record in summary.json. — deps: T10
- [ ] **T12** Review (different family from the T9/T10 author): security review of hardened JSON + scorer; findings only, file:line, in the commit message of a docs-only commit or `.ai/HANDOFF.md`. — deps: T11
- [ ] **T13** `evals/findings.md` one-pager: rollups, per-code table, OWASP mapping, residual risk (frontier). — deps: T12
- [ ] **T14** README results table + `README.md` §Loom script (4 min) filled from findings (cheap prose). Public link is a human gate. — deps: T13
- [ ] **T15** *(optional, not DoD)* Sheets adapter notes in README §7-equivalent. — deps: T13
