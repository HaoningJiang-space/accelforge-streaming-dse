"""Moved to graph/views.py; kept so existing commands and imports keep working."""
from research.index_coupling.graph.views import ffm_like_curve, separate  # noqa: F401


def consumers(graph, t):
    return graph.consumers(t)
