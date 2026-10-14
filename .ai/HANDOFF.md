# Current handoff
Task: T2 close (owner plan 2026-10-14). Docs, licence, brand, demo Markdown, Loom script, and drafts done. See `specs/t2-rescue/tasks.md` § T2 close.

## Owner gates left (C7–C11)
- Enable GitHub Pages: Settings → Pages → Deploy from a branch → `main` → `/docs`.
- Set repo description (text in plan § 3.6).
- Record the Loom and paste its link into `docs/index.md`.
- Approve push of `main` and tag `v1.0.1`.
- Then the agent re-checks the live demo page and every link on it.

## Decisions recorded 2026-10-14
- D-1 demo = Markdown on GitHub Pages (no HTML file).
- D-2 model in docs = `gpt-4o-mini-2024-07-18`. Code label still DeepSeek (Q-A: docs only).
- D-3 licence = Apache-2.0 (`LICENSE`). Brand = Spanfold. GitHub owner unchanged.

## Known issues
- `src/replay/run.py:110-112`, `workflows/hardened/t2-hardened.json:482`, `tests/test_replay.py:210-213`: DeepSeek label, not renamed.
- `docs/` is published by Jekyll, which also renders `docs/ARCHITECTURE.md` and `docs/DECISIONS.md`. Accepted for now.

## Checks run 2026-10-14
56 unit tests OK; compileall OK; strict static check on hardened JSON clean; secret grep clean on docs, workflows, evals.
