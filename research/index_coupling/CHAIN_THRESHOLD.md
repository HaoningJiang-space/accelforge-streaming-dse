# A zero-traffic capacity lower bound for chains of dense contractions

This proves the mechanism observed in ZERO_TRAFFIC_THRESHOLD.md. The argument
is a liveness argument in the style of the red-blue pebble game (Hong and
Kung, 1981). It applies to every schedule of the serial, no-recomputation
execution model that the cell-level executor accepts. It does not depend on
the loop grammar, so it holds in v1 and v2 alike.

## 1. Setting

A span S is executed serially, without recomputation. Each cell holds one
element. Partial sums are final only after their last contribution, and an
operand is used only when final (the executor rejects nonfinal reads).

*Zero extra traffic* means:

- every element of a span input or a nonresident weight is loaded once;
- every span output is written once, when final;
- no intermediate or partial sum leaves the chip.

A live element therefore occupies a cell over its whole live interval:

- an input element from its load to its last use;
- a produced element from its first contribution to its last use (or its
  write, if it is a span output).

Resident (external) tensors occupy no span cells.

**Chain.** The span's operators form a chain of *vectors* V_0, V_1, ..., V_m
and *contractions* c_0, ..., c_{m-1}, where c_j maps V_j to V_{j+1}.

- c_j is **dense**: every element of V_{j+1} receives a contribution from
  every element of V_j through one element of a weight W_j.
- Elementwise operators (for example H → Z) may sit between contractions. A
  vector element then means the whole elementwise chain H[f] → Z[f]. It is
  live from the first contribution to H[f] until the last use of Z[f], and
  needs at least one cell throughout.
- Sizes are taken at the current extents: a_j = |V_j|.
- s_j = 1 if W_j is nonresident, else 0.

c_j has a **predecessor** if V_j is produced by c_{j-1} inside S, and a
**successor** if V_{j+1} is consumed by c_{j+1} inside S. A vector at the
span boundary is loaded or written once.

For the tiny FFN and attention stacks this applies to any span with a unit
M extent: rows are then single vectors, and each contraction is dense over
its contracted rank at the current extents. With M > 1, different rows are
independent and density fails.

## 2. Two first events per contraction

For contraction c_j, define:

- α_j: the time of the multiply-add that completes the first element of
  V_{j+1};
- β_j: the time of the multiply-add that is the last use of the first element
  of V_j to die.

Each event is a single step, and the step itself needs its operands in cells.

**Lemma 1 (one whole vector).**

- If α_j < β_j, then at time α_j every element of V_j is live.
  - The completed element received contributions from all of V_j, and each
    contribution requires a final operand, so every element of V_j has been
    produced or loaded.
  - None has died, because α_j < β_j.
  - The step also holds the completing element of V_{j+1} and, if s_j = 1,
    one element of W_j.
  - Peak ≥ a_j + 1 + s_j.
- If β_j ≤ α_j, then at time β_j every element of V_{j+1} is live.
  - The dying input has contributed to every output, so all of them have
    started.
  - None is complete before this step, and a started partial sum cannot
    leave the chip.
  - The step also holds the dying input and the weight element.
  - Peak ≥ a_{j+1} + 1 + s_j.

**Lemma 2 (successor case).** Let α_j < β_j and let c_j have a successor.
Then

  Peak ≥ min( a_j + a_{j+1} + s_j,  a_j + a_{j+2} + 1 + s_{j+1} ).

*Proof.* Throughout [α_j, β_j), all of V_j is live (Lemma 1). Let γ be the
first time an element of V_{j+1} dies, that is, its last use in c_{j+1}.

- **γ ≥ β_j.** At time β_j, every element of V_{j+1} has started, because the
  dying input contributed to all of them, and none has died. So all are live.
  Together with V_j and the weight element of that step, the peak is at least
  a_j + a_{j+1} + s_j.
- **γ < β_j, and some element of V_{j+1} is not final at γ.** The dying
  element contributed to every element of V_{j+2}. No element of V_{j+2} can
  be final yet, because some element of V_{j+1} is not final. So every element
  of V_{j+2} is a live partial sum. At γ we also hold:
  - V_j, whole, because γ ≥ α_j (the dying element was final) and γ < β_j;
  - the dying element of V_{j+1};
  - the weight element of c_{j+1}.

  The peak is at least a_j + a_{j+2} + 1 + s_{j+1}.
- **γ < β_j, and all of V_{j+1} is final at γ.** No element of V_{j+1} died
  before γ, so all are live just before the step at γ. Together with V_j, the
  step's accumulator in V_{j+2} and its weight element, the peak is at least
  a_j + a_{j+1} + 1 + s_{j+1} ≥ a_j + a_{j+1} + s_j.

Each case is bounded below by the stated minimum. ∎

