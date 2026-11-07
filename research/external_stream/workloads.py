"""Translate the two native proxy workloads to STREAM's official affine IR."""

from math import prod

from xdsl.dialects.builtin import i8
from xdsl.ir.affine import AffineMap

from stream.workload.node import ComputationNode, InEdge, OutEdge
from stream.workload.tensor import Tensor
from stream.workload.workload import Workload


def three_mm(m=256, kn=256):
    nodes = []
    x = Tensor.create("T0", i8, (m, kn))
    nodes.append(InEdge(name=x.name, outputs=(x,)))
    maps = tuple(AffineMap.from_callable(f) for f in (
        lambda m, k, n: (m, k), lambda m, k, n: (k, n), lambda m, k, n: (m, n)))
    for stage in range(3):
        w = Tensor.create(f"W{stage}", i8, (kn, kn))
        y = Tensor.create(f"T{stage + 1}", i8, (m, kn))
        nodes.append(InEdge(name=w.name, outputs=(w,), parameter=True))
        nodes.append(ComputationNode(name=f"Matmul{stage}", type="MatMul", inputs=(x, w),
                                     outputs=(y,), operand_mapping=maps))
        x = y
    return Workload([*nodes, OutEdge(name="output", inputs=(x,))])


def attention_proxy(n=128, heads=1, depth=64):
    q, k, v, out = (Tensor.create(name, i8, (1, n, heads, depth)) for name in ("Q", "K", "V", "AV"))
    scores, prob = (Tensor.create(name, i8, (1, n, n, heads)) for name in ("QK", "QK_softmax"))
    qk = tuple(AffineMap.from_callable(f) for f in (
        lambda b, m, p, h, e: (b, m, h, e),
        lambda b, m, p, h, e: (b, p, h, e),
        lambda b, m, p, h, e: (b, m, p, h)))
    av = tuple(AffineMap.from_callable(f) for f in (
        lambda b, m, p, h, f: (b, m, p, h),
        lambda b, m, p, h, f: (b, p, h, f),
        lambda b, m, p, h, f: (b, m, h, f)))
    return Workload([
        *(InEdge(name=t.name, outputs=(t,)) for t in (q, k, v)),
        ComputationNode(name="QK", type="MatMul", inputs=(q, k), outputs=(scores,), operand_mapping=qk),
        ComputationNode(name="QK_softmax", type="Relu", inputs=(scores,), outputs=(prob,),
                        operand_mapping=(AffineMap.identity(4),) * 2),
        ComputationNode(name="AV", type="MatMul", inputs=(prob, v), outputs=(out,), operand_mapping=av),
        OutEdge(name="output", inputs=(out,)),
    ])


def inspect(workload, expected):
    report = []
    for node in workload.dataflow_sort():
        if not isinstance(node, ComputationNode):
            continue
        dims = [workload.get_dimension_size(d) for d in workload.get_dims(node)]
        count = prod(dims)
        if count != expected[len(report)]:
            raise ValueError(f"{node.name}: wrong iteration count {count}")
        if any(t.operand_type.bitwidth != 8 for t in node.tensors):
            raise ValueError(f"{node.name}: precision mismatch")
        report.append(dict(name=node.name, stream_op=node.type, iterations=count,
                           inputs=[t.name for t in node.inputs], outputs=[t.name for t in node.outputs],
                           shapes=[t.shape for t in node.tensors],
                           affine_projections=[str(m) for m in node.operand_mapping]))
    if len(report) != len(expected):
        raise ValueError("wrong number of compute operators")
    return report
