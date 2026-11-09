| Point | FFM capacity B | Model peak B | Simulated peak B | FFM DRAM B | Model DRAM B | Simulated DRAM B | FFM classification |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| L1: n4 cross | 6 | 6 | 6 | 288 | 272 | 272 | EXCLUDED in fork/upstream representation (E1) |
| L2: n8 cross | 19 | 19 | 19 | 1152 | 1088 | 1088 | EXCLUDED in fork/upstream representation (E1) |
| L3: n16 cross | 69 | 69 | 69 | 4608 | 4352 | 4352 | EXCLUDED in fork/upstream representation (E1) |
| L4: T1 cross | 265 | 265 | 265 | 18432 | 17408 | 17408 | EXCLUDED in fork/upstream representation (E1) |
| L5: C2 cross | 6 | 6 | 6 | 3392 | 3360 | 3360 | EXCLUDED in fork/upstream representation (E1) |
| L6: C2 cross | 11 | 11 | 11 | 2112 | 2080 | 2080 | EXCLUDED in fork/upstream representation (E1) |
| L7: attention 8,8,4,4 | 38 | 37 | 37 | 256 | 224 | 224 | UNRESOLVED in fork/upstream (E2) |
| L8: attention 16,4,4,8 | 37 | 37 | 37 | 368 | 336 | 336 | UNRESOLVED in fork/upstream (E2) |
| L9: attention 4,16,8,4 | 19 | 19 | 19 | 560 | 528 | 528 | UNRESOLVED in fork/upstream (E2) |
| L10: attention 4,16,8,4 | 37 | 37 | 37 | 368 | 336 | 336 | UNRESOLVED in fork/upstream (E2) |

All ten model-lower witnesses survive element-level execution. **No capacity, traffic, dependence, or recomputation bug was found in the tested witnesses.** The full run checked all **216** saved FFM comparison points, including all **206 equal** points, and reproduced the model's peak and traffic exactly at every point. Six cross-coupling witnesses require a form of sharing absent from FFM's backing-reservation representation. The four attention gaps remain UNRESOLVED: executable model witnesses alone do not prove why FFM missed them.

Reviewed offline on 2026-11-08, with Python 3.14.2 and the standard library only. This review implements HANDOFF tasks 1 and 2; it does not run AccelForge or perform task 3. The only files created by this review are this report and [simulate_nest.py](simulate_nest.py).

Source prefixes used below:

- `R/` = `research/index_coupling/` in this repository.
- `F/` = this repository's `accelforge/`, HEAD `efd6d83357870cb2e5ffb0fce180488abf916860`.
- `U/` = `../accelforge/accelforge/`, HEAD `7312a7d915625552bf6eb1db577941f8317b6ac7`.

These citations describe the source checkouts actually available here. In particular, upstream is newer than the `04cf894e` revision mentioned in README and the previous review. Saved FFM numbers are historical measurements, not newly reproduced searches against these HEADs. The saved attention frontiers are upstream results with detailed evaluation enabled (`R/results/attention_heldout.jsonl:1–3`); the coupling frontiers come from the fork.

**Independent execution and witness interpretation**

`simulate_nest.py` accepts `curve(graph, witness=True)` witnesses. It does not implement the separate `plateau` witness format; the zero-extra-traffic endpoints below are curve witnesses. Its comparison driver alone imports `curve_model`, to obtain witnesses and claimed numbers. The parser and executor read only graph declarations and witness annotations, never `curve_model.size`, `Graph.size`, the cost recurrences, or compulsory/extra-traffic arithmetic.

The witness is a flat preorder list without closing markers or explicit terminal operations. I chose these semantics:

