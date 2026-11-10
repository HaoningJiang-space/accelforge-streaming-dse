# Exact consumer-symmetry quotient in an order-complete fork grammar

This is a separate optimizer and execution grammar. It does not change
`graph/curve.py` defaults, earlier fixed-order predictions, or their scores.
The implementation target is `model.fork`, with homogeneous private pairs
within each literal k/i role, one producer, terminal independent consumers,
serial execution, ordinary partial-sum cost two, and unrestricted sharing.
There are no banks, layouts, consumer-specific costs, cut constraints or
additional output dependencies. Tiles use an explicitly chosen existing domain.

## 1. What the symmetry proves

Let Gamma* be the union of the original loop/partition grammar over all
permutations of independent consumers, with EX preceding every consumer.
A permutation within a role maps inputs and outputs together. If it also maps
the conditional boundary state, every legal construction maps to one of equal
capacity/traffic, and the inverse maps it back. Conditional frontiers are equal.
This extends the order-completion argument in P18_STRUCTURAL_INTERPRETATION.md
to decorated residency states; it is not a new fixed-order equivalence.

If only private-input residency varies, an m-consumer homogeneous fork has
m+1 orbits; an a/b-role fork has (a+1)(b+1). If both private input and output
residency vary, use four JOINT profiles per role:

    (input resident?, output resident?) in {00, 01, 10, 11}.

There are binomial(m+3,3) profile-count states, or
binomial(a+3,3)*binomial(b+3,3) with two roles. Separate marginal input/output
counts lose their pairing. Shared A/B/X residency, extents, producer presence,
entry, and ownership of X's final write remain explicit. This is a sufficient
signature within this grammar, not a minimal signature for general DAGs.

At an initially unretained whole-fork K split, the homogeneous obligations
are A and the m private outputs. Including A's separate bit, the local choices
shrink from 2^(m+1) to 2(m+1): 128 to 14 at m=6. With a k-role and b i-role
consumers, K lacks the k outputs and i inputs, giving 2(a+1)(b+1): 32 for
a=b=3. Later ancestors can separate consumers into more joint profiles, so
these initial-mask counts are not a bound on the entire recursive search.

Root queries with no resident private tensors already have only one decorated
order in the all-homogeneous fork. Every global order has the same curve there.
Thus improving that root's optimal value and avoiding duplicate intermediate
search are different questions. The latter is the opportunity measured here.

## 2. Why recursive canonicalization needs a different partition recurrence

Canonicalizing a state inside fixed-order `curve.py` would erase its contiguous
prefix constraints and is unsound. `graph/fork_quotient.py` instead computes
over unordered consumer sets, and returns a chosen order alongside each point.

Inductive invariant: each cached solve/group response is the Pareto union over
all consistent consumer orders of that decorated state. Its witnesses name the
actual consumers and realize one of those orders. The induction decreases
extents for loops and consumer count for nontrivial partitions.

- **Canonical state.** Sort consumers within each role by their joint residency
  profile; map their private pairs and operators together. Project unused ranks
  and ancestor-owned writes as before. Keep a reverse map for the caller.
- **Scalar leaf.** Preserve the original whole-span scalar reservation shortcut.
  Do not replace it with singleton composition.
- **Group entry.** Preserve legal common ranks and the internal-X completion
  rule. For a selected rank/tile, lacking private tensors are interchangeable
  only within the same role/profile/type class. Enumerate the number retained
  in each class; A/B/X decisions remain separate. Every labeled mask maps to a
  representative under the CURRENT boundary state's stabilizer. Invoke solve
  on the resulting canonical child and reverse-map its plan.
- **Solve entry.** Include the whole group. For a nontrivial partition, choose
  how many consumers of each current role/profile belong to the first group.
  EX belongs to that first group whenever present. The remaining consumer-only
  suffix is optimized by a memoized sequence recurrence over remaining counts.
  Every ordered partition has a representative; it is not restricted to
  contiguous subsets of a preselected order.
- **Consistent global order.** A loop adopts its child's order. A partition
  concatenates disjoint child orders. Hence each returned tree determines one
  global order obeyed by every node and every repeated iteration. Conversely,
  every plan from any globally fixed order follows these membership/loop choices.
  This establishes equality to Gamma*, without assuming arbitrary incompatible
  reordering at each recursion node is free.

Capacity composes by maximum across serial groups, traffic by sum. There is
only one potentially cross-group tensor, X. A kept X is charged once across
the whole partition; every child sees it external. A spilled X costs one read
per group after the first, plus one final write if the producer is present and
the ancestor does not already own that write. The producer child then receives
ownership. Consumer-only suffixes count each read; the first group's baseline
read is not added again. The standalone whole-group candidate never reserves
X merely to expose extra loop ranks. X can become shared only in a genuinely
nontrivial partition.

All transformations preserve parent reservation and spill charges. Comparing
bare conditional traffic without those charges is not a dominance rule.
No greedy or submodularity assumption is used. For two residency bits x,y,
the abstract costs min(4-4x,4-4y) and min(4,9-3x-3y) give retention benefits
whose marginal gains respectively decrease (4 then 0) and increase (0 then 1).
Thus the minimum-over-mappings form alone supplies neither curvature guarantee.
These are mathematical examples, not measurements or realizability claims for
this graph grammar.

