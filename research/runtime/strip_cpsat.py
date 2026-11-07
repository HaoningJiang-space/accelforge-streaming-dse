"""Independent OR-Tools CP-SAT encoding of the full strip co-design grammar."""

from math import gcd

from ortools.sat.python import cp_model

from research.joint_budget.protocol import Hardware
from research.runtime.strip_codesign import (
    CAPACITIES, COMPUTE, DRAM, GB_READ, GB_WRITE, GEOMETRIES, PE_COUNT,
    Segment, ceildiv, evaluate, representatives,
)


def common_incumbent(rows, widths, capacities, geometries):
    """A legal fully fused, streamed schedule for setting safe objective bounds."""
    pairs = list(zip(widths, widths[1:]))
    seeds = []
    for x, y in geometries:
        tiles = tuple((min(k, y), min(n, x)) for k, n in pairs)
        b = min(rows, *((capacities[-1] - p * q) // (k + n)
                        for (p, q), (k, n) in zip(tiles, pairs)))
        if b > 0:
            hardware = Hardware(x, y, capacities[-1])
            plan = (Segment(0, len(pairs), b, (False,) * len(pairs), tiles),)
            cost, _ = evaluate(rows, widths, hardware, plan)
            seeds.append((cost, hardware, plan))
    return min(seeds, key=lambda seed: seed[0][0] * seed[0][1])


