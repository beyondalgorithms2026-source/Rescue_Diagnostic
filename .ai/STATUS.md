# Status

| Milestone | State | Evidence |
|---|---|---|
| M0 Harness + architecture (T0) | Done, awaiting human acceptance of ADR-001/002 and frozen contracts | this commit |
| M1 Scorer + static checks (T1–T2) | Done | T1 scorer and T2 static checks; 10 unit tests pass |
| M2 50 synthetic inputs (T3–T4) | Done | T4 generated the 50-row manifest, gold records, and PDFs; 13 unit tests pass |
| M3 Sink + baseline + runner (T5–T7) | Not started; T6 blocked on Q-2, Q-3 | — |
| M4 Baseline run + trace reading (T8) | Blocked on Q-1, Q-6 (online target) | — |
| M5 Hardened + replay (T9–T11) | Not started | — |
| M6 Review, findings, README/Loom (T12–T14) | Not started; T13 needs Q-4 | — |
| Public link | Human gate, out of scope for agents | — |

Targets: local Docker n8n 2.22.5 (running, image unpinned `latest`); online instance TBD (Q-6).

Last updated: 2026-10-05 (T4 fixture generator).
