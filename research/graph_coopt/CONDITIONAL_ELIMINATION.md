# A restricted conditional-elimination contract

This follow-up tests one aggregation law needed by an architecture–mapping factor
solver. It does **not** replace the research goal with a faster fixed-FFM pruner.
The default FFM path is unchanged. Candidates are already generated, architecture
is conditioned, and only a terminal consumer bucket is supported. No full
InsideOut, variable-order search, architecture-family compiler or new Memo is
implemented.

## Variables and separator

Let a be one global architecture, p a completed prefix candidate and R one
prepared consumer group. R includes the actual permuted Compatibility and native
Join program, not merely tensor names. K_R(p) retains every producer field used
by numeric matching or surviving output loop symbols. In the supported no-adjust
program, carried tensor-size columns have no downstream read and may be omitted
from this separator. They cannot be dropped for an allocation/free/alias program.

For each finite memory, compile the native terminal response into

\[
\Phi_{p,R}(x)=\max_{j}\{b_j(p)+c_j^\top x\},\qquad x\ge0,
\]

where x contains the consumer's exact resource coordinates, coefficients and
intercepts are nonnegative integers, and maxima are componentwise by memory.
This is the **final resource response** of one Join, not a sufficient nonterminal
live-copy state for arbitrary future operators.

The conditional summary has the conceptual form

\[
V_R(a,k)=\operatorname{ND}\{(E_p,T_p,\Phi_{p,R},\operatorname{source}_p):
 p\in\mathcal P(a),K_R(p)=k\}.
\]

The prototype does not construct all such factors or minimize over architecture.
It checks a conservative sufficient dominance relation in the current bucket.

## Sufficient replacement condition

Within identical required fields and the same immutable Join context, remove q
only if there is a retained p satisfying:

\[
E_p\le E_q,\quad T_p\le T_q,\quad
\Phi_{p,R}(x)\le\Phi_{q,R}(x)\quad\text{for all }x\ge0.
\]

At least one cost inequality must remain strict after native binary addition
with every consumer cost in this bucket. Resource-only improvements and tiny
cost differences are deliberately retained to avoid changing selected sources
through new ties. Witness chains terminate at a retained candidate.

For max-plus polynomials f and g, the implemented sufficient test is: every term
of f is covered by a term of g with no smaller intercept or coefficient. Since
x is nonnegative, each covered term is no larger, and hence f(x)≤g(x). Failure
of this sufficient test means **unknown/not dominated**, not infeasibility.

For example,

\[
\max(640,512+x)\le\max(576,768+x)\quad\forall x\ge0.
\]

Raw historical/current resource vectors (640,512) and (576,768) are incomparable.
Their effects are ordered. This is the distinction the earlier strict-interface
hashes and coordinate Pareto did not express.

### Why the reduction preserves this bucket

1. Equal matching fields give p every numeric match available to q, within the
   already accepted structural group/permutation.
2. The supported native cost program adds consumer E and T once. Nonnegative
   binary floating addition is monotone; the strictness guard below prevents a
   strict improvement disappearing through rounding.
3. The compiled resource program is exactly the supported sequence of checked
   bit additions and terminal maxima. Pointwise response dominance makes every
   capacity-feasible completion of q feasible for p with no worse resource vector.
4. There is no remaining suffix after this consumer. Other output objective and
   matching dimensions are either preserved or explicitly unsupported. Thus q
   cannot contribute an undominated result absent from the retained set.

Writing F_r for this fixed continuation operation gives the local law

\[
\operatorname{ND}\{F_r(p):p\in S\}
=\operatorname{ND}\{F_r(p):p\in D_R(S)\}.
\]

Here D_R is the conservative reduction, not a general commutative aggregation.
This law does not justify reassociating FFM operator Joins, moving pruning into
Tile enumeration, or invoking the full InsideOut complexity theorem. In
particular, native floating cost addition is not an associative algebra over
arbitrary evaluation trees.

## Executable resource contract

`resource_effect.py` reads the actual `_prepare_column_operations()` program
after native `_prepare_join_plan()` has run **once**. It shadows resource additions
and exactly mirrors `free_to_loop_index(-1)`, including the native treatment of
nested right reservations. It compiles only the following case:

