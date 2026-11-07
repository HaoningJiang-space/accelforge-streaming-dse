# BCGE feasibility experiment under explicit resource budgets

Status: **SOTA acceptance is not achieved.** This directory contains a frozen
native baseline protocol and a read-only necessary-condition support experiment.
It does not implement the proposed complete BCGE optimizer. This distinction is
also explicit in each generated JSON report.

The user requires Chat to supervise and Codex to implement. The research
[supervision chat](https://chatgpt.com/c/6aee2ce0-094c-83e8-bfdd-5132e0ab9d62)
was configured through the visible Chat UI as **GPT-6 / Extra High**. Chat selected
budget-conditioned graph elimination as a hypothesis, not a proven contribution.

## Problem and frozen baseline

Choose one global hardware h and legal graph mappings m to minimize native
whole-workload E(h,m) * T(h,m). Every operator must fit that same hardware.
`ResourceBudget` restricts PE count and physical SRAM bytes; it is **not a
calibrated area budget**. Budget admission occurs before any prospective joint
search; baseline selection after complete independent searches is only a
reference, not the proposed optimization algorithm.

The predeclared native case is NVDLA `matmuls(3,256,256)`, with all existing FFM
templates, array shapes 16x384 / 32x192 / 64x96 and capacities 131072 / 135167 /
135168 / 262144 bytes. The three budgets cap PEs at 6144 and SRAM at 131072 /
135168 / 262144 bytes. All dimensions, costs, constraints, and fallback policy
remain native. The separate Stage 0–2 `joint_search` implementation supports
dyadic **2mm** only; it is not silently relabelled as a valid 6144-PE 3mm method.

The frozen reference runner supports independent FFM, its existing enumeration
cache, and existing per-shape Event + Bitset + Cache. It records complete native
E/T/exact-resource fronts, measured expansion/Join work, one selected physical
mapping per point and reconstruction at the actual point. It does not claim to
replay every tied source. Every cross-method frontier comparison occurs outside
the search timer. Failed comparisons are saved and terminate with an error.

## Non-incremental hypothesis and first certificate test

The proposed BCGE search would eliminate graph decision variables while carrying
physical boundary requirements, possible global hardware, exact resource effects
and reconstruction provenance. Its contribution would have to be **sound
cross-operator pruning before numeric Tile expansion**, beyond Event cohorts.
Reusing native Join, adding a cache, or filtering final demand vectors by hardware
does not establish that contribution.

The first implemented experiment obtains complete native raw template catalogs
before numeric Tile enumeration. On the first native Join edge it reuses the
existing necessary-interface relaxation: all unit-loop deletion subsets, shared
tensor backing memory/persistence and temporal/spatial loop counts. Rank, order,
aliasing and sizes are relaxed. Unknown interfaces are wildcards.

The new relation includes a hardware identity. A producer family survives only
if at least one family of each mandatory neighbor has potentially intersecting
interface keys **at the same hardware**. Propagation runs simultaneously to a
fixpoint, in both directions. A hardware ID survives only if every mandatory
operator has at least one surviving family. Every deletion records its round,
missing neighbor and the previous round's available neighbor families.

Necessity proof: any concrete legal complete plan supplies one family per
operator at one hardware. Its boundary key belongs to both overapproximations.
Inductively those witnesses support one another in every round, so none can be
deleted. Unknown descriptors cannot justify deletion. Incomplete catalogs are
errors. On graphs with cycles, remaining local support need not imply a global
plan; surviving sets are still overapproximations.

**This proof concerns the relaxed support relation. It does not prove that
removing a raw FFM job preserves its ordered fallback and prefix-Pareto history.**
The integration therefore observes catalogs only, skips zero real jobs, performs
no numeric enumeration or native Join, and claims no speedup. Independent native
preparation per hardware is explicitly charged as diagnostic preprocessing, not
hidden as free work of a future shared optimizer.

If there are no deletion certificates on this real case, the abstraction has
failed to establish useful nonlocal pruning. Do not enable it as an optimizer or
infer that a more precise abstraction must succeed. A stronger resource/consumer
predicate needs a separate native-semantic proof and policy-equivalence audit.

## Research acceptance still required

The supervisor proposed preregistered go/no-go targets: preserve comparable full
frontiers and all returned witnesses; reduce numeric expansion rows by at least
30% and actual Join pairs by at least 50% relative to Events; attain at least 2x
cold median improvement on two non-toy workloads with acceptable RSS. Five fresh
process trials, alternating order, and a backward-propagation ablation are needed.
These are targets, not measured outcomes. An Attention proxy and a larger
predeclared architecture domain remain additional obligations.

External SOTA comparison additionally requires common evaluator/grammar/budgets,
or an explicit valid translation and rescoring protocol. No comparison is valid
between independent toy-grammar EDP and NVDLA/FFM EDP, across different hosts, or
by dividing a new number by an unreplicated paper's reported result.

## Paper mechanisms and reproducibility

- DB: [Cascades (1995)](https://15799.courses.cs.cmu.edu/spring2025/papers/05-cascades/graefe-ieee1995.pdf)
  supplies required physical properties, enforcers and cost limits. A Memo alone
  is not a new algorithm.
- DB: [FAQ / InsideOut](https://arxiv.org/abs/1504.04044) motivates variable
  elimination and intermediate-size control; legal aggregation laws are still
  needed for resource effects and E/T frontiers.
- OS: [Alpa, OSDI 2022](https://www.usenix.org/conference/osdi22/presentation/zheng-lianmin)
  couples local execution choices and global resource allocation. Its distributed
  execution model does not prove a Fusion lifetime rule.
- HPC: [memory-constrained multiprocessor scheduling, ICPP 2025](https://arxiv.org/abs/2507.17411)
  jointly models parallel scheduling, communication and memory, and demonstrates
  the risk of separating those decisions.
- HPC: [weighted red-blue pebbling, SPAA 2025](https://csl.yale.edu/~rajit/abstracts/spaa2025.html)
  motivates explicit weighted storage/data-movement constraints.
- Co-design: [DOSA, MICRO 2023](https://people.eecs.berkeley.edu/~ysshao/assets/papers/dosa-micro2023.pdf)
  and [DiGamma, DATE 2022](https://arxiv.org/abs/2201.11220) already search
  hardware and mapping together. Their original evaluators differ from this
  repository. [SENNA](https://doi.org/10.1145/3705731) is another necessary related
  comparison; an official runnable implementation was not confirmed here.

DOSA and DiGamma/GAMMA sources were downloaded into ignored `libraries/`
directories. Downloading sources is not reproduction. DOSA's official setup
requires a Gurobi license and a native Timeloop/Accelergy stack. Native Windows
runtime limitations are documented in `../runtime/README.md`.