1. A `groups` record splits operations into consecutive siblings. A tensor marked `kept` reserves every concrete cell of the current tile from its first through its last using sibling, including intervening siblings.
2. A `loop` record iterates contiguous, ascending blocks of the stated tile length. Its `kept` tensors reserve their current tiles around the entire loop. `refetched` tensors receive no reservation at that level; descendant reservations end normally on each trip.
3. An omitted leaf executes every remaining coordinate of each operation, in graph order. Remaining rank variables are sorted and iterated lexicographically. “No more unheld nonscalar tensors” does **not** mean “no arithmetic”: reductions over tensors already held by ancestors still execute.
4. Reservations count even before an output is initialized or an input is first fetched. Payload is loaded on first access. The machine has an explicit `set[(tensor, index_tuple)]` for all reserved buffer cells, a resident-value dictionary, and a separate DRAM dictionary. There is no uncharged cache.
5. When a reservation ends, a dirty value is written if a future consumer/reduction needs it, or it is a graph output. Clean data can be discarded; later use causes an actual DRAM read. A dead final intermediate can be discarded. Static remaining-use counts tell the machine whether a value is dead; they do not store its numeric payload.
6. “Via DRAM” specifies passage between siblings, not an obligation to reload in a consumer that still shares the producer's buffer scope. Thus an X tile can feed EU locally, then be written once before its reservation ends for later EV. This is the write-through behavior discussed in README; delaying that write until eviction changes neither traffic nor peak.
7. Every cell is one abstract byte, as in these INT8 cost graphs; Python integers are used for arithmetic validation without overflow. A scalar MAC updates its already reserved accumulator and adds no modeled workspace. Unary operations, including ESoft, are implemented as identity maps. This checks the supplied **elementwise** attention abstraction; it does not validate real normalized softmax or its additional state.

The machine independently enumerates every operation's full coordinate domain, records each executed contribution, and rejects duplicate or missing iterations. Before **every consumer read**, it checks that a produced cell has received all contributions from its full, original reduction domain, not just its current tile. Accumulator reloads are the only reads permitted to use partial results. DRAM stores carry a contribution-version number; reloading stale or missing state fails. Final graph outputs must be written to DRAM and numerically equal a separate untiled, topological reference execution.

Implementation evidence: explicit cell enumeration `R/simulate_nest.py:72`; witness parsing `:96`; event generation `:143`; final-value and DRAM-load checks `:221`; scalar arithmetic `:243`; individual stores on release `:258`; complete-domain and numeric-output checks `:273`.

The full run executed **4,621,568 scalar operations**, performed **9,240,768 consumer-read checks**, and checked **136,832 final graph-output cells** across the 216 executions. It found zero peak mismatches and zero traffic mismatches, not merely results within the FFM capacity. For L7, the model's actual peak is **37 B**, although the comparison is at FFM's **38 B** point.

The built-in independent control has two X elements, each reduced over two A elements, followed by Y=X. Explicitly evicting each partial and each final X gives peak 2, reads A:4/X:4, writes X:4/Y:2, total **14**; X has two partial reads and two partial writes. Deliberately consuming X after only one of its two reductions, and deliberately executing the same reduction twice, are both rejected (`R/simulate_nest.py:314`). These checks exercise the conditions that a purely symbolic size calculation would miss.

**Per-tensor evidence for all ten model-lower points**

| Point | DRAM reads by tensor (B) | DRAM writes by tensor (B) | First peak: reserved cells by tensor |
| --- | --- | --- | --- |
| L1 | A:16, B:64, C:64, D:16, X:64 | U:16, V:16, X:16 | A:1, B:1, X:4 |
| L2 | A:64, B:256, C:256, D:64, X:256 | U:64, V:64, X:64 | A:2, B:1, X:16 |
| L3 | A:256, B:1024, C:1024, D:256, X:1024 | U:256, V:256, X:256 | A:4, B:1, X:64 |
| L4 | A:1024, B:4096, C:4096, D:1024, X:4096 | U:1024, V:1024, X:1024 | A:8, B:1, X:256 |
| L5 | A:128, B:512, C:1024, D:256, X:1024 | U:256, V:128, X:32 | A:1, B:1, X:4 |
| L6 | A:128, B:256, C:512, D:256, X:512 | U:256, V:128, X:32 | A:2, B:1, X:8 |
| L7 | K:64, Q:64, V:64 | O:32 | K:1, O:16, Q:4, S:16 |
| L8 | K:16, Q:64, V:128 | O:128 | A:16, K:16, Q:4, S:1 |
| L9 | K:256, Q:128, V:128 | O:16 | K:1, O:8, Q:2, S:8 |
| L10 | K:128, Q:128, V:64 | O:16 | K:1, O:16, Q:4, S:16 |

