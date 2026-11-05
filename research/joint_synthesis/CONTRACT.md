# First composition gate: architecture-independent 2mm physical plans

Status: the restricted grammar, analytical rules, separator DP, independent
scalar Oracle and normalized-budget hardware binding are executable. See
`ARCHITECTURE_CONTRACT.md` for the latter. General Fusion, calibrated hardware
synthesis and strong-system baselines remain open.

This is a **restricted proof/Oracle gate**, not a completed new optimizer or a
novelty claim. Native FFM remains an untouched reference. The new grammar and
DP must import neither its candidate generator nor its Join/search routines.

## 0. Program, grammar and model

The graph is `X=A·B; Y=X·W`, with A[M,K], B[K,N], W[N,P]. `MatMul.precision`
explicitly distinguishes `operand_dtype`, `accumulator_dtype`, `output_dtype`
and `overflow`. This grammar requires all three to be the same signed integer
byte width, with **checked overflow after every MAC**, not wraparound,
saturation or an unbounded hidden accumulator. The 2mm generator uses 16 bits.
All initialized values and all intermediate writes must fit, not only final
results. For example `32767*2 + (-32767)*2` is rejected even though its final
mathematical result is zero. A request for a wider accumulator is explicitly
unsupported until its storage/access and cost rules are modeled independently.
Resource dominance is conditional on this common numerical contract; these
bounded-input checks do not prove numerical validity for arbitrary input data.
The model has one shared SRAM, DRAM, a rectangular PE array and nonoverlapping
DMA/compute service. It has no aliasing, recomputation, parallel stages, leakage,
NoC or calibrated area model. Positive bandwidth is a performance parameter, not
a feasibility threshold unless a deadline is separately imposed.
SRAM is an ideal byte-capacity pool: simultaneous owned-copy sizes determine
occupancy. Fragmentation, bank/address assignment and physical relocation cost
are not modeled. Packed addresses in the Oracle are relative to each copy;
this is not a global SRAM placement or allocator feasibility proof.

Each local implementation chooses divisor tiles (ti,tj,tk), an output-stationary
`i,j,k`, row-strip `i,k,j`, or column-strip `j,k,i` order, and spatial dimensions
(ti,tj). The strip orders retain a larger output working set to reuse an input
tile. Input/output properties choose a complete tensor's row/column-major layout
and SRAM/DRAM location. The final output is row-major DRAM. All options are
generated **without a hardware point/list**; hard resource demands are outputs.

The first graph cut is a complete materialization barrier. A SRAM-backed X is
kept until the consumer finishes; its storage may be borrowed but never silently
released or double-allocated. A DRAM-backed X is loaded by consumer tiles.
Streaming Fusion is **outside this grammar**, not rejected as physically invalid.
Any later streaming grammar requires its own live-channel/accumulator interface
and proof. This gate cannot establish a compact interface for general FFM Fusion.

Primitive service is deliberately simple and exact. Each MAC has unit compute
energy; SRAM/DRAM accesses have declared fixed integer energy per byte. Compute
cycles count spatial waves. Each DRAM transfer has a setup cost per contiguous
physical address run and fluid service `bytes/B`, with no compute/DMA overlap.
Thus each plan has `T(B)=c+q/B`, c,q nonnegative integers. This is not a
cycle-accurate bandwidth or FFM energy model. No performance comparison to FFM
is valid until grammar and cost-model differences are reconciled.

## 1. Sufficient interface and state

Within one fixed graph/cut, the materialized interface I records logical
tensor/version, full shape, element width, physical layout and storage location.
Exclusive ownership is a fixed grammar invariant, not a per-state choice.
Copies have distinct identities in the execution trace. There is no hidden
live tensor at this cut; A/B temporaries are dead and Y is not yet allocated.
Internal tile views refer to a known owner; they do not allocate duplicate copies.
The interpreter validates the whole View extent against its live owner and each
access against the View's local coordinates. Allocation validates positive
integer shape, location/layout and the exact rectangular initial data and its
signed precision before changing IDs or occupancy. Host initialization does not
count as an executed memory action. Uninitialized reads and dangling owners are
errors. A failed execution is rejected, not a partially valid cost observation;
the Runtime is not a transactional simulator after a failed MAC or copy.
Conversion checks actual source shape, width, location/layout and a live Copy ID
even on an identity edge. A MAC output cannot share an allocation with either
input, including disjoint views of one owner; in-place MACs need a separate rule.
Unknown/unsupported aliasing, partial production or concurrency is an error,
not zero occupancy or an equivalent interface.

A prefix summary is `(I, u, v, P, L, E, c, q, Plan)`:

- u,v: required spatial extents, not just a total PE count;
- P: absolute SRAM peak during the prefix, including retained output;
- L: SRAM bytes still live at its output interface (fixed by I);
- E,c,q: exact integer energy and latency coefficients;
- Plan: reconstruction provenance, not a dominance dimension.

A consumer alternative requires interface J and summarizes its **scratch** peak
S, excluding the borrowed full SRAM input L_J. It cannot free that borrowed
input early. Its tile/strip accumulators and nonborrowed operand copies are
included in S. Required properties and delivered properties are distinct.

## 2. Explicit conversions

