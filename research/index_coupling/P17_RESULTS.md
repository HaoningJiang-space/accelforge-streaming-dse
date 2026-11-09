# P17: completed output and its interpretation

The archived output contains 95 unique shapes, exactly the set declared by
`run_p17.shapes()`: 64 development shapes and 31 held-out shapes. There are
no missing, additional or duplicated shapes.

| Frozen prediction | Observed result |
| --- | --- |
| P17: same/cross numerical curves equal with spill_cost=1 | 95/95 |
| P17-control: curves differ with spill_cost=2 | 95/95 |

This is an audit of an already completed run, not a rerun. The error log was
empty at inspection. The output stores equality decisions, not the full curves.

[Raw output](results/p17/observed.jsonl) ·
[Audit metadata](results/p17/audit.json)

The raw file SHA-256 is
`66f238aac732c008af301aa2db2e1a0e0c25e6be36673dd240df3eb814d7aefb`.
The inspected source checkout was at `0e47637e`, which contains the frozen
prediction and runner. The output does not embed a launch revision, so the
observed checkout is not independently verified proof of the run's source pin.

[The role-symmetry derivation](ROLE_SYMMETRY_AND_SYSTEMS_CASE.md) supplies a
structural explanation: swapping the terminal D/V roles pairs recursive
constructions when extra input and output revisits have equal charges. The
proof was committed at `f237e031` before this output was inspected. It applies
to arbitrary shapes within the stated recursive model; the non-square extension
has not been counted as an experimental result.

P17 supports the implementation's predicted role-neutral symmetry. It does not
prove cross is always worse at ordinary transfer costs, validate a physical
DRAM-side accumulation engine, or establish a lower bound over all executions.
