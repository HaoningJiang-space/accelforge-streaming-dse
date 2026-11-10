# Independent review of the 4/5 threshold

Reviewed `CHAIN_THRESHOLD.md` and `check_chain_threshold.py` at `c0848e61`.
The dense-chain lower bound survives this review under its stated incidence,
final-read, unit-row and nonresident-activation assumptions. A direct proof
below closes the predecessor case without relying on time reversal. The 4/5
rule is exact for the specified multi-layer binary FFN family. It is not a
general formula for every shape or every execution interface.

This audit is independent of the integration branch. The original bound,
solver, executor and their archives are unchanged. All measurements below are
retrospective checks, not new frozen predictions.

## 1. Close the predecessor lemma in forward time

Keep the notation of the original proof: c_j maps a_j input elements to
a_{j+1} outputs; s_j is one for a nonresident weight and zero otherwise.
alpha_j is the first dense output completion, and beta_j is the first input's
last use. Count cells during the multiply-add, before last-use releases.

The original Lemma 3 invokes time reversal to exchange alpha and beta. That
sentence is insufficient by itself: reversing a schedule also exchanges first
and last events. It does not directly establish the hypotheses of Lemma 2 for
the named first events. The claimed inequality has the following direct proof.

Assume beta_j <= alpha_j and a predecessor exists. At beta_j every output of
c_j has started and is live: the dying input has contributed to each output,
and none could have completed earlier than alpha_j. Let delta be the first
contribution to the *last-started* element of V_j, produced by c_{j-1}.

- If delta < beta_j, every V_j element has started and none has died before
  beta_j. At the step beta_j, both complete vectors occupy cells, together
  with the current weight element if nonresident. Peak >= a_j+a_{j+1}+s_j.
- If delta > beta_j, some V_j element has not started at beta_j. The input
  dying at beta_j was already final, so density of c_{j-1} implies every
  V_{j-1} element has been produced/loaded. None can die before delta, since
  each still owes a contribution to the last-started V_j element. Meanwhile
  no V_{j+1} element can finish before that V_j element becomes final. Thus
  at delta all V_{j-1} and V_{j+1} elements are live, along with the newly
  started V_j element and the predecessor's weight element. Peak is at least
  a_{j-1}+a_{j+1}+1+s_{j-1}.

The two events belong to different operators, so equality of their step times
does not arise. Taking the minimum proves the original Lemma 3. Unary
out-of-place chains between contractions remain valid logical channels: an
element is represented by at least one cell from its first dense contribution
through its final downstream use. The argument never counts a resident
activation as free; such states remain outside this theorem's scope.

## 2. Exact result for the binary FFN family

