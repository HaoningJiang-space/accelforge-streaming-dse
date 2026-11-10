# P21f: existence passes; the corrected plateau threshold fails

All 140 frozen arm jobs completed with valid source/configuration checks and
1,919/1,919 independently exact frontier replays. The plateau prediction fails
under its original criterion: each of four strata required 8/8. Existence
passes 32/32. Neither a new tolerance nor the tile diagnostic changes this score.

| Primary stratum (historical halving tiles) | Correct / valid | Verdict |
| --- | ---: | --- |
| Independent H input, K<L<2K: equal plateaus | 7/8 | fail |
| Independent H input, L>2K: strict plateau gap | 8/8 | pass |
| H reads X, K<L<2K: strict plateau gap | 8/8 | pass |
| H reads X, L>2K: strict plateau gap | 8/8 | pass |
| Some capacity benefits from separating EH0 from EX | 32/32 | pass |

Free permits every cut; tied forbids separating EX and EH0. Both optimize all
other legal choices. The results concern the existing serial grammar, not every
physically possible execution.

## The one primary counterexample

Case 2 has (I,K,L)=(6,4,6), depth 6, and an independent H input. The common
minimum traffic is 216 B. Free reaches it at 61 B, tied at 62 B. Their curves
differ at exactly one integer capacity: at C=61, free costs 216 B and tied
costs 240 B. This is a complete, valid counterexample, not a timeout or a
replay/accounting failure.

The saved plateau executions identify the peak allocation:

| Tensor | Free at (61,216) | Tied at (62,216) |
| --- | ---: | ---: |
| W0 | 24 | 24 |
| W1 | 24 | 24 |
| X | 4 | 4 |
| H1 | 4 | 4 |
| D | 4 | 0 |
| H0 | 1 | 6 |
| Total | 61 | 62 |

Both peaks already reserve W0, W1, X and H1: 56 B. The free witness adds a
D row plus scalar H0 (4+1); the tied witness adds an H0 row (6). H1 is already
reserved by their interfaces; counting it as an additional free-only K row
misstates the marginal comparison. The observed 1 B gap is L-(K+1) for this
witness pair. This is post-hoc peak attribution, **not** a replacement universal
threshold. It reinforces comparing full reservations and lifetimes, rather
than an isolated two-row sketch.

Raw witnesses and execution ledgers:
[free](results/p21f/02_halving_free.json),
[tied](results/p21f/02_halving_tied.json).

## All-divisor diagnostic (separate from the primary score)

All 19 paired diagnostic cases are valid, with the expanded tile domain never
worse for either arm independently. Whole-curve free/tied gaps behave as follows:

| Cohort | Equal in both domains | Gap removed | Gap persists | Gap introduced |
| --- | ---: | ---: | ---: | ---: |
| 16 new L<K cases | 8 | 3 | 4 | 1 |
| 3 seen P21e controls | 0 | 1 | 2 | 0 |

For example, new case 32, (2,6,4) without X reads, has equal curves under
halving but a gap at two capacities under all divisors. Enlarging both search
spaces can improve their optima by different amounts; it need not close their
difference. Some persistent cases have identical tile domains already, including
(2,16,4). Thus tile omission explains some gaps, not all of them. All seen
halving controls reproduce their archived P21e curves.

## Reproduction and provenance

- Frozen source: `b230162ec19688b5343576d10b526e93dc323aa4` in a detached shallow
  checkout. No solver, runner, scorer or manifest source was changed for the run.
- Manifest SHA256:
  `d5117f4e4f82f4a0b0ea3a068a6067cbc8b0d955ecccbae472d470cafc5584b7`.
- Fresh Linux processes, Python 3.10.12, hash seed 0, at most four concurrent
  arms, 1,800 s and 8 GiB address space per arm. No retried or missing arms.
- Sum of per-arm elapsed search/replay times: 69.648 s; longest arm: 1.299 s.
  This sum is neither CPU time nor total deployment elapsed time.
- Nine P21f unit tests passed locally and on the experiment machine before
  execution. The scorer exits 1 because the scientific plateau prediction
  failed; all jobs and paired validity checks succeeded.
- [All records](results/p21f/), [score](results/p21f/score.json),
  [provenance and record hashes](results/p21f/provenance.json).

Run the unchanged scorer from the repository root:

```sh
python3 -m research.index_coupling.score_p21f research/index_coupling/results/p21f
```

The frozen protocol and its required scores remain unchanged. This closes P21f;
the next interface theorem must account for full conditional occupancy, and
cannot assume that changing K to 2K settles the plateau decision.
