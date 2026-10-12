# Rescue Teardown: n8n invoice-extraction template 16643

A before/after of the n8n community template **"Extract and validate invoice PDFs with OpenAI, Google Sheets,
and Gmail"** ([n8n.io/workflows/16643](https://n8n.io/workflows/16643-extract-and-validate-invoice-pdfs-with-openai-google-sheets-and-gmail/),
by creator `isawow`). We replay 50 labelled invoices through the template as published, record what goes
wrong, harden it, and replay the same 50 again. You can re-run both.

Baseline is n8n community template 16643, 'Extract and validate invoice PDFs with OpenAI, Google Sheets, and Gmail'
by isaWOW (https://n8n.io/workflows/16643-extract-and-validate-invoice-pdfs-with-openai-google-sheets-and-gmail/),
marked Use for free. No republish licence was stated, so the upstream JSON is not vendored. You fetch it yourself;
our node swaps are listed in [`workflows/baseline/DIFF.md`](workflows/baseline/DIFF.md).

> **All data is synthetic.** Every invoice, vendor, person and email address in this repo was generated for
> this test. Vendors are fictional US/UK/EU businesses; amounts are in USD, EUR or GBP; every PDF has the footer
> "SYNTHETIC TEST DOCUMENT — NOT A REAL INVOICE". No client data was used.

Status: **runs complete** — results below, full write-up in [`evals/findings.md`](evals/findings.md).

## The seven stages we look at

| Stage | Template 16643 does | We check |
|---|---|---|
| intake | form: name, email, currency, notes, PDF | size limits, what free text reaches the model |
| extract | PDF → text → OpenAI → JSON | schema, token spend, injection |
| validate | two fields must exist; totals checked later | do totals foot *before* anything is written |
| decide | subject line says `[Verified]` or `[Check Totals]` | does a bad invoice still get written |
| act | append to Sheets, email the submitter | duplicate rows on resubmit, who can receive email |
| approve | — | is there a hold for a human |
| record | — | run id, cost, per-step outcome |

## What gets measured

- **Field scorecard** (`evals/scorecard.csv`): per invoice, per phase — invoice no, vendor, date, currency,
  subtotal, tax, total, line items, number of header rows written, failure codes, tokens, cost.
- **Failure codes**: 12 named failure modes (schema_miss … audit_gap), defined in `docs/ARCHITECTURE.md` §6.
- **Document-level rollup**: share of invoices with zero failure codes.
- **Replay proof**: the hardened workflow, fed the same 50 again, writes zero new rows.

## How to replay

Requires Docker (n8n), Python 3.9+, an OpenAI API key (or a DeepSeek key, see below). No Google account needed:
writes go to a local append-only sink (`src/sink/`) that stands in for Sheets and Gmail. Results were produced on a
local Docker n8n; you replay on yours with the same workflow files. Model output can vary slightly; formats and the
no-duplicate-rows property should not.

```bash
docker run -d --name n8n -p 5678:5678 -v n8n_data:/home/node/.n8n n8nio/n8n:2.22.5
```
```bash
cp .env.example .env
```

Fill `.env`: `OPENAI_API_KEY`, `SINK_TOKEN`, `SINK_PORT=8787`, `SINK_BASE_URL=http://host.docker.internal:8787`,
`N8N_BASE_URL=http://localhost:5678`, `RUN_USD_CAP=0.25`, `LLM_PRICE_IN_PER_MTOK=0.15`, `LLM_PRICE_OUT_PER_MTOK=0.60`,
and random values for `T2_WEBHOOK_TOKEN`, `T2_WEBHOOK_PATH_BASELINE`, `T2_WEBHOOK_PATH_HARDENED`. `.env` is gitignored.

```bash
python3 -m src.baseline.fetch
```
```bash
python3 -m src.baseline.equivalent
```
```bash
python3 -m src.replay.run setup --phase hardened --sqlite unused
```
```bash
python3 -m src.replay.run run --phase baseline --baseline-mode repaired --sqlite unused
```
```bash
python3 -m src.replay.run run --phase hardened --sqlite unused
```
```bash
python3 -m src.replay.run run --phase hardened --sqlite unused --replay-of <hardened_run_id>
```
```bash
python3 -m src.score.score --baseline <baseline_run_id> --hardened <hardened_run_id> --out evals/scorecard.csv
```

`setup` creates the local n8n credentials from `.env` in memory. The last replay command sends pass B again into the same
store and records `new_header_rows` in that run's `summary.json`. The hardened model is set in the `0. Config` node
(`llm_base_url`, `llm_model`, prices); to use DeepSeek, set those to `https://api.deepseek.com` / `deepseek-flash` with
DeepSeek's prices and run with `T2_LLM_PROVIDER=deepseek`. n8n pin: `n8nio/n8n:2.22.5`. Spend cap: $0.25 per run.

## Results

Same model (`gpt-4o-mini-2024-07-18`) and the same 50 synthetic invoices, two passes each.

| Measure | Template (repaired to run) | Hardened |
|---|---|---|
| Invoices with no failure | 0 / 50 | 49 / 50 |
| Duplicate invoice rows after resubmission | 48 | 0 |
| Third replay into the same store: new rows | — | 0 |
| Invoices lost with no record or error | 3 | 0 |
| Invoices with no audit trail | 50 | 0 |
| Bad documents written anyway | 2 | 0 |
| Prompt injections from PDF text followed | 2 | 1 |
| Tax captured correctly (where a record exists) | 0 / 47 | 38 / 38 |
| Model calls / cost | 100 / $0.042 | 58 / $0.014 |

As published, the template does not run at all: node 2 reads the wrong binary key and node 3 builds invalid JSON
(`workflows/baseline/DIFF.md`). Residual risk, the OWASP LLM mapping, and the label caveats are in
[`evals/findings.md`](evals/findings.md).

## Loom script (≈ 4 min)

1. **0:00 – 0:30 · The promise.** "This is a popular free n8n template: upload an invoice PDF, AI extracts it, it logs to
   Sheets and emails a verified report. I replayed 50 synthetic invoices through it."
2. **0:30 – 1:10 · It does not run.** Show `DIFF.md` smoke table: node 2 reads binary `data`, the form stores
   `Invoice_PDF`; node 3 puts PDF text outside the JSON string. "Out of the box, nothing is extracted."
3. **1:10 – 2:00 · Repaired to run, it still fails.** Two minimal repairs, then the baseline scorecard: 48 duplicate rows
   on resubmission, tax never captured, 3 invoices lost silently, no audit trail, two PDF injections overwrote invoice
   numbers. The "Verified" banner checks fields that are never there.
4. **2:00 – 3:00 · The hardened workflow.** Walk the seven stages: intake guard and hash, size and spend caps, schema gate
   and totals check, review queue, dedupe key with the header row as commit marker, escaped report, audit row per invoice.
5. **3:00 – 3:30 · Proof.** Replay the same 50: 0 duplicate rows; replay pass B again: 0 new rows; 49 of 50 clean;
   58 model calls instead of 100.
6. **3:30 – 3:50 · What is still open.** One PDF injection still changed an invoice number; dedupe is not atomic under
   concurrency; the n8n database keeps the webhook token. "Hardening reduces risk; it does not remove it."
7. **3:50 – 4:00 · Offer.** "If your automation looks like this, a Rescue Diagnostic finds these failures in your flow."

## Google Sheets adapter (optional, not replayed)

The hardened graph maps to Sheets one-for-one: H11 and the H12 line lookup become Sheets "Get Rows" filtered on the
`dedupe_key` / `line_key` column, and the appends become Sheets "Append". The same rule holds: lines first, header row last
as the commit marker. The same race remains (lookup then append is not atomic), and the Sheets node in `defineBelow`
mode returns only the mapped columns, so downstream nodes must read from the earlier node, not from the Sheets output.

## What this is not

Not an audit and not a product. It shows specific failure modes on synthetic inputs, the controls that reduced them,
and the risk that remains.

## Repo map

`docs/` architecture and decisions · `specs/t2-rescue/` task list · `evals/` inputs, gold, runs, scorecard,
findings · `workflows/` baseline diff and hardened n8n JSON · `src/` sink, runner, scorer, fixture generator.
