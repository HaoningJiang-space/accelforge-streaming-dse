# Why a streamed weight costs 5 B instead of 4 B, except at the ends

This answers the open question of C2_BOUND_RESULTS.md §2 and §5. It is an
explanation from executed witnesses plus a counting rule that reproduces all
256 archived subsets. It is **not** yet a lower-bound proof.

Setting: grammar v2. The case is the tiny 4-layer FFN child of the outer M
loop, `ffn_stack(4, m=1)`, so every activation (X_i, H_i, Z_i) has 2 cells
and every weight has 4. K is the set of resident weights. The witnesses below
come from `curve(..., external=K, witness=True, scalar_leaf='v2')`, run
locally in under a second.

## 1. The witnesses

**All weights resident: plateau 4.**

- The optimum is a partition into singletons that keeps every intermediate
  activation (X1..X3, H0..H3, Z0..Z3) across its producer-to-consumer
  interval.
- Each matmul EH_i or EY_i therefore runs with its input vector and its
  output vector both held whole: 2 + 2 = 4.
- Its own D or F loops then cost nothing, because both vectors are already
  held.

**One interior weight streamed (for example W1_1 or W2_1): plateau 5.**

- The two activations are still held whole at that matmul (2 + 2).
- The weight is not resident, so the operator's own loops must stream it.
  Streaming needs one operand cell, which gives 4 + 1 = 5.
- The witnesses at 5 reorganise the neighbouring groups (fused pairs under F
  loops, held as scalars), but the peak is set at this matmul.

**W1_0 or W2_3 streamed: plateau 4.**

- At EH0, the input X0 is not an intermediate. Nothing else in the span uses
  it, so it is private to EH0, and EH0's own loops can slice it:
  - the D0 loop reduces X0 to one cell;
  - the F0 loop then keeps that one cell.
- So the peak is H0 (2, held for EZ0) + X0 cell (1) + W1_0 cell (1) = 4.
- EY3 is symmetric. Its output X4 is a private terminal output, sliced by the
  D4 loop, so the peak is Z3 (2) + X4 cell (1) + W2_3 cell (1) = 4.
- The cell saved by slicing the boundary activation pays for the weight's
  operand cell.

## 2. The rule

At zero extra traffic in these witnesses, the peak at operator o is

    B(o) = sum of the intermediates o must hold whole
           + one cell for each tensor o streams.

- An *intermediate* is produced and consumed by different operators inside
  the span.
- A tensor is *streamed* when it is live and private to o. That covers a
  non-resident weight and a boundary activation.

The plateau is max_o B(o). For this child:

- every interior matmul has B = 4 + [its weight is streamed];
- the two boundary matmuls have B = 2 + 1 + [weight streamed] ≤ 4;
- so the plateau is 4 when every streamed weight is W1_0 or W2_3, and 5
  otherwise.

**Check against the archived census (C2_BOUND_RESULTS.md §2):**

| Kept k | Rule predicts plateau 4 for | Archive |
| --- | --- | --- |
| 8 | the single subset | 4 |
| 7 | 2 of 8 (drop W1_0 or W2_3) | 2 at 4, 6 at 5 |
| 6 | 1 of 28 (drop both) | 1 at 4, 27 at 5 |
| 0-5 | none of 219 | all 219 at 5 |

The rule also gives the k = 0 plateaus of the other archived roots:

- FFN-1: 4, because both its weights sit at the boundary matmuls;
- FFN-2 and FFN-3: 5;
- attention-2 and attention-4: 5.

All of these match. The M8 cases have different sizes and were not checked
against the rule.

## 3. What the rule means

1. **For the zero-traffic endpoint, retention separates by operator.** The
   2^m retention subsets affect the child's plateau only through max over
   operators of B(o). Each weight belongs to one operator and adds one cell
   there. This is a max-plus structure. Releasing a weight is cheap (one
   cell), but its cost depends on the operator's local context: whether its
   neighbouring activations are intermediates or boundary tensors.

   This does not contradict LIFT_RESULTS.md. That study concerns full
   curves, whose positive-traffic points remain non-local.
2. **C2's optimism has a precise source.** The all-resident anchor's plateau
   is 4. Every proper subset with an interior weight streamed has plateau 5.
   C2 shifts the anchor's 4 for every subset, so its endpoint is one cell
   too low exactly when some streamed weight is interior.
3. **The general mechanism is the row model of P21e.** A dense contraction
   either holds its whole input row or accumulates its whole output row.
   Chained contractions hold intermediates on both sides of an operator.
   Streamed operands add operand cells on top of these held rows.

## 4. What is not established

- **B is constructive, not a lower bound.** Fusing a producer and consumer
  under a common loop can hold only a tile of an intermediate. The witnesses
  at plateau 5 use such fusion elsewhere in the span. The rule is exact here
  because, at these sizes, no fusion beats holding both vectors at a matmul.
  A proof must show when the held whole rows are unavoidable at zero extra
  traffic. The natural tool is a red-blue pebble argument (Hong and Kung,
  1981) for two consecutive dense contractions, applied under the grammar's
  fixed order and no recomputation.
- **The rule bounds only the endpoint.** A certified threshold would raise
  C2's zero-extra endpoint for interior subsets. C2_BOUND_RESULTS.md already
  notes that this alone does not bound positive-traffic points.
- The rule has been checked on one shape family (all extents 2) and its
  archived aggregates only. The larger M8 stacks have been neither predicted
  nor checked.

## 5. Suggested next step

Before any implementation:

1. State the threshold as a lower bound for a chain of dense contractions with
   private streamed operands, and prove it with a pebbling argument.
2. Freeze a prediction for the M8 stacks' per-subset plateaus from that bound,
   and test it with Codex's offline C2 machinery. That machinery already
   records child responses per subset.
