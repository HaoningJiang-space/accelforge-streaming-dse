"""Workloads for independent branched-schedule experiments."""

from research.runtime.dag_model import Graph, Op


def glu(rows=128, k=128, n=192, output=128):
    return Graph(rows, (("X", k),), (
        Op("Gate", ("X",), n), Op("Up", ("X",), n),
        Op("Mix", ("Gate", "Up"), n, "mul"), Op("Y", ("Mix",), output),
    ))


def diamond(rows=193):
    return Graph(rows, (("X", 128),), (
        Op("Stem", ("X",), 160), Op("Left", ("Stem",), 192), Op("Right", ("Stem",), 192),
        Op("Merge", ("Left", "Right"), 192, "add"), Op("Y", ("Merge",), 128),
    ))


def residual(rows=257):
    return Graph(rows, (("X", 160),), (
        Op("Stem", ("X",), 192), Op("Wide", ("Stem",), 320),
        Op("Project", ("Wide",), 192), Op("Merge", ("Stem", "Project"), 192, "add"),
        Op("Y", ("Merge",), 144),
    ))


def asymmetric(rows=193):
    return Graph(rows, (("X", 160),), (
        Op("Stem", ("X",), 192), Op("Wide", ("Stem",), 384), Op("Left", ("Wide",), 128),
        Op("Narrow", ("Stem",), 64), Op("Right", ("Narrow",), 128),
        Op("Merge", ("Left", "Right"), 128, "mul"), Op("Y", ("Merge",), 192),
    ))


CASES = {"glu": glu, "diamond": diamond, "residual": residual, "asymmetric": asymmetric}
