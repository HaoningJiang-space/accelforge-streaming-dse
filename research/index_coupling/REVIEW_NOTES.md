| Check | Verdict | Finding |
| --- | --- | --- |
| 1. Nest minimum, cache key, slice sizes | CONFIRMED | Independent exhaustive tiny-graph enumeration agrees; sound for the stated, fixed graph model. |
| 3. Copies reserve no buffer / are only aliases | REFUTED | Both implementations model copy storage reservations and movement; alias deduplication does not mean zero occupancy. |
| 4. Only intermediates are shared | REFUTED | Upstream includes shared graph inputs in `fusable_tensors`. Snowcat's backing-storage policy explains the copy benefit. |
| 4. Saved shared-input 96 B versus 80 B comparison | UNRESOLVED | The supplied files contain only the copy case's 80 B result, not the uncopied 96 B or detailed comparison. |
| 6. Raw scores and plateaus | CONFIRMED | All requested numbers and the complete `heldout_scores.json` object reproduce independently. |
| 2. F4's extra 4 B (source analysis only) | UNRESOLVED | Early `CopydY` lifetime is a concrete candidate: imposing it changes 149 to exactly 153 B. No saved mapping proves attribution. |

Reviewed offline, without importing/running AccelForge or using `evaluate.py`. Source abbreviations below: `R/` = `research/index_coupling/`, `U/` = `../accelforge/accelforge/`, `F/` = this fork's `accelforge/`. `git -C ../accelforge rev-parse HEAD` returned `04cf894e3f33aae6ea9814104a852c160f4d9e25`; its tracked source is clean. Check 5's FFM replay is outside the requested runnable scope and remains unvalidated.

**1. Independent nest check.** `/tmp/index_coupling_review_enum.py` builds the two coupling variants and the chain `X=AB; U=XC` independently. It exhausts consecutive partitions and every common, unsliced loop variable, including Cartesian combinations of sibling alternatives, without memoization or minimum-cost pruning. Storage is a set of explicit `(tensor, coordinate)` cells; sibling lifetimes run from first through last use. This checks allocation sizes without calling `Graph.size`, `Graph.tensors`, or the model's recurrence. Symmetric loop iterations use coordinate zero. Terminal arithmetic on already resident tensors needs no further allocation.

Command from the repository root:

```sh
PYTHONPATH="$PWD" python3 -B /tmp/index_coupling_review_enum.py
```

```text
n=2 same: exhaustive=7 plateau=7 nests=414
n=2 cross: exhaustive=7 plateau=7 nests=414
n=2 chain: exhaustive=7 plateau=7 nests=46
n=3 same: exhaustive=13 plateau=13 nests=414
n=3 cross: exhaustive=13 plateau=13 nests=414
n=3 chain: exhaustive=13 plateau=13 nests=46
```

An additional sweep of all 16 assignments of `{2,3}` to `(I,J,K,L)`, both coupling variants, gave `mixed 2/3 coupling shapes matched: 32` using the same enumerator.

The cache is local to one `plateau(graph)` call (`R/nest_model.py:45–50`). For fixed, consistent projections and sizes, `ops` determines accesses and legal loop indices; `sliced` determines every remaining tile; `external` identifies allocations already charged by ancestors. The return value is **additional** peak, so differing ancestor allocation sizes with the same key do not change it. Their costs are added outside the cached call (`:71–86`). Ancestor loop order cannot change these unit-slice sizes or the allowed remaining choices. No missing state was found within these assumptions; this is not a general affine/tiled execution proof.

`Graph.size` removes only already sliced dimensions (`:37–39`), and both cross-group and held allocations use the *parent* slice (`:71,83`). For `X[I,K]`, the explicit checks printed `4 -> 2 -> 1` at n=2 and `9 -> 3 -> 1` at n=3 for no slice, I sliced, and I/K sliced. Charging the original whole matrix after slicing would overcount; charging after the newly opened loop would undercount its lifetime. The printed witness omits arithmetic loops once all unheld tensors are scalar (`:50–53`); `scalars ()` does not mean the operations themselves disappear.

**3–4. Copy semantics and shared inputs.** In the fork, `convert_to_copy` renames holders to the source and merges same-memory holders (`F/model/_looptree/reuse/symbolic/symbolic.py:452–487`). Copy compute returns no arithmetic/buffet work (`:1228–1240`), but reservation insertion still runs (`:500–505`), and `analyze_reservation` computes nonzero tile occupancy (`:1185–1213`). Occupancies feed buffer totals even for copies (`F/mapper/FFM/_make_pmappings/make_pmappings_from_templates/run_model.py:116–145`).

