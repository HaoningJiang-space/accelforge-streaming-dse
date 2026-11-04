# Search contracts and pre-enumeration support

## Contract and metadata fixes

JoinContext now captures effective `pareto.TOLERANCE` and checks it at start,
snapshot, resume, advance and finalize. The regression changes tolerance after
real 2mm/3mm prefix work and requires rejection before further pruning.

Initial candidates separately carry GenerationContract: metrics, generation-time
tolerance, AF settings and resource units. Filtering retains provenance; combining
runs retains all known contracts plus an unknown marker for any unrecorded source.
The generation cache version is bumped to populate new entries. Legacy objects
are not assigned their caller's current settings. JoinContext retains this history
without requiring generation settings to equal Join settings. The conservative
AF check applies within the Join stage; intentional phase transitions before
Join-context creation remain permitted. Different policies are not thereby
claimed to be numerically equivalent.

save_partial caches immutable IntermediateGroup metadata. groups_for returns the
cached tuple without resume, copying, compression, generation or Join. A test
makes resume and state-copy functions raise if a metadata query enters them.
Real advances/resumes retain the deep-copy correctness path, including pending
groups. Its long-chain copying cost has not been eliminated.

## Read-only observation

```sh
python -m research.graph_coopt.template_support_audit --params 2,16,16 \
  --output research/graph_coopt/results/template_support/2mm.json
python -m research.graph_coopt.template_support_audit --params 3,16,16 \
  --output research/graph_coopt/results/template_support/3mm.json
```

The observer runs after resource tracking is assigned and before _allocate_jobs.
It records raw mappings/backings, loop positions, rank bounds, resource tracking
and mandatory neighbors. Every original task still executes in original order.
It times the original make_tile_shapes and uses native get_fused_loop_indices
to count effective-loop masks before pooled template Pareto. Returned frames
and mappings are unchanged. An integration regression compares the complete FFM
frontier with/without observation while forcing unknown patterns with a tiny
budget. The observer supports only one worker and uncached full generation.

The experiment uses NVDLA 4x8 and 8x4 at 512/1024 bytes for each case, with 8-bit
values and the conservative Fusion filter. Each point is independently generated
and measured once, in fixed serial order. Cold/JIT effects are visible; timings
are diagnostics, not stable speedup estimates or a comparison to cached FFM.

## Conservative abstraction

For each raw Compatibility, allow every subset of loops to disappear, then use
the original drop_loop_indices normalization. Some subsets are impossible for
actual tiles: this intentionally overapproximates the possible interfaces.
Compare shared backing resource/persistence and per-tensor temporal/spatial loop
counts. Ignore ranks, ordering, reservation indices, tile values, sizes, aliases,
PE constraints and joint consistency. Legal permutations preserve the compared
counts, so they are included without assuming all permutations are legal.

Unknown/missing descriptors and pattern-budget overflow (default 128) return
unknown, never an empty feasible set. Shared external inputs enter each neighbor
pair's incidence without creating false producer edges.

Within direct FFM matching of the declared shared tensors, a true interface match
must have a counterpart in this relaxation. No relaxed support means no raw
template of a mandatory neighbor matches even these necessary conditions.
Possible support does not establish numeric compatibility, physical feasibility,
a common tile assignment for multiple consumers, or global feasibility. Allowing
impossible unit-loop deletion can retain actually unsupported templates.

Even structural impossibility would not yet license task removal: pooled Pareto,
fallback and resource/scheduling interactions must also be checked. The observer
never prunes. Absence of a relaxed witness among actual template output masks is
reported separately as a post-hoc diagnostic, not a proof over physical Mapspace
and not an inference from final winners.

## Outcome

All 264 template execution instances across the eight workload/architecture
points ran exactly once. These are not 264 unique templates.

| Per architecture | Templates | Templates with multiple effective masks | Pre-proved no relaxed support | Nonempty templates without an observed relaxed witness |
| --- | ---: | ---: | ---: | ---: |
| 2mm | 24 | 12 | 0 | 0 |
| 3mm | 42 | 24 | 0 | 0 |

No inspection was unknown and no template returned zero rows. One real raw
template with loops [M,N1,N1] produced masks 001, 010, 011, 100, 101, 110 and 111
at the same architecture. A raw template therefore cannot simply receive one
fixed effective-loop label. These masks are still not complete copy contracts.

Pre-analysis took about 3.5 ms per 2mm point and 8.4–8.9 ms per 3mm point.
Generation cost of pre-proved unsupported templates was zero, so the reported
unsupported-generation cost minus pre-analysis cost is negative. Post-inspection
and post-support analysis are recorded separately. Even a positive difference
would not itself prove speedup because cache warming and pooled selection can
change after skipping tasks. Actual skipped jobs remain zero.

The result confirms tile-dependent loop interfaces, but offers no positive
evidence for deploying a pre-generation filter. A stronger method needs cheap
symbolic facts that exclude deletion/binding patterns and then demonstrate
unsupported work beyond existing lookahead. This coarse abstraction cannot
decide whether that stronger approach is worthwhile.

## Verification

The declared research/tracking_audit, research/streaming_join and graph_coopt
regression passed 627 tests. Targeted graph/coopt and generation-cache checks
passed 47 tests; these overlap the full regression and are not additional unique
cases. Logs and both raw audits are retained in results/template_support.
The old legacy compatibility_util collection issue remains outside that test set.
