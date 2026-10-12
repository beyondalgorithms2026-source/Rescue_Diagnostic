Changed: `workflows/hardened/t2-hardened.json`, `workflows/hardened/t2-error-handler.json`, `tests/test_hardened.py`, `.ai/HANDOFF.md`, `.ai/STATUS.md`, `.ai/REVIEW.md`.
Did: T10 is in progress. H8–H16 exist. Six T9 defects are fixed. T10 is not ticked.
Did-not: T11, the runner, `docs/DECISIONS.md`, the baseline files, and the gold files.
Check: 45 unit tests passed. Strict static checks passed on both hardened files. The live drill stops at `H1 PDF SHA-256`.
Risk: the error workflow did not run on an unhandled error. The DeepSeek key in `.env` is a placeholder.
Next: T10 (finish), then T11.
```mermaid
flowchart LR
  H1[H1 intake] --> Hash[H1 SHA-256: fails]
  Hash --> H6[H6 DeepSeek]
  H6 --> H8[H8 schema + foot]
  H8 --> H10{H10 decide}
  H10 --> H11[H11 dedupe] --> H12[H12 lines] --> H13[H13 header] --> H14[H14 report]
  H10 --> H15[H15 review]
  H14 --> H16[H16 audit]
  H15 --> H16
```
