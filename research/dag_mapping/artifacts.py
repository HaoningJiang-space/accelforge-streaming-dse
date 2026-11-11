"""Source manifests and Git-pinned bytes for reproducible DAG experiments.

COMMON_SOURCES is a conservative bundle of graph fixtures, native semantics,
response providers and witness validation. Each runner adds its own protocol,
tests and driver. Historical records always use their recorded Git revision.
"""
from functools import lru_cache
import hashlib
from pathlib import Path
import re
import subprocess

COMMON_SOURCES = (
    'research/dag_mapping/artifacts.py', 'research/dag_mapping/workloads.py',
    'research/dag_mapping/boundary.py', 'research/dag_mapping/hierarchy.py',
    'research/dag_mapping/reuse.py',
    'research/index_coupling/graph/curve.py', 'research/index_coupling/graph/model.py',
    'research/index_coupling/graph/branch_symmetry.py', 'research/index_coupling/graph/fork_quotient.py',
    'research/index_coupling/graph/remainder.py', 'research/index_coupling/graph/span_names.py',
    'research/index_coupling/graph/stacks.py', 'research/index_coupling/graph/widths.py',
    'research/index_coupling/run_ancestor_width.py', 'research/index_coupling/unified_search.py',
    'research/index_coupling/response/prefix.py', 'research/index_coupling/response/substitution.py',
    'research/index_coupling/response/chains.py', 'research/index_coupling/response/forms.py',
    'research/index_coupling/simulate_nest.py',
)


def source_set(*extra):
    """Declare shared dependencies explicitly, without importing other runners."""
    return tuple(sorted(set(COMMON_SOURCES) | set(extra)))


def source_hashes(sources):
    return {p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in sources}


def verify_sources(revision, sources):
    """Reject a new run if declared inputs differ from its source commit."""
    for source in sources:
        if subprocess.check_output(['git', 'show', f'{revision}:{source}']) != Path(source).read_bytes():
            raise ValueError(f'unfrozen source: {source}')


@lru_cache(maxsize=None)
def frozen_bytes(revision, source):
    """Read an archived source version, never the current working-tree file."""
    path = Path(source)
    if (not re.fullmatch(r'[0-9a-f]{40}', revision) or path.is_absolute()
            or '..' in path.parts):
        raise ValueError('invalid frozen source reference')
    repo = Path(__file__).resolve().parents[2]
    return subprocess.check_output(['git', 'show', f'{revision}:{source}'], cwd=repo)
