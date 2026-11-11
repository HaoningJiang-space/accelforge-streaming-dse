# Bounded top-level group-span diagnostic

This is an offline diagnostic of the existing grammar, not a new solver or
a general physical fusion-width theorem. Scope and checks below are written
before running it. No search rule or prior experiment verdict changes.

## Definition and interpretation

For an unconstrained chain **solve** state s, let U_k be its response when
every group selected by its first partition has at most k operators. Every
group retains its original exact group response, with the same extents,
residency, write ownership and v2 halving grammar. Boundary activation
retention uses the original whole-tensor contract at those extents.

Then U_1 >= U_2 >= U_3 >= F pointwise, and U_n = F for a span of n operators.
The hierarchy counts operators, including elementwise operators. It is not
a bound on simultaneous live tensors, contraction count or physical SRAM.
A common outer M loop over a long span is excluded when n > k, even when
its body has only small local groups. Descendants of an admitted top-level
group cannot enlarge its operator span.

The result applies to solve entry. It does not replace a larger group-entry
state, whose initial common-loop obligation cannot be discarded.

## A predicted semantic control

Use `ffn_stack(2, m=8, d=1, f=1)` (six operators), all four weights externally
resident, activation endpoints streamed. Caller-reserved weights are outside
the measured child capacity. At C=2 the predicted total traffic is:

| Response | F / U_6 | U_3 | U_2 | U_1 |
| --- | ---: | ---: | ---: | ---: |
| Total traffic | 16 | 32 | 48 | 96 |

A whole-span M loop executes one row at a time with two activation cells and
only compulsory endpoint traffic (16). A top-level cut at C=2 cannot retain
its whole eight-cell activation, so each cut adds 16 transfers. The minimum
numbers of cuts are respectively 0, 1, 2 and 5. All original tensor/loop
semantics are unchanged.

This control predicts why a small U_k can fail without a large live frontier:
it forbids a cheap shared row loop. It is a constructed control, not a held-out
prediction of the archived M8 results.

## Bounded archive study

Cases are exactly `ffn_forward_l1_m8`, `ffn_forward_l2_m8`, and the existing
tiny `ffn_forward_l4` control. Inspect every recognised chain solve state
with M > 1 in their existing C2 call archives. No new shapes or censuses.

1. Reconstruct U_1, U_2, U_3 and U_n by a chain boundary DP using the archived
   **group** responses, with full projected state keys. Missing responses
   fail the audit; never substitute solve for group or ignore ownership.
2. Require U_n = F and the nesting inequalities over complete breakpoints.
   Check U_1 against the already implemented singleton upper bound on the
   union of its and F's breakpoints. Verify the synthetic control separately
   with original constrained partitions and executor replay.
3. Report full-curve equality, including a separate nontrivial stratum n > k.
   M8-1 has only three operators: U_3 equality there is automatic, not evidence
   that longer graphs admit local fusion.
4. Report exclusive local work at equal states and the archived root work that
   would disappear if those states were free terminals, both alone and beyond
   existing unit-M terminals. The latter is a hypothetical zero-cost replacement,
   not an online saving or an implementable equality certificate.
5. Record distinct group interfaces requested, their residency multiplicity,
   and the union of their original dependency work. Time archive loading and
   composition separately. Archived response lookup is not fresh response
   construction; do not compare its timer to online native search as a speedup.

Stop after this diagnostic, regardless of coverage. Equality with the known
optimum is retrospective evidence, not a condition available before search.
Low coverage rejects this group-span restriction on the measured states, not
every possible local resource representation. No continuation threshold is
invented after seeing the result.
