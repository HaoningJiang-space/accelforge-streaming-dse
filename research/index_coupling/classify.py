"""Moved to graph/experiments.py (classify); kept so existing commands and imports keep working."""
import sys

from research.index_coupling.graph.experiments import pts  # noqa: F401
from research.index_coupling.graph.references import RESULTS as R, ffn_case  # noqa: F401

if __name__ == '__main__':
    from research.index_coupling.graph.experiments import main
    main(['classify'] + sys.argv[1:])