For `ffn_stack(L,m=1,d=2,f=2)`, L >= 2, let K contain only resident weights.
Under the documented zero-extra, final-read, no-recomputation semantics,

    Z(K) = 4 + 1[an interior contraction's weight is absent from K].

Here the two boundary weights are W1_0 and W2_(L-1). Z excludes the caller's
resident-weight reservation. This equality holds for both the unrestricted
dependency-legal scalar schedules and the v2 loop grammar in this family.

**Lower bound.** The chain has 2L dense contractions. At least one is interior.
All a_j=2, so each interior L_j=4+s_j and each boundary L_j=3+s_j. Their maximum
is precisely the expression above. The corrected predecessor proof and the
successor proof give the bound for all legal scalar schedules.

**Construction in the grammar.** Partition into singleton operators and keep
every intermediate vector across its producer/consumer cut. Interior matmuls
hold the input and output vectors (2+2); a missing private weight streams one
cell at a time, adding one. A resident weight adds no local storage. Copies
hold two vectors, costing 4. At the first matmul, reduce D0 to one cell and
retain that boundary input cell across F0; its peak is at most 2+1+1=4. At the
last matmul, slice the terminal output first and keep its one partial sum
through the reduction; again the peak is at most 4. Every weight/input cell is
loaded once, no intermediate is spilled and final outputs are written once.
This attains the lower bound within v2.

The statement is about unit cells (unit bytes in the toy accounting). It is
not an application of the all-scalar MaxLive theorem to non-scalar states.

## 3. Independent scheduling oracle and the one-layer exception

`audit_chain_schedule.py` enumerates every dependency-legal scalar step order
for bounded cases. For a fixed order, load inputs just before their first use,
allocate results at their first contribution, and release a value immediately
after its last use/final write. Any zero-extra schedule can use these timings
without increasing its peak. Thus the completed-step bit mask determines the
minimum live set; a min/max recurrence over ready steps finds the exact peak.
It neither imports the loop grammar's recurrence nor restricts operator
interleaving. Each selected schedule is replayed with `simulate_nest.Machine`,
with resident weights explicitly allocated and loaded in a pinned outer frame.

| Family | Residency cases | Chain bound = schedule optimum | Schedule optimum = v2 plateau |
|---|---:|---:|---:|
| One-layer binary FFN | 4 | 4 | 3 |
| Two-layer binary FFN | 16 | 16 | 16 |

The sole difference has **both one-layer weights resident**. The chain bound
and schedule optimum are 3; the v2 plateau is 4. The schedule executes all
EH0 steps, then all EZ0 steps, then all EY0 steps. No operator reordering is
needed. During the copy, each H element is released after its corresponding Z
element is created. At most three activation cells coexist. V2's whole-vector
cut reservations keep both H and Z allocated through the copy, requiring four.

The physical replay reserves 8 weight cells plus 3 free cells: peak 11, with
10 input reads (including 8 weight reads), 2 output writes and no partial-sum
transfers. This demonstrates a grammar-versus-lifetime gap without changing
the grammar or claiming that the schedule is a representable v2 witness.

The original document's statement that the bound is attained throughout the
uniform family therefore needs the L >= 2 qualification; its later table
already reports the one-layer gaps. Separately, all 340 archived root M-loop
subsets across depths 1,2,3,4 reproduce the **grammar** formula 4/5. Those
archive checks are distinct from the 20 schedule-oracle checks.

## 4. Two guards against overgeneralization

**Rectangular extents.** For the all-resident one-layer state M=1,D=4,F=8,
the exact v2 plateau is 10. A framed witness executes with that free capacity.
Holding both H and Z whole would count 16. Thus the original whole-vector
count B(o) is not a general lower bound. A common F loop can retain the two
outer vectors (4+4) while processing the H/Z pair with two scalar cells. This
does not contradict the chain lower bound, which is more conservative.

**Dense incidence must be checked.** The current checker was exercised only
on registered FFN/attention graphs. Its public `chain_bound(graph,state)`
function does not independently verify that a contraction is dense. On

    Y[M,I] = X[M,I] * W[I],  M=1, I=2,

it returns 4, while the exact zero-extra curve is (capacity 3, traffic 6).
This is a pointwise multiplication outside the theorem's domain, not a
counterexample to the dense-chain theorem or the archived results. Before
using the function as a general pruning certificate, require distinct input
and output feature ranks, a weight carrying both ranks, compatible unary
channel projections, positive extents, and the declared residency contract.
Operand counts alone do not establish density.

## 5. Evidence and next use

- All 20 independent optimum schedules replay exactly; the rectangular framed
  witness adds one more replay. These are 21 new checks, separately counted
  from the old v2 and C2 archives.
- 340 binary archive subsets agree; their raw digests are recorded.
- Source hashes and every selected scalar schedule are in
  [chain.json](results/independent_contract_audit/chain.json).
- Seven combined audit controls cover the scheduling and mapping-interface
  checks. No lower-bound optimization is installed in the solver.

The existing post-hoc clipping result in CHAIN_THRESHOLD.md remains pertinent:
an endpoint theorem only forces positive traffic below the endpoint, and the
one-element floor added no ideal exclusions. The next useful certificate must
quantify positive traffic or tighten a boundary contract; a correct endpoint
alone does not establish useful pruning coverage.

```sh
python3 -m research.index_coupling.audit_chain_schedule --out NEW_CHAIN_AUDIT.json
PYTHONHASHSEED=0 python3 -m unittest research.index_coupling.test_independent_contract_audit
```
