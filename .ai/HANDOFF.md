# Current handoff
Task: T10 complete — hardened validate through record, plus T9 defect fixes.

Done:
- H8–H16 in `workflows/hardened/t2-hardened.json`: schema gate + foot check, decide, dedupe lookup, line lookup/append
  (line_key), header last as commit, escaped report + allowlist, review queue, one audit row per input.
- T9 defects fixed: Config `includeOtherFields`; HTTP credential fields; webhook `webhookId`; valid IF operator names;
  H1 reads real PDF bytes with `getBinaryDataBuffer` (n8n 2.x keeps binary on disk); H1 PDF SHA-256 is a dependency-free
  JS SHA-256 (tested against hashlib); error builder records the real code; ids `t2HardenedFlow01` / `t2ErrorHandler01`.
- H6 DeepSeek `deepseek-flash`, `json_object`, `thinking: disabled`; Config prices 0.30/1.20 per 1M (peak, docs 2026-10-12).

Evidence (local n8n 2.22.5, scratchpad drill, fake DeepSeek for logic, real DeepSeek for the error drill):
- Logic drill, 10 submissions: t2-001 A committed; t2-001 B duplicate_skip (content hash, no model call); t2-027
  duplicate_skip; t2-033 committed (trap); t2-036 rejected (reject:schema invoice_no missing); t2-037 review; t2-039 rejected
  (line_items empty); t2-047 rejected (reject:capped, no model call); t2-003 committed after one 503 retry; t2-044 committed,
  outbox HTML escaped. 4 header rows, 7 model calls.
- Error drill: real api.deepseek.com with the placeholder key → 401 → errors row `error:external` + audit `error`; no ledger or writes.
- The error workflow runs only when published (n8n `workflow-execution.service.js`: `activeVersion === null` → refuse).

Commands passed: 46 unit tests; compileall; strict static checks on both hardened files; secret grep (pattern files only).

Next task: T11 — runner support for the hardened phase, then the hardened run.
Runner changes needed (`src/replay/run.py`): `--phase hardened` uses `workflows/hardened/t2-hardened.json`, imports and
publishes `t2-error-handler.json` too, webhook path `T2_WEBHOOK_PATH_HARDENED`, credentials `t2-webhook-auth`,
`t2-sink-auth`, `t2-deepseek`; prices and model from the `0. Config` node; LLM node `H6 LLM Extract — DeepSeek`;
stage map for H-nodes; `--replay-of RUN_ID` for the I-8 pass-B replay into an existing sink.
Blocked on the owner: a real `DEEPSEEK_API_KEY` (current value is an 8-character placeholder), Q-8 baseline re-run confirmation,
trace notes in `evals/findings.md`, push approval. T12 must be a non-Claude reviewer (ROUTING: T10 author is Claude).
Local n8n: T2 workflows imported, none active.
