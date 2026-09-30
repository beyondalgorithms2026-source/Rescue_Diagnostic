# Current handoff
Task: T1 — `src/common/norm.py` + `src/score/score.py` scoring a hand-built STUB run (see `specs/t2-rescue/plan.md` §T1)
Branch: main (repo not yet initialised — see QUESTIONS Q-5; human runs `git init` first)
Last commit: none
Done: T0 harness — AGENTS, CLAUDE, README, docs/ARCHITECTURE, docs/DECISIONS (ADR-001, ADR-002), .ai/*, specs/t2-rescue/*, evals/README
Next task: T1. Outcome: `python3 -m unittest discover -s tests -t . -v` passes; scorer emits the frozen §5.6 header and correct codes on the stub.
Read first: AGENTS.md; docs/ARCHITECTURE.md §3.5, §4.2–4.3, §5, §6; docs/DECISIONS.md ADR-001; specs/t2-rescue/plan.md §T1
Do not change: AGENTS.md, CLAUDE.md, THIN-LEDGER-v0.1.md, docs/ARCHITECTURE.md, docs/DECISIONS.md, specs/t2-rescue/spec.md, specs/t2-rescue/plan.md, evals/README.md, .ai/ROUTING.md, .ai/QUESTIONS.md (append answers only), anything under evals/ (no stub data there), .claude/
Tests run / result: none — no code exists yet
Open questions: Q-1..Q-6 in .ai/QUESTIONS.md; none block T1–T5. T1 needs no n8n at all.
Targets: develop against local Docker n8n (2.22.5, port 5678) only; the online instance is human-operated (ARCHITECTURE §1.1).
