"""Moved to graph/scoring.py (p15); kept so existing commands and imports keep working."""
import sys

if __name__ == '__main__':
    from research.index_coupling.graph.scoring import main
    main(['p15'] + sys.argv[1:])
