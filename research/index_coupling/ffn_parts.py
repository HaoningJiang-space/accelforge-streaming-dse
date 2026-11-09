"""Moved to graph/experiments.py (ffn-part); kept so existing commands and imports keep working."""
import sys

if __name__ == '__main__':
    from research.index_coupling.graph.experiments import main
    main(['ffn-part'] + sys.argv[1:])
