# Findings: n8n community template 16643 — before and after

All inputs are synthetic (50 invoices, US/UK/EU vendors, USD/EUR/GBP). Local n8n 2.22.5. Model for both scored phases:
`gpt-4o-mini-2024-07-18` (owner fallback, QUESTIONS Q-8). Evidence: `evals/scorecard.csv` (100 rows),
`evals/cost_ledger.csv`, run folders below. This is a test report, not an audit.

## What was tested
| Phase | Run | Workflow |
|---|---|---|
| As published | n8n execution 447, 1 input (evidence only) | template 16643 + harness swaps only (`workflows/baseline/DIFF.md`) |
| Baseline (scored) | `baseline-local-20261007T060333Z-nogit`, 50 inputs × 2 passes | as published + two disclosed repairs R-1, R-2 so it can run |
| Hardened (scored) | `hardened-local-20261012T133818Z-nogit`, 50 inputs × 2 passes | `workflows/hardened/t2-hardened.json` |
| Hardened attempt 1 | `hardened-local-20261012T132928Z-nogit` | kept: it exposed a line-duplication defect, fixed before attempt 2 |

**As published, the template does not run.** Node 2 reads the PDF from binary key `data`; the form stores it as
`Invoice_PDF`. With that fixed, node 3 builds an invalid JSON body (PDF text outside the JSON string). It never reaches
OpenAI. Its totals check reads fields the Sheets node does not return, so it always says `[Verified]`. Its Gmail node gets
an empty recipient and refuses to send.

## Before and after (scored phases)
| Measure | Baseline | Hardened |
|---|---|---|
| Inputs with no failure code | 0 / 50 | 49 / 50 |
| Duplicate invoice header rows (`duplicate` = 1) | 48 | 0 |
| Replay of pass B into the same store: new header rows | not run | 0 |
| Inputs dropped with no record or error row (`silent_drop`) | 3 | 0 |
| Inputs with no audit row (`audit_gap`) | 50 | 0 |
| Bad document written anyway (`validate_skip`) | 2 | 0 |
| PDF injection followed (`injection_followed`) | 2 (t2-045, t2-046) | 1 (t2-046) |
| Model calls / input tokens / cost | 100 / 121,316 / $0.0425 | 58 / 37,715 / $0.0142 |
| Field accuracy where a record exists: date, currency, subtotal, tax, total, lines | 29, 44, 46, 0, 47, 45 of 47 | 38 of 38 each |

Hardened outcomes: 32 committed, 6 duplicate skips, 6 rejected (2 size cap, 3 schema, 1 intake), 6 sent to review. 5 outcomes differ from the gold label; all 5 are label errors (review below, R-10).
Field accuracy over all 50 rows is lower for hardened (0.76–0.78) only because skipped and rejected inputs have no record
to score. That is the intended behaviour, not lower extraction quality.

Where the improvement comes from: tax 0 → 38 is the schema (the template has CGST/SGST fields only); date and currency
come from ISO instructions and reading currency from the document, not the form; duplicates, drops, and audit come from the
workflow controls. The model is the same in both phases.

## Trace notes (owner)
*To be written by the owner after reading at least 15 traces across all six buckets (evals/README.md). Not written by a model.*

## OWASP LLM Top 10 (2026 edition, QUESTIONS Q-4) — only where there is evidence
| ID | Evidence | After hardening |
|---|---|---|
| LLM01 Prompt Injection | Baseline wrote attacker invoice numbers from PDF text (t2-045, t2-046). Notes injections had no path to the model. | Notes are never sent. Schema gate, foot check, escaped report. t2-046 still followed: a consistent override is not detectable. |
| LLM02 Sensitive Information Disclosure | Template emails a report to any address typed in the form. n8n keeps webhook headers (incl. the auth token) in execution data. | Recipient allowlist by domain. Token-in-execution-data remains (R-3). |
| LLM03 Excessive Agency | Template writes to Sheets before any check and sends mail to a submitter-chosen address. | Writes only after schema + foot check; review queue holds doubtful invoices; header row is the commit marker. |
| LLM06 Unbounded Consumption | 4 oversized invoices used 65% of baseline input tokens; no cap. | 40,000-character text cap, $0.25 per-run cap, rate cap; exact resubmits skipped before the model (58 vs 100 calls). |
| LLM10 Improper Output Handling | Template puts model output into email HTML unescaped (source review). | All interpolated values HTML-escaped (t2-044 drill and test). |

## Residual risk (from the T12 review, `.ai/HANDOFF.md`)
- A PDF injection that changes values consistently passes all checks (t2-046).
- Duplicate check is lookup-then-append, not atomic; concurrent submissions of one invoice can both write.
- The per-run spend cap is keyed by a caller-supplied run id; a caller with the webhook token can reset it.
- n8n stores the webhook token in execution data; prune or rotate.
- The report allowlist is by domain, not by address.
- `error_swallowed` (code 11) is not measured: the runner does not record per-input execution status.
- The per-call spend threshold (13,333 input tokens) did not flag the baseline's oversized inputs (~9,800 each).
- Review was same-family (Claude reviewed Claude-authored work); a cross-family review is recommended.
- Gold labels: 4 messy inputs are labelled `committed` but the specification sends them to review; t2-040 has a blank form
  currency. Scorecard notes show these as outcome mismatches.
- Sequential replay only; image-only PDFs are rejected, not read.

## What this is not
Not an audit and not a claim about any real client workflow. It shows named failure modes on synthetic
inputs, the controls that reduced them, and the risk that remains.