**Lemma 3 (predecessor case).** Let β_j ≤ α_j and let c_j have a predecessor.
Then

  Peak ≥ min( a_j + a_{j+1} + s_j,  a_{j+1} + a_{j-1} + 1 + s_{j-1} ).

*Proof.* Reverse time and the direction of the chain. The model is symmetric
under this reversal:

- "final" (received every contribution) and "dead" (made every use) exchange
  roles;
- "used only when final" becomes "contributes only before being used";
- loads and writes exchange, each still occurring once;
- weights and the cell count are unchanged.

c_j with its predecessor becomes a contraction with a successor, and β_j and
α_j exchange. Lemma 2 applied to the reversed schedule gives the claim. ∎

## 3. Theorem

For every contraction c_j, define

  TI_j = a_j + 1 + s_j                                         if no successor,
       = min(a_j + a_{j+1} + s_j, a_j + a_{j+2} + 1 + s_{j+1})   otherwise;
  TO_j = a_{j+1} + 1 + s_j                                     if no predecessor,
       = min(a_j + a_{j+1} + s_j, a_{j+1} + a_{j-1} + 1 + s_{j-1}) otherwise;
  L_j  = min(TI_j, TO_j).

**Theorem.** Every zero-extra-traffic execution of S has peak at least
L(S) = max( d, max_j L_j ), where d is the operand-slot bound
max over operators of the number of nonresident operands and outputs.

*Proof.* For each j, either α_j < β_j or β_j ≤ α_j. Combine Lemma 1 with
Lemma 2 or Lemma 3 respectively. ∎

**Uniform chain (all a_j = n).**

- An interior contraction has L_j = 2n + s_j, since n + n + 1 + s ≥ 2n + s_j.
- A first or last contraction has L_j = n + 1 + s_j.

So at n = 2 the bound is 4 + s_j in the interior, and 3 + s_j ≤ 4 at the two
ends. This is the 4 B / 5 B rule of ZERO_TRAFFIC_THRESHOLD.md, now as a lower
bound. The archived witnesses attain it, which makes it the exact plateau in
that family. The boundary exception has a precise cause: a span-boundary
vector is loaded or written once, so its contraction has only one-sided
whole-vector liveness.

## 4. Scope and consequences

- **What it bounds.** The lower bound is on the zero-extra-traffic capacity
  (the plateau start), for any schedule, and so for both grammars. It says
  nothing about positive-traffic points.
- **What it requires.** Density holds only at unit M extent. The bound
  ignores resident activations, which contribute 0 cells; a span with a
  resident activation needs that term set to 0 and the corresponding
  liveness argument re-checked. The checker below excludes such states.
- **Effect on C2.** The C2 bound can be clipped at L(S ∪ K-complement):
  every candidate child with weights K resident has zero-traffic capacity at
  least L computed with s_j = [W_j not in K]. This removes C2's one-cell
  optimism for interior streamed weights. Whether it changes the work
  accounting must be measured with the same shared-DAG method.
- **Check.** `check_chain_threshold.py` evaluates L(S) on every archived
  C2-audit node that qualifies: a forward FFN or attention stack, unit M
  extent, no resident activation, and a finite zero-extra point. It counts
  violations (L > actual, which would refute the theorem or its
  implementation) and equalities. Results are recorded below.

## 5. Check on the archived v2 C2-audit nodes

`python -m research.index_coupling.check_chain_threshold <cases>` reads only
archived responses and runs locally in seconds.

| Case | Qualifying nodes | L = actual | L < actual | Violations |
| --- | ---: | ---: | ---: | ---: |
| FFN forward 1 / 2 / 3 / 4 layers | 56 / 184 / 568 / 1,976 | 49 / 163 / 533 / 1,927 | 7 / 21 / 35 / 49 | 0 |
| attention forward 2 / 4 layers | 184 / 1,976 | 163 / 1,927 | 21 / 49 | 0 |
| FFN forward 1 / 2 layers, M8 D4 F8 | 156 / 392 | 127 / 303 | 29 / 89 | 0 |
| **Total** | **5,492** | **5,092 (92.7%)** | **400** | **0** |

The bound is never violated, as the theorem requires. It is exact on 93% of
qualifying nodes. On full-span unit-M nodes it is exact:

- in all of them for the 2-, 3- and 4-layer tiny stacks (16, 64 and 256 for
  FFN; 16 and 256 for attention);
- in only 7 of 12 for the one-layer FFN. In
the tiny stacks the remaining gaps are 1-3 cells. In the M8 stacks they reach
14 cells.

Two explanations for the gaps are possible:

- the loop grammar may not attain the schedule-level optimum;
- the bound may omit further forced liveness, for example from elementwise
  intermediates or from both neighbours at once.

These numbers do not distinguish the two. The equality rate is post hoc; only
the zero-violation result tests the theorem.
