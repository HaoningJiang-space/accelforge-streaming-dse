"""Moved to graph/references.py and graph/experiments.py (compare); kept so existing commands and imports keep working."""
import sys

from research.index_coupling.graph.analysis import traffic_at as at  # noqa: F401
from research.index_coupling.graph.references import RESULTS as R, cases  # noqa: F401

if __name__ == '__main__':
    from research.index_coupling.graph.experiments import main
    main(['compare'] + sys.argv[1:])
