# Current handoff
Task: T10 — IN PROGRESS (not ticked). Paused 2026-10-12 by the owner.
Last commits: `95e2a43` T10a scorer (done), then the T10 WIP commit.

Done in T10 so far (`workflows/hardened/*.json`, `tests/test_hardened.py`):
- H8–H16 added: schema gate + foot check (H8), decide (H10), dedupe lookup (H11), line lookup/append with line_key (H12),
  header last as commit (H13), escaped report + recipient allowlist (H14), review queue (H15), one audit row per input (H16).
- JS normalizer in H8 passes the §3.5 vectors and matches Python (`tests/test_hardened.py`, run under node).
- T9 defects fixed: Config `includeOtherFields: true` (Set 3.4 dropped body/binary); every HTTP node now has
  `authentication: genericCredentialType` + `genericAuthType: httpHeaderAuth` (credentials were never sent);
  webhook `webhookId` added (path was not registered); IF operators renamed to valid n8n names
  (`isEmpty`→`empty`, `larger`→`gt`, `largerEqual`→`gte`) with `singleValue` and condition `version: 2`;
  workflow ids `t2HardenedFlow01` / `t2ErrorHandler01`; error builder records the real code (`reject:capped` etc.).
- H6 uses DeepSeek `json_object` (docs list no `json_schema`), `thinking: disabled`, word "json" in the prompt.
- Config prices = DeepSeek `deepseek-flash` peak, cache miss: 0.30 in / 1.20 out per 1M tokens (pricing page, 2026-10-12).
- Strict static checks clean on both files. 45 unit tests pass.

Where it stopped (live drill on local n8n 2.22.5, scratchpad script, fake DeepSeek on :8788):
- Every input now passes H1, then fails at `H1 PDF SHA-256`: `$binary.Invoice_PDF.data` is undefined because n8n 2.x keeps
  binary data on disk. The same fault makes the H1 byte-size check wrong (`pdf.data.length`).
- That failure is unhandled (Crypto node has no error output) and the error workflow `t2ErrorHandler01` did not run
  (no execution rows). Under investigation: `dist/execution-lifecycle/execute-error-workflow.js` line 50.

Next steps for T10:
1. H1: get bytes with `await this.helpers.getBinaryDataBuffer(0, 'Invoice_PDF')` in the Code node; size = buffer length.
2. Hash: Crypto node binary mode (check `nodes/Crypto/Crypto.node.js` params) or hash in H1 from the same buffer; give the hash step an error output.
3. Find why the error workflow does not fire (published state? settings key?). Fix or record as residual risk.
4. Re-run the logic drill. Expected routes: t2-001 A committed, t2-001 B duplicate_skip (content hash), t2-027 duplicate_skip (key),
   t2-033 committed, t2-036 rejected, t2-037 review, t2-039 rejected, t2-047 rejected+capped, t2-003 committed after one 503 retry,
   t2-044 committed with escaped HTML. Then the error drill: real api.deepseek.com with the placeholder key → errors row + audit `error`.
5. Tick T10, update REVIEW/STATUS, commit.

Blocked on the owner:
- `DEEPSEEK_API_KEY` in `.env` is an 8-character placeholder (DeepSeek returns 401). T11 cannot run until a real key is set.
- Q-8: confirm a DeepSeek re-run of the baseline (owner said "DeepSeek for all purpose").
- `evals/findings.md` § Trace notes (human, ≥15 traces). Push approval: `main` is ahead of `origin` and tags `t8a-rescore` are local.

Local state: n8n has `t2HardenedFlow01`, `t2ErrorHandler01`, `t2BaselineEquiv1` imported, none active. Credentials
`t2-webhook-auth`, `t2-sink-auth` hold throwaway drill tokens; `t2-deepseek` holds the placeholder. Runner `setup` must overwrite them.
Read first next time: AGENTS.md, this file, ARCHITECTURE §3, QUESTIONS Q-8.
