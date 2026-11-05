# Oracle invariants and cross-shape differential gate

The `a986b381` review identified real missing checks that also remained in the
independent branch's `6d3d3c99` Oracle. Fixes were first pushed as `0b6ecea8`;
the follow-up below expands validation without adding a search mechanism.
Native FFM and the legacy research backends are unchanged.

## Execution invariants

- `address()` checks the complete View extent against a live allocation, and
  checks the local integer indices against that View. A 1×1 View of a 2×2 owner
  cannot access the owner's other elements. Negative/empty extents, noninteger
  indices and dangling owners are rejected. Copy/fill/MAC entry points validate
  views even when an invalid extent would otherwise produce an empty loop.
- Allocation checks positive integer dimensions, location/layout, exact
  rectangular initial shape and each signed integer value before changing the
  copy ID or occupancy. Initialization does not count as an executed access and
  does not retain mutable host-data aliases. Read-before-production is an error.
- `MatMul.precision` names operand, accumulator and output dtypes separately.
  The current grammar requires **uniform signed width, overflow='reject'**.
  Every MAC writes a checked accumulator value. The cancelling dot product
  `32767*2 + (-32767)*2` therefore fails at its first 16-bit MAC, as declared.
  Wider accumulators, wraparound and saturation are explicitly unsupported;
  adding them would require new allocation/action and resource rules.

The tests include initialization/write overflow, accumulation overflow with a
representable final result, valid signed limits, standalone uniform 8-bit MACs
and rejection of a 16/32/16-bit request. This clarifies the bounded model rather
than claiming to implement normal mixed-precision accelerator arithmetic.
Resource frontiers remain conditional on this numerical contract. They are not
a proof of numerical validity for arbitrary inputs. Failed execution is rejected;
the interpreter is not a transactional runtime after a failed MAC/copy.

## New full-grammar checks

`validate_oracle.py` uses fixed seeds to generate different strictly positive
integer cost coefficients. It runs the same independent execution/differential
protocol on new shapes, after production DP has finished. The Oracle does not
call production demand, composition, scheduling or frontier rules.

| Case `(M,K,N,P)` | Intermediate | Cost `(MAC,SRAM byte,DRAM byte,burst)` | Local checks | Complete executions | Root vectors | Hardware queries |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| (1,2,4,3) | 1×4 | (3,11,3,10) | 144 | 5,184 | 17 | 540 |
| (3,2,1,2) | 3×1 | (11,1,2,3) | 96 | 2,304 | 10 | 540 |
| (2,3,4,5) | 2×4 | (10,11,7,8) | 288 | 20,736 | 82 | 3,000 |
| Total | | | 528 | 28,224 | 109 | 4,080 |

Every local summary/action count and every complete composition agrees with the
scalar copy/MAC execution. The complete six-coordinate demand frontiers agree
with unpruned execution. Root plans are JSON-restored and re-executed with three
additional bounded input seeds. Post-DP hardware queries include all observed
peaks P−1/P/P+1 and bandwidths 1,2,3,5,8, comparing complete E/T fronts. A separate
test binds an executed plan at exactly its peak and at one byte less; only the
former is feasible. These are finite checks, not a proof across all shapes.

Row/column-major packing coincides for 1×N/N×1 tensors, but different layout tags
still use the declared explicit converter. Tests check both coincident packing
and nonzero converter cost. This conservative converter library does not cover
every legal or cheapest physical conversion.

## Real bandwidth-dependent winners

A regression now uses actual generated and independently executed plans rather
than only fabricated latency coefficients. For default-cost 2mm `(2,2,2,2)` at
fixed Px=1, Py=2 and SRAM=12 bytes:

| Winning at | Demand `(u,v,P,E,c,q)` | EDP at B=1 | EDP at B=1024 |
| --- | --- | ---: | ---: |
| low bandwidth | (1,1,12,592,40,48) | 52,096 | 23,707.75 |
| high bandwidth | (1,2,10,736,28,64) | 67,712 | 20,654 |

The first plan transfers fewer bytes, the second has fewer fixed cycles. Both
must remain available; choosing a local winner at one bandwidth is insufficient.
Arithmetic in the implementation/tests uses exact integers/Fractions.

## Reproduction and receipts

```sh
python -S -m research.joint_synthesis.validate_oracle --output research/joint_synthesis/results/oracle_shape_gate.json
python -S -m research.joint_synthesis.validate_architecture --output research/joint_synthesis/results/architecture_gate_hardened.json
python -m pytest -q research/joint_synthesis/tests --disable-warnings
```

- [oracle_shape_gate.json](results/oracle_shape_gate.json) records the new
  exhaustive cases, costs/seeds, full frontiers and top-level source fingerprints.
- [oracle_shape_tests.txt](results/oracle_shape_tests.txt) records **62 passing
  tests**, including prior tests. The 54-test hardening and 19/11/10-test receipts
  are historical overlapping subsets, not additional independent coverage.
- [architecture_gate_hardened.json](results/architecture_gate_hardened.json)
  reruns the four previous normalized hardware configurations with the hardened
  Oracle: complete H/E/T fronts and all 452 integer-budget queries still match.
  Historical receipts are retained, not overwritten.

No new search-speed, FFM-quality, calibrated-area, streaming or general-DAG claim
is made. The production FFM regression suite was not rerun because its code and
interfaces were not changed. This gate hardens the execution reference needed
before attempting a new streaming composition model.
