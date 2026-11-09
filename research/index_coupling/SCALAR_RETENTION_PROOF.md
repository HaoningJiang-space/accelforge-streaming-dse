# Cost-preserving scalar production under two residence scopes

This proves a restricted construction theorem, not completeness of arbitrary
nested fusion. Base `2b4d1b96`; motivating failures are already observed.

## Contract

Positive integer I,J,K,L, one-byte independently stored cells, exact arithmetic,
two memory levels, serial execution, no recomputation, no external consumer
of X. Compute X=AB (I×J times J×K), U=XC; either V=XD (same) or V=DX (cross).
The complete fork has inputs A,B,C,D and outputs U,V. No aliasing, banking,
parallel ports, alignment or communication-time objectives are introduced.
Every X cell completes its entire J reduction before either consumer reads it.
Only I/K strips change; J and L are complete within the specified scopes.

Write h=J+2L. A row strip has width r<=I, p=ceil(I/r); a column strip has
width c<=K, q=ceil(K/c). The last strip can be smaller.

## Theorem 1: row strip with scalar X

For each I strip reserve A[r,J] and (U[r,L],V[r,L]) for same, or
(U[r,L],D[L,r]) for cross. These r*h cells remain allocated across all K.
For each single k reserve B[J,k] and (C[k,L],D[k,L]) for same, or
(C[k,L],V[L,k]) for cross: h additional cells, retained across the strip's I.
For each i in the strip reserve one X[i,k], complete its J reduction, update
all L contributions to U and V, and release X. Release the k-slices after the
I loop; release the outer slices after the K loop.

The exact peak is S_scalar_row(r)=(r+1)h+1. The largest strip attains it.
Its reads/writes are exactly those of the existing nonretaining row-X-strip:

| Pattern | Reads | Writes |
| --- | --- | --- |
| same | A:IJ, B:pJK, C:pKL, D:pKL | U:IL, V:IL |
| cross | A:IJ, B:pJK, C:pKL, D:IL, V:(p-1)KL | U:IL, V:pKL |

Proof. Every A cell is fetched once during its single outer residence; every
B/C slice is fetched once per I strip and reused for its r rows. Same-pattern
D behaves like C, while U/V remain live through all their K contributions.
Cross D remains live through K, while V receives contributions from each I
strip: one store per strip and one reload for each strip after the first.
Each X is computed once, all consumers finish before release, and X never
enters DRAM. The iteration sets partition all MACs exactly once. This proves
both dependency legality and all transfers in the table. The allocations are
disjoint, overlap in the inner body, and sum to (r+1)h+1. Ragged tails only
reduce the last strip's peak; they do not change p or total element counts.

## Theorem 2: column analogue

Reserve B[J,c], C[c,L], and D[c,L] (same) or V[L,c] (cross) across I. For
one i reserve A[i,J], U[i,L], and V[i,L] (same) or D[L,i] (cross) across the
c columns. Produce/consume X one cell at a time. Peak is (c+1)h+1.
Reads/writes equal the existing nonretaining column-X-strip:

| Pattern | Reads | Writes |
| --- | --- | --- |
| same | A:qIJ, B:JK, C:KL, D:KL, U:(q-1)IL, V:(q-1)IL | U:qIL, V:qIL |
| cross | A:qIJ, B:JK, C:KL, D:qIL, U:(q-1)IL | U:qIL, V:KL |

The proof is the symmetric partition/lifetime argument. In cross, V completes
all its I contributions while retained; U spills between K strips. In same,
both U and V spill between K strips. No partial X is consumed.

## Corollary: choose the smaller live set before execution

For a fixed row width r, three constructions have IDENTICAL per-tensor traffic:

1. Retain the X strip: r(K+1)+1.
2. Retain outer operand/output slices, vector X: r(h+1)+1.
3. Retain slices at two scopes, scalar X: (r+1)h+1.

Consequently their best peak is

    S_row(r) = 1 + min(r(K+1), r(h+1), (r+1)h).

For columns replace r,K by c,I. When r>=h the scalar construction weakly
dominates the vector-X operand construction; when r<=h the reverse holds.
The scalar construction need not dominate retention of X or other mappings.
This is an executable upper bound on the unrestricted optimum, not a lower
bound or an assertion that all other retention masks may be discarded.

The two prior misses follow without fitting parameters:
- (16,2,64,4), cross, rows r=16: h=10, peak=171 and traffic=800.
- (64,4,64,8), cross, columns c=32: h=20, peak=661 and traffic=4352.

## Theorem 3: eliminate strip-width search for a capacity query

Consider ONLY the six families above (three row, three column), all integer
widths. Let B be an integer capacity. For rows, the largest feasible width is

    r_max = min(I, max(floor((B-1)/(K+1)),
                      floor((B-1)/(h+1)), floor((B-1)/h)-1)).

If r_max<1 there is no feasible row candidate. Replace I,K for columns.
All row costs are alpha*ceil(I/r)+beta with positive alpha:

    same:  alpha=K(J+2L), beta=IJ+2IL
    cross: alpha=K(J+3L), beta=IJ+2IL-KL.

Columns have positive alpha=I(J+4L) (same) or I(J+3L) (cross), with
beta=JK+2KL-2IL (same), beta=JK+2KL-IL (cross).
Therefore the largest feasible width minimizes traffic. For equal traffic,
choose its smallest width ceil(I/p), p=ceil(I/r_max), and the representation
with smallest peak; this is the nondominated representative. Compare the two
directions. For a power-of-two-plus-full-extent grid, round r_max down to the
largest allowed width, and round the equal-traffic lower endpoint up to the
smallest allowed width. Those roundings preserve the same argument.

No Mapping list, resource table, recursive model or candidate frontier is
needed for this query: a constant number of integer operations, hence O(1)
in an arithmetic-operation model (not unit-bit complexity for unbounded ints).
The correctness is exact only inside these six families.

## Corollary: full frontier in O(sqrt(I)+sqrt(K)) representatives

ceil(n/r)=floor((n-1)/r)+1 takes O(sqrt(n)) distinct values. Within each
constant-quotient interval all traffic is identical; each of the three peak
functions is increasing, so retain only the smallest width. Starting at r=1,
advance to floor((n-1)/(p-1))+1 for p=ceil(n/r)>1; finish when p=1. Evaluate
three peak expressions and keep their minimum at each interval start.
Thus only O(sqrt(I)+sqrt(K)) plans precede the 2D skyline (sorting adds a
logarithmic factor). Power-of-two grids already use O(log I+log K) widths.
These bounds concern formula construction, not the time to execute MACs.

## What is not proven

This is a normal form for three specified residence alternatives per strip,
not a normal form for all legal loop nests. It does not prove a small separator
for arbitrary DAGs, a bound on quality relative to the recursive model, direct
FFN applicability, native FFM generation savings, or new hardware timing/area
results. It also makes no literature novelty claim. Independent finite tests
validate the implementation; the arbitrary-size argument is the proof above.
