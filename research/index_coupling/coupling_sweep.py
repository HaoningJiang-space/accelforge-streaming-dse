"""Moved to graph/experiments.py (sweep); kept so existing commands and imports keep working."""
import sys

from research.index_coupling.graph.experiments import SIDES, run_sweep as run  # noqa: F401

if __name__ == '__main__':
    from research.index_coupling.graph.experiments import main
    main(['sweep'] + sys.argv[1:])
