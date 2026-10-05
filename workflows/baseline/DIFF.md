# Baseline equivalence: template 16643 → `16643-equivalent.json`

Baseline is n8n community template 16643, "Extract and validate invoice PDFs with OpenAI, Google Sheets, and Gmail"
by isaWOW (https://n8n.io/workflows/16643-extract-and-validate-invoice-pdfs-with-openai-google-sheets-and-gmail/),
marked Use for free. No republish licence was stated, so the upstream JSON is not vendored (QUESTIONS Q-3).

Neither JSON file is committed. Both are generated into the gitignored `workflows/baseline/upstream/`:

```bash
python3 -m src.baseline.fetch
```
```bash
python3 -m src.baseline.equivalent
```

`src/baseline/equivalent.py` applies exactly the swaps below and fails loudly if the upstream shape changes.
`tests/test_baseline.py` asserts that every other node is identical, field for field, and that connections change only as listed.
Fetched 2026-10-05: 15 nodes, canonical sha256 `1d1c62722505c2fcc38e4656bd5d1e73ccc55617d0652ccefda33cf71fc015dc`
(sorted keys, compact separators). If the hash changes, upstream changed: re-run the tests and re-check this file.

## Swaps (ARCHITECTURE §2.3)

| # | Upstream node (JSON path `nodes[name=…]`) | Equivalent | Why |
|---|---|---|---|
| S-1 | `1. Form — Upload Invoice PDF` (formTrigger 2.2) | New `0. Webhook — Replay Intake` (webhook 2, POST, path `__WEBHOOK_PATH__`, `responseMode: lastNode`) → Code node with the **same name** `1. Form — Upload Invoice PDF` that rebuilds the Form Trigger output item | The runner cannot drive a Form Trigger. Downstream code reads `$('1. Form — Upload Invoice PDF').first().json['Your Name']` etc. at the top level; a Webhook puts fields under `body`. The shim restores the top-level keys (`Your Name`, `Your Email`, `Invoice PDF` metadata, `Currency`, `Notes`, `submittedAt`, `formMode`) and the binary key `Invoice_PDF`, which is what Form Trigger 2.2 produces (`fieldLabel.replace(/\W/g,'_')`, n8n 2.22.5 `nodes/Form/utils/utils.js`). |
| S-2 | Webhook auth (none upstream) | `authentication: headerAuth`, credential `t2-webhook-auth` (header `X-T2-Token`) | Harness control (I-11), not a fix. The intake finding is assessed on the upstream JSON. |
| S-3 | `5a. Sheets — Log Invoice Header` (googleSheets 4.5 append) | httpRequest 4.2, same name and position, `POST __SINK_BASE_URL__/append/invoices`, credential `t2-sink-auth`, keypair body = the 12 mapped columns with the same expressions, in sheet-schema order | No live Google account in replay. No lookup, no retry, no onError — the original had none. |
| S-4 | `7. Sheets — Log Each Line Item` | same as S-3 with `/append/line_items` | as S-3 |
| S-5 | `10. Gmail — Send Extraction Report` (gmail 2.1) | New Code `10a. Gmail — Recipient Check (equivalence shim)` → httpRequest `10. Gmail — Send Extraction Report`, `POST __SINK_BASE_URL__/append/outbox` with `{to, subject, html}` = upstream `sendTo`, `subject`, `message` expressions | The shim reproduces the Gmail node's pre-send check (every recipient must contain `@`, else `Invalid email address`; n8n 2.22.5 `Google/Gmail/GenericFunctions.js prepareEmailsInput`). Without it the sink would accept mail the real node refuses. |
| S-6 | `3. HTTP — AI Extract Invoice Fields` `parameters.jsonBody` | `"model": "gpt-4o-mini"` → `"model": "gpt-4o-mini-2024-07-18"`; nothing else in `parameters` changes | Owner decision Q-1 (dated snapshot for both phases). Disclosed baseline change. |
| S-7 | Credential bindings | Node 3 gets `credentials.openAiApi.name = t2-openai`; S-2..S-5 reference `t2-webhook-auth` / `t2-sink-auth` by name only | Upstream ships no credential references. Ids are bound at import (`bind_credentials`), never committed. |
| S-8 | Workflow `id`, `name`, `active`, `versionId` | `t2BaselineEquiv1`, `T2 baseline — template 16643 equivalent`, `false`, removed | Deterministic CLI import; never active except during a run. |

Connections: added `0. Webhook → 1. Form`; `9. Code — Verify… → 10. Gmail` becomes `9 → 10a → 10`. All other edges unchanged.
Sticky notes, settings (`binaryMode: separate`, `executionOrder: v1`), and nodes 2, 4, 5b, 6, 8, 9 are copied unchanged.

## Known divergences (effect-checked, not hidden)

- **D-1 Sheets output shape.** Sheets append 4.5 in `defineBelow` mode outputs only the mapped Title-Case columns
  (n8n 2.22.5 `Google/Sheet/v2/actions/sheet/append.operation.js`). The sink node outputs `{"row": {...}}`. In both cases
  node 9 finds none of `lineTotal`, `invoiceTotal`, `currency`, `email`, so it computes the same values
  (sum 0, total 0, `[Verified]`, currency `INR`, email empty). On an **empty** sheet upstream switches to auto-map and
  passes items through; the equivalent models a sheet that already has its header row (the documented setup).
- **D-2 Static checks.** The swapped sink nodes report "httpRequest has no positive options.timeout". Sheets/Gmail nodes have
  no such option; this is a property of the swap, not a template finding.

## Manual smoke — local n8n 2.22.5, 2026-10-05

Fixture `t2-001` (clean). Equivalent imported with `n8n import:workflow`, published with `n8n publish:workflow`,
container restarted (CLI publish needs a restart), one POST, outcome read from the n8n SQLite execution tables.
Unpublished and restarted afterwards. Tokens were random per run and not stored.

| Variant | HTTP | Execution | Last node | Error |
|---|---|---|---|---|
| Wrong `X-T2-Token` | 403 | none | — | — |
| Faithful equivalent | 500 | 343, `error` | `2. Extract From File — PDF to Text` | `The item has no binary field 'data' [item 0]` |
| Probe (not committed): node 2 `binaryPropertyName = Invoice_PDF` | 500 | 342, `error` | `3. HTTP — AI Extract Invoice Fields` | `The value in the "JSON Body" field is not valid JSON` |

Sink rows written: none in either variant. OpenAI was not called in either variant.

What this shows:
1. **Upstream defect U-1:** node 2 reads binary `data` (default); the Form Trigger stores the PDF as `Invoice_PDF`. Every
   submission fails at node 2.
2. **Upstream defect U-2:** node 3 builds `"content": {{ JSON.stringify("<prompt>") + <pdf text> }}"`. The PDF text lands
   outside the JSON string, so the body is never valid JSON, for any input.
3. "Extract From File" reads a T3 fixture PDF: shown by the probe, which passed node 2 with the key corrected.

How to score a template that cannot reach its LLM is an owner decision: QUESTIONS Q-7.
