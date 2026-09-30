# Plan — t2-rescue

Per-task acceptance. Sections referenced are in `docs/ARCHITECTURE.md`. Commands are in `AGENTS.md`.

## T1 — normalizers + scorer (next)
Files: `src/__init__.py`, `src/common/__init__.py`, `src/common/norm.py`, `src/score/__init__.py`, `src/score/score.py`,
`tests/__init__.py`, `tests/test_norm.py`, `tests/test_score.py`, `tests/fixtures/stub_run/**`, `.gitignore`.
- `norm.py` implements §3.5 exactly and the amount/date/currency parse rules in §6. Pass all §3.5 vectors.
- `score.py` CLI: `--baseline RUN_ID [--hardened RUN_ID] --out PATH [--runs-dir evals/runs] [--manifest evals/inputs/manifest.csv]`.
  Without `--hardened` it writes 50 baseline rows (interim, T8); the committed `evals/scorecard.csv` is only ever the 100-row version (T11).
  Reads sink CSVs, `requests.jsonl`, `trace.jsonl`; applies §4.3 and §6; writes §5.6 columns in exact order; prints rollups.
- Stub fixture: `tests/fixtures/stub_run/` with its own `manifest.csv`, 3 gold files (clean, duplicate of the clean one,
  missing_field), and two run dirs (`STUB-baseline`, `STUB-hardened`) whose CSVs are hand-written to trigger at least
  duplicate_write, validate_skip, silent_drop, audit_gap in baseline and none in hardened. Every stub file has `STUB` in
  its name or first line. Stub data never goes under `evals/`.
- Tests assert: header row equals the frozen string; failure_codes ordering; write_count across passes; blank `*_ok`
  semantics; rollup doc-level clean rate.
Done: tests pass; `evals/scorecard.csv` untouched.

## T2 — static checks
- Secret patterns: `sk-[A-Za-z0-9_-]{20,}`, `sk-proj-`, `ya29\.`, `AIza[0-9A-Za-z_-]{35}`, `Bearer [A-Za-z0-9._-]{20,}`,
  `"(access|refresh)_token"\s*:\s*"[^"]+"`, `"apiKey"\s*:\s*"[^"={]` , `-----BEGIN [A-Z ]*PRIVATE KEY-----`.
- Workflow audit per node of type httpRequest/googleSheets/gmail/openAi: `onError` set to an error output (or not, for baseline — report, don't fail);
  `retryOnFail` ⇒ `maxTries ≤ 3`; httpRequest has `options.timeout`.
- CLI exits non-zero only in `--strict` (used for hardened). Output JSON: `{file, sha256, secrets:[…], nodes:[{name,type,onError,retry,maxTries,timeout}], violations:[…]}`.

## T3 / T4 — fixtures
- `pdfwriter.py`: PDF 1.4, Helvetica, text-only, multi-page; output must round-trip through n8n "Extract From File (pdf)" — verify one file manually in T6 and note it.
- Generator writes gold first, renders the PDF from gold (I-2). Seeded; re-running yields byte-identical files (no timestamps in PDF metadata).
- Mix and semantics exactly §5.3; gold format §5.2; `dedupe_key` computed with `norm.py`.

## T5 — sink
- Endpoints: `POST /append/<table>`, `GET /lookup/<table>?<col>=<val>[&<col>=<val>]` → `{"count":n,"rows":[…]}`,
  `GET /ledger/sum?run_id=` → `{"usd":x}`, `GET /ledger/count?run_id=&since_s=` , `POST /_replay/active`, `POST /_replay/fault`, `GET /_health`.
- Tables fixed to §3.4 plus baseline's two 12-column tables (columns taken from the first append; header written once).
- Unknown table → 400. Never updates or deletes (I-4). Single-threaded server is fine (I-7).
- Every endpoint requires `X-Sink-Token == SINK_TOKEN` (401 otherwise, logged). Refuse to start if `SINK_TOKEN` is empty.
- `.env.example` with every name in ARCHITECTURE §3.2, values empty.

## T6 — baseline
- Blocked by Q-3 (and Q-2 pin). Swaps exactly §2.3, including headerAuth + placeholders. `DIFF.md` lists JSON path per swap.
  Test compares non-swapped nodes. Verify the equivalent imports and a single `clean` fixture runs end-to-end on the **local**
  2.22.x container (manual, noted in DIFF.md with date and n8n version) — including that "Extract From File" reads a T3 PDF.

## T7 — runner
- §1.1, §4.1–4.4. `--target local|online`. Substitution in memory only; the grep in AGENTS.md must stay clean after a run.
- Deactivate in `finally`. Online: never create credentials, never print tokens/URLs, fail fast if `_health` fails.
- Fake n8n stub in tests (no network). No retries on submission. Scrub per §3.6.

## T8 — baseline run
- Requires prices + budget (Q-1) and the online target ready (Q-6): credentials created in the UI by the human, tunnel up.
- Dry run first on `local` (not committed), then the scored run on `online`. Commit only the online run dir.
- Human gate: read ≥15 traces before any findings prose.

## T9 / T10 — hardened
- Graph §3.1, config §3.2, schema §3.3, tables §3.4, norms §3.5. `static_checks --strict` clean.
- Notes field is stored, never sent to the LLM. Report recipient allowlist. HTML-escape everything interpolated.

## T11 — hardened run + scorecard
- 100-row scorecard; extra pass-B replay → 0 new header rows (I-8), recorded in that run's summary.json.

## T12 — review
- Different model family from the T9/T10 author (see `.ai/ROUTING.md`). Merge-blockers only: file:line + how to show it fails.

## T13 — findings (`evals/findings.md`, ≤ 1 page)
Sections: What was tested (links to run_ids) · Before/after table (rollups) · Per-code counts · Trace notes (human) ·
OWASP mapping (only where evidence exists) · Residual risk (§3.7 + anything new) · What this is not.

## T14 — README + Loom
Results table from findings; Loom script ≈ 4 min: 0:00 problem · 0:40 baseline replay live · 1:40 scorecard before ·
2:20 hardened replay + second pass shows 0 new rows · 3:20 residual risk · 3:45 offer.