Upstream explicitly requires a copy's same-memory holders to share tiling (`U/model/_looptree/reuse/symbolic/_symbolic.py:123–145`), inserts reservations (`:173–183`), and combines copy buffet statistics by their minimum, including zero for no movement (`:281–294`). `U/model/run_model.py:175–216` counts those occupancies. Aliases share one reservation, retained until all aliases die (`U/mapper/FFM/_join_pmappings/pmapping_group.py:91–116`). Thus copies can avoid a *duplicate* buffer and can be no-ops at the same location; they are not universally buffer-free or movement-free. `R/nest_model.py:123–125` overstates this equivalence.

The cited intersection exists at `U/mapper/FFM/_make_pmappings/make_pmappings.py:174–176`, but **it is not the fusable set**. That comes from `shared_tensor_names()` (`:95,148`), which includes every tensor accessed by multiple einsums (`U/frontend/workload.py:1146–1159`). The intersection separately constrains recomputation/loop placement (`U/mapper/FFM/_make_pmappings/make_pmapping_templates/make_loops.py:201–208,357–378`). The fork likewise selects multi-einsum tensors (`F/mapper/FFM/_make_pmappings/make_pmappings.py:86`; `F/frontend/workload.py:800–803`).

The narrower Snowcat explanation is supported: `../accelforge/examples/arches/snowcat.yaml:23–28` requires MainMemory to keep `~Intermediates`; GlobalBuffer keeps all (`:42–44`). A graph input therefore has its shared backing at DRAM, while a copy creates a produced-and-consumed tensor eligible for buffer backing (`R/shared_input.yaml:9–21`; `U/frontend/workload.py:703–708`). Joining sums per-einsum energy; shared-reservation deduplication does not subtract duplicate input-read energy (`U/mapper/FFM/_join_pmappings/pmapping_dataframe.py:741–777`). For n=4, reading X twice costs `2*16 + 4*16 = 96 B`; once costs `5*16 = 80 B`.

However, `R/results/upstream_probe.jsonl:1–5` contains only same, cross, the two diamonds, and GPT. Its 96 B entries are **different workloads**, with six boundary matrices. `R/results/upstream_nodetail.jsonl:3` records only `shared_input_copy`, ending at `(21,80)`, without actions or detailed evaluation. The absent uncopied/detailed records prevent an empirical 96-versus-80 or row-for-row confirmation. The separate FFN 384-versus-256 minima *are* recorded (`upstream_nodetail.jsonl:4,1`).

**6. Independent scoring.** `/tmp/index_coupling_review_scores.py` parses every result JSON/JSONL, sums boundary tensors, selects the smallest capacity attaining that floor, and derives P3 predicates from the action-key suffixes. It does not import `evaluate.py`. All fork frontier action sums also equal their reported traffic. Command: `PYTHONPATH="$PWD" python3 -B /tmp/index_coupling_review_scores.py`.

| Case | Boundary traffic B | Plateau B | Nest prediction B | Raw evidence under `R/results/` |
| --- | ---: | ---: | ---: | --- |
| T1 same / cross | 6144 | 1057 / 1057 | 1057 / 1057 | `T1_same.json:3795`, `T1_cross.json:4261` |
| T2 same / cross | 1728 | 201 / 201 | 201 / 201 | `T2_same.json:2428`, `T2_cross.json:3038` |
| T3 same / cross | 3840 | 265 / 265 | 265 / 265 | `T3_same.json:3068`, `T3_cross.json:3134` |
| C1 same / cross | 960 | 337 / 337 | 337 / 337 | `C1_same.json:3668`, `C1_cross.json:3520` |
| C2 same / cross | 960 | 37 / 37 | 37 / 37 | `C2_same.json:1362`, `C2_cross.json:1912` |
| F1 M16 D4 F8 | 384 | 147 | 148 | `ffn_heldout.jsonl:1` |
| F2 M4 D4 F16 | 320 | 81 | 81 | `ffn_heldout.jsonl:2` |
| F3 M8 D2 F16 | 192 | 75 | 76 | `nest_heldout_ffn.jsonl:1` |
| F4 M16 D8 F4 | 640 | 153 | 149 | `nest_heldout_ffn.jsonl:2` |

FFN's boundary sum is `4*M*D + 4*D*F`, from inputs X/W1/W2/dY and outputs Y/dW2/dW1/dX (`R/ffn_train.yaml:18–65`). These are joined values, not replayed executions.

```text
T1: P1=True P2=True P3=4/5 P3prime=2/2 misses=[(273, 15360.0, 14336.0)] onset=273
T2: P1=True P2=True P3=7/7 P3prime=4/4 misses=[] onset=None
T3: P1=True P2=True P3=1/1 P3prime=0/0 misses=[] onset=None
heldout_scores.json: exact full-object match (all 3 cases, 13 P3 checks)
```

