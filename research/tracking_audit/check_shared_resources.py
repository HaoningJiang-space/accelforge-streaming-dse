"""Do joined groups share a tensor that the two sides reserve in different memories?

usage: check_shared_resources.py PARAMS CAP [--workload W] [--arch A] [--jobs N] [ABLATION=MEM[,MEM] ...]

PmappingDataframe.merge_next frees one copy of every shared tensor reserved above the
shared loop, taking the reservation from the *left* compatibility. That is only right if
the right side reserved the same tensor in the same memory; otherwise one copy is
subtracted that was never added. This runs one independent ENERGY|LATENCY search at CAP
and counts, per joined pair of compatibilities, shared tensors whose left and right
reservations differ in memory or level.
"""
import argparse
import collections
import json

import common
from accelforge.mapper.FFM._join_pmappings.pmapping_group import PmappingGroup

p = argparse.ArgumentParser()
p.add_argument('params')
p.add_argument('--workload', default=common.DEFAULT_CASE.workload, choices=common.WORKLOADS)
p.add_argument('--arch', default=common.DEFAULT_CASE.arch, choices=common.ARCHES)
p.add_argument('cap', type=float)
p.add_argument('--jobs', type=int, default=1)
p.add_argument('ablations', nargs='*')
a = p.parse_args()
case = common.Case.parse(a.workload, a.arch, a.params)
common.set_jobs(a.jobs)

pairs = collections.Counter()
mismatches = collections.Counter()
examples = []
original = PmappingGroup.merge_next


def merge_next(self, right, live_tensors, *args, **kwargs):
    # Same shared-loop rule as PmappingGroup.merge_next / _prepare_join_plan.
    shared_loop_index = self.compatibility.shared_loop_index(right.compatibility.tensor_names | live_tensors)
    for name in self.compatibility.tensor_names & right.compatibility.tensor_names:
        lt = self.compatibility.get_tensor_by_name(name)
        rt = right.compatibility.get_tensor_by_name(name)
        freed = lt.above_loop_index <= shared_loop_index
        key = (name, lt.resource_name, rt.resource_name, freed)
        pairs[key] += 1
        if freed and (lt.resource_name != rt.resource_name or lt.above_loop_index != rt.above_loop_index):
            mismatches[key] += 1
            if len(examples) < 5:
                examples.append({'tensor': name, 'left': str(lt), 'right': str(rt),
                                 'shared_loop_index': shared_loop_index})
    return original(self, right, live_tensors, *args, **kwargs)


PmappingGroup.merge_next = merge_next
res, st = common.search(common.build(case, a.cap, common.EL), ablations=common.parse_ablations(a.ablations))
common.shutdown_workers()
fmt = lambda c: {f'{k[0]} L={k[1]} R={k[2]} freed={k[3]}': v for k, v in c.items()}
print('SHARED', json.dumps({'cap_mib': a.cap, 'ablations': a.ablations, 'stats': st,
                            'pairs': fmt(pairs), 'freed_with_mismatch': fmt(mismatches),
                            'examples': examples}), flush=True)
