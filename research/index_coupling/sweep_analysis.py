"""Moved to graph/analysis.py and graph/scoring.py (sweep); kept so existing commands and imports keep working."""
import sys

from research.index_coupling.graph.analysis import capacity_for as s_of, delta, sign  # noqa: F401

if __name__ == '__main__':
    from research.index_coupling.graph.scoring import sweep
    sweep(sys.argv[1])
