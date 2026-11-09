"""Moved to graph/scoring.py (ffn); kept so existing commands and imports keep working."""
import sys

if __name__ == '__main__':
    from research.index_coupling.graph.scoring import main
    main(['ffn'] + sys.argv[1:])
