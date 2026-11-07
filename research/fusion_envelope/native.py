"""Relax native symbol costs before tile expansion; never replace native Join.

Independent operator minima deliberately forget fusion compatibility, rather
than pretending raw interface matches model composed-prefix semantics.
"""
from dataclasses import asdict
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path
import time
from unittest.mock import patch
import sympy as sp

from research.joint_search import ffm_backend as backend
from research.tracking_audit import common
from research.tracking_audit.shape_capacity_audit import build, mapping_structure
from research.joint_budget.analytic_bounds import check_frozen_inputs, lower_bound
from .linear_relaxation import Relaxation
from .correlated import minimum_product


class Captured(Exception):
    pass


def capture(job):
    result = {}
    def intercept(**kwargs):
        result.update(kwargs)
        raise Captured()
    try:
        with patch.object(backend.tiles,'get_tile_shape_choices_for_targets',intercept):
            backend.tiles._make_tile_shapes(job)
    except Captured:
        return result
    raise AssertionError('symbolic capture reached numeric enumeration')


def model_from_capture(data, shape):
    job = data['job']
    symbols = data['symbols']
    bounds = {s:int(hi) for s,lo,hi in data['what_tiles_symbol'].bounds}
    model = Relaxation(symbols,bounds)
    for outer,inner in data['what_tiles_symbol'].what_tiles_symbol:
        model.relation(outer,inner)
    objectives = {obj.name:obj for obj in data['objectives']}
    # Relaxation drops all fallback/min-usage, prefix order, Pareto, loop-count
    # and interface predicates. Only necessary hard capacity/fanout constraints
    # remain. This cannot exclude a native local candidate.
    for name,obj in objectives.items():
        if name.startswith('usage<SEP>memory<SEP>'):
            memory = name.split('<SEP>')[-1]
            if memory not in ('GlobalBuffer','Register') or not obj.exact:
                continue
            model.constrain(model.lower(obj.formula),0,parameter=('memory',memory))
    # Derive exact spatial factors from the loop tree, avoiding any floating
    # normalization by the preparation architecture's non-dyadic fanout.
    previous = dict(job.rank_variable_bounds)
    spatial_factors = {'reuse_input':sp.Integer(1),'reuse_output':sp.Integer(1)}
    for node in job.mapping.nodes:
        if isinstance(node,backend.tiles.Loop):
            outer = previous[node.rank_variable]
            if isinstance(node,backend.tiles.Spatial):
                spatial_factors[node.name] *= sp.sympify(outer)/node.tile_shape
            previous[node.rank_variable] = node.tile_shape
    for name,factor in spatial_factors.items():
        model.spatial(factor,1,name)
    energy = model.lower(objectives['Total<SEP>energy'].formula,F(10**6))
    latency = model.lower(objectives['Total<SEP>latency'].formula,F(10**6))
    model.finalize()
    return model,energy,latency


