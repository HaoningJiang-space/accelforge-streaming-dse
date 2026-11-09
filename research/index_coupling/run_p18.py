"""Moved to graph/experiments.py (p18); kept so existing commands and imports keep working."""
import sys

from research.index_coupling.graph.experiments import P18_ROLES as ROLES, p18_shapes as shapes, run_fork as run  # noqa: F401

if __name__ == '__main__':
    from research.index_coupling.graph.experiments import main
    main(['p18'] + sys.argv[1:])
