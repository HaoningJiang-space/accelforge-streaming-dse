# P18: penalty extent and an order-complete control

These are follow-up analyses, not changes to the frozen P18 verdicts. The
profile analysis reads the archived 84 curves and performs no mapping search.
The order control evaluates three orders of one previously identified sensitive
shape. Both ran in clean pinned checkouts on the designated experiment machine.

## 1. The trend survives a representation-independent measure

For each shape use one common extra-traffic domain [0,q_hi], defined before the
analysis as the largest extra-traffic breakpoint across its seven archived
curves. Integrate the inverse capacity difference exactly over step intervals,
rather than averaging a different set of breakpoints for every curve pair.
Uniform weighting in q is an explicit convention, not an observed distribution
of hardware budgets. The full definition is in [the protocol](P18_PROFILE_PROTOCOL.md).

For four consumers, comparing kkii (two minority directions) with kkki (one):

| Measure | Shapes supporting an increase |
| --- | ---: |
| Interval-weighted mean relative capacity penalty | 12/12 |
| Signed capacity-gap area | 12/12 |
| Length of positive-gap traffic-budget intervals | 12/12 |
| Maximum capacity gap | 0/12 strictly increase; 12/12 equal |

The two independent area calculations agree on all 36 pure/mixed pairs:

    integral (S_mixed(q)-S_pure(q)) dq
      = integral (Q_mixed(S)-Q_pure(S)) dS.

Inserting extra interior q samples leaves all integrated metrics unchanged.
The input manifest contains exactly 84 unique expected records, with valid
monotone frontiers and the expected compulsory traffic.

For I=K=n, the percentages below use that common per-shape q domain. They are
not interchangeable with averages using a different domain or weighting.

| n,J,L | One minority: mean relative penalty | Two minorities | Signed-area ratio, two/one | Positive-domain length ratio |
| --- | ---: | ---: | ---: | ---: |
| 4,4,4 | 4.459% | 6.854% | 1.75 | 1.50 |
| 4,4,8 | 3.632% | 3.984% | 1.10 | 1.40 |
| 4,8,4 | 3.806% | 5.851% | 1.75 | 1.50 |
| 4,8,8 | 3.316% | 3.638% | 1.10 | 1.40 |
| 8,4,4 | 2.251% | 5.207% | 2.28 | 2.50 |
| 8,4,8 | 2.014% | 5.060% | 2.21 | 2.67 |
| 8,8,4 | 2.490% | 4.784% | 2.02 | 1.88 |
| 8,8,8 | 2.141% | 4.919% | 2.20 | 2.40 |
| 16,4,4 | 0.819% | 3.630% | 3.09 | 3.75 |
| 16,4,8 | 1.300% | 4.532% | 2.02 | 3.88 |
| 16,8,4 | 0.962% | 3.332% | 2.58 | 3.67 |
| 16,8,8 | 0.970% | 4.259% | 2.57 | 6.00 |

For (16,8,16,8), q_hi=19968:

| Quantity | kkki | kkii |
| --- | ---: | ---: |
| Maximum gap | 128 | 128 |
| q interval(s) attaining the maximum | [640,768) | [640,896) |
| Length of all positive-gap intervals | 640 | 3840 |
| Signed gap area | 19840 | 50944 |
| Mean gap conditional on a positive gap | 31 | 13.267 |

Thus the maximum alone hides a broader affected range; the mean magnitude
within that range can even decrease. "More frequent" should mean a larger
measure of traffic budgets here, not a probability of execution or the number
of plotted breakpoints.

With one minority consumer, the four-consumer case also has a smaller signed
area and smaller weighted relative mean than the three-consumer case in all
12 shapes. This supports the observed dilution inside this grammar. Adding a
consumer changes the workload and baseline as well; it is not a general theorem
about fixed-work performance or a hardware speedup.

## 2. Order completion removes a small loss, not the whole coupling effect

The selected shape is (16,4,16,4), the one archived instance where kki and ikk
differed. Evaluate kki, kik and ikk with the original tensor identities and
data bindings preserved. The two K-contracting consumers are symmetric in this
model, so these orders cover all permutations up to that symmetry.

| Check | Result |
| --- | --- |
| Re-evaluated kki and ikk versus their archived curves | Exact matches |
| New kik curve | Equals ikk |
| Pareto union over all three orders | Equals kki |
| Independent execution of every union-frontier point | 21/21 pass, exact peak/traffic and correct outputs |

The only improvement over ikk/kik occurs at integer capacities 53 and 54:
traffic falls from 1728 to 1664, a reduction of 64. The following breakpoint is
55, where those orders agree again. The envelope never improves on the archived
kki curve. Therefore its capacity gap against the all-K graph, including the
maximum of 64, survives order completion in this instance.

This separates two mechanisms: a fixed-order restriction causes a localized
loss, while mixed contraction roles retain a difference after that restriction
is removed. It is a known-case control, not held-out generalization. The
four-consumer profiles above remain fixed-order results; the control does not
make them order-complete by implication.

## Reproducibility and remaining work

- Profile source: `8932b9a2`; [raw output](results/p18_profile/profile.jsonl).
- Order-control source: `cefab311`; [raw output](results/p18_profile/order_check.jsonl).
- Both embed clean-checkout status and the input hash. [Artifact hashes](results/p18_profile/audit.json).
- No FFM model, original curve model, independent simulator, P18 prediction or
  existing FFN job was modified. The recorded run times are diagnostic single
  runs, not an optimizer speedup benchmark.

The next larger-fork prediction should name its q domain, weighting and order
space before execution. A natural primary pair is positive-domain length and
signed gap area, with the maximum retained as a separate statistic. For an
order-independent claim, complete the same order space for every configuration.
Separately inspect the witness transitions before attributing every maximum to
one retained accumulator: n*min(L,n/2) equals n*L only in one of its regimes.
