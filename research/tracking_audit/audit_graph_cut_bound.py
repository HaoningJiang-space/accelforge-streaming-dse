"""Exhaustive synthetic graph-cut experiment, not an FFM performance test."""
import argparse
from dataclasses import asdict
from fractions import Fraction
import hashlib
import json
from pathlib import Path
from time import perf_counter

from research.tracking_audit.graph_cut_bound import (
    Architecture, Branch, Model, branch_bound, complete_cost, search,
)


def run(output):
    model = Model(macs=4096, base_dram_bytes=192, mac_energy=1, byte_energy=4)
    branches = [
        Branch('stream4',4,2,64,False),
        Branch('stream8',8,2,40,False),
        Branch('stream16',16,2,24,False),
        Branch('barrier-small-reservation',64,2,0,True),
        Branch('barrier-large-reservation',64,24,0,True),
        Branch('barrier-extra-reservation',64,40,0,True),
    ]
    extras = (32,16,8,0)
    # Interleave shapes and bandwidths so prefixes include changing winners.
    arches = [Architecture(px,py,c,bw)
              for c in (8,16,24,32,40,48,64,80)
              for px,py in ((2,4),(4,4),(8,8),(16,8))
              for bw in (2,8)]
    initial = [(0,32)] * len(arches)  # identical, explicitly feasible seed
    cases = []
    for k in (16,32,64):
        timings, records = {}, {}
        for prune in (False,True):
            start = perf_counter()
            picks, stats = search(model, arches[:k], branches, extras, initial[:k], prune=prune)
            timings[str(prune)] = perf_counter()-start
            records[prune] = (picks,stats)
        plain, bounded = records[False][0],records[True][0]
        assert [p[0] for p in plain] == [p[0] for p in bounded]
        # Independent post-hoc audit of every possible bound / completion.
        for arch in arches[:k]:
            for branch in branches:
                bound = branch_bound(model,arch,branch)
                for extra in extras:
                    value = complete_cost(model,arch,branch,extra)
                    assert (bound is None) == (value is None)
                    if value is not None:
                        assert bound <= value
        for witness in records[True][1]['witnesses']:
            arch = arches[witness['architecture']]
            branch = branches[witness['branch']]
            lower, upper = Fraction(witness['lower_bound']), Fraction(witness['incumbent'])
            assert lower == branch_bound(model, arch, branch)
            assert upper == complete_cost(model, arch, branches[witness['incumbent_branch']], witness['incumbent_extra'])
            assert upper <= lower
            assert all(upper <= complete_cost(model, arch, branch, extra) for extra in extras)
        cases.append(dict(k=k, timings_s=timings, baseline=records[False][1], bounded=records[True][1],
                          mismatched_best_costs=0,
                          winners=[dict(architecture=asdict(a), branch=branches[p[1]].name,
                                        edp=str(p[0]), extra=p[2]) for a,p in zip(arches[:k],bounded)]))
    report = dict(scope='synthetic restricted cost model, not FFM', model=asdict(model),
                  branches=[asdict(b) for b in branches], extras=extras, cases=cases)
    root = Path(__file__).parent
    files = ('audit_graph_cut_bound.py','graph_cut_bound.py','test_graph_cut_bound.py')
    report['source_sha256'] = {name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in files}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report,indent=2)+'\n')
    for c in cases:
        print(json.dumps(dict(k=c['k'], mismatch=c['mismatched_best_costs'],
                              completed_baseline=c['baseline']['completed_pairs'],
                              completed_bounded=c['bounded']['completed_pairs'],
                              pruned=c['bounded']['pruned_arch_branches'],
                              infeasible=c['bounded']['infeasible_arch_branches'])))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    run(p.parse_args().output)