All ten have **zero partial-sum DRAM reads and writes**. Their traffic differences therefore do not hide an omitted partial spill. Every X read in L1–L6 is a final-value read by EV; EU uses the buffered producer tile. Every S and A in L7–L10 is consumed only after its producer has finished that element.

For L1–L4 the EX/EU row-block heights are respectively 1, 2, 4, 8; their resident X tiles contain 4, 16, 64, 256 cells. C2 is `I,J,K,L = 8,16,4,32`; L5 and L6 use row-block heights 1 and 2, with 4 and 8 resident X cells. The execution is:

```text
for each I block:
    reserve X[I block, all K]
    execute EX for the entire block, including every J reduction
    execute EU for the block, reading final X from that reservation
    write each X cell once to DRAM before releasing the X block
execute EV separately, loading final X tiles from DRAM
```

The detailed leaf loops for EX, EU and EV come from the witness, not this abbreviated sketch. The observed peak in each of these six runs occurs during EX, with X plus one A slice and one B scalar, as recorded above.

The attention witnesses have these distinct lifetimes:

| Point | Outer tile schedule | Retained intermediate/accumulator state | Producer-before-consumer check |
| --- | --- | --- | --- |
| L7 | M blocks of 4; P blocks of 4 | O[4,4] across all P blocks; S[4,4] through ES then ESoft/EO | All 4 E contributions to each S finish before ESoft; O becomes final only after all 8 P contributions. |
| L8 | M blocks of 4, with K retained across the whole run | K[4,4]; A[4,4] through ES/ESoft then EO | Each S receives all 4 E contributions; EO sees final A and accumulates all 4 P contributions. |
| L9 | M blocks of 2; P blocks of 4 | O[2,4] across all P blocks; S[2,4]; A[2,1] in the consumer subnest | Each S receives all 8 E contributions; O is not final until all 16 P contributions. |
| L10 | P blocks of 4, all 4 M rows | O[4,4] across the run; S[4,4] through ES then ESoft/EO | Each S receives all 8 E contributions; O is not final until all 16 P contributions. |

In L8 the raw witness has adjacent M splits (16→8→4); K is allocated outside the outermost split and the A tile inside the second. The above description collapses adjacent iteration levels only for readability. L9 and L10 similarly have adjacent P splits before the S reservation.

**Equal-point evidence across 19 different graphs**

Two equal points per graph are shown: the middle saved equal point and the final zero-extra-traffic point. All 38 appear in the full run, and all remaining 168 equal points also passed. These include materialized intermediates, refetches, partial-sum spills, and fully buffered intermediates.

