"""Full-grid binding Oracle; imports no production synthesis or cost helpers."""
from dataclasses import dataclass
from fractions import Fraction
from itertools import product

from .hardware_ir import Hardware


@dataclass(frozen=True)
class ObservedDesign:
    hardware: Hardware
    resource_cost: int
    energy: int
    latency: Fraction
    measured_demand: tuple
    plan: object


def enumerate_hardware(observations,envelope,prices,budget_ceiling):
    """All grids and all measured vectors; no minimum-hardware substitution.

    Equal (hardware cost, energy) keys retain their best measured latency, a
    directly dominated duplicate elimination. No global Pareto rule is used here.
    The returned keys also retain higher-cost/lower-quality pairs for queries.
    """
    axes=(envelope.px,envelope.py,envelope.sram_bytes,envelope.bandwidth)
    grids=[range(a.minimum,a.maximum+1,a.step)for a in axes]
    stats=dict(hardware_grid_points=0,budget_feasible_hardware=0,
               feasible_observation_bindings=0,unique_measured_demands=len(observations))
    best={}
    for x,y,capacity,bw in product(*grids):
        stats['hardware_grid_points']+=1
        cost=x*y*prices.pe+capacity*prices.sram_byte+bw*prices.bandwidth
        if cost>budget_ceiling:continue
        stats['budget_feasible_hardware']+=1
        for vector,plan in observations.items():
            if vector[0]>x or vector[1]>y or vector[2]>capacity:continue
            stats['feasible_observation_bindings']+=1
            latency=Fraction(vector[4]*bw+vector[5],bw)
            key=cost,vector[3]
            if key not in best or latency<best[key].latency:
                best[key]=ObservedDesign(Hardware(x,y,capacity,bw),cost,vector[3],latency,vector,plan)
    stats['cost_energy_keys']=len(best)
    return tuple(best.values()),stats


def full_frontier(observed):
    """Independent sorted scan with an E/T skyline; no production frontier."""
    ordered=sorted(observed,key=lambda d:(d.resource_cost,d.energy,d.latency))
    best_latency={};kept=[]
    for d in ordered:
        if any(energy<=d.energy and latency<=d.latency for energy,latency in best_latency.items()):
            continue
        kept.append(d)
        # Earlier points have <= cost and can suppress later ones. Do not
        # remove a kept lower-cost point just because a newer point is faster.
        previous=best_latency.get(d.energy)
        if previous is None or d.latency<previous:best_latency[d.energy]=d.latency
    return kept


def query_budget(observed,budget):
    feasible={(d.energy,d.latency)for d in observed if d.resource_cost<=budget}
    kept=set();best_latency=None
    for energy,latency in sorted(feasible):
        if best_latency is None or latency<best_latency:
            kept.add((energy,latency));best_latency=latency
    return kept
