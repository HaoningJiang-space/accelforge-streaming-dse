"""Separate fixed-map validation adapter; never imported by symbolic search."""
from research.diagnostics.causal_3mm import replay
from accelforge.frontend import mapping as mp


def mapping_for(plan):
    """Emit this grammar directly, not via a native template/Tile generator."""
    def store(component, tensors):
        return mp.Storage(component=component,tensors=tensors)
    def temporal(rank, tile):
        return mp.Temporal(rank_variable=rank,tile_shape=tile)
    def tail(i, k, j):
        return [mp.Spatial(component='ArrayFanout',rank_variable=f'n{i}',tile_shape=1,name='reuse_output'),
                mp.Spatial(component='ArrayFanout',rank_variable=f'n{i+1}',tile_shape=1,name='reuse_input'),
                store('Register',[f'W{i}']),temporal('m',1),mp.Compute(component='MAC',einsum=f'Matmul{i}')]
    (k0,j0),(k1,j1),(k2,j2)=plan.tiles
    a=mp.Nested(nodes=[mp.Reservation(purposes=['T1'],resource='GlobalBuffer'),temporal('n0',k0),store('GlobalBuffer',['T0']),temporal('n1',j0),
                       store('GlobalBuffer',['W0']),*tail(0,k0,j0)])
    # Native fused-template syntax keeps W1 Storage at the shared scope;
    # native reuse analysis derives its effective k1*j1 occupancy there.
    # Moving this node below the loops also changes native T1 compatibility.
    bnodes=[mp.Reservation(purposes=['T1','T2'],resource='GlobalBuffer'),
            temporal('n1',k1),temporal('n2',j1),*tail(1,k1,j1)]
    bnodes.insert(0 if plan.stripe<256 else 3,store('GlobalBuffer',['W1']))
    b=mp.Nested(nodes=bnodes)
    c=mp.Nested(nodes=[store('MainMemory',['W2','T3']),mp.Reservation(purposes=['T2'],resource='GlobalBuffer'),temporal('n3',j2),
                       store('GlobalBuffer',['T3']),temporal('n2',k2),
                       store('GlobalBuffer',['W2']),*tail(2,k2,j2)])
    if plan.stripe==256:
        a.nodes.insert(0,store('MainMemory',['T0','W0']))
        b.nodes.insert(0,store('MainMemory',['W1']))
        return mp.Mapping(nodes=[store('GlobalBuffer',['T1','T2']),mp.Sequential(nodes=[a,b,c])])
    ab=mp.Nested(nodes=[store('MainMemory',['T0','W0','W1']),mp.Reservation(purposes=['T2'],resource='GlobalBuffer'),temporal('n1',plan.stripe),
        store('GlobalBuffer',['T1']),mp.Sequential(nodes=[a,b])])
    return mp.Mapping(nodes=[store('GlobalBuffer',['T2']),mp.Sequential(nodes=[ab,c])])


def check(plan):
    # Generous validation capacity avoids hiding excess native peaks. No mapper
    # search, capacity-event enumeration, or performance claim uses this call.
    from research.tracking_audit import common
    common.af.set_n_parallel_jobs(1)
    return replay(mapping_for(plan),[64,96],1024*1024)
