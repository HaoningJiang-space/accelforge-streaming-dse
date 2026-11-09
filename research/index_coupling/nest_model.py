"""Moved to graph/model.py and graph/plateau.py; kept so existing commands and imports keep working."""
from research.index_coupling.graph.model import Graph, attention, coupling, ffn, fork  # noqa: F401
from research.index_coupling.graph.plateau import plateau, show  # noqa: F401

if __name__ == '__main__':
    from research.index_coupling.graph.experiments import plateau_table
    plateau_table()