- one final consumer, same reference operator order, tracked RU/E/L resources;
- exact bit metadata and checked nonnegative resource operands within the native
  integer-exact range; legacy unbounded resource coordinates must be zero;
- no live allocation, shared free, duplicate alias adjustment, arbitrary row
  callback, preexisting prepared plan or research switch;
- the recognized native E/T program consists of one binary sum per objective;
- at most 512 producer rows and 128 terms per effect expression.

Unknown schemas or bounds retain the native inputs. No copy-layout conversion,
new physical lifetime rule or repair of unsupported Fusion is introduced. The
native preparation's mutation remains in its original place and order; a
copy-isolated filtered input is used only for the ensuing numeric Join.

The IEEE guard requires normal finite nonnegative f32/f64 operands with
M=max(producer costs, largest consumer cost), M<max_f32/4. A cost gap above
8·eps32·M exceeds the combined rounding errors of both sums. Subnormal domains,
overflow ranges, approximate Pareto and other dtypes are unsupported. Resource
arithmetic remains exact under the existing bit range; costs are not silently
converted into an exact-real model.

## Independent checks and ablations

The native reference path is instrumented separately by `NativeTransferCheck`.
Before local Pareto it compares each surviving native resource result to the
compiled expression at the original producer/consumer source bindings. These
observations are **not passed to the reducer**. A separate unit test compares 156
synthetic resource bindings against native numeric composition with test-only
Pareto disabled. This checks the shadow implementation, not physical hardware.

Three reductions use the same generated catalog and saved prefix:

| Mode | Compared information |
| --- | --- |
| coordinates | Original tensor fields, matching fields and prepared resource coordinates |
| live_coordinates | Drop metadata proved unused by this no-adjust program; compare resource coordinates |
| effect | Same live requirements; compare resource response functions |

Each mode must reproduce all ordinary numeric frontier columns and Mapping
identities. The effect result is reconstructed and re-evaluated with the FFM
model. No target optimum, incumbent bound or enumerated completion response is
an input to elimination. Initial generation/fallback/Pareto behavior is frozen.

Six predeclared probes cover the previous four small cut cases (2mm/3mm,
4×8/8×4, 96/128 B) and the two decision-audit cases (2mm/3mm, 16×16, 4 KiB).
Raw outcomes, response expressions, surviving witnesses and source hashes are
in `results/conditional_elimination/audit.json`. Producer removals are **row
occurrences in particular consumer buckets**, not globally deleted mappings.

The three 3mm terminal pair counts are **130→91**, **180→132** and **394→302**;
the three 2mm counts are unchanged. Both coordinate controls remove nothing.
All complete numeric frontiers and Mapping identities agree. The separate
native transfer check covers 816 composed rows / 2,448 exact coordinates, and
all 45 final effect-result instances pass model reconstruction/re-evaluation.
See the [full table and interpretation](results/conditional_elimination/README.md).

## Architecture–mapping scope

For reuse across architectures, a future rule additionally needs valid cost and
resource expressions, compatible interfaces and candidate availability over a
domain. In particular, availability of p must cover q's domain. The prototype
has not proved that ordered fallback membership is invariant across capacities
or PE shapes. Six independent conditional tests are not one architecture-family
certificate or proof for a previously unseen architecture.

This is a local **elimination-contract experiment**, not evidence of faster
complete DSE. Candidate generation and earlier Joins are unchanged. Copies,
quadratic comparisons, effect compilation and verification have costs; reduced
pair counts cannot be translated into end-to-end speedup. Performance and a
consumer-driven candidate request before generation remain separate gates.

## Reproduce

```sh
python -m research.graph_coopt.audit_conditional_elimination --output research/graph_coopt/results/conditional_elimination/audit.json
python -m pytest -q research/graph_coopt/test_conditional_elimination.py --disable-warnings
```

The conceptual connection to [FAQ](https://arxiv.org/pdf/1504.04044v7) and
[Cascades](https://15799.courses.cs.cmu.edu/spring2025/papers/05-cascades/graefe-ieee1995.pdf)
is documented in [the focused reading notes](READING_INSIDEOUT_CASCADES.md).
The condition and its limits above are a project-specific derivation, not a
theorem claimed by those papers or a claim of research novelty.
