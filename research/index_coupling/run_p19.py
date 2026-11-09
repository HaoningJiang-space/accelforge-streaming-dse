"""Moved to graph/experiments.py (p19); kept so existing commands and imports keep working."""
import sys

from research.index_coupling.graph.experiments import P19_ROLES as ROLES, p19_shapes as shapes, run_fork as run  # noqa: F401

if __name__ == '__main__':
    from research.index_coupling.graph.experiments import main
    main(['p19'] + sys.argv[1:])
