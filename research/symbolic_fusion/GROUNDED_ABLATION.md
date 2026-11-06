# A: grounded DP removes the apparent need for universal effects

Same original 192-plan, fixed 64x96 / full-GB-T2 grammar; same cost formulas,
constructor, factor cache and frontier operations. Only the intermediate
comparison changes to grounded (Peak,E,T). All methods may precompile once and
reuse their frontier for the same capacity queries.

| Method | Factor evaluations | Partial combines | Complete candidates before Pareto | Final numeric points |
| --- | ---: | ---: | ---: | ---: |
| Cached flat | 28 | 576 | 192 | 11 |
| Grounded DP | 28 | 81 | 33 | 11 |
| Universal effect DP | 28 | 108 | 60 | 11 |

Fresh independent event execution of all 192 plans and 35 capacities matches
all three exact numeric frontiers. Grounded order reversal and budget pushdown
also match. Twenty-five experiment tests pass (19 previous + 6 ablation tests).

Nine shuffled, warm, paired trials include construction and the same five
precompiled capacity queries. Median totals are 7.558 / 6.327 / 6.269 ms for
cached flat / grounded / universal. Grounded compile-only is 0.549 ms, universal
0.613 ms; construction dominates and small total differences are not evidence
of a universal-effect performance advantage. Raw measurements are in
[summary.json](results/grounded_ablation/summary.json).

**Negative attribution result:** ordinary multiobjective DP explains the
candidate reduction in this fixed context, and is less conservative. The
universal response representation supplies no demonstrated extra legal context
in this grammar. The earlier 192-to-60 result must not be presented as a unique
Resource-Effect Algebra benefit. Keep its correctness evidence, but test actual
GB-backed versus DRAM-backed execution before retaining the method as a core
research direction.

```sh
python -m research.symbolic_fusion.grounded_ablation --output research/symbolic_fusion/results/grounded_ablation/summary.json
python -m pytest -q research/symbolic_fusion/tests --disable-warnings
```
