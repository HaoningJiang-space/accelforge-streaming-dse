"""Activation-frontier audit; stdlib only, no mapper or hardware assumptions."""
import argparse
from dataclasses import dataclass
import json
from pathlib import Path
from time import perf_counter


@dataclass
class DAG:
    inputs: dict
    ops: list  # (output name, input names, output bytes, operator kind)

    def __post_init__(self):
        self.sizes = dict(self.inputs)
        self.producer = {}
        self.users = {x: 0 for x in self.inputs}
        self.deps = []
        for i, (name, args, size, _) in enumerate(self.ops):
            if name in self.sizes or size <= 0 or not set(args) <= self.sizes.keys():
                raise ValueError("require positive sizes, unique tensors and topological input")
            self.deps.append(sum(1 << self.producer[x] for x in set(args) if x in self.producer))
            for x in set(args):
                self.users[x] |= 1 << i
            self.sizes[name] = size
            self.producer[name] = i
            self.users[name] = 0
        if any(v <= 0 for v in self.inputs.values()):
            raise ValueError("positive input sizes required")
        self.full = (1 << len(self.ops)) - 1

    def live(self, done):
        # External inputs are fetched at first use and held through last use.
        return {x for x, users in self.users.items() if users & (self.full ^ done)
                and ((done & (1 << self.producer[x])) if x in self.producer else users & done)}

    def cut(self, done):
        live = self.live(done)
        edges = sum((users & (self.full ^ done)).bit_count()
                    for x, users in self.users.items()
                    if x in self.producer and done & (1 << self.producer[x]))
        return len(live), sum(self.sizes[x] for x in live), edges

    def event_bytes(self, done, i):
        name, args, _, _ = self.ops[i]
        return sum(self.sizes[x] for x in self.live(done) | set(args) | {name})

    def ready(self, done):
        return [i for i, deps in enumerate(self.deps)
                if not done & (1 << i) and deps & done == deps]


METRICS = ("live_tensors", "cut_bytes", "internal_crossing_edges", "event_bytes")


def trace(graph, order):
    done = 0
    peaks = [0] * 4
    rows = []
    for i in order:
        if i not in graph.ready(done):
            raise ValueError("invalid schedule")
        event = graph.event_bytes(done, i)
        done |= 1 << i
        values = (*graph.cut(done), event)
        peaks = [max(a, b) for a, b in zip(peaks, values)]
        rows.append(dict(op=graph.ops[i][0], live=sorted(graph.live(done)),
                         **dict(zip(METRICS, values))))
    if done != graph.full:
        raise ValueError("incomplete schedule")
    return dict(zip(METRICS, peaks)), rows


def exact(graph, state_limit=50000):
    # Each objective has its own best prefix and predecessor, not one joint optimum.
    layer = {0: (0, 0, 0, 0)}
    parents = {}
    states = 1
    for _ in graph.ops:
        following = {}
        for done, costs in layer.items():
            for i in graph.ready(done):
                nxt = done | (1 << i)
                local = (*graph.cut(nxt), graph.event_bytes(done, i))
                candidate = tuple(max(a, b) for a, b in zip(costs, local))
                if nxt not in following:
                    following[nxt] = [float("inf")] * 4
                    parents[nxt] = [None] * 4
                    states += 1
                    if states > state_limit:
                        return dict(status="state_limit", states=states, optimum=None)
                for j, cost in enumerate(candidate):
                    if cost < following[nxt][j]:
                        following[nxt][j] = cost
                        parents[nxt][j] = (done, i)
        layer = following
    witnesses = {}
    for j, metric in enumerate(METRICS):
        done, order = graph.full, []
        while done:
            done, i = parents[done][j]
            order.append(i)
        order.reverse()
        peaks, rows = trace(graph, order)
        assert peaks[metric] == layer[graph.full][j]
        witnesses[metric] = dict(order=[graph.ops[i][0] for i in order], peaks=peaks, trace=rows)
    return dict(status="exact", states=states, optimum=dict(zip(METRICS, layer[graph.full])),
                witnesses=witnesses)


def greedy(graph, objective):
    done, order = 0, []
    while done != graph.full:
        def key(i):
            values = (*graph.cut(done | (1 << i)), graph.event_bytes(done, i))
            return values[objective], values[1], i
        i = min(graph.ready(done), key=key)
        order.append(i)
        done |= 1 << i
    return order


