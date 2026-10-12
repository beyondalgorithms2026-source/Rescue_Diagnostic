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

Update 2026-10-12: T11a runner support done (`8208775`). H6 is provider-neutral (`H6 LLM Extract`, credential `t2-llm`,
Config `llm_base_url`); OpenAI `gpt-4o-mini-2024-07-18` is the owner-approved fallback (Q-8).
Next task: T11 — the scored hardened run on local n8n:
  T2_WEBHOOK_TOKEN=<random> T2_WEBHOOK_PATH_HARDENED=<random> N8N_BASE_URL=http://localhost:5678 \
  python3 -m src.replay.run setup --phase hardened --sqlite unused   (creates credentials in memory)
  ... python3 -m src.replay.run run --phase hardened --sqlite unused   then  --replay-of <run_id>
Still open: trace notes in `evals/findings.md` (owner), push approval (owner). T12 reviewer family: ROUTING asks for a
non-Claude reviewer; the owner wants the remaining steps done in Claude, so disclose a same-family review if used.
DeepSeek returns 401 with the current key; OpenAI fallback is approved (Q-8).
Local n8n: T2 workflows imported, none active.
