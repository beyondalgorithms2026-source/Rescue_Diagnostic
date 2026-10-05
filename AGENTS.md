# AGENTS.md — standing law

Harness: Thin Ledger v0.1 (`THIN-LEDGER-v0.1.md`). The repo is memory; chat is not.

## Read before any edit
1. This file
2. `.ai/HANDOFF.md`, `.ai/STATUS.md`
3. `docs/DECISIONS.md` and the sections of `docs/ARCHITECTURE.md` your task cites
4. `specs/t2-rescue/tasks.md` and your task's section in `plan.md`
5. `git status`, recent relevant commits
6. Only the source files the task names

## Authority order
AGENTS.md → accepted ADRs (`docs/DECISIONS.md`) → `docs/ARCHITECTURE.md` → `specs/t2-rescue/*` → existing conventions → model preference

## Rules
- One task (one checkbox in `specs/t2-rescue/tasks.md`) per session. Tick it in the same commit.
- Architecture files outrank your preference. Frozen contracts (taxonomy, scorecard columns, file formats, dedupe key) change only in an architecture session.
- No drive-by refactors. No new subsystem, database, dependency, framework, dashboard, agent/MCP layer, or public API without an ADR. ADR cap for this project is 2 and both are used — so the answer is `.ai/QUESTIONS.md` and stop.
- Search for an existing helper (`src/common/`) before writing another.
- Python ≥ 3.9 standard library only. No pip installs.
- All data synthetic and Western (USD/EUR/GBP). No India-specific fields (GSTIN, IRN, HSN, CGST, SGST) anywhere except the verbatim baseline template and its documented mapping.
- Never hand-type, estimate, or "fill in" timestamps, token counts, costs, or scores. Evidence comes from runs.
- Never write secrets to any file. `.env` is gitignored. Workflow JSON references credentials by name only.
- Never call live Gmail/Sheets of anyone. Replay uses the local sink.
- Two n8n targets (ARCHITECTURE §1.1). Agents develop and test against `local` only. Runs on `online` are started by the human. Never commit an online hostname, webhook URL, tunnel URL, or token; never use `$env` in workflow JSON.
- Never use the words secure, certified, compliant, production-ready about this work.
- Reviewer reports findings (file:line + how it fails); reviewer does not rewrite.
- Stuck on an architecture question → write it in `.ai/QUESTIONS.md` and stop.

## Closeout (every milestone)
Before you stop, overwrite .ai/REVIEW.md. Do not append.
Write 80% ASD-STE100: one fact per sentence. Max 12 lines. No synonyms. No praise.

Use these headings only:
- Changed: files you edited.
- Did: the one task you finished.
- Did-not: files and tasks you left alone.
- Check: the command you ran, and the result.
- Risk: one thing still open. Write "none" if there is none.
- Next: the next task id from tasks.md.

Add one mermaid diagram of the path you touched.
Do not make an HTML page. Do not make a video. Do not add a dependency.
If the diagram needs more than 12 nodes, the task was too big. Stop and say so in Risk.
Print that same card as your final chat reply. Do not add a longer summary. The file and the reply must match.

## Commands (real; they run once T1 creates `src/` and `tests/`)
```bash
python3 -m unittest discover -s tests -t . -v        # tests
python3 -m compileall -q src tests                   # syntax check (no linter/type-checker by design)
grep -rEn 'sk-[A-Za-z0-9_-]{20,}|sk-proj-|ya29\.|AIza[0-9A-Za-z_-]{35}|Bearer [A-Za-z0-9._-]{20,}|"(access|refresh)_token" *: *"[^"]+"|BEGIN [A-Z ]*PRIVATE KEY' workflows evals src tests 2>/dev/null && echo "SECRET FOUND" || echo "secret grep clean"
```
After T2: `python3 -m src.checks.static_checks --strict workflows/hardened/t2-hardened.json`.
Do not claim tests passed unless you ran them in this session and saw the output.

## End of session
1. `git diff` — drop anything unrelated to the task. Expected 2–6 files; more → stop and explain.
2. Run the commands above.
3. Overwrite `.ai/HANDOFF.md`; update `.ai/STATUS.md` if a milestone moved.
4. One focused commit. New session for the next task.