### A bound on all memo contexts, including ancestor residency

For this fork implementation, let a/b be the original role multiplicities and
D the number of possible four-rank extent tuples. Every canonical state is
specified by two four-profile count vectors, whose sums are at most a and b,
plus producer presence, shared A/B/X residency, X write ownership, extent
tuple and entry (solve/group/sequence). Consequently the total number of entries
in these three response caches is bounded by

    96 D binomial(a+4,4) binomial(b+4,4).

The loose factor 96 is 3 entries × 2 producer flags × 8 shared-residency masks
× 2 ownership flags. Many combinations are unreachable. The stars-and-bars
terms allow consumers to be absent from the subproblem as well as to have any
of the four joint profiles. Fixing the root consumer counts instead gives the
smaller binomial(a+3,3) binomial(b+3,3) boundary count.

This is an upper bound on actual keys of the quotient implementation, not on
semantically necessary states. It includes accumulated ancestor residency;
there is no missing factor of 2^m hidden in that interface. For fixed shape
domains it is O(m^4) for one role, O(a^4 b^4) for two. Transition enumeration,
Pareto-frontier size, witness construction and numeric tensor extents remain
additional work; this is not a linear-runtime theorem. The growing-rank
single-operator 3^k example and Transformer stacks fall outside the constant
four-rank, two-role family. A high-degree polynomial can still be impractical
at small m, as the mixed-eight timeout illustrates.

## 3. Independent references and physical replay

`fork_order_oracle.py` calls the unchanged fixed-order solver for every literal
consumer permutation, or one representative per decorated-profile word.
For fixed boundary state with profile multiplicities n_rho, there are
m! / product(n_rho!) words. This is the stabilizer of that boundary, not an
arbitrary sort of the consumers. Thus the six-consumer mixed root has twenty
reference orders, while a homogeneous root with three pinned inputs also has
twenty. One canonical conditional state still needs an order-complete response.

Every prototype point saves its selected order and ordinary flat witness.
Nonconditional witnesses run directly in `simulate_nest.py`. To replay private
input/output conditional boundaries, add a new rank of extent two to every
nonexternal tensor, retaining the external cells across that outer loop.
For reservation A and conditional point (c,q), the independently executed
wrapper must give (A+c, A+2q). This restores excluded allocations and compulsory
transfers. It does not pretend that c is total physical SRAM or that q includes
the caller's external transfers. The executor itself is unchanged.

## 4. Bounded measurement plan (before server runs)

This is implementation validation on diagnostic controls, not a held-out P
prediction or a revised P19 score. Expected complete references and prototype
curves are exactly equal; every prototype frontier witness must replay exactly.
Do not infer equality or speedup from a timeout.

All shape extents are two, historical halving tiles. Fresh Linux workers,
hash seed zero, 60 seconds including replay, 6 GiB address space each, at most
four concurrent jobs. Record source hashes, all attempts, cache/choice counts,
elapsed time and memory. The prototype counts solve/group/sequence memo entries;
reference totals count all independently searched order cases. Profiled
reference timings and lightly counted prototype timings are not a controlled
production-speed comparison.

- Prototype root curves: homogeneous and balanced mixed forks at m=2,4,6,8;
  plus m=6 homogeneous with C0,C2,C4 pinned (nine jobs).
- Complete reference orders: homogeneous/mixed m=4 and m=6, and m=6 pinned
  homogeneous. Respectively 1,6,1,20,20 independent order jobs (48 total).
- Joint-state validation: all 64 private input/output residency assignments
  for m=3 homogeneous and kki. Compare each prototype response to all six
  literal orders; replay every returned conditional point. Record the 20/40
  predicted boundary orbit counts and actual memo reuse (two jobs).

There are 59 jobs. The m=8 prototype is a scaling control without an exhaustive
reference in this run; its physical frontier witnesses must still execute.
Small oracle agreement plus the recurrence argument does not replace a future
independent formal proof audit. General graphs and externally constrained
consumer orders remain outside this implementation.

## 5. Separate attribution control, specified after the first study

The first study combines a different partition recurrence with a symmetry
quotient. To isolate the quotient, `quotient=False` now preserves all consumer
identities, enumerates every labeled group subset and every retention mask,
while retaining the SAME all-order sequence recurrence and witness construction.
It is not the fixed-order grammar. Predicted result: enabling the quotient
changes work but not any numeric frontier.

`bench_fork_quotient.py` declares eight ablation jobs: m=4,6 homogeneous/mixed,
with/without quotient. Two fresh Linux workers maximum, 60 s and 6 GiB per job.
All complete pairs must have identical curves and exact witnesses. Incomplete
pairs provide no speed ratio or completed-state comparison.

After those jobs, six fresh processes run sequentially: three alternating
fixed-order DP / quotient pairs for homogeneous m=6. Fixed-order profiling is
disabled; prototype counters remain enabled. Homogeneous unconditional root
curves are order-invariant, so this comparison has the same optimal frontier.
Report median search time, not a factorial multiplier inferred from orbit counts.
The first study and its 60-second mixed-eight timeout are retained unchanged.