def cases():
    from research.runtime.dag_cases import CASES
    for name, factory in CASES.items():
        g = factory()
        yield "native_" + name, "repository runtime DAG; FP16 activations", DAG(
            {x: g.rows * w * 2 for x, w in g.inputs},
            [(op.name, op.inputs, g.rows * op.width * 2, op.kind) for op in g.ops])
    for blocks in (1, 4, 16):
        ops, x = [], "X"
        for b in range(blocks):
            a, c, d, y = [f"b{b}_{s}" for s in ("reduce", "spatial", "expand", "add")]
            ops.extend([(a, (x,), 56*56*64, "conv1"), (c, (a,), 56*56*64, "conv3"),
                        (d, (c,), 56*56*256, "conv1"), (y, (x,d), 56*56*256, "add")])
            x = y
        yield f"resnet_identity_{blocks}", "structural identity bottlenecks; INT8, 56x56", DAG({"X":56*56*256}, ops)
    for depth in (2, 4, 6, 8):
        ops, x, skips = [], "X", []
        size = 256*256*32*2
        for d in range(depth):
            s, down = f"skip{d}", f"down{d}"
            ops.extend([(s, (x,), size, "conv"), (down, (s,), size//2, "downsample")])
            skips.append((s,size)); x=down; size//=2
        ops.append(("bottom", (x,), size, "conv")); x="bottom"
        for d, (s,size) in reversed(list(enumerate(skips))):
            up, cat, out = f"up{d}", f"cat{d}", f"decode{d}"
            ops.extend([(up,(x,),size,"upsample"),(cat,(s,up),size*2,"concat"),
                        (out,(cat,),size,"conv")]); x=out
        yield f"unet_depth_{depth}", "structural U-Net; FP16, doubling channels on downsample", DAG({"X":256*256*32*2},ops)
    for tokens in (16, 128, 512):
        for blocks in (1, 4):
            h, heads, ops, x = 256, 8, [], "X"
            a, s = tokens*h*2, heads*tokens*tokens*2
            for b in range(blocks):
                q,k,v,score,p,ctx,proj,out = [f"b{b}_{n}" for n in ("q","k","v","score","softmax","context","proj","add")]
                ops.extend([(q,(x,),a,"linear"),(k,(x,),a,"linear"),(v,(x,),a,"linear"),
                            (score,(q,k),s,"qk"),(p,(score,),s,"softmax"),(ctx,(p,v),a,"av"),
                            (proj,(ctx,),a,"linear"),(out,(x,proj),a,"add")]); x=out
            yield f"attention_t{tokens}_b{blocks}", "structural unfused attention+residual; FP16, no MLP/norm", DAG({"X":a},ops)
    for branches in (2,4,8,12):
        ops = [("stem",("X",),4096,"linear")]
        for b in range(branches):
            ops.extend([(f"wide{b}",("stem",),65536,"linear"),
                        (f"end{b}",(f"wide{b}",),1024,"linear")])
        ops.append(("merge",tuple(f"end{b}" for b in range(branches)),branches*1024,"concat"))
        yield f"fanout_{branches}", "synthetic all-branch concat; not a routed MoE model", DAG({"X":4096},ops)
    # Adversarial source order exposes scheduling gains without changing the DAG.
    g = DAG({"X":4096},[(f"wide{i}",("X",),65536,"linear") for i in range(6)] +
            [(f"end{i}",(f"wide{i}",),1024,"linear") for i in range(6)] +
            [("merge",tuple(f"end{i}" for i in range(6)),6144,"concat")])
    yield "fanout_6_breadth_first", "synthetic scheduling control", g


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("research/graph_structure/results/local.json"))
    parser.add_argument("--state-limit", type=int, default=50000)
    args = parser.parse_args()
    results = []
    for name, provenance, graph in cases():
        start = perf_counter()
        baseline, rows = trace(graph, list(range(len(graph.ops))))
        heuristics = [trace(graph, greedy(graph,j))[0] for j in range(4)]
        solved = exact(graph,args.state_limit)
        results.append(dict(name=name, provenance=provenance, nodes=len(graph.ops),
                            shared_tensors=sum(u.bit_count()>1 for u in graph.users.values()),
                            graph=dict(inputs=graph.inputs, ops=graph.ops), baseline=baseline,
                            baseline_trace=rows, greedy=heuristics, solution=solved, seconds=perf_counter()-start))
        print(name, solved["status"], solved["optimum"], flush=True)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(dict(schema=1, cases=results),indent=2)+"\n",encoding="utf-8")


if __name__ == "__main__":
    main()
