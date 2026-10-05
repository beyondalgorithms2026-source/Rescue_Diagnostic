# Open questions (decisions the architecture session refused to invent)

Answer inline, date it, and move the answer into ARCHITECTURE/README as the task needs.

## Q-1 OpenAI model, prices, and total budget — blocks T8
The template uses `gpt-4o-mini` via `api.openai.com`. Needed from the owner:
- Is `gpt-4o-mini` still served on your account (Sep 2026)? If not, which model replaces it for **both** phases (the baseline must stay as published except §2.3; a model swap is a baseline change and must be disclosed)? 
- Current per-million-token input/output prices for that model → `LLM_PRICE_IN_PER_MTOK`, `LLM_PRICE_OUT_PER_MTOK`. Not guessed... 
- Total project spend ceiling. Default per-run cap is $2.00 (ADR-002); ~4 runs expected. 
Answer (2026-10-05):
- Model for both phases: gpt-4o-mini-2024-07-18. A later swap is a baseline change and must be disclosed.
- LLM_PRICE_IN_PER_MTOK=0.15, LLM_PRICE_OUT_PER_MTOK=0.60. These go in the Config node, not in workflow code.
- Owner override of ADR-002: per-run cap is $0.25, not $2.00. About 4 runs, so the project ceiling is $1. Do not raise the cap without asking.
## Q-2 n8n version pin — blocks T6
Partly answered 2026-09-28: local target is Docker container `n8n`, image `n8nio/n8n:latest`, reporting 2.22.5.
Still needed: may we pin the local image to `n8nio/n8n:2.22.5` (so `latest` doesn't drift mid-project), and must the
online instance run the same version? Recommended: pin local to whatever the online instance reports, so the
local dry run matches the scored run. The template's typeVersions (formTrigger 2.2, httpRequest 4.2, googleSheets 4.5,
gmail 2.1, code 2) must load on it — checked in T6.

Answer (2026-10-05): Pin the local image to n8nio/n8n:2.22.5. Do not leave it on latest. There is no online instance (see Q-6), so there is no second version to match. T6 checks that the template typeVersions load on 2.22.5.

## Q-3 May we republish the template JSON? — blocks T6
Template 16643 is a community template by `isawow`. The page states no licence that I could confirm. Options:
(a) commit `16643-original.json` verbatim with attribution; (b) commit only `DIFF.md` + a fetch script that pulls it from
`api.n8n.io` at setup; (c) ask the author. (b) keeps the repo publishable either way but adds a network step to replay.
Answer:

Decision: baseline is template 16643, used on our own n8n instance only.
- Import and run it locally. No grant from isaWOW is required for that.
- Do not commit their workflow JSON, and do not present it as ours.
- Repo contains: attribution, the n8n.io URL, a fetch script, and a documented diff of our node swaps.
- Hardened workflow JSON, scorer, scorecard, and findings are ours and may be committed.
- Public artifact is repo + findings + Loom. No public submission endpoint.
- If the URL 404s, stop and ask. Do not swap templates.

Attribution line for README: "Baseline is n8n community template 16643, 'Extract and validate invoice PDFs with OpenAI, Google Sheets, and Gmail' by isaWOW (https://n8n.io/workflows/16643-extract-and-validate-invoice-pdfs-with-openai-google-sheets-and-gmail/), marked Use for free. No republish licence was stated, so the upstream JSON is not vendored."

## Q-4 Which OWASP LLM Top 10 edition? — blocks T13 only
The brief says "(2026)". I could not confirm a 2026 edition. The 2025 edition uses LLM01 Prompt Injection,
LLM02 Sensitive Information Disclosure, LLM03 Supply Chain, LLM06 Excessive Agency. Confirm the edition and titles to cite.
Note: with the 2025 list, LLM05 Improper Output Handling (HTML in email) and LLM10 Unbounded Consumption (spend) are the
closest fits for two of our findings; the brief limits mapping to 01/02/03/06 — cite 05/10 too, or stay within four?
Answer:
A 2026 edition does exist (published Aug 2026). Cite the four you named, with 2026 names: LLM01 Prompt Injection, LLM02 Sensitive Information Disclosure, LLM03 Excessive Agency, LLM06 Unbounded Consumption. Optional one-liner on LLM10 Improper Output Handling for the “email HTML the submitter controls” bug. Do not expand the findings into all ten.

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
Q-6 answer (2026-10-05): local only. No online target for this artifact.

Decision:
- Build, baseline, harden, and score on the local Docker n8n already on this machine (2.22.5, pin that tag). Do not use n8n Cloud and do not stand up a VPS for T8.
- Public API key: not required. The runner talks to the local instance only. Do not enable a public API for this POC.
- Execution data: turn on saving successful executions with data on the local instance, so trace.jsonl can be built from execution data. If a run is missing data, the runner records audit_gap rather than inventing a trace.
- Tunnel / local sink: not used. The sink stays on localhost. No Cloudflare Tunnel, no ngrok, no hostname in git.
- Public artifact means repo + findings.md + Loom only. A buyer must not be able to submit to a live endpoint. That would spend the OpenAI key on strangers and is out of scope.
- Codex never sees a cloud URL, webhook URL, tunnel URL, or token. If a later human records one cloud replay for the Loom, that run is not the committed scorecard.

Unblocks T8 against local. Do not add an online target to tasks.md.

## Q-5 Git — blocks the first commit
This folder is not a git repository. Thin Ledger Session A says the human runs `git init`. Public remote name/visibility is a later human gate.
Answer (2026-10-05): git init done by hand. No public remote yet.