| Equal-point graph | FFM capacity B | Model / simulated peak B | FFM / model / simulated DRAM B | Simulated reads B | Simulated writes B |
| --- | ---: | ---: | ---: | ---: | ---: |
| n4 same | 7 | 7 / 7 | 224 / 224 / 224 | 160 | 64 |
| n4 same | 21 | 21 / 21 | 96 / 96 / 96 | 64 | 32 |
| n4 cross | 11 | 11 / 11 | 160 / 160 / 160 | 112 | 48 |
| n4 cross | 21 | 21 / 21 | 96 / 96 / 96 | 64 | 32 |
| n8 same | 11 | 11 / 11 | 1280 / 1280 / 1280 | 1024 | 256 |
| n8 same | 73 | 73 / 73 | 384 / 384 / 384 | 256 | 128 |
| n8 cross | 11 | 11 / 11 | 1344 / 1344 / 1344 | 1088 | 256 |
| n8 cross | 73 | 73 / 73 | 384 / 384 / 384 | 256 | 128 |
| n16 same | 21 | 21 / 21 | 6912 / 6912 / 6912 | 6144 | 768 |
| n16 same | 273 | 273 / 273 | 1536 / 1536 / 1536 | 1024 | 512 |
| n16 cross | 21 | 21 / 21 | 6912 / 6912 / 6912 | 6144 | 768 |
| n16 cross | 273 | 273 / 273 | 1536 / 1536 / 1536 | 1024 | 512 |
| T1 same | 37 | 37 / 37 | 39936 / 39936 / 39936 | 36864 | 3072 |
| T1 same | 1057 | 1057 / 1057 | 6144 / 6144 / 6144 | 4096 | 2048 |
| T1 cross | 37 | 37 / 37 | 39936 / 39936 / 39936 | 36864 | 3072 |
| T1 cross | 1057 | 1057 / 1057 | 6144 / 6144 / 6144 | 4096 | 2048 |
| T2 same | 19 | 19 / 19 | 7680 / 7680 / 7680 | 6656 | 1024 |
| T2 same | 201 | 201 / 201 | 1728 / 1728 / 1728 | 704 | 1024 |
| T2 cross | 21 | 21 / 21 | 7232 / 7232 / 7232 | 5632 | 1600 |
| T2 cross | 201 | 201 / 201 | 1728 / 1728 / 1728 | 1152 | 576 |
| T3 same | 21 | 21 / 21 | 13056 / 13056 / 13056 | 12288 | 768 |
| T3 same | 265 | 265 / 265 | 3840 / 3840 / 3840 | 3328 | 512 |
| T3 cross | 21 | 21 / 21 | 13824 / 13824 / 13824 | 12288 | 1536 |
| T3 cross | 265 | 265 / 265 | 3840 / 3840 / 3840 | 2560 | 1280 |
| C1 same | 37 | 37 / 37 | 4160 / 4160 / 4160 | 3392 | 768 |
| C1 same | 337 | 337 / 337 | 960 / 960 / 960 | 704 | 256 |
| C1 cross | 37 | 37 / 37 | 4288 / 4288 / 4288 | 3392 | 896 |
| C1 cross | 337 | 337 / 337 | 960 / 960 / 960 | 576 | 384 |
| C2 same | 7 | 7 / 7 | 3072 / 3072 / 3072 | 2048 | 1024 |
| C2 same | 37 | 37 / 37 | 960 / 960 / 960 | 448 | 512 |
| C2 cross | 19 | 19 / 19 | 1824 / 1824 / 1824 | 1408 | 416 |
| C2 cross | 37 | 37 / 37 | 960 / 960 / 960 | 576 | 384 |
| attention 8,8,4,4 | 16 | 15 / 15 | 416 / 416 / 416 | 384 | 32 |
| attention 8,8,4,4 | 74 | 74 / 74 | 128 / 128 / 128 | 96 | 32 |
| attention 16,4,4,8 | 11 | 11 / 11 | 624 / 624 / 624 | 432 | 192 |
| attention 16,4,4,8 | 56 | 56 / 56 | 240 / 240 / 240 | 112 | 128 |
| attention 4,16,8,4 | 16 | 16 / 16 | 624 / 624 / 624 | 560 | 64 |
| attention 4,16,8,4 | 56 | 56 / 56 | 240 / 240 / 240 | 224 | 16 |

For example, at `n4 same / 7 B`, the simulator reads U:16 and V:16 partial bytes and writes U:32 and V:32, of which 16 each are partial writes. At `attention 4,16,8,4 / 16 B`, it reads O:48 partial bytes and writes O:64, of which 48 are partial writes. These are counted transactions, not an added spill-cost formula.

**E1 — why L1–L6 are excluded from FFM's representation**

This is an exclusion of these particular witnesses under the two-level Snowcat setup, not proof that no other FFM mapping could attain the same numerical point.

