"""Bounded memory diagnosis; instrument the original curve without changing its recurrence."""
import functools, hashlib, json, resource, signal, sys, time
from pathlib import Path
from research.index_coupling import curve_model as cm
from research.index_coupling.nest_model import fork
roles, mode = sys.argv[1:3]
shape = tuple(map(int, sys.argv[3:7]))
graph = fork(*shape, roles)
names = sorted(graph.sizes)
meta = {}
for i in range(len(graph.ops)):
    for j in range(i + 1, len(graph.ops) + 1):
        ops = graph.ops[i:j]
        meta[ops] = (frozenset(graph.tensors(ops)), frozenset(graph.rank_vars(ops)))
stats = {}
caches = {}
start = time.monotonic()
last = start
pstats = dict(calls=0, max_list_input=0, total_list_input=0, max_output=0)
reserve = bytearray(4 * 1024 * 1024)
resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
class Deadline(Exception): pass
def alarm(*args): raise Deadline()
signal.signal(signal.SIGALRM, alarm)
signal.alarm(60)
def snapshot(status, **extra):
    return dict(status=status, roles=roles, mode=mode, shape=shape,
        seconds=round(time.monotonic()-start,3),
        peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        caches={n:dict(stats[n], **c.cache_info()._asdict()) for n,c in caches.items()},
        pareto=pstats, source_sha256=hashlib.sha256(Path(cm.__file__).read_bytes()).hexdigest(), **extra)
def audit_cache(maxsize=None):
    def decorate(fn):
        name = fn.__name__
        s = stats[name] = dict(rows=0, states_with_irrelevant_external=0,
            irrelevant_external_members=0, max_frontier=0, calls_started=0)
        def compute(ops, ext, external):
            global last
            s["calls_started"] += 1
            irrelevant = external - meta[ops][0]
            if irrelevant:
                s["states_with_irrelevant_external"] += 1
                s["irrelevant_external_members"] += len(irrelevant)
            value = fn(ops, ext, external)
            s["rows"] += len(value)
            s["max_frontier"] = max(s["max_frontier"], len(value))
            now = time.monotonic()
            if now-last >= 10:
                last = now
                print(json.dumps(snapshot("progress")), flush=True)
            return value
        cached = functools.lru_cache(maxsize=maxsize)(compute)
        caches[name] = cached
        def call(ops, ext, external):
            if mode in ("project_external", "project_both"):
                external = external & meta[ops][0]
            if mode == "project_both":
                ext = tuple(x if v in meta[ops][1] else 1 for v,x in zip(names,ext))
            return cached(ops, ext, external)
        return call
    return decorate
original_pareto = cm.pareto
def audited_pareto(points, *args, **kwargs):
    pstats["calls"] += 1
    if isinstance(points, (list,tuple)):
        pstats["max_list_input"] = max(pstats["max_list_input"], len(points))
        pstats["total_list_input"] += len(points)
    out = original_pareto(points,*args,**kwargs)
    pstats["max_output"] = max(pstats["max_output"],len(out))
    return out
cm.lru_cache = audit_cache
cm.pareto = audited_pareto
try:
    points = cm.curve(graph)
    signal.alarm(0)
    print(json.dumps(snapshot("complete", points=points)), flush=True)
except (Deadline, MemoryError) as e:
    signal.alarm(0)
    reserve = None
    print(json.dumps(snapshot(type(e).__name__)), flush=True)
