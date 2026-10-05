# Status

| Milestone | State | Evidence |
|---|---|---|
| M0 Harness + architecture (T0) | Done, awaiting human acceptance of ADR-001/002 and frozen contracts | this commit |
| M1 Scorer + static checks (T1–T2) | Done | T1 scorer and T2 static checks; 10 unit tests pass |
| M2 50 synthetic inputs (T3–T4) | Done | T4 generated the 50-row manifest, gold records, and PDFs; 13 unit tests pass |
| M3 Sink + baseline + runner (T5–T7) | In progress | T5 sink, T6 baseline equivalence + local smoke done; 23 unit tests pass; T7 next |
| M4 Baseline run + trace reading (T8) | Blocked on Q-7 (template fails at node 2 and node 3 before OpenAI) | `workflows/baseline/DIFF.md` |
| M5 Hardened + replay (T9–T11) | Not started | — |
| M6 Review, findings, README/Loom (T12–T14) | Not started; T13 needs Q-4 | — |
| Public link | Human gate, out of scope for agents | — |

Targets: local Docker n8n 2.22.5 only (Q-6). Running container still uses tag `latest`; README pins `n8nio/n8n:2.22.5` for re-creation (human step).

Last updated: 2026-10-05 (T6 baseline equivalence).
