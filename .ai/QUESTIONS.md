# Open questions (decisions the architecture session refused to invent)

Answer inline, date it, and move the answer into ARCHITECTURE/README as the task needs.

## Q-1 OpenAI model, prices, and total budget — blocks T8
The template uses `gpt-4o-mini` via `api.openai.com`. Needed from the owner:
- Is `gpt-4o-mini` still served on your account (Sep 2026)? If not, which model replaces it for **both** phases (the baseline must stay as published except §2.3; a model swap is a baseline change and must be disclosed)?
- Current per-million-token input/output prices for that model → `LLM_PRICE_IN_PER_MTOK`, `LLM_PRICE_OUT_PER_MTOK`. Not guessed.
- Total project spend ceiling. Default per-run cap is $2.00 (ADR-002); ~4 runs expected.
Answer:

## Q-2 n8n version pin — blocks T6
Partly answered 2026-09-28: local target is Docker container `n8n`, image `n8nio/n8n:latest`, reporting 2.22.5.
Still needed: may we pin the local image to `n8nio/n8n:2.22.5` (so `latest` doesn't drift mid-project), and must the
online instance run the same version? Recommended: pin local to whatever the online instance reports, so the
local dry run matches the scored run. The template's typeVersions (formTrigger 2.2, httpRequest 4.2, googleSheets 4.5,
gmail 2.1, code 2) must load on it — checked in T6.
Answer:

## Q-3 May we republish the template JSON? — blocks T6
Template 16643 is a community template by `isawow`. The page states no licence that I could confirm. Options:
(a) commit `16643-original.json` verbatim with attribution; (b) commit only `DIFF.md` + a fetch script that pulls it from
`api.n8n.io` at setup; (c) ask the author. (b) keeps the repo publishable either way but adds a network step to replay.
Answer:

## Q-4 Which OWASP LLM Top 10 edition? — blocks T13 only
The brief says "(2026)". I could not confirm a 2026 edition. The 2025 edition uses LLM01 Prompt Injection,
LLM02 Sensitive Information Disclosure, LLM03 Supply Chain, LLM06 Excessive Agency. Confirm the edition and titles to cite.
Note: with the 2025 list, LLM05 Improper Output Handling (HTML in email) and LLM10 Unbounded Consumption (spend) are the
closest fits for two of our findings; the brief limits mapping to 01/02/03/06 — cite 05/10 too, or stay within four?
Answer:

## Q-6 Online target details — blocks T8
The owner will build/score on a live online n8n (ARCHITECTURE §1.1). Needed:
- n8n Cloud or self-hosted (VPS)? Plan/tier? Is the **public API** enabled with an API key (the runner needs it to
  import, activate/deactivate and read execution data; n8n Cloud trials may not include it)?
- Execution saving: are successful executions saved with data? (trace.jsonl is built from execution data.)
- How does the online instance reach the local sink? Recommended: a temporary HTTPS tunnel from this Mac
  (e.g. Cloudflare Tunnel or ngrok — owner's choice; tool install is a human step), token-protected, stopped after each run.
  Alternative: host the sink somewhere persistent (more to operate; not recommended for a one-week artifact).
- "Public artifact": does that mean only repo + findings + Loom (recommended), or should a buyer be able to submit to
  a live endpoint? The latter spends your OpenAI key on strangers and is out of this architecture.
Answer:

## Q-5 Git — blocks the first commit
This folder is not a git repository. Thin Ledger Session A says the human runs `git init`. Public remote name/visibility is a later human gate.
Answer:
