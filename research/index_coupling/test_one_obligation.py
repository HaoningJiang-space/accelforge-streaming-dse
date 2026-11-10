"""Two-live normal form and counterexamples to a general obligation-count law."""
from itertools import product
import unittest

from research.index_coupling.graph.curve import curve
from research.index_coupling.graph.model import fork, Graph
from research.index_coupling.one_obligation import two_live_response
from research.index_coupling.simulate_nest import simulate
from research.index_coupling.test_streamed_bridge import framed_streamed_witness


def cases(pairs=((2,1),(3,4),(4,4),(6,3),(8,8),(13,12))):
    for (n,s), roles, axis in product(pairs, ('kk','ki'), ('I','K')):
        original = fork(n if axis=='I' else 1,s,1 if axis=='I' else n,s,roles)
        for ops in (original.ops,original.ops[1:]):
            graph = Graph(original.sizes,[(o,original.access[o]) for o in ops])
            for tensor in sorted(graph.tensors(ops)-{'X'}):
                if axis not in graph.dims(tensor):
                    resident = graph.tensors(ops)-{'X',tensor}
                    yield (n,s,roles,axis,ops,tensor), graph, resident


def frame(graph,resident,child,owned=False):
    """A real caller; optionally it owns X's final write for a later reader."""
    parent, notes, capacity, _ = framed_streamed_witness(graph,resident,child)
    if owned:
        if 'EX' not in graph.ops:
            raise ValueError('this ownership frame requires the X producer')
        name, output = 'Read_Parent_X', 'Final_Parent_X'
        dims = parent.dims('X')
        parent = Graph(parent.sizes,[(o,parent.access[o]) for o in parent.ops] +
                       [(name,{'X':dims,output:dims})])
        notes = list(notes)
        first = notes[0]
        notes[0] = ('groups',first[1]+((name,),),'kept',first[3],'via DRAM',('X',))
        looped = False
        for axis in dims:
            if parent.sizes[axis] > 1:
                if looped:
                    notes.append(('groups',((name,),),'kept',(),'via DRAM',()))
                notes.append(('loop',(name,),axis,f'tile 1 x{parent.sizes[axis]}','kept',(),'refetched',()))
                looped = True
        notes = tuple(notes)
    compulsory = sum(parent.size(t,set()) for t in parent.consumed() ^ parent.produced())
    expected = compulsory + 2*child[0][1] + (2*parent.size('X',set()) if owned else 0)
    return parent,notes,capacity,expected


class OneObligationTests(unittest.TestCase):
    def test_normal_form_full_curves_and_frames(self):
        checked = 0
        for label,graph,resident in cases():
            for domain in ('halving','divisors'):
                for owned in (False,True) if 'EX' in graph.ops else (False,):
                    with self.subTest(case=label,domain=domain,owned=owned):
                        written = {'X'} if owned else set()
                        predicted = two_live_response(graph,graph.ops,tuple(graph.sizes.values()),resident,
                                                      written,tuple(graph.sizes),witness=True,tile_domain=domain)
                        compulsory = sum(graph.size(t,set()) for t in
                                         (graph.consumed()^graph.produced())-resident)
                        expected = tuple((c,q+compulsory) for c,q,_ in predicted)
                        for method in ('dp','enumerate'):
                            self.assertEqual(curve(graph,external=resident,written=written,
                                                   partitions=method,tile_domain=domain),expected)
                        # One domain suffices for replay when both have the same
                        # frontier, but divisors have distinct tiling in 13/12.
                        if domain=='halving' or label[:2]==(13,12):
                            for point in predicted:
                                parent,notes,c,q = frame(graph,resident,(point,),owned)
                                actual = simulate(parent,notes)
                                self.assertTrue(actual['valid'])
                                self.assertEqual((actual['peak'],actual['traffic']),(c,q))
                                checked += 1
        self.assertGreater(checked, 300)

    def test_more_than_two_points_and_alternative_materialization(self):
        for roles,t,expected in (
                ('kk','C0',((2,56),(3,24),(5,8),(9,0))),
                ('ik','V0',((2,72),(3,40),(5,16),(9,0)))):
            graph = fork(8,8,1,8,roles)
            resident = graph.tensors(graph.ops)-{'X',t}
            predicted = two_live_response(graph,graph.ops,(8,8,1,8),resident,set(),('I','J','K','L'))
            self.assertEqual(tuple(p[:2] for p in predicted),expected)

    def test_equal_single_axis_summary_does_not_determine_full_response(self):
        graph = fork(4,4,1,4,'ii')
        expected = {'A':((2,20),(3,8),(5,0)), 'D1':((2,24),(3,8),(5,0))}
        for other in ('A','D1'):
            resident = graph.tensors(graph.ops)-{'X','V0',other}
            self.assertIsNone(two_live_response(graph,graph.ops,(4,4,1,4),resident,set(),('I','J','K','L')))
            compulsory = sum(graph.size(t,set()) for t in
                             (graph.consumed()^graph.produced())-resident)
            points = curve(graph,external=resident,partitions='dp',witness=True)
            self.assertEqual(tuple((c,q-compulsory) for c,q,_ in points),expected[other])
            for c,q,w in points:
                parent,notes,pc,pq = frame(graph,resident,((c,q-compulsory,w),))
                actual = simulate(parent,notes)
                self.assertTrue(actual['valid'])
                self.assertEqual((actual['peak'],actual['traffic']),(pc,pq))


if __name__ == '__main__':
    unittest.main()
