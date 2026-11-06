"""Native fixed-map evidence for the two bounded Residency contexts only."""
from .native_check import mapping_for


def mapping_for_context(plan,context):
    if context not in ('gb','dram'):
        raise ValueError('unknown backing')
    result=mapping_for(plan)
    if context=='gb':return result
    from accelforge.frontend import mapping as mp
    def rewrite(nodes):
        result=[]
        for node in nodes:
            if isinstance(node,mp.Storage) and node.component=='GlobalBuffer' and 'T2' in node.tensors:
                node.tensors=[str(t)for t in node.tensors if str(t)!='T2']
                if not node.tensors:continue
            if isinstance(node,mp.Reservation) and node.resource=='GlobalBuffer' and 'T2' in node.purposes:
                node.purposes=[str(t)for t in node.purposes if str(t)!='T2']
                if not node.purposes:continue
            if hasattr(node,'nodes'):node.nodes=rewrite(node.nodes)
            result.append(node)
        return result
    result.nodes=rewrite(result.nodes)
    result.nodes.insert(0,mp.Storage(component='MainMemory',tensors=['T2']))
    def add_copies(nodes):
        for node in nodes:
            if isinstance(node,mp.Nested) and node.nodes and isinstance(node.nodes[-1],mp.Compute):
                name=str(node.nodes[-1].einsum)
                rank='n2' if name in ('Matmul1','Matmul2') else None
                if rank:
                    index=next(i for i,n in enumerate(node.nodes)if isinstance(n,mp.Temporal)and str(n.rank_variable)==rank)
                    node.nodes.insert(index+1,mp.Storage(component='GlobalBuffer',tensors=['T2']))
            elif hasattr(node,'nodes'):add_copies(node.nodes)
    add_copies(result.nodes)
    return result


def check(plan,context,shape):
    from research.diagnostics.causal_3mm import replay
    from research.tracking_audit import common
    common.af.set_n_parallel_jobs(1)
    return replay(mapping_for_context(plan,context),list(shape),1024*1024)
