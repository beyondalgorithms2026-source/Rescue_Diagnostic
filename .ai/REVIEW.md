Changed: `src/sink/`, `tests/test_sink.py`, `.env.example`, `specs/t2-rescue/tasks.md`, `.ai/HANDOFF.md`, `.ai/STATUS.md`, `.ai/REVIEW.md`.
Did: T5 added the append-only local HTTP sink and ticked T5.
Did-not: T6, `docs/DECISIONS.md`, and the existing `.ai/QUESTIONS.md` change.
Check: 17 unit tests passed; compileall passed; secret grep found only test literals; `main`, `v0.3.0`, and `t5-sink` pushed.
Risk: T1 scorer does not read the required `replay_input_id` sink stamp before T8.
Next: T6.
```mermaid
flowchart LR
n8n --> HTTP --> Auth --> CSV
Replay --> Active --> CSV
```
