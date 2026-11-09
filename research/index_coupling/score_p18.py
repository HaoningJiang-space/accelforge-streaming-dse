"""Moved to graph/scoring.py (p18); kept so existing commands and imports keep working."""
import sys

if __name__ == '__main__':
    from research.index_coupling.graph.scoring import main
    main(['p18'] + sys.argv[1:])
