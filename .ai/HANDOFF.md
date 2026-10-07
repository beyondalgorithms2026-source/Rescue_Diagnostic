# Current handoff
Task: T8 complete — local repaired baseline run and baseline-only scorecard.
Branch: main
Done: As-published evidence is execution 447, which stops at node 2 with no sink delivery or OpenAI request. Repaired run `baseline-local-20261007T060333Z-nogit` reached node 3 on all 100 ordered A/B submissions. `evals/scorecard.csv` has 50 baseline rows from that run only. R-2 serializes the complete node-3 request after joining extracted PDF text to the unchanged user prompt. The workflow is unpublished after every replay.
Tests / checks run: `python3 -m unittest discover -s tests -t . -v` — 29 tests OK. `compileall` OK. Secret grep found only known scanner and test literals.
Next task: A human reads at least 15 repaired traces and writes trace notes, then T9.
Read first: AGENTS.md; `.ai/QUESTIONS.md` Q-1, Q-6, Q-7; `docs/ARCHITECTURE.md` §1.1, §4, §5.4–5.5; `specs/t2-rescue/plan.md` §T8; `workflows/baseline/DIFF.md`; `src/replay/run.py`.
T8 note: The scorecard has baseline rows only until T11 adds the hardened phase.
Open risk: Node 9, recipient, currency, and lookup findings remain intentionally unfixed.
