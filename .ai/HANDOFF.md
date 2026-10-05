# Current handoff
Task: T3 complete — deterministic PDF writer and clean/messy synthetic fixture generator.
Branch: main
Last commit: T2 static checks (`5399b34`); T3 changes are pending the focused commit.
Done: `src/fixtures/pdfwriter.py` writes deterministic text-only PDF 1.4 files with Helvetica and the required footer. `src/fixtures/make_inputs.py` writes the first 14 clean and 12 messy invoices from saved gold JSON, plus the frozen manifest format. The generator uses `src/common/norm.py` for dedupe keys.
Tests / checks run: `python3 -m unittest discover -s tests -t . -v` — 13 tests passed; `PYTHONPYCACHEPREFIX=/private/tmp/t3-pycache python3 -m compileall -q src tests` — passed; required secret grep — clean. `pdfinfo` read a generated PDF as one Letter-size page.
Next task: T4 — extend the generator to the remaining 24 inputs and test all 50 PDFs and gold records.
Read first: AGENTS.md; `.ai/STATUS.md`; `docs/DECISIONS.md`; `docs/ARCHITECTURE.md`; `specs/t2-rescue/tasks.md`; `specs/t2-rescue/plan.md` §T4.
Do not change: architecture contracts, docs/DECISIONS.md, or tasks beyond the T4 checkbox.
Open questions: n8n Extract From File smoke test waits until T6.
Targets: local only; T3 did not call n8n or APIs.
