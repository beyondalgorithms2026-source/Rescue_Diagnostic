# Status

| Milestone | State | Evidence |
|---|---|---|
| M0 Harness + architecture (T0) | Done, awaiting human acceptance of ADR-001/002 and frozen contracts | this commit |
| M1 Scorer + static checks (T1–T2) | Done | T1 scorer and T2 static checks; 10 unit tests pass |
| M2 50 synthetic inputs (T3–T4) | Done | T4 generated the 50-row manifest, gold records, and PDFs; 13 unit tests pass |
| M3 Sink + baseline + runner (T5–T7) | Done | T5 sink, T6 baseline equivalence, and T7 local replay runner; 26 unit tests pass |
| M4 Baseline run + trace reading (T8, T8a) | Run done; re-scored by T8a. Human trace notes still missing (`evals/findings.md`) | execution 447 as-published evidence (1 input); repaired run `baseline-local-20261007T060333Z-nogit`; 50-row scorecard re-scored 2026-10-12 |
| M5 Hardened + replay (T9–T11) | Done | `hardened-local-20261012T133818Z-nogit`: clean rate 0.98, 0 duplicate headers, I-8 replay 0 new header rows; attempt 1 `...132928Z` kept as evidence of the retry line-duplication defect | T9 hardened intake through ledger workflow files pass strict static checks |
| M6 Review, findings, README/Loom (T12–T14) | Done (T15 optional also done) | T12 review in HANDOFF; `evals/findings.md`; README results + Loom script |
| Public link | Human gate, out of scope for agents | — |

Targets: local Docker n8n 2.22.5 only (Q-6). Running container still uses tag `latest`; README pins `n8nio/n8n:2.22.5` for re-creation (human step).

Model: DeepSeek for all model calls from 2026-10-12 (Q-8); prices and baseline re-run still open.

Last updated: 2026-10-12 (T12–T15 done; owner gates remain: trace notes, push, public link).
