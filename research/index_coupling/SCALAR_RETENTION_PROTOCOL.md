# Frozen test of the scalar-retention theorem

Freeze proof, implementation and this protocol before evaluating new curves.
Keep all previous constructors, reference curve and independent simulator
unchanged. The two formerly worst points are calibration, not held-out wins.

1. Check exact per-tensor equality with original no-retention row/column strips
   for every integer width of all 256 development shapes, 31 archived held-out
   shapes, eight previous fresh shapes, and eight NEW shapes listed below.
2. Execute every scalar width/direction/pattern on a fixed small set including
   non-power-of-two dimensions; reject invalid widths/interfaces. Poison
   metrics() during one replay to check execution does not consult formulas.
3. Exhaustively compare the direct capacity query and quotient-compressed
   frontier with brute force over all integer widths for the six-family
   grammar on each test shape. Repeat for the power-of-two grid. Count formula
   evaluations and query/compile times, including construction. These checks
   cannot establish quality relative to a larger grammar.
4. Regression: rescore the original 78 instances with the new scalar family
   added to the unchanged reduced and full families. No held-out claim for
   these already observed instances. Exact curve comparison uses the same
   union of knots and integer-budget intervals as HELDOUT_PROTOCOL.
5. Fresh: both patterns of (4,1,16,2), (16,1,4,8), (32,1,32,2), (64,1,64,4),
   (8,16,32,1), (32,16,8,1), (16,32,64,2), (64,4,16,1). These J=1 or L=1/2
   cases include both small/large h and were not used to derive the rule.
   Build the recursive reference three times, constructors seven times rotated.
6. Execute fresh winning scalar plans at all their frontier knots. Independently
   replay both calibration witnesses. Record every error or unhandled case.

Quality gates remain maximum traffic excess <=10%, >=90% of integer budgets
within 5%, and zero uncovered reference-feasible budgets. Report the gates
separately from correctness. Do not repair misses inside this frozen run.
A direct six-family query can be fast while the families still miss the best
plan; never call that an exact native search speedup. FFN remains outside
this three-MatMul grammar.

Run on the designated server, at most four workers; 12 GiB per worker and
600 CPU seconds per case. Record source revision, data hashes and all times.