def solve(rows, widths, budget, seconds, geometries=GEOMETRIES, seed=0,
          on_incumbent=None, initial_design=None):
    model = cp_model.CpModel()
    capacities = [c for c in CAPACITIES if c <= budget]
    pairs = list(zip(widths, widths[1:]))
    weights = [k * n for k, n in pairs]
    # Every energy and time term is a multiple of rows or a weight size.
    # Remove this exact common factor before forming the CP-SAT int64 product.
    scale = gcd(rows, *weights)
    scaled_rows = rows // scale
    last = len(pairs) - 1
    max_x, max_y = (max(values) for values in zip(*geometries))
    px = model.new_int_var_from_domain(cp_model.Domain.from_values([x for x, _ in geometries]), "px")
    py = model.new_int_var_from_domain(cp_model.Domain.from_values([y for _, y in geometries]), "py")
    model.add_allowed_assignments((px, py), geometries)
    cap = model.new_int_var_from_domain(cp_model.Domain.from_values(capacities), "capacity")
    cuts = [model.new_bool_var(f"cut{i}") for i in range(last + 2)]
    model.add(cuts[0] == 1)
    model.add(cuts[-1] == 1)
    pins = [model.new_bool_var(f"pin{i}") for i in range(last + 1)]
    bmax = min(rows, capacities[-1] // min(k + n for k, n in pairs))
    row_sizes = representatives(rows, bmax)
    left, right, b_vars, p_vars, q_vars = [], [], [], [], []
    energy_terms, time_terms = [], []
    for i, (k, n) in enumerate(pairs):
        w = weights[i]
        left.append(model.new_int_var(0, min(sum(weights[:i]), budget), f"left{i}"))
        right.append(model.new_int_var(0, min(sum(weights[i+1:]), budget), f"right{i}"))
        b = model.new_int_var_from_domain(cp_model.Domain.from_values(row_sizes), f"b{i}")
        p = model.new_int_var_from_domain(cp_model.Domain.from_values(representatives(k, max_y)), f"p{i}")
        q = model.new_int_var_from_domain(cp_model.Domain.from_values(representatives(n, max_x)), f"q{i}")
        b_vars.append(b)
        p_vars.append(p)
        q_vars.append(q)
        if i > 0:
            model.add(b == b_vars[i-1]).only_enforce_if(cuts[i].Not())
        model.add(p <= py)
        model.add(q <= px)

        # The representatives remove only larger tiles with identical block counts.
        km, nm, bm = (model.new_int_var(0, extent - 1, f"{name}{i}")
                      for name, extent in (("km", k), ("nm", n), ("bm", rows)))
        model.add_division_equality(km, k - 1, p)
        model.add_division_equality(nm, n - 1, q)
        model.add_division_equality(bm, rows - 1, b)
        repeats = model.new_int_var(0, rows - 1, f"reloads{i}")
        model.add(repeats == bm).only_enforce_if(pins[i].Not())
        model.add(repeats == 0).only_enforce_if(pins[i])

        scratch = model.new_int_var(1, min(k, max_y) * min(n, max_x), f"tile_bytes{i}")
        model.add_multiplication_equality(scratch, (p, q))
        live = left[i] + w * pins[i] + right[i] + (k + n) * b
        model.add(live <= cap).only_enforce_if(pins[i])
        model.add(live + scratch <= cap).only_enforce_if(pins[i].Not())

        waves = model.new_int_var(1, w, f"waves{i}")
        model.add_multiplication_equality(waves, (km + 1, nm + 1))
        dram = (w // scale) * (repeats + 1) + scaled_rows * (k * cuts[i] + n * cuts[i+1])
        reads = (w // scale) * (bm + 1) + scaled_rows * (k * (nm + 1) + n * km + n * cuts[i+1])
        writes = (w // scale) * (repeats + 1) + scaled_rows * (n * (km + 1) + k * cuts[i])
        energy_terms.append(dram * DRAM[0] + reads * GB_READ[0] + writes * GB_WRITE[0]
                            + scaled_rows * w * COMPUTE[0])
        time_terms.append(dram * DRAM[1] + reads * GB_READ[1] + writes * GB_WRITE[1]
                          + scaled_rows * waves * COMPUTE[1])

    for i in range(last + 1):
        if i > 0:
            model.add(left[i] == 0).only_enforce_if(cuts[i])
            model.add(left[i] == left[i-1] + weights[i-1] * pins[i-1]).only_enforce_if(cuts[i].Not())
        if i < last:
            model.add(right[i] == 0).only_enforce_if(cuts[i+1])
            model.add(right[i] == right[i+1] + weights[i+1] * pins[i+1]).only_enforce_if(cuts[i+1].Not())

    if initial_design is None:
        initial_design = common_incumbent(rows, widths, capacities, geometries)
    cost, hardware, (initial,) = initial_design
    incumbent = (cost[0] // scale) * (cost[1] // scale)
    compulsory = sum(weights) + rows * (widths[0] + widths[-1])
    macs = rows * sum(weights)
    low_e = ceildiv(compulsory * DRAM[0] + macs * COMPUTE[0], scale)
    low_t = ceildiv(compulsory * DRAM[1] + ceildiv(macs, PE_COUNT) * COMPUTE[1], scale)
    energy = model.new_int_var(low_e, incumbent // low_t, "energy")
    ticks = model.new_int_var(low_t, incumbent // low_e, "ticks")
    model.add(energy == sum(energy_terms))
    model.add(ticks == sum(time_terms))
    objective = model.new_int_var(low_e * low_t, incumbent, "edp")
    model.add_multiplication_equality(objective, (energy, ticks))
    model.minimize(objective)
    for var, value in [(px, hardware.px), (py, hardware.py), (cap, hardware.capacity_bytes)]:
        model.add_hint(var, value)
    normalized_b = next(b for b in row_sizes if ceildiv(rows, b) == ceildiv(rows, initial.rows))
    for i, (k, n) in enumerate(pairs):
        p, q = initial.tiles[i]
        model.add_hint(b_vars[i], normalized_b)
        model.add_hint(p_vars[i], next(t for t in representatives(k, max_y) if ceildiv(k, t) == ceildiv(k, p)))
        model.add_hint(q_vars[i], next(t for t in representatives(n, max_x) if ceildiv(n, t) == ceildiv(n, q)))
        model.add_hint(pins[i], False)
        model.add_hint(cuts[i], i == 0)
    model.add_hint(cuts[-1], True)

    def witness(v):
        plan = []
        start = 0
        for stop in range(1, last + 2):
            if v(cuts[stop]):
                plan.append(Segment(start, stop, v(b_vars[start]), tuple(bool(v(pins[i])) for i in range(start, stop)),
                                    tuple((v(p_vars[i]), v(q_vars[i])) for i in range(start, stop))))
                start = stop
        point = Hardware(v(px), v(py), v(cap))
        actual, _ = evaluate(rows, widths, point, plan)
        if actual != (v(energy) * scale, v(ticks) * scale) or actual[0] * actual[1] != v(objective) * scale**2:
            raise AssertionError("CP-SAT result disagrees with common evaluator")
        return actual, point, tuple(plan)

    class Incumbents(cp_model.CpSolverSolutionCallback):
        def on_solution_callback(self):
            on_incumbent(witness(self.value))

    solver = cp_model.CpSolver()
    solver.parameters.num_workers = 1
    solver.parameters.random_seed = seed
    solver.parameters.max_time_in_seconds = seconds
    status = solver.solve(model, Incumbents() if on_incumbent is not None else None)
    stats = dict(status=solver.status_name(status), bound=solver.best_objective_bound * scale**2,
                 branches=solver.num_branches, conflicts=solver.num_conflicts)
    if status not in (cp_model.FEASIBLE, cp_model.OPTIMAL):
        if status != cp_model.UNKNOWN:
            raise ValueError(f"{stats}: {model.validate()}")
        return (cost, hardware, (initial,)), stats
    return witness(solver.value), stats
