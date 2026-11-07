"""Build native raw families, before numeric Tile enumeration, and audit support.

Every hardware point is prepared independently for this proof/diagnostic gate.
Its cost is reported; this is not the proposed shared BCGE optimizer or a speedup.
"""
import argparse
from dataclasses import asdict
import hashlib
import importlib
import json
from pathlib import Path
import time
from unittest.mock import patch

from research.graph_coopt.workload_dag import WorkloadDAG
from research.graph_coopt.template_support_audit import possible_interfaces
from research.tracking_audit import common
from research.tracking_audit.shape_capacity_audit import build
from .protocol import registered_domain, registered_budgets
from .family_support import propagate


def audit():
    common.clear_switches()
    common.af.set_n_parallel_jobs(1)
    pmapper = importlib.import_module('accelforge.mapper.FFM._make_pmappings.make_pmappings')
    case = common.Case('matmuls', 'nvdla', (3, 256, 256))
    domain = registered_domain()
    catalogs, interfaces, preparations = {}, {}, []
    edges = None
    graph_edges = None
    for h, point in enumerate(domain.points):
        started = time.perf_counter()
        spec = build(case, (point.px, point.py), point.capacity_bytes, common.RU)
        evaluated = spec._spec_eval_expressions(eval_arch=False, eval_non_arch=True)
        dag = WorkloadDAG.from_workload(evaluated.workload)
        current_graph_edges = tuple(sorted({(a, b) for a, b, _ in dag.edges}))
        if graph_edges is not None and graph_edges != current_graph_edges:
            raise AssertionError('the hardware domain changed the mandatory graph')
        graph_edges = current_graph_edges
        # Later raw-operator edges do not represent the actual native prefix
        # Compatibility. Chat's proof review limits the gate to the first Join.
        edges = graph_edges[:1]
        jobs = pmapper.get_jobs(evaluated, common.RU, evaluated.workload.einsum_names, True)
        by_op = {}
        for op, groups in jobs.items():
            by_op[str(op)] = {}
            for values in groups.values():
                for job in values:
                    fingerprint = hashlib.sha256(job.mapping.compact_str().encode()).hexdigest()
                    # The descriptor may depend on the raw native template,
                    # not on any observed terminal winner or post-Pareto rows.
                    if fingerprint in by_op[str(op)]:
                        raise AssertionError('raw template fingerprint is ambiguous')
                    by_op[str(op)][fingerprint] = job.compatibility
            catalogs[h, str(op)] = frozenset(by_op[str(op)])
        for producer, consumer in edges:
            shared = frozenset(t for t, users in dag.tensor_uses
                               if producer in users and consumer in users)
            for source, peer in ((producer, consumer), (consumer, producer)):
                for family, compatibility in by_op[source].items():
                    interfaces[h, source, family, peer] = possible_interfaces(compatibility, shared)
        preparations.append(dict(hardware=h, architecture=asdict(point),
            preparation_s=time.perf_counter() - started,
            templates=sum(len(v) for v in by_op.values()),
            loops_without_iteration_formulas=sum(
                loop.tile_pattern.calculated_n_iterations is None
                for by_comp in jobs.values() for values in by_comp.values() for job in values
                for loop in job.compatibility.loops),
            families_by_operator={op: sorted(values) for op, values in by_op.items()}))
    budgets = []
    for budget in registered_budgets():
        allowed = {h for h, point in enumerate(domain.points) if budget.admits(point)}
        selected = {key: value for key, value in catalogs.items() if key[0] in allowed}
        started = time.perf_counter()
        _, report = propagate(selected, edges, interfaces)
        report.update(budget=asdict(budget), propagation_s=time.perf_counter() - started)
        budgets.append(report)
    return dict(status='complete', workload=str(case), domain=[asdict(p) for p in domain.points],
        graph_edges=graph_edges, audited_edges=edges,
        later_prefix_interfaces_unsupported=True,
        native_match_coverage_certified=False, bucket_closedness_certified=False,
        preparation=preparations, budgets=budgets,
        interface_instances=len(interfaces),
        unknown_interface_instances=sum(value is None for value in interfaces.values()),
        abstraction='all unit-loop deletions; necessary backing/persistence/loop counts; sizes/ranks/aliases relaxed',
        numeric_expansion_calls=0, native_join_calls=0, bcge_implemented=False,
        sota_acceptance=False, policy_preserving_pruning_enabled=False,
        decision=('no_nonlocal_family_elimination_certified' if all(not r['removed'] for r in budgets)
                  else 'necessary_support_deletions_found_policy_equivalence_still_unproved'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    tiles = importlib.import_module(
        'accelforge.mapper.FFM._make_pmappings.make_pmappings_from_templates.make_tile_shapes')
    def forbidden(*args, **kwargs):
        raise AssertionError('read-only support gate must not enumerate Tiles or invoke native Join')
    with patch.object(tiles, '_compute_symbol_choices', forbidden), \
            patch.object(common, 'make_pmappings', forbidden), \
            patch.object(common, 'join_pmappings', forbidden):
        result = audit()
    result['numeric_generation_and_join_forbidden_during_audit'] = True
    paths = list(Path(__file__).parent.glob('*.py')) + [
        Path('research/graph_coopt/template_support_audit.py'),
        Path('research/graph_coopt/workload_dag.py')]
    result['source_sha256'] = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(decision=result['decision'], budgets=result['budgets'])), flush=True)


if __name__ == '__main__':
    main()
