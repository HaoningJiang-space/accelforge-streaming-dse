from fractions import Fraction
import random

import pytest

from research.tracking_audit.graph_cut_bound import (
    Architecture, Branch, Model, branch_bound, complete_cost, search, spill_bytes,
)


def trace_barrier(live, available):
    """Independent byte-level account: produce all, then consume all."""
    resident, dram = set(), set()
    writes = reads = 0
    for byte in range(live):
        if len(resident) < available:
            resident.add(byte)
        else:
            dram.add(byte)
            writes += 1
        assert len(resident) <= available
    for byte in range(live):
        if byte in resident:
            resident.remove(byte)
        else:
            assert byte in dram
            dram.remove(byte)
            reads += 1
    assert not resident and not dram
    return writes, reads


@pytest.mark.parametrize('live,available', [(s,c) for s in range(11) for c in range(11)] + [(64,48)])
def test_cut_matches_independent_event_trace(live, available):
    # A one-byte unrelated reservation also tests the capacity subtraction.
    branch = Branch('barrier', live, 1, 0, True)
    arch = Architecture(1,1,available+1,1)
    writes, reads = trace_barrier(live, available)
    assert spill_bytes(branch, arch) == writes + reads
    assert writes == reads == max(0, live-available)


def test_infeasible_cuts_and_untrusted_incumbents():
    model = Model(100,30,1,1)
    arch = Architecture(2,2,8,1)
    branches = [Branch('stream', 4, 5, 0, False), Branch('spill', 8, 2, 0, True)]
    assert spill_bytes(branches[0], arch) is None
    assert spill_bytes(branches[1], arch) == 4
    with pytest.raises(ValueError, match='infeasible incumbent'):
        search(model,[arch],branches,[0],[(0,0)],prune=True)
    with pytest.raises(ValueError, match='actual completion'):
        search(model,[arch],branches,[0],[(1,1)],prune=True)
    with pytest.raises(ValueError, match='epsilon'):
        search(model,[arch],branches,[0],[None],prune=True,epsilon=Fraction(-1,10))


def test_bound_and_branch_pruning_against_complete_enumeration():
    rng = random.Random(104729)
    for _ in range(40):
        model = Model(rng.randint(1,1000),rng.randint(1,100),rng.randint(1,4),rng.randint(1,7))
        arches = [Architecture(rng.randint(1,8),rng.randint(1,8),rng.randint(1,30),rng.randint(1,20)) for _ in range(12)]
        branches = [Branch(str(i),rng.randint(0,35),rng.randint(0,15),rng.randint(0,50),bool(rng.getrandbits(1))) for i in range(15)]
        extras = [0,1,3,7]
        initial = [None] * len(arches)
        for arch in arches:
            for branch in branches:
                lower = branch_bound(model,arch,branch)
                for extra in extras:
                    candidate = complete_cost(model,arch,branch,extra)
                    assert (lower is None) == (candidate is None)
                    if lower is not None:
                        assert lower <= candidate
        exact,_ = search(model,arches,branches,extras,initial,prune=False)
        for epsilon in (Fraction(0),Fraction(1,20)):
            pruned,_ = search(model,arches,branches,extras,initial,prune=True,epsilon=epsilon)
            for found,optimum in zip(pruned,exact):
                assert (found is None) == (optimum is None)
                if optimum is not None:
                    assert found[0] <= (1+epsilon)*optimum[0]


def test_seeded_batch_pruning_does_not_lose_best_cost():
    model = Model(4096,192,1,4)
    arches = [Architecture(2,4,c,b) for c in (8,16,32,64,96) for b in (2,4,8)]
    branches = [Branch('stream',4,2,128,False),Branch('barrier',64,2,0,True),
                Branch('large_barrier',1024,2,0,True)]
    extras = [32,16,8,0]
    initial = [(0,32)]*len(arches)
    baseline,_ = search(model,arches,branches,extras,initial,prune=False)
    actual,stats = search(model,arches,branches,extras,initial,prune=True)
    assert [x[0] for x in baseline] == [x[0] for x in actual]
    assert stats['pruned_arch_branches'] > 0
