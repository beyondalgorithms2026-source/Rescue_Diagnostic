# Rescue Teardown: n8n invoice-extraction template 16643

by **Spanfold** · Rescue Diagnostic → Fix & Harden · licence Apache-2.0 (see [`LICENSE`](LICENSE))

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

Requires Docker (n8n), Python 3.9+, an OpenAI API key (model `gpt-4o-mini-2024-07-18`). No Google account needed:
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
(`llm_base_url`, `llm_model`, prices) and are set to `gpt-4o-mini-2024-07-18` via api.openai.com.
n8n pin: `n8nio/n8n:2.22.5`. Spend cap: $0.25 per run.

> **Label note.** `workflows/hardened/t2-hardened.json` (line 482) and `src/replay/run.py` (lines 110–112) still carry a
> DeepSeek label and credential name (`t2-deepseek`, `T2_LLM_PROVIDER=deepseek`). That label is wrong: every recorded call
> used `gpt-4o-mini-2024-07-18`. The label is left in place so the workflow file matches the committed evidence byte for
> byte; it will be renamed in a later code change.

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

## Loom script (3–5 min, 7 segments)

Each segment: the screen to show, what to run beforehand, the spoken line, and the fallback if a live run fails.
No live API run is needed: every segment reads saved outputs. A live run is capped at 3 invoices and must be costed first.

| Segment | Screen | Set up before recording | Spoken line | Fallback |
|---|---|---|---|---|
| 1. Problem (0:00–0:30) | Demo page top | Open `docs/index.md` (GitHub Pages) | "A supplier invoice arrives as a PDF. The n8n template reads it with an LLM and writes it to a sheet. I tested what goes wrong." | Static page |
| 2. Original fails (0:30–1:30) | `evals/scorecard.csv`, baseline rows for t2-001, t2-023, t2-046 | Filter the CSV to `run_phase=baseline` | "On these three invoices the original writes duplicates, bad totals, and in one case an attacker's invoice number." | Saved scorecard |
| 3. Hardened handles the same (1:30–2:30) | Same three IDs, hardened rows | Filter to `run_phase=hardened` | "Same invoices, hardened version. t2-001 is written once. t2-023 is sent to a person. t2-046 still gets the attacker's number, and I say so." | Saved run `hardened-local-20261012T133818Z-nogit` |
| 4. Scorecard (2:30–3:10) | `evals/findings.md` before/after table | Open file | "49 of 50 clean. 0 duplicate rows. Replay writes nothing new. 58 model calls instead of 100." | Saved findings |
| 5. One safeguard (3:10–3:40) | `summary.json`, `replay_check` block | Open file | "I sent the same 50 again into the same store. Zero new header rows. The header row is written last and is the commit marker." | Saved summary |
| 6. Limits (3:40–4:20) | Demo page limitations section | Open | "Synthetic data, public template, not a client deployment. One injection still changed a value. Dedupe is not atomic under concurrency." | Static page |
| 7. Next step (4:20–4:40) | Demo page contact section | Open | "On a client workflow I would start with an intake check and a human-review gate, then measure it the same way." | Static page |

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
