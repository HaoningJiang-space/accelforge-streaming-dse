"""Bind complete graph demands to one global hardware under normalized budgets.

PE/SRAM minima follow a fixed-plan monotonicity proof, not hardware-grid search.
All returned numerical (hardware cost, energy, latency) fronts are exact in the
declared fixed-cost model. This is not calibrated area or general Fusion DSE.
"""
from dataclasses import dataclass, field
from fractions import Fraction

from .hardware_ir import GridAxis, Hardware, HardwareEnvelope, NormalizedPrices
from .resource_demand import Demand
from .conditional_frontier import frontier


def first_at_least(axis,required):
    offset=max(0,required-axis.minimum)
    value=axis.minimum+((offset+axis.step-1)//axis.step)*axis.step
    return value if value<=axis.maximum else None


def hardware_cost(hardware,prices):
    return prices.pe*hardware.px*hardware.py+prices.sram_byte*hardware.sram_bytes+prices.bandwidth*hardware.bandwidth


@dataclass(frozen=True)
class JointDesign:
    hardware: Hardware
    resource_cost: int
    demand: Demand
    latency: Fraction=field(init=False)

    def __post_init__(self):
        object.__setattr__(self,'latency',self.demand.latency(self.hardware.bandwidth))

    @property
    def energy(self):return self.demand.energy

    @property
    def edp(self):return self.energy*self.latency

    @property
    def vector(self):return self.resource_cost,self.energy,self.latency


@dataclass(frozen=True)
class SynthesisResult:
    designs: tuple[JointDesign,...]
    budget_ceiling: int
    envelope: HardwareEnvelope
    prices: NormalizedPrices

    def query_budget(self,budget):
        """Full E/T frontier; tied sources prefer cheaper retained hardware."""
        if type(budget) is not int or budget<0 or budget>self.budget_ceiling:
            raise ValueError('query outside compiled integer budget interval')
        candidates=sorted((d for d in self.designs if d.resource_cost<=budget),
                          key=lambda d:(d.resource_cost,d.hardware))
        kept=[]
        for d in candidates:
            if any(p.energy<=d.energy and p.latency<=d.latency for p in kept):continue
            kept=[p for p in kept if not (d.energy<=p.energy and d.latency<=p.latency)]
            kept.append(d)
        return tuple(sorted(kept,key=lambda d:(d.energy,d.latency,d.resource_cost,d.hardware)))

    def best_edp(self,budget):
        """Minimum EDP among E/T-frontier witnesses, not every tied source."""
        return min(self.query_budget(budget),key=lambda d:(d.edp,d.resource_cost,d.hardware),default=None)


def synthesize(demands,envelope,prices=NormalizedPrices(),budget_ceiling=128):
    if type(budget_ceiling) is not int or budget_ceiling<1:
        raise ValueError('positive integer normalized budget ceiling required')
    demands=tuple(demands)
    candidates=[];hardware_seen=set()
    stats=dict(demand_states=len(demands),outside_envelope_demands=0,
               budget_infeasible_demands=0,constructed_plan_hardware_bindings=0,
               distinct_hardware_constructed=0,architecture_mapper_calls=0)
    for d in demands:
        if (not isinstance(d,Demand) or any(type(v) is not int or v<0 for v in d.vector)
                or d.pe_x<1 or d.pe_y<1):
            raise ValueError('complete nonnegative integer demand summaries required')
        x=first_at_least(envelope.px,d.pe_x)
        y=first_at_least(envelope.py,d.pe_y)
        capacity=first_at_least(envelope.sram_bytes,d.peak)
        if x is None or y is None or capacity is None:
            stats['outside_envelope_demands']+=1
            continue
        base=prices.pe*x*y+prices.sram_byte*capacity
        maximum=min(envelope.bandwidth.maximum,(budget_ceiling-base)//prices.bandwidth)
        if maximum<envelope.bandwidth.minimum:
            stats['budget_infeasible_demands']+=1
            continue
        for bw in range(envelope.bandwidth.minimum,maximum+1,envelope.bandwidth.step):
            hardware=Hardware(x,y,capacity,bw)
            candidates.append(JointDesign(hardware,hardware_cost(hardware,prices),d))
            stats['constructed_plan_hardware_bindings']+=1
            hardware_seen.add(hardware)
    kept=tuple(sorted(frontier(candidates),key=lambda d:(d.vector,d.hardware)))
    stats.update(distinct_hardware_constructed=len(hardware_seen),pareto_designs=len(kept),
        full_hardware_grid_size=1,scope='Exact for supplied complete demands and fixed-cost model.')
    for axis in (envelope.px,envelope.py,envelope.sram_bytes,envelope.bandwidth):
        stats['full_hardware_grid_size']*=1+(axis.maximum-axis.minimum)//axis.step
    return SynthesisResult(kept,budget_ceiling,envelope,prices),stats


def solve_joint(graph,model,envelope,prices=NormalizedPrices(),budget_ceiling=128):
    """Public graph entry point: one model/DP, then global hardware binding.

    Lower-level synthesize() assumes its supplied demands already belong to
    one complete graph/model. This entry point establishes that by construction.
    Subsequent budget queries reuse the returned family without rerunning DP.
    """
    from .graph_dp import solve
    demands,dp_stats=solve(graph,model)
    result,binding_stats=synthesize(demands,envelope,prices,budget_ceiling)
    return result,dict(graph_dp=dp_stats,hardware_binding=binding_stats,graph_dp_calls=1)
