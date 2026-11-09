"""Reading capacity-traffic staircases: Q(C), S(q) and the capacity gap dS(q).

A curve is a Pareto staircase of (capacity, traffic, ...) points, capacity
ascending and traffic descending; its last point is the plateau.
- traffic_at(C): least traffic within capacity C (Q_FFM(C) for an FFM archive,
  which may keep dominated records at equal capacity).
- capacity_for(q): least capacity whose extra traffic above the curve's own
  plateau is at most q. Every q >= 0 is reachable.
- delta(base, other): dS(q) = S_other(q) - S_base(q) at every breakpoint q of
  either curve, as (q, dS, S_base).
- gap_steps(base, other, q_hi): dS as exact step intervals on [0, q_hi], for
  integrated measures that do not depend on how many breakpoints a curve has.
"""


def traffic_at(capacity, points):
    return min((t for c, t, *_ in points if c <= capacity), default=float('inf'))


def capacity_for(points, q):
    base = points[-1][1]
    return min(c for c, t, *_ in points if t - base <= q)


def extra_traffic(points):
    return [t - points[-1][1] for _, t, *_ in points]


def delta(base, other):
    qs = sorted(set(extra_traffic(base)) | set(extra_traffic(other)))
    return [(q, capacity_for(other, q) - capacity_for(base, q), capacity_for(base, q)) for q in qs]


def sign(ds):
    signs = {(d > 0) - (d < 0) for _, d, _ in ds}
    return {frozenset({1}): 'cross needs more', frozenset({-1}): 'cross needs less',
            frozenset({0}): 'equal'}.get(frozenset(signs), 'mixed' if {1, -1} <= signs else
                                         'cross more or equal' if 1 in signs else 'cross less or equal')


def gap_steps(base, other, q_hi):
    qs = sorted(set(extra_traffic(base)) | set(extra_traffic(other)) | {0, q_hi})
    return [(lo, hi, capacity_for(other, lo) - capacity_for(base, lo)) for lo, hi in zip(qs, qs[1:])]


def positive_width(steps):
    return sum(hi - lo for lo, hi, gap in steps if gap > 0)


def compare_to_reference(model, reference):
    # (C, Q_ref(C), Q_model(C) - Q_ref(C)) on the union of breakpoints where the
    # reference is feasible.
    caps = sorted({c for c, *_ in reference} | {c for c, *_ in model})
    return [(c, traffic_at(c, reference), traffic_at(c, model) - traffic_at(c, reference))
            for c in caps if traffic_at(c, reference) < float('inf')]
