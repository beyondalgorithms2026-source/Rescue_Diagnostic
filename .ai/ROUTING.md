# Routing

Classes are law; the vendor mapping is config and can change without a process change.

| Class | Use for in this repo | Not for |
|---|---|---|
| Frontier reasoning | Architecture, ADRs, findings narrative (T13), security review (T12 when Codex authored) | CRUD, fixtures, README tables, commits |
| Coding agent | Hardened n8n JSON (T9, T10), replay runner (T7), sink (T5), scorer + CSV writers (T1), baseline equivalence (T6) | Changing frozen contracts |
| Cheap coding | Scorer unit tests, fixture generator details (T3, T4), static checks (T2), README results table (T14) | Security design, taxonomy changes |
| Local small / cheap prose | HANDOFF drafts, commit messages, Loom script polish | Decisions, anything with numbers |

## Current mapping (2026-09-28)
- Frontier: Claude Opus 5.5 (Claude Code)
- Coding agent: Codex (Codex CLI, reads AGENTS.md natively)
- Cheap coding: any cheap hosted coding model via Cline/Continue/Aider
- Local small: Ollama small model

## Rules
- Author ≠ reviewer family whenever a control is added (T9/T10 by Codex → T12 review by Claude; if Claude writes a control, a GPT-family model reviews).
- One dirty tree, one writer. Parallel agents only in separate git worktrees.
- Escalate to frontier on evidence: a task failed twice, it crosses a trust boundary, or it touches a frozen contract.
- Target mix: frontier ≤ 10% of sessions after T0.