T3's stored `P3_prime=false` means no qualifying point, not a counterexample. F1 passes P5/P6; F2 passes P5 and misses P6 by 1 B. P7 remains indirect, as the README acknowledges. P8 is 4/6 exact; P8′ is 5/6 within 2 B. The nine calibration points are 7 exact and all within 1 B. All seven n=16 README table rows also match raw envelopes. This command returned no diff (exit 0):

```sh
python3 -B -m research.index_coupling.nest_model | diff -u research/index_coupling/results/nest_scores.txt -
```

**2. F4: evidence and a specific hypothesis.** Printing `plateau(ffn(16,8,4), witness=True)` gives outer M with `{W1,W2,dW1,dW2}=128 B`. The peak inner group is `(EdW2,EdZ)` under E, holding X=8, H=4, Z=4, dZ=4 and scalar dY=1: `128+21=149`. This schedule first fetches dY at its consumers.

The actual workload places `CopydY` **before EH** (`R/ffn_train.yaml:18–24`). Upstream preserves workload ordering in pmapping groups (`U/mapper/FFM/_make_pmappings/make_pmappings.py:423`; `_join_pmappings/join_pmappings.py:803–818,916–948`). Shared tensors must match loop prefixes and tile shapes (`_join_pmappings/compatibility.py:35–40`; `pmapping_dataframe.py:574–586`); permutations cannot cross reservations (`compatibility.py:594–601`). In particular, `merge_next` rejects a live left compatibility deeper than the next non-copy's (`:549–568`). Copy exceptions apply when the **right** operand is a copy; EH is not one. Rank translation and intermediate-loop relevance impose further checks (`rank_variable_translation.py:49–109`; `_make_pmappings/make_pmapping_templates/make_loops.py:201–208`). These are constraints absent from the alias-only nest model.

**Hypothesis:** an already produced dY scalar would need an M/E loop carried from `CopydY` through EH/EZ, which lack E. Instead FFM may require the full 8 B token row live from the early copy through EdZ. With that lifetime, an EY peak is `128 + X(8) + H(4) + Z(4) + dY(8) + Y(1) = 153`. Splitting EdW2/EdZ can release Z before allocating dZ, so this is not simply adding 7 B to the old peak.

The following **model sensitivity experiment**, not an FFM run or proof of incompatibility, reproduces exactly that change:

```sh
python3 -B - <<'PY'
from research.index_coupling.nest_model import Graph, ffn, plateau
for dims in [(16,8,4),(8,4,8),(16,4,8),(4,4,16),(8,2,16)]:
    g = ffn(*dims)
    h = Graph(g.sizes, [('Read_dY', {'dY': ('M','E')})] +
              [(op, g.access[op]) for op in g.ops])
    print(dims, plateau(g), plateau(h))
PY
```

```text
(16, 8, 4) 149 153
(8, 4, 8) 148 148
(16, 4, 8) 148 148
(4, 4, 16) 81 81
(8, 2, 16) 76 76
```

The extra read-only pseudo-op tests only dY's earlier lifetime, not the complete copy mapspace. A different mapping, pruning, or reservation interaction could also explain the saved frontier. Neither this analysis nor the JSONL identifies the scalar responsible for the other cases' 1 B gaps.

**README claims needing qualification.**

- `:110–119`: “FFM shares only intermediates” is false as a general source claim; make this specific to Snowcat's backing policy. The uncopied shared-input measurement, detailed copy comparison, and FFN detailed-crash trace are absent from the supplied results. The recorded cross-diamond error (`upstream_probe.jsonl:4`) does not establish the FFN crash.
- `:152`: “FFM saves one scalar the model counts” is an unverified explanation of a numerical 1 B gap, not an identified buffer element.
- `:155–156`: 153 B is the saved frontier's result, not a proof that FFM cannot express 149 B. Moreover, no-detail **FFM objects do retain** per-einsum mappings and a lazy `MappingFromRow` (`U/mapper/FFM/_join_pmappings/join_pmappings.py:605–617,1323–1339`; `U/mapper/FFM/main.py:104–111`). It is the probe's JSON serialization that omits witnesses (`R/upstream_probe.py:44–55,82–88`); constructing one may still hit the merge failure.
- `:137–143`: “search-free” needs the qualification “no FFM search.” `plateau` explicitly enumerates partitions and loop choices with memoization (`R/nest_model.py:56–85`). Its verified minimum is over that restricted model, not all legal mappings. Numerical agreement alone does not validate copy equivalence or executable FFM witnesses.