For every ordered I→J, matching logical tensor/version/shape/width is mandatory.
Identical physical properties use an identity conversion. Other pairs use an
explicit row-ordered logical copy; SRAM destinations allocate a new full copy
before the source is released. A DRAM→DRAM layout change uses a full SRAM staging
copy. This is one declared finite converter grammar, not an optimal converter
library. It may be expanded only with new execution/summary checks.

Conversion K has absolute cut peak P_K (all source/destination/staging copies),
energy E_K and latency coefficients c_K,q_K. On exit only J remains live.
Conversions are not free merely because logical tensor names agree.

## 3. Composition law

For p delivering I, K converting I→J, and consumer r requiring J:

\[
u=\max(u_p,u_r),\quad v=\max(v_p,v_r),
\]
\[
P=\max(P_p,P_K,L_J+S_r),
\]
\[
(E,c,q)=(E_p,c_p,q_p)+(E_K,c_K,q_K)+(E_r,c_r,q_r).
\]

Hardware feasibility is `Px≥u, Py≥v, C≥P`; latency is `c+q/B` for any B>0.
No architecture is independently chosen per operator. For example sequential
demands (2,4) and (4,2) require (4,4); max(total PE)=8 would incorrectly admit
either 2×4 or 4×2. SRAM requirements are neither blindly summed nor represented
by a context-free scalar max.

Equivalently the prefix resource response to future scratch x is
`F_p(x)=max(P_p,L_I+x)`. Equal peak alone does not imply equal response:
SRAM-resident X and DRAM-backed X can have different L and different future
transfer costs. SRAM→SRAM relayout can temporarily require two full X copies,
even if both endpoint footprints fit individually.

## 4. Safe local dominance

Only compare prefixes at the **same graph/cut with identical complete I**. A sufficient condition for
replacing q by p is componentwise nonincrease of `(u,v,P,E,c,q_bytes)`.
L is identical because I is identical. The consumer analogue compares identical
required J and `(u,v,S,E,c,q_bytes)`.

Proof: every continuation admitted by the removed plan is also admitted by the
replacement's identical I/J. Conversion choice/cost is unchanged. Componentwise
max and addition are monotone; for every B>0, smaller c and q_bytes give no larger
latency. Thus complete energy, latency and resource demand cannot worsen on any
hardware that could execute the removed plan. Equal vectors may retain one
witness; all numerical Pareto vectors are preserved, not every tied source.

This is a sufficient relation, not the exact order of all latency functions.
It does not permit comparisons across interfaces, arbitrary reassociation,
concurrent resource reuse, or moving this rule into native FFM fallback cohorts.
It is a project-specific restricted theorem, not a novel general DP theorem.

Local minimum EDP is insufficient: (E,T)=(1,10) wins over (4,3), but after adding
a suffix (100,0), the complete EDPs are 1010 and 312. Keep the conditional
frontier, not a scalar local winner.

## 5. Independent executable validation

The implemented summaries use closed-form tile/strip transfer and resource counts.
The independent Oracle enumerates the complete finite grammar without DP pruning and runs
explicit allocations, physical-layout reads/writes, scalar MACs and releases.
It computes global occupancy from simultaneously live copies, counts actual
DRAM address runs, checks numeric Y against plain scalar matrix multiplication,
and never calls the summary/composition routines to obtain a cost or peak.

Validate all local summary coordinates against traces, every complete pairing
and conversion against composed demands, and the DP's complete demand frontier
against exhaustive trace results. Only afterwards may a validation grid query
both sets at (Px,Py,C,B). That grid is not an input to local generation or DP.
All checks use integers/Fractions, not relaxed floating comparisons.

Record raw versus retained local states per interface, materialized pair counts,
root frontier size, runtime and source witnesses. The test of this first gate
is correctness and whether any safe pruning exists **in this grammar**. It does
not establish fast realistic synthesis, a general separator-width bound or a
performance advantage over existing accelerator co-design systems.

## Related mechanisms and scope

[Cascades](https://15799.courses.cs.cmu.edu/spring2025/papers/05-cascades/graefe-ieee1995.pdf)
motivates required/delivered properties and explicit enforcers. [Alpa §4–5](https://www.usenix.org/system/files/osdi22-zheng-lianmin.pdf)
exchanges local parallelization cost/resource information with global planning
and accounts for resharding; it does not validate this SRAM-lifetime law.
[Orojenesis / Mind the Gap](https://people.csail.mit.edu/emer/media/papers/2024.06.isca.orojenesis.pdf)
studies attainable movement/capacity bounds, which are distinct from this concrete
schedule cost. [FAQ](https://arxiv.org/pdf/1504.04044v7) requires legal aggregation
and ordering rules; writing a graph does not supply them.
[SENNA](https://doi.org/10.1145/3705731) already explores a unified hardware/software
space, so architecture–mapping joint selection itself is not a novelty claim.

The strong FFM/Cache/Event results remain in `research/joint_search`. They use a
different execution grammar/model and cannot be directly ranked by EDP or speed
against this proof gate. General Fusion, realistic model alignment, synthesis
under calibrated budgets, 3mm/GLU scalability and strong performance baselines
remain uncompleted roadmap steps.