class NativeEnvelope:
    def __init__(self, case, correlated=False):
        check_frozen_inputs()
        if backend.tiles.IMPERFECT or backend.tiles.pareto_module.TOLERANCE != 0:
            raise ValueError('perfect native tiles and zero tolerance required')
        self.case = case
        self.weights = (F(1,8),F(1,4),F(1,2),F(1),F(2)) if correlated else ()
        self.models = {}
        self.catalogs = {}
        self.stats = dict(raw_instances=0, unique_symbolic_models=0, unsupported=0,
                          lp_solves=0, dual_reuses=0, exact_infeasibility_proofs=0,
                          catalog_family_reuses=0)
        self.duals = {}
        self.functions = {}
        self.infeasibility = []
        self.unsupported = []
        self.factor_catalog = None
        # Raw template construction reads cumulative component fanouts, not the
        # individual dimension bounds or SRAM size. For this fixed hierarchy
        # every 6144-PE factor pair therefore has the same raw grammar. Numeric
        # Tile policy histories are NOT shared. Fail closed if that code changes.
        directory = common.ROOT/'accelforge/mapper/FFM/_make_pmappings/make_pmapping_templates'
        fingerprint = hashlib.sha256()
        for path in sorted(directory.glob('*.py')):
            fingerprint.update(path.name.encode()+b'\0'+path.read_bytes().replace(b'\r\n',b'\n'))
        if fingerprint.hexdigest()!='197e5e3c7b1373a2579c20c613d02605fedc4b5f9fa59e2575c9a1c61bef97db':
            raise ValueError('raw-template family invariance lemma requires re-review')

    def prepare(self, shape, capacity_bytes):
        """Native raw catalog at each physical shape; reuse only fixed-cost formulas.

        NVDLA action costs and zero leakage make E/T expressions independent of
        SRAM/fanout limits. Fanout and capacity constraints are target parameters.
        Tensor identities, persistence, loop structure and rank bounds are keyed.
        No policy Tile set is reused across physical architectures.
        """
        if shape[0]*shape[1]==6144 and self.factor_catalog is not None:
            self.catalogs[shape] = self.factor_catalog
            self.stats['catalog_family_reuses'] += 1
            return
        common.clear_switches()
        common.af.set_n_parallel_jobs(1)
        spec = build(self.case,shape,capacity_bytes,common.RU)
        evaluated = spec._spec_eval_expressions(eval_arch=False,eval_non_arch=True)
        jobs = backend.pmapper.get_jobs(evaluated,common.RU,evaluated.workload.einsum_names,True)
        backend.pmapper._fill_jobs_with_memories_to_track(jobs,evaluated,common.RU,False)
        catalog = {}
        for name,groups in jobs.items():
            keys = []
            for values in groups.values():
                for job in values:
                    if job.is_copy_operation:
                        continue  # Additional copies have nonnegative E/T.
                    if any(float(getattr(node,'leak_power',0)) != 0 for node in job.flattened_arch):
                        raise ValueError('fixed-cost symbolic sharing requires zero leakage')
                    costs = [(node.name,str(getattr(node,'total_latency',None)),str(getattr(node,'latency_scale',1)),
                              str(getattr(node,'bits_per_value_scale',{})),
                              [(a.name,str(a.energy),str(a.latency),str(getattr(a,'bits_per_action',None)))
                               for a in getattr(node,'actions',[])]) for node in job.flattened_arch]
                    key_text = json.dumps(dict(einsum=str(name),mapping=mapping_structure(job.mapping),
                        private_mapping=[dict(fused=getattr(node,'_fused',None),
                            backing=getattr(node,'_backing',None)) for node in job.mapping.nodes],
                        rank_bounds=job.rank_variable_bounds,costs=costs),sort_keys=True,default=str)
                    key = hashlib.sha256(key_text.encode()).hexdigest()
                    keys.append(key)
                    self.stats['raw_instances'] += 1
                    if key not in self.models:
                        try:
                            data = capture(job)
                            self.models[key] = model_from_capture(data,shape)
                            self.stats['unique_symbolic_models'] += 1
                        except (ValueError,KeyError,TypeError,NotImplementedError) as error:
                            # An unsupported model contributes zero, not exclusion.
                            self.models[key] = None
                            self.stats['unsupported'] += 1
                            self.unsupported.append(dict(key=key,error=f'{type(error).__name__}: {error}'))
            if not keys:
                raise ValueError('operator lacks an ordinary compute template')
            catalog[str(name)] = tuple(keys)
        self.catalogs[shape] = catalog
        if shape[0]*shape[1]==6144:
            self.factor_catalog = catalog

    def bound(self, point, solve=True):
        shape = (point.px,point.py)
        if shape not in self.catalogs:
            self.prepare(shape,point.capacity_bytes)
        totals,details = [F()]*(2+len(self.weights)),[]
        for name,keys in self.catalogs[shape].items():
            minima = [None]*len(totals)
            surviving = 0
            for key in keys:
                prepared = self.models[key]
                if prepared is None:
                    minima = [F()]*len(totals)
                    surviving += 1
                    continue
                model,*objectives = prepared
                objectives += [objectives[0].plus(objectives[1].scale(weight)) for weight in self.weights]
                bounds = []
                impossible = False
                for kind,objective in enumerate(objectives):
                    cache_key = (key,kind)
                    certificates = self.duals.setdefault(cache_key,[])
                    functions = self.functions.setdefault(cache_key,[])
                    if solve is True or (solve=='missing' and not certificates):
                        cert = model.solve(objective,point)
                        self.stats['lp_solves'] += 1
                        if cert['infeasible']:
                            impossible = True
                            self.stats['exact_infeasibility_proofs'] += 1
                            self.infeasibility.append(dict(key=key,architecture=asdict(point),
                                dual=[str(y) for y in cert['dual']],contradiction=str(cert['contradiction']),
                                residual=str(cert['residual'])))
                            break
                        if cert['dual'] not in certificates:
                            certificates.append(cert['dual'])
                            functions.append(model.compile_dual(objective,cert['dual']))
                    if certificates:
                        value = max(model.evaluate_dual(function,point) for function in functions)
                        self.stats['dual_reuses'] += len(certificates)
                    else:
                        value = F()
                    bounds.append(max(F(),value))
                if impossible:
                    continue
                surviving += 1
                for kind,value in enumerate(bounds):
                    minima[kind] = value if minima[kind] is None else min(minima[kind],value)
            if surviving == 0:
                # Do not extrapolate numerically detected emptiness. Every
                # removed template had an exact phase-I contradiction above.
                return dict(infeasible=True,operators=details,stats=dict(self.stats))
            for kind,value in enumerate(minima):
                totals[kind] += value
            details.append(dict(einsum=name,templates=len(keys),surviving=surviving,
                                energy_lower_microjoule=str(minima[0]),latency_lower_microsecond=str(minima[1])))
        analytic = lower_bound(self.case,point)
        # Same finite-native numeric audit requirement as the analytic control.
        energy = max(analytic.energy, totals[0]/10**6*F(99,100))
        latency = max(analytic.latency, totals[1]/10**6*F(99,100))
        weighted = [(w,value/10**6*F(99,100)) for w,value in zip(self.weights,totals[2:])]
        product,vertex_e,vertex_t = minimum_product(energy,latency,weighted)
        return dict(infeasible=False,energy=energy,latency=latency,edp=product,
                    independent_edp=energy*latency,weighted_bounds=weighted,
                    relaxation_vertex=(vertex_e,vertex_t),
                    analytic_edp=analytic.edp,operators=details,stats=dict(self.stats))

    def serialize_duals(self):
        return {key+':'+str(kind):[[str(y) for y in dual] for dual in values]
                for (key,kind),values in self.duals.items()}

    def serialize_models(self):
        def affine(obj):
            return dict(constant=str(obj.constant),terms={str(i):str(v) for i,v in obj.terms.items()})
        return {key:None if prepared is None else dict(
                    upper=[str(v) for v in prepared[0].upper],
                    rows=[{str(i):str(a) for i,a in row.items()} for row in prepared[0].rows],
                    rhs=prepared[0].rhs,objectives=[affine(obj) for obj in prepared[1:]])
                for key,prepared in self.models.items()}
