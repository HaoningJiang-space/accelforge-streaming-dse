"""Use the unchanged FFM implementation for generation and composition."""
from accelforge.mapper.FFM.main import make_pmappings, join_pmappings

from .memo import GraphMemo
from .workload_dag import WorkloadDAG


def generate_memo(spec):
    dag = WorkloadDAG.from_workload(spec.workload)
    dag.require_chain()
    return GraphMemo(dag, make_pmappings(spec, print_number_of_pmappings=False))


def join_memo(memo):
    # FFM continues to own all grouping, permutation, reservations and Pareto.
    return join_pmappings(memo.materialize())
