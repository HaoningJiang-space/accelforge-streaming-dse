"""Adapt published GAMMA genetic operators to the shared strip mapping genome."""

from copy import deepcopy
import hashlib
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import random
from time import perf_counter

import numpy as np

from research.joint_budget.protocol import Hardware
from research.runtime.strip_codesign import GEOMETRIES, Segment
from research.runtime.strip_overlap_cost import evaluate_overlap


PINNED_SOURCE = "3d6caf8448b269fa25c2f224db97fcc470d0370f"
SOURCE_SHA256 = "b0066452877b0f4a55291db771256386cf029a1c7ca8c7763f3287cc5effff4f"
DIMENSIONS = ("K", "C", "Y", "X", "R", "S")


def upstream(root):
    source = root / "src" / "GAMMA" / "gamma.py"
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if digest != SOURCE_SHA256:
        raise ValueError(f"GAMMA operator source differs from pinned {PINNED_SOURCE}")
    loader = spec_from_file_location("upstream_strip_gamma", source)
    module = module_from_spec(loader)
    loader.loader.exec_module(module)
    return module.GAMMA, digest


def chromosome(result, geometries):
    _, hardware, plan = result
    geometry = geometries.index((hardware.px, hardware.py)) + 1
    genes = []
    for group in plan:
        for i, ((p, q), pin) in enumerate(zip(group.tiles, group.pinned), group.start):
            genes.extend([["K", 1], *[[key, val] for key, val in zip(
                DIMENSIONS, (q, p, group.rows, 1 + pin, 1 + (i == group.start), geometry)
            )]])
    return genes


def decode(genes, rows, widths, capacity, geometries):
    x, y = geometries[genes[6][1] - 1]
    stages = len(widths) - 1
    h = Hardware(x, y, capacity)
    layers = [tuple(int(g[1]) for g in genes[i*7+1:i*7+7]) for i in range(stages)]
    stops = [0, *[i for i in range(1, stages) if layers[i][4] == 2], stages]
    plan = []
    for start, stop in zip(stops, stops[1:]):
        pairs = tuple(zip(widths[start:stop], widths[start+1:stop+1]))
        pins = [pin == 2 for _, _, _, pin, _, _ in layers[start:stop]]
        tiles = tuple((min(p, k, y), min(q, n, x))
                      for (q, p, *_), (k, n) in zip(layers[start:stop], pairs))
        base = sum(k * n for (k, n), pin in zip(pairs, pins) if pin)
        # Fold hardware-invalid widths to the boundary and repair strip height.
        # An already feasible genotype is left in the same phenotype.
        while True:
            limit = min((capacity - base - (0 if pin else p * q)) // (k + n)
                        for (k, n), pin, (p, q) in zip(pairs, pins, tiles))
            if limit >= 1 or not any(pins):
                break
            index = max((j for j, pin in enumerate(pins) if pin),
                        key=lambda j: pairs[j][0] * pairs[j][1])
            pins[index] = False
            base -= pairs[index][0] * pairs[index][1]
        if limit < 1:
            return None
        b = min(rows, limit, layers[start][2])
        plan.append(Segment(start, stop, b, tuple(pins), tiles))
    plan = tuple(plan)
    cost, _ = evaluate_overlap(rows, widths, h, plan)
    return cost, h, plan


def mutate_stage(engine, genes, stage, rows, widths, geometries):
    start = stage * 7
    x, y = geometries[genes[6][1] - 1]
    k, n = widths[stage:stage+2]
    engine.dimension_dict = dict(zip(DIMENSIONS, (min(n, x), min(k, y), rows, 2, 2, len(geometries))))
    child = [genes[start:start+7]]
    engine.mutate_tile(child, num_mu_loc=3, alpha=0.53, is_finetune=False)
    genes[start:start+7] = child[0]


def search(kernel, rows, widths, budget, seeds, limit, seed, on_incumbent, population_size=100,
           geometries=GEOMETRIES):
    """Keep upstream selection, dimension crossover and tile mutation."""
    random.seed(seed)
    np.random.seed(seed)
    stages = len(widths)-1
    capacity = seeds[0][1].capacity_bytes
    if capacity > budget:
        raise ValueError("seed exceeds SRAM budget")
    engine = kernel([1] * 7, fitness=("edp",), use_factor=False)
    engine.normalize = engine.use_pleteau = False
    population = [chromosome(design, geometries) for design in seeds]
    while len(population) < population_size:
        child = deepcopy(random.choice(population[:len(seeds)]))
        for stage in range(stages):
            mutate_stage(engine, child, stage, rows, widths, geometries)
        population.append(child)
    best = min(seeds, key=lambda design: design[0][0] * design[0][1])
    attempts = valid = generations = 0
    while perf_counter() < limit:
        scores = []
        for genes in population:
            if perf_counter() >= limit:
                break
            result = decode(genes, rows, widths, capacity, geometries)
            attempts += 1
            if result is None:
                scores.append(None)
                continue
            valid += 1
            score = result[0][0] * result[0][1]
            scores.append(score)
            if score < best[0][0] * best[0][1]:
                best = result
                on_incumbent(best)
        if len(scores) < len(population):
            break
        ranks = {score: -index for index, score in enumerate(sorted({s for s in scores if s is not None}))}
        rewards = np.asarray([[ranks.get(s, -len(ranks))] for s in scores], dtype=np.int64)
        _, _, parents = engine.select_parents(population, rewards, max(2, population_size * 2 // 5),
                                              population_size)
        elites = deepcopy(parents[:max(1, population_size // 20)])
        children = [None] * (population_size - len(elites))
        engine.crossover_tile(parents, children, alpha=0.57)
        for child in children:
            mutate_stage(engine, child, random.randrange(stages), rows, widths, geometries)
        population = elites + children
        generations += 1
    return best, dict(attempts=attempts, valid=valid, generations=generations)
