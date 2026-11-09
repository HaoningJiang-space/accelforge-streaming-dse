# Constructive fork experiment

Start point: c82f2ee8. Run experiments only on the experiment server, in a separate checkout.
Existing FFN processes and frozen P11–P14 experiments are not changed.

The objective is to turn the observed capacity/traffic effect into executable
decisions without enumerating all recursive loop nests. This is an exploratory
small schedule family, not a new claim of completeness or novelty. Earlier
256-shape curves have already been seen. No result here is called held-out.

Family: row strips or column strips of X, with any subset of the three tensors
invariant across the outer strip loop retained; and whole-X execution with
strip-sized scratch for each matrix multiplication. Construct candidates from
shape and contraction axis alone. Use the same unit-byte, exact-integer,
no-recomputation execution semantics as the independent cell simulator.
No new simulator, FFM changes, or curve_model changes.

Evaluate both power-of-two strip choices and all integer strip widths, with
ragged final strips. The latter tests a wider grammar and is labeled separately.
Traffic/peak estimates must match explicit cell execution, including per-tensor
reads and writes, partial sums, numerical outputs and complete MAC coverage.

Measurements fixed before execution:

1. Execute every candidate on shapes (1,1,1,1), (2,3,4,5), (5,3,3,2),
   (4,4,4,4), both contraction patterns, including nondivisor strips.
2. Score all 256 archived shapes, both patterns, at every archived curve knot.
   Report uncovered capacities, matches, regressions and improvements; do not
   claim exactness only from the selected favorable points.
3. Target traffic: 9n² for n8 and n16; 3456 for (32,4,32,16); 3840 for
   the exception (32,8,32,4). Independently execute the chosen constructive
   schedule and a newly generated exact-nest witness for each pattern.
4. Also score, on every shape, the traffic achieved by a nonretaining row strip
   of width floor(I/2) in the same pattern. Compare least capacities at that
   target for both patterns. This target is not fitted per result.
5. Include construction time. A narrow constructive family is not the same
   optimization problem as exhaustive nest search: timing differences are
   time/quality measurements, never an exact-mapper speedup claim.

For an unretained row strip of width b, p=ceil(I/b), the proposed schedule has
S=bK+b+1. Its traffic is IJ+pJK+2pKL+2IL (same) and
IJ+pJK+(3p−1)KL+2IL (cross). Thus the fixed schedule's cross penalty is
(p−1)KL. These are constructive costs, not lower bounds for other schedules.
For square n with b=n/2, same uses n²/2+n/2+1 cells at 9n² traffic;
cross uses the same cells at 10n². Whole-X with scratch n/2+1 can attain
9n² at n²+n/2+1 cells. The archived complete nest frontier, not these
constructions alone, supplies the restricted-grammar minimality evidence.

These corrected formulas distinguish n/2 scratch from n scratch; some older
README prose used n while its tabulated values used n/2.