FFM can store a tensor at more than one memory level. The relevant restriction is that **only its first/backing reservation is the shared inter-einsum identity**. A lower cache copy is not a second independently shared channel.

| Mechanism | Fork evidence | Upstream evidence |
| --- | --- | --- |
| First storage placement alone gets `_backing` | `F/mapper/FFM/_make_pmappings/make_pmapping_templates/make_storages.py:101–108` | `U/mapper/FFM/_make_pmappings/make_pmapping_templates/make_storages.py:123–130` |
| Compatibility records only the first reservation of each shared tensor; subsequent copies are skipped | `F/mapper/FFM/_join_pmappings/compatibility.py:533–550` | `U/mapper/FFM/_join_pmappings/compatibility.py:695–712` |
| Tensor compatibility includes memory resource and its loop prefix | `F/mapper/FFM/_join_pmappings/compatibility.py:143–154,582–588` | `U/mapper/FFM/_join_pmappings/compatibility.py:203–217,35–40` |
| Joining matches compatibility buckets, including those tensor identities | `F/mapper/FFM/_join_pmappings/pmapping_group.py:224–234`; `F/mapper/FFM/_join_pmappings/join_engine.py:282–288` | `U/mapper/FFM/_join_pmappings/pmapping_group.py:276–285`; `U/mapper/FFM/_join_pmappings/join_pmappings.py:1031–1039` |
| Reconstructing a joined tree shares loops only above shared backing reservations | `F/frontend/mapping/mapping.py:931–951` | `U/frontend/mapping/mapping.py:1070–1099` |

Apply those rules to each of L1–L6:

- If X has MainMemory backing in all three einsums, its shared backing reservation is above the loops. X is their only shared tensor, so EX and EU have **zero shared loops** under the cited reconstruction rule. The local EX→EU tile handoff in the witness is unavailable. Merely adding a GlobalBuffer copy does not create a second compatibility identity.
- If EX and EU instead choose GlobalBuffer backing below their I-block loop to obtain that handoff, EV's later MainMemory-backed X has a different resource/prefix identity and cannot join it. Choosing GlobalBuffer backing for EV as well would require a common loop/lifetime across EV, replacing the witness's separate DRAM-fed EV stage.
- Choosing both MainMemory and GlobalBuffer for X does not evade the first-reservation rule: MainMemory is first. Default outermost-memory placement is fixed (`F/frontend/mapper/ffm.py:80–88`; `U/frontend/mapper/ffm.py:103–110`), and same-tensor memory order is enforced (`F/mapper/FFM/_make_pmappings/make_pmapping_templates/make_storage_order.py:315–319`; `U/mapper/FFM/_make_pmappings/make_pmapping_templates/make_storage_order.py:395–399`).

Thus L1, L2, L3, L4, L5 and L6 each require X to serve as a shared buffer tile for EX/EU and as a separate DRAM channel for EV. The cited representation cannot encode both sharing scopes for that tensor. This supports **EXCLUDED**, beyond the README's original plausibility statement.

The model rule responsible for the *difference in mapspaces* is its composition of `via DRAM X` at the outer sibling split with `kept X` in the EX/EU child (`R/curve_model.py:74–90`). Simulation shows that this composition is physically executable and its traffic is correctly charged. It is **not a model-accounting bug**.

**E2 — L7, L8, L9 and L10 remain UNRESOLVED**

All four are valid executions of the stated graph and attain the claimed buffer/traffic. They do not use the mixed X-backing pattern above: S and A remain in the buffer. Source inspection did not establish a conclusive rejection of their exact per-einsum encodings.

The most concrete candidate is repeated fused tiling of one rank. In the abstract nest, L7, L9 and L10 have a P-block level above S and a finer P level toward A; L8 has an M-block level above A and a finer M level toward S. However, **counting textual witness loops is not enough to prove an FFM exclusion**: adjacent loops can collapse, omitted terminal loops must be reconstructed, storage nodes can be lowered, and FFM counts nontrivial tile relationships rather than raw witness records.

