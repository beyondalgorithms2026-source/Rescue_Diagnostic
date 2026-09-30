# Spec — T2 Automation Rescue Teardown (template 16643)

## Outcome
A public, replayable before/after of n8n community template 16643 that a buyer can re-run locally and
see: what failed, how often, what it cost, and that the hardened version does not double-write.
It is the proof behind the Rescue Diagnostic ($150–250) → Fix & Harden offer.

## Users
- **Buyer** (ops lead / founder running n8n invoice automations): reads README + findings, watches the Loom, optionally replays.
- **Operator** (us): runs the replay, reads traces, writes findings.

## In scope
1. Baseline = template 16643, verbatim JSON plus the documented equivalent (ARCHITECTURE §2.3).
2. 50 labelled synthetic Western inputs (ARCHITECTURE §5.3) with gold rendered-from JSON.
3. Baseline replay (two passes), failures classified into the frozen taxonomy.
4. Hardened workflow: error path on every external call, idempotent writes (ADR-001), schema-bound output,
   secrets out of nodes, spend + rate caps (ADR-002), audit + cost log.
5. Hardened replay of the same 50; scorecard with both phases; replay adds zero duplicate header rows.
6. One-page findings mapped where relevant to OWASP LLM Top 10 IDs LLM01, LLM02, LLM03, LLM06 (edition: Q-4). Residual risk stated.
7. README + 4-minute Loom script.

## Out of scope
Threshold/48-combo matrix; branded eval UI or dashboard; eval SaaS; agent/MCP layer; live Gmail or Sheets of
any client; T1 intake product; Jira, GST, Tally, Make/Zapier; India-specific fields; human-approval UI;
OCR of image-only PDFs; concurrency testing.

## Frozen contracts (do not change without a new session of the architecture worker)
- Failure taxonomy: 12 codes, names and numbers in ARCHITECTURE §6.
- Scorecard columns: ARCHITECTURE §5.6, exact order.
- Manifest, gold, trace, cost ledger formats: ARCHITECTURE §5.
- Dedupe key and normalizers: ARCHITECTURE §3.5 / ADR-001.

## Acceptance (project-level)
- [ ] `evals/scorecard.csv` has exactly 100 rows (50 × {baseline, hardened}) from two real run_ids.
- [ ] Hardened: `duplicate` = 0 on every row; the extra pass-B replay records 0 new header rows.
- [ ] Hardened: no `silent_drop`, `error_swallowed`, `audit_gap`, `unbounded_spend`, `retry_storm` codes.
- [ ] `static_checks.json` for the hardened workflow: no secrets, every external node has an error output and bounded retries.
- [ ] Every number in findings traces to a file in `evals/runs/` or `evals/scorecard.csv`.
- [ ] Findings contain a residual-risk section and none of: secure, certified, compliant, production-ready.
- [ ] Both scored run_ids come from the online target and record `target` + `n8n_version` in summary.json.
- [ ] Fresh clone + `.env` + README steps reproduces a hardened run on a **local** Docker n8n (numbers may differ; formats may not) — a buyer never needs our online instance.
- [ ] No committed file names the online instance hostname, webhook URL, tunnel URL, or any token (I-10).

Hardened is **not** required to score 1 on every field. Model extraction errors that are correctly routed
(review/rejected with an error row) are acceptable and must be reported, not tuned away.
