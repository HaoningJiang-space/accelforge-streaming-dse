"""Moved to graph/experiments.py (witness); kept so existing commands and imports keep working."""
import sys

if __name__ == '__main__':
    from research.index_coupling.graph.experiments import main
    main(['witness'] + sys.argv[1:])
