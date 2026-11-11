# Primary-source check for the DAG interface

This is a bounded reading record, not a completed novelty survey or a performance
comparison. D1 falsifies our closed-region restrictions; it does not falsify any
of the systems below. No implementation of these systems was run in this study.

## Welder: checked paper and algorithm figure

[OSDI 2023 paper](https://www.usenix.org/system/files/osdi23-shi.pdf), Sections
3.1–3.3 and 4.1, especially Figure 7, proceedings page 706. The PDF was downloaded
directly and the algorithm page was visually checked.

Welder assigns memory levels to edges, propagates output/reduction tile choices,
checks memory footprint against capacity, and ranks tile configurations by
traffic. Figure 7 retains Top-K tile configurations and commits edge connection
choices using measured latency. Its representation is hierarchical, with
recursive subgraph execution at different memory levels. Thus "Welder only
checks tile compatibility" is inaccurate, and its search is not an exhaustive
capacity–traffic frontier oracle for our grammar.

For D1, the relevant question is whether its hierarchical graph can express
the all-operator I scope and downstream-only L scope with matching reservations.
The paper mechanism gives no basis to declare this impossible. A mapped example,
hardware alignment and lifetime comparison remain necessary. Top-K selection
is a search-space restriction, not evidence that the representation is invalid.

## Crane: checked publisher text, PDF unavailable

[MICRO 2025 publisher article](https://doi.org/10.1145/3725843.3756023), Sections
4–6, Definition 5, equations 7–12 and 22–25. Direct PDF and full-page fetches
returned HTTP 403; the official indexed article text exposed these sections.
No proxy was used to bypass the failure, and no PDF visual check is claimed.

ScT tracks sub-batch execution progress. MeT describes stored sub-batch ranges
in SRAM and DRAM; equations 11–12 explicitly constrain their capacities. The
paper combines hierarchical blocks with intra-block MILP scheduling. Its broader
search filters sub-batch candidates through K1/K2 stages, applies intra-layer
scheduling, and refines hierarchy. An intra-block optimality statement therefore
does not establish exhaustive global joint tiling/scheduling optimality.

For D1, I streaming resembles sub-batch progress, but L streaming and K partial
sums require a mapping to its intra-layer/hierarchical semantics. That mapping
has not been demonstrated. It would be unjustified to claim that Crane ignores
lifetime or SRAM, or that the D1 counterexample invalidates its tables.

## PolyMage 2020: detailed recurrence still unverified

The [author's publication page](https://sites.google.com/site/abhijangda/publications)
identifies the [TOPLAS article](https://doi.org/10.1145/3404846) as an extension
of the PPoPP 2018 paper and links its source code. The publisher PDF returned
403. The [institutional repository copy](https://eprints.iisc.ac.in/79023/1/ACM_tra_pro_42-3_2020.pdf)
returned 502 on direct access and was unavailable through hosted retrieval.

Consequently, this note does not claim to have checked its exact DP state,
partition completeness, complexity, or optimality theorem. An older paper or
project overview cannot silently substitute for the journal version.

## What remains a research question

The candidate contribution is a sufficiently small conditional interface that
permits exact reuse across streaming contexts at lower total construction cost.
It is not DAG fusion, hierarchical tiling, explicit memory tables, or DP alone.
The [next-interface note](INTERFACE_PLAN.md) states the local substitution
conditions before proposing any compression. Literature coverage does not yet
establish that this specific combination is absent from prior work.

LoopTree, DaCe, Cascades, FAQ, Apollo, VTC and the remaining suggested papers have
not been re-audited in this reading pass. No publication dates, benchmark numbers
or novelty comparisons for those works are newly certified here.
