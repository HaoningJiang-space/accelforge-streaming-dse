from dataclasses import replace
from itertools import product

import pytest

from research.joint_budget.protocol import Hardware
from research.runtime.dag_calendar import CheckedCalendar, events, replay
from research.runtime.dag_model import Graph, Group, Op
from research.runtime.dag_overlap_cost import score
from research.runtime import dag_overlap_search as search, dag_roofline


def diamond(rows=5):
    return Graph(rows, (("X", 3),), (
        Op("S", ("X",), 4), Op("A", ("S",), 2), Op("B", ("S",), 2),
        Op("J", ("A", "B"), 2, "add"),
    ))


def test_fork_join_preserves_fanout_and_finishes_tail_partials():
    graph, h = diamond(), Hardware(2, 3, 45)
    group = Group(("S", "B", "A", "J"), 3, ((3, 2), (3, 2), (3, 2), (0, 2)), (False,) * 4)
    result = replay(graph, h, events(graph, h, (group,)), numeric=True)
    assert score(graph, h, (group,)) == (result["energy"], result["ticks"])
    actions = result["actions"]
    assert actions["dram/X/read"] == 15
    assert actions["dram/J/write"] == 10
    assert actions["read/S/read"] == 40  # Shared SRAM producer read independently by both branches.
    assert actions["read/B/read"] == 20  # Prior sum and the pointwise join.
    assert not any(f"dram/{name}/write" in actions for name in ("S", "A", "B"))
    assert result["overlapped_waves"] > 0


def test_spilled_edges_cross_independent_row_bands():
    graph, h = diamond(), Hardware(2, 3, 48)
    plan = (
        Group(("S", "A"), 2, ((3, 2), (3, 2)), (False, False)),
        Group(("B", "J"), 3, ((3, 2), (0, 2)), (False, False)),
    )
    result = replay(graph, h, events(graph, h, plan), numeric=True)
    assert score(graph, h, plan) == (result["energy"], result["ticks"])
    for tensor, words in (("S", 20), ("A", 10)):
        assert result["actions"][f"dram/{tensor}/write"] == words
        assert result["actions"][f"dram/{tensor}/read"] == words


def test_three_consumer_fanout_spills_once():
    graph = Graph(7, (("X", 3),), (
        Op("S", ("X",), 4), Op("A", ("S",), 2), Op("B", ("S",), 2), Op("C", ("S",), 2),
        Op("J", ("A", "B"), 2, "add"), Op("Y", ("J", "C"), 2, "mul"),
    ))
    h = Hardware(2, 3, 64)
    plan = (
        Group(("S", "A"), 2, ((3, 2), (3, 2)), (False, False)),
        Group(("B",), 4, ((3, 2),), (False,)),
        Group(("C", "J", "Y"), 3, ((3, 2), (0, 2), (0, 2)), (False,) * 3),
    )
    result = replay(graph, h, events(graph, h, plan), numeric=True)
    assert score(graph, h, plan) == (result["energy"], result["ticks"])
    assert result["actions"]["dram/S/write"] == 28
    assert result["actions"]["dram/S/read"] == 56


def test_port_replay_rejects_compute_before_ingress(monkeypatch):
    book = CheckedCalendar.reserve

    def early_compute(self, port, start, elapsed, actions):
        if port == "mac":
            start -= 1
        book(self, port, start, elapsed, actions)

    monkeypatch.setattr(CheckedCalendar, "reserve", early_compute)
    with pytest.raises(AssertionError, match="read/compute/write dependency"):
        CheckedCalendar().wave(2, 3, 2, False, True)


def test_verifier_rejects_premature_free_partial_output_and_capacity():
    graph, h = diamond(), Hardware(2, 3, 45)
    group = Group(("S", "A", "B", "J"), 3, ((3, 2), (3, 2), (3, 2), (0, 2)), (False,) * 4)
    schedule = list(events(graph, h, (group,)))
    index = next(i for i, step in enumerate(schedule) if step.kind == "release" and step.name == "S")
    tampered = schedule.copy()
    tampered.insert(4, tampered.pop(index))
    with pytest.raises(ValueError, match="unavailable tensor S"):
        replay(graph, h, tampered)
    tampered = [step for step in schedule if not (step.kind == "gemm" and step.name == "B" and step.inner.start)]
    with pytest.raises(ValueError, match="unavailable tensor B"):
        replay(graph, h, tampered)
    with pytest.raises(ValueError, match="SRAM"):
        replay(graph, replace(h, capacity_bytes=24), schedule)


def test_dag_order_pruning_matches_unpruned_search(monkeypatch):
    graph = diamond()
    monkeypatch.setattr(search, "CAPACITIES", (28, 45))
    for capacity in search.CAPACITIES:
        opts = []
        for prune in (False, True):
            (cost, h, plan), _ = search.exact_search(graph, capacity, ((2, 3), (3, 2)), prune_orders=prune)
            result = replay(graph, h, events(graph, h, plan), numeric=True)
            assert cost == (result["energy"], result["ticks"])
            opts.append(cost[0] * cost[1])
        assert opts[0] == opts[1]


@pytest.mark.parametrize("overlap", ("finite", "free_staging", "serial", "roofline"))
def test_all_tiny_dag_mappings_agree_with_exact_search(monkeypatch, overlap):
    graph = Graph(2, (("X", 2),), (
        Op("A", ("X",), 1), Op("B", ("X",), 1), Op("J", ("A", "B"), 1, "mul"),
    ))
    monkeypatch.setattr(search, "CAPACITIES", (9,))
    hardware = Hardware(1, 2, 9)
    values = []
    for order, cuts in product((("A", "B", "J"), ("B", "A", "J")),
                               ((), (1,), (2,), (1, 2))):
        domains = []
        for left, right in zip((0, *cuts), (*cuts, 3)):
            group = order[left:right]
            choices = [[((p, 1), pin) for p, pin in product((1, 2), (False, True))]
                       if name != "J" else [((0, 1), False)] for name in group]
            domains.append([
                Group(group, rows, tuple(x[0] for x in options), tuple(x[1] for x in options))
                for rows, *options in product((1, 2), *choices)
            ])
        for plan in product(*domains):
            try:
                result = replay(graph, hardware, events(graph, hardware, plan), numeric=True)
            except ValueError as error:
                assert "SRAM" in str(error)
            else:
                e, t = dag_roofline.score(graph, hardware, plan) if overlap == "roofline" else score(graph, hardware, plan, overlap)
                assert e == result["energy"]
                if overlap in ("free_staging", "roofline"):
                    assert t <= result["ticks"]
                elif overlap == "serial":
                    assert t >= result["ticks"]
                else:
                    assert t == result["ticks"]
                values.append(e*t)
    (cost, _, _), _ = search.exact_search(graph, 9, ((1, 2),), overlap=overlap)
    assert cost[0] * cost[1] == min(values)
