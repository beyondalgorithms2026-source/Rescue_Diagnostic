# evals — how we judge outputs

This folder is product evals (Thin Ledger §8), not coding ceremony. Formats are frozen in
`docs/ARCHITECTURE.md` §5–§6; this file says how to use them honestly.

## There is no gold set yet
Gold files are created by the fixture generator (T3/T4). Until then this folder holds only this README.
Do not add example or placeholder gold rows.

## Where gold comes from
Each `gold/<input_id>.json` is written **first**; the PDF is rendered from it. Gold is never produced by, or
corrected toward, a model's output. If a PDF renders ambiguously (e.g. a date that could be two dates), fix
the generator, not the gold.

## What is judged
1. **Field checks, yes/no.** Each `*_ok` column is 0 or 1 against gold by the rules in ARCHITECTURE §6. No
   "quality = 7". Blank means not applicable.
2. **Failure codes.** 12 named modes. Each is a deterministic check on sink rows, traces and the request log.
   No LLM judge is used in this project. If one is ever added, it gets one failure mode only and is validated
   against human labels first.
3. **Document rollup.** Share of inputs with no failure code, per phase.
4. **Replay proof.** A second pass writes zero new invoice header rows in the hardened phase.
5. **Workflow-level checks.** `secret_in_node` and config findings come from `runs/<run_id>/static_checks.json`,
   not from per-input rows.

## Top-down vs bottom-up
- **Top-down** (frozen now): the 12 codes and the field checks. Domain requirements anyone would state
  before seeing output: no duplicate writes, no silent drops, totals foot before writing, spend bounded.
- **Bottom-up** (human, after the baseline run): read at least 15 traces across all six buckets before writing
  findings. Record what you saw in `findings.md` § Trace notes. A pattern that is not one of the 12 codes goes
  into notes and `.ai/QUESTIONS.md` — the taxonomy is not extended mid-project.

## Rules
- Numbers in findings must trace to a file under `runs/` or to `scorecard.csv`.
- Do not tune prompts against the 50 inputs and then report the same 50 as the result without saying so.
- Model errors that the hardened workflow routes correctly (review/rejected with an error row) are reported
  as extraction misses, not hidden.
- Stub data for tests lives in `tests/fixtures/`, never here.