The inspected constraints are:

| Candidate constraint | Fork evidence | Upstream evidence | What remains unproved |
| --- | --- | --- | --- |
| Default maximum of one fused loop per rank variable | `F/frontend/mapper/ffm.py:65–66`; `F/mapper/FFM/_make_pmappings/make_pmappings_from_templates/make_tile_shapes.py:1518–1526,1770–1775,625–667` | `U/frontend/mapper/ffm.py:66–67`; `U/mapper/FFM/_make_pmappings/make_pmappings_from_templates/make_tile_shapes.py:2087–2095,2534–2539,938–983` | Which loops survive as counted nontrivial fused loops in an actual template for each witness. Upstream's check explicitly ignores integer tile-shape entries at 961–962; its last loop is set to integer 1 at 2098–2108. The default value alone is not a rejection proof. |
| Fusion labeling ends at shared backing; lowering affects that boundary | `F/model/_looptree/reuse/symbolic/symbolic.py:762–804` | `U/model/_looptree/reuse/symbolic/_symbolic.py:488–512` | The actual storage/reservation placement for each candidate's S and A. |
| Shared-prefix tile shapes must agree at joins | `F/mapper/FFM/_join_pmappings/pmapping_dataframe.py:617–637` | `U/mapper/FFM/_join_pmappings/pmapping_dataframe.py:563–589` | No concrete unequal pair of required S/A tile shapes was demonstrated. |

Consequently the per-point decisions are **L7 UNRESOLVED; L8 UNRESOLVED; L9 UNRESOLVED; L10 UNRESOLVED** for both inspected implementations. This leaves the explanation of the saved 32 B DRAM gaps open; it does not leave the model witnesses' execution costs untested. Demonstrating an actual rejected template or an accepted FFM encoding would be needed to change these classifications. The four saved frontiers alone cannot distinguish a mapspace restriction from pruning, scoring, or a different equally good mapping.

**Reproduction**

From the repository root; these commands write no files and do not import AccelForge:

```sh
# All 216 comparisons, including the ten lower points:
PYTHONHASHSEED=0 python3 -B -m research.index_coupling.simulate_nest --all

# The 48 rows covered by the two result tables above:
PYTHONHASHSEED=0 python3 -B -m research.index_coupling.simulate_nest

# Raw selected witness and every individual DRAM transfer:
PYTHONHASHSEED=0 python3 -B -m research.index_coupling.simulate_nest \
  --case 'n4 cross' --capacity 6 --witness --trace

# Hand-counted positive and negative controls only:
python3 -B -m research.index_coupling.simulate_nest --self-check
```

The full run's final line was:

```json
{"summary": {"points": 216, "lower": 10, "equal": 206, "model_bugs": 0}}
```

`PYTHONHASHSEED=0` fixes which tied witness is selected, since the model iterates a set of candidate loop variables. Each comparison selects the model witness with the least traffic among capacities no greater than the saved FFM capacity, exactly as the comparison envelope requires. The simulator accepts no claimed cost as an execution input.

For reproducibility, the reviewed model/source-data SHA-256 values are:

```text
curve_model.py             c93fd00e3f0e86ccacc7d8ef81fd72d5b30edb9343bc53f00405a8ac9f420fd1
nest_model.py              a9244eedea35c88fa3dec7dbd12fff433341bfa44072336ce33ef77fb83b12ea
compare_curves.py          f56f9d0969d41de7931119e2cca47d90ba6b353aaa88724205564e9630e59af7
results/curve_comparison.txt c524a2d18ed5293618dfe9f6bfbb840cd7d70910ce2a5c513aab3b57103400a9
```

The findings establish feasibility for the selected witnesses on these concrete sizes under the stated cell-storage interpretation. They do not prove the entire recursive model sound for every graph, establish global optimality, resolve FFN copy ordering, or resolve HANDOFF task 3.
