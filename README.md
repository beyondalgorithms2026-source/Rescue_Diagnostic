# Rescue Teardown: n8n invoice-extraction template 16643

A before/after of the n8n community template **"Extract and validate invoice PDFs with OpenAI, Google Sheets,
and Gmail"** ([n8n.io/workflows/16643](https://n8n.io/workflows/16643-extract-and-validate-invoice-pdfs-with-openai-google-sheets-and-gmail/),
by creator `isawow`). We replay 50 labelled invoices through the template as published, record what goes
wrong, harden it, and replay the same 50 again. You can re-run both.

> **All data is synthetic.** Every invoice, vendor, person and email address in this repo was generated for
> this test. Vendors are fictional US/UK/EU businesses; amounts are in USD, EUR or GBP; every PDF has the footer
> "SYNTHETIC TEST DOCUMENT — NOT A REAL INVOICE". No client data was used.

Status: **harness only** — no run results yet. See `.ai/STATUS.md`.

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

## How to replay (available after task T11)

Requires Docker (n8n), Python 3.9+, an OpenAI API key. No Google account needed — writes go to a local
append-only sink (`src/sink/`) that stands in for Sheets and Gmail.

The published results were produced on a live online n8n instance; you replay on your own local Docker n8n
with the same workflow files. Numbers will differ slightly (model non-determinism); formats and the
no-duplicate-rows property should not.

```bash
cp .env.example .env
```
```bash
python3 -m src.replay.run setup --target local --phase baseline
```
```bash
python3 -m src.replay.run run --target local --phase baseline
```
```bash
python3 -m src.replay.run setup --target local --phase hardened
```
```bash
python3 -m src.replay.run run --target local --phase hardened
```
```bash
python3 -m src.score.score --baseline <baseline_run_id> --hardened <hardened_run_id> --out evals/scorecard.csv
```

n8n version pin: *to be set in T6*. Spend is capped per run (`RUN_USD_CAP`, default $2.00).

## Results

*Filled in T14 from `evals/findings.md`. No numbers until real runs exist.*

## Loom script (≈ 4 min)

*Filled in T14.*

## What this is not

Not a security certification, not an audit, not a product. It shows specific failure modes on synthetic
inputs and the controls that reduced them, with the risk that remains.

## Repo map

`docs/` architecture and decisions · `specs/t2-rescue/` task list · `evals/` inputs, gold, runs, scorecard,
findings · `workflows/` baseline and hardened n8n JSON · `src/` sink, runner, scorer, fixture generator.
