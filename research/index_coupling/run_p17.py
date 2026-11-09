"""Moved to graph/experiments.py (p17); kept so existing commands and imports keep working."""
import sys

from research.index_coupling.graph.experiments import p17_shapes as shapes, run_p17 as run  # noqa: F401

if __name__ == '__main__':
    from research.index_coupling.graph.experiments import main
    main(['p17'] + sys.argv[1:])
