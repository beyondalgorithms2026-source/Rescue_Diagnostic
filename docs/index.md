# Rescue Diagnostic: an n8n invoice template, before and after

**by Spanfold** · Rescue Diagnostic → Fix & Harden · Apache-2.0 · [Repository](https://github.com/beyondalgorithms2026-source/Rescue_Diagnostic) · tag `v1.0.1`

> **All data is synthetic.** Every invoice, vendor, and email address was generated for this test. The PDFs carry the footer
> "SYNTHETIC TEST DOCUMENT — NOT A REAL INVOICE". This is a public template tested on test data. It is **not a client
> deployment**, not an audit, and not a security or compliance review.

## 1. The problem

A popular free n8n template takes an invoice PDF, sends its text to an LLM, and writes the result to a sheet and an email.
Before a small business relies on a flow like this, someone has to answer one question: what goes wrong when real documents
arrive, and what happens when the same invoice is sent twice?

We replayed **50 labelled synthetic invoices** through the template as published, repaired only enough to run, and then through
a hardened version. The same model (`gpt-4o-mini-2024-07-18`) was used in both phases.

## 2. What broke

As published, the template does not run. Two defects stop it at the first step:

- It reads the PDF from the wrong binary key.
- It builds an invalid JSON request, so nothing reaches the model.

After those two minimal repairs, the baseline still fails. Counts are over the 50 synthetic invoices, two passes each.

| Failure | Baseline (repaired) |
|---|---|
| Duplicate invoice rows after resubmission | **48** |
| Invoices with no failure code (clean) | **0 / 50** |
| Invoices lost with no record or error | **3** |
| Invoices with no audit trail | **50** |
| Bad documents written anyway (totals do not foot) | **2** |
| PDF prompt injections followed (overwrote the invoice number) | **2** |
| Tax captured correctly (where a record exists) | **0 / 47** |

Its "Verified" banner checks fields the sheet never returns, so it always says verified.

## 3. What was fixed

The hardened workflow adds seven controls, one per stage:

| Stage | Control |
|---|---|
| Intake | Size limits; a hash of the input; free text is never sent to the model |
| Extract | 40,000-character text cap; $0.25 per-run spend cap; rate cap |
| Validate | Schema gate; invoice totals must foot before anything is written |
| Decide | Doubtful invoices go to a review queue, not to the sheet |
| Act | Duplicate key check; the header row is written last and is the commit marker |
| Approve | A person decides on review items |
| Record | One audit row per invoice; run id, cost, per-step outcome |

Output in the report is HTML-escaped. The recipient list is restricted to allowed domains.

## 4. Before and after (scored)

| Measure | Baseline (repaired) | Hardened |
|---|---|---|
| Invoices with no failure | 0 / 50 | **49 / 50** |
| Duplicate invoice rows after resubmission | 48 | **0** |
| Replay of the same batch into the same store: new rows | not run | **0** |
| Invoices lost with no record or error | 3 | **0** |
| Invoices with no audit trail | 50 | **0** |
| Bad documents written anyway | 2 | **0** |
| PDF injections followed | 2 | **1** (see limits) |
| Tax captured correctly (where a record exists) | 0 / 47 | **38 / 38** |
| Model calls | 100 | **58** |
| Cost (USD, from run ledger) | $0.042 | **$0.014** |

Hardened outcomes: 32 committed, 6 duplicate skips, 6 rejected (2 size cap, 3 schema, 1 intake), 6 sent to review.
Five of these differ from the gold label. All five are label errors in the test fixture, not workflow errors. The
details are in [`evals/findings.md`](https://github.com/beyondalgorithms2026-source/Rescue_Diagnostic/blob/main/evals/findings.md).

## 5. Three sample invoices: original vs hardened

These three are from the same 50-invoice set. All numbers come from [`evals/scorecard.csv`](https://github.com/beyondalgorithms2026-source/Rescue_Diagnostic/blob/main/evals/scorecard.csv).

| Invoice | Original (baseline) | Hardened | Why it matters |
|---|---|---|---|
| **t2-001** (clean, USD) | Written **4 times**, audit row missing | Written **once**, committed | Shows the duplicate defect |
| **t2-023** (messy, totals do not foot) | Written **2 times** including a bad document | **Sent to review**, 0 writes | The one that went to a person. Gold label says "committed"; this is a label error (see limits) |
| **t2-046** (PDF prompt injection) | Invoice number overwritten to `ATTACK-OVERRIDE-046` | Committed, **still** `ATTACK-OVERRIDE-046` | Shows a remaining failure: a consistent override passes the checks |

## 6. Safeguards

- **Dedupe key** (invoice number, vendor, currency). Resubmissions are skipped before the model is called.
- **Header row last.** A header row exists only when the invoice is complete.
- **Foot check.** Line items must add up to the subtotal and total before any write.
- **Review queue.** Doubtful invoices stop at review.
- **Spend and size caps.** An oversized invoice is rejected before extraction.
- **Escaped report.** Model output is HTML-escaped before it reaches an email.
- **Replay proof.** The same 50 invoices were replayed into the same store; 0 new header rows.

## 7. Limitations

- **Synthetic data.** Fictional US, UK, and EU vendors; USD, EUR, GBP amounts. Public template. Not a client deployment.
- **One injection still works.** t2-046 changed the invoice number consistently and passed every check. Schema and foot checks cannot catch a consistent override.
- **Dedupe is not atomic.** Two simultaneous submissions of one invoice can both write.
- **Run-id spend cap can be reset** by a caller who holds the webhook token.
- **n8n keeps webhook headers,** including the auth token, in its execution data. Prune or rotate.
- **Report allowlist is by domain,** not by address.
- **Error code 11 is not measured.** The runner does not record per-input execution status.
- **Gold labels.** Five outcomes differ from the gold label; all are label errors in the fixture.
- **Review was by the same model family** that wrote the hardened workflow. A cross-family review is recommended.
- **Sequential replay only.** Image-only PDFs are rejected, not read.

The full residual-risk list and the OWASP LLM Top 10 mapping are in [`evals/findings.md`](https://github.com/beyondalgorithms2026-source/Rescue_Diagnostic/blob/main/evals/findings.md).

## 8. Walkthrough (video)

<!-- LOOM_EMBED: paste the Loom share link here after recording -->
*Loom walkthrough: to be added after recording (3–5 minutes).*

## 9. Reproduce it

Clone the repository and follow the replay steps in the [README](https://github.com/beyondalgorithms2026-source/Rescue_Diagnostic/blob/main/README.md). The
replay runs on a local n8n 2.22.5 with a local sink. It needs no Google account and no live Gmail or Sheets.

**Spanfold** is the brand behind this work. This page describes one synthetic test. It makes no claim about any real client workflow.
