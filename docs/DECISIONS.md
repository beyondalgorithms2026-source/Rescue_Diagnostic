# Decisions

Cap for this project: 2 ADRs. Cheaper-to-reverse choices live in `docs/ARCHITECTURE.md`.

## ADR-001: Append-only sink, workflow-owned idempotency, dedupe key invoice_no + vendor_norm + currency
Status: Proposed (architecture session; human acceptance pending)
Date: 2026-09-28
Decision:
- All demo writes go to a local append-only sink (CSV tables over HTTP). No update, no delete, no upsert endpoint.
- Idempotency lives in the hardened workflow, not the sink: lookup-then-append on
  `dedupe_key = invoice_no_norm | vendor_norm | currency` (ARCHITECTURE §3.5).
- Line items are written before the header; each line has `line_key = dedupe_key#line_no` and is looked up before append.
  The header row is the commit marker. An invoice "exists" iff its header row exists.
- A content-hash (sha256 of PDF bytes) lookup against committed audit rows short-circuits exact resubmits before any LLM call.
Reason:
- An append-only log is what Sheets actually gives a buyer; putting upsert in the sink would hide the bug being demonstrated.
- `invoice_no` alone collides across vendors; adding `currency` keeps multi-currency billing from the same vendor distinct.
- Header-last makes a partially failed run safely re-playable: lines are skipped, the header is written once.
Consequences:
- Lookup-then-append is not atomic. Concurrent duplicates can both write. Replay is sequential, so the demo cannot show this; findings must state it as residual risk.
- Two JS/Python implementations of the normalizers must agree; test vectors in ARCHITECTURE §3.5 are the contract.
- Replay proof: a second pass over the same inputs adds zero header rows (invariant I-8).
- Reversing this (e.g. SQLite with a UNIQUE constraint) changes what the before/after proves; needs a new ADR.

## ADR-002: Spend cap per run_id, plus per-input size caps, enforced before the LLM call
Status: Proposed (architecture session; human acceptance pending)
Date: 2026-09-28
Decision:
- The hardened workflow refuses an LLM call when `usd_so_far(run_id) + est_usd(call) > RUN_USD_CAP` (default 2.00),
  reading the sink ledger. It also refuses input text over `MAX_INPUT_CHARS` (default 40,000) and PDFs over
  `MAX_PDF_BYTES` (default 2,000,000), and bounds output with `MAX_OUTPUT_TOKENS` (2,000) and `LLM_MAX_RPM` (20).
- A refusal is an error row + audit row with `capped=1`, never a silent stop.
- The replay runner enforces the same `RUN_USD_CAP` as a safety net because the baseline has no cap.
- Prices come only from env (`LLM_PRICE_IN_PER_MTOK`, `LLM_PRICE_OUT_PER_MTOK`); usd = tokens × price / 1e6.
Reason:
- Oversized and injection inputs are the cheapest way to show unbounded consumption; a cap that can be measured is the fix being sold.
- Per-run keeps the replay reproducible; the ledger is the same data that feeds the cost report.
Consequences:
- Callers without a run id get a fresh run_id per request, so per-run cap bounds little outside the replay; findings state that production should key the cap by calendar day or by credential.
- `est_usd` before the call uses `ceil(chars/3)` input tokens + `MAX_OUTPUT_TOKENS`; conservative, may refuse slightly early.
- Changing the cap unit (per day, per tenant) is a new ADR.
