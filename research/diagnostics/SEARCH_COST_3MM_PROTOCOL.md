# Native 3mm search-cost diagnosis: frozen protocol

Case: native NVDLA `matmuls(3,256,256)`, shapes 16×384 / 32×192 / 64×96,
GB 131,072 / 135,168 bytes, fixed 8-bit Register, stock 8-bit workload and fixed
bandwidth/clock. No synthesis core or native search implementation is modified.

## Contract groups

| Group | Methods | Required equality |
| --- | --- | --- |
| EL | independent FFM; existing EnumerationReuse | Complete returned E/T numerical frontier at all six points |
| EL + Resource Usage | independent FFM; EnumerationReuse; existing capacity Event + bitset + cache | Complete returned E/T/exact-resource numerical frontier at all six points |

The Event API requires RESOURCE_USAGE. EL and RU may keep different candidates
because resource goals participate in prefix selection; their times or frontiers
must not be combined into a same-contract speedup. The original causal witness
was EL. RU is a separate matched group, not a replacement for that reference.

Capacity Events use the existing native two-capacity enumeration within each
shape, with exact integer bit targets. No largest-capacity winner filtering is
substituted for target policy membership. The single-template Region Compiler
does not implement 3mm Fusion, and the frozen shared-architecture adapter accepts
only 2mm/dyadic extents. Neither is presented as an available baseline here.

## Timing and correctness

Three fresh processes per method, alternating forward/reverse method order,
run serially. One worker and requested single-thread NumPy/Numba/BLAS environment
settings. Each process performs a cold complete search then a warm complete
search. Every search has fresh candidates and a new explicit reuse scope; only
generic interpreter/JIT/formula caches can survive. Imports/startup are outside
timers; spec construction, generation, Join, queries and scope teardown are inside.

Cold/warm and repeated numerical fronts must agree. Methods are compared only
inside their contract group. Distinct source identities can tie; selected EDP
sources are reconstructed and re-evaluated on all six actual targets outside
timing. Equality covers numerical returned frontiers, not every physical mapping
or global optimality of the FFM heuristic. No real-chip area conclusion follows.

In repeat 1 only, a separate warmed search records phase times and actual work.
Inclusive phases nest; exclusive remainders subtract instrumented children and
can be added. Remainders can contain uninstrumented helpers. Numeric Join timing
includes a nested reservation/Pareto pipeline; do not add its inclusive time to
those children. Instrumented timings do not replace uninstrumented wall times.

The cached RU and Event RU processes also run an untimed heavy repetition pass.
It must produce the same frontier. That pass's hashing, retained key payload and
memory use are excluded from timing/RSS comparisons. A separate untimed filter
audit can count actual capacity/Pareto row rejections against the same snapshots.

## Repetition identities and limits

- Prefix and formula identities use actual native cache-key equality, including
  exact numeric dtype/content and Symbol assumptions. Requests/hits are separated
  from actual computations. Retained prefix-key payload is bounded; unclassified
  requests are reported rather than silently treated as unique or reusable.
- Physical-model observations compare the symbolic DF and template structure
  after excluding capacity metadata. They do not include separately returned
  hardware-normalized usage constraints. Equal outputs are discovered **after**
  analysis, not a proven pre-analysis lookup key or a reusable whole Job.
- Resource-program keys include observed compatibility/context and native GB
  column operations, allocation/free descriptors. Resource-input keys also retain
  ordered resource/tensor/matching subframes and dtypes. Row weights count actual
  pre-membership matched pairs, not post-Pareto result rows.

Those resource keys omit costs, Pareto history and membership state and are
**not future-equivalence certificates**. Equal programs with different inputs
are not repeated numerical work. Even identical resource subcalculations do not
prove two complete states can be merged or that earlier pruning is safe. Actual
post-materialization rejection counts are opportunities to investigate, not a
claim that a new algorithm can avoid all of them.

## Reproduce

```sh
python -m research.diagnostics.profile_3mm_search --repeats 3 --output research/diagnostics/results/search_cost_3mm
```

`progress.json` is explicitly incomplete until `summary.json` is complete.
Per-trial JSON and logs, source fingerprints, phase counts and variance are
retained. Results should decide whether a resource-transfer search mechanism is
worth designing; this protocol does not assume the answer is positive.
