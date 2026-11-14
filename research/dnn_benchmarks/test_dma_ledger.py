import ast,json,shutil,tempfile,unittest
from pathlib import Path
from .audit_repaired_dma import audit, checked_region, DMABoundsError
from .audit_gemm_tail import diagnose

class CompiledLedgerTests(unittest.TestCase):
    root=Path(__file__).parent/'results/pytorchsim/1860f851'
    def test_archived_compiled_controls(self):
        for name,cycles,reads,writes in [('native_tuple',736,768,1024),('small_tile',8774,3072,1024),('subtile_m',9233,3072,1024),('aligned_n',597,544,512),('aligned_k',637,1536,64)]:
            with self.subTest(case=name):
                r=audit(self.root/name)
                self.assertTrue(r['timing_accepted']);self.assertEqual(r['expected_transactions'],dict(read=reads,write=writes));self.assertEqual(r['total_cycles'],cycles)
    def test_incorrect_observed_traffic_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            run=Path(tmp)/'run';shutil.copytree(self.root/'small_tile',run)
            log=next((run/'result/logs').glob('*.log'))
            log.write_text(log.read_text().replace('3072 reads, 1024 writes','3456 reads, 1216 writes'))
            self.assertFalse(audit(run)['timing_accepted'])
    def test_tag_collision_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            run=Path(tmp)/'run';shutil.copytree(self.root/'aligned_n',run)
            path=next((run/'result/compiler').glob('*/*_tog.py'));tree=ast.parse(path.read_text())
            graph=ast.literal_eval(next(n.value for n in tree.body if isinstance(n,ast.Assign)))
            for node in graph.values():
                if node['node_type']==3 and not node['is_write'] and node['base_address']=='arg1':node['tag_stride_list']=[0]*len(node['tag_stride_list'])
            path.write_text('graph = '+repr(graph)+'\n')
            with self.assertRaisesRegex(ValueError,'load-tag collision'):audit(run)

    def test_resnet_tail_is_not_implicit_padding(self):
        root=Path(__file__).parent/'results/resnet_tail'
        archived=json.loads((root/'diagnosis.json').read_text())
        for saved,expected in zip(archived,[(3200,16384,65536),(896,57344,229376)]):
            with self.subTest(case=saved['case']):
                r=diagnose(root/saved['case'])
                self.assertEqual(r,saved)
                self.assertTrue(r['transactions_match'])
                self.assertTrue(r['instruction_counts_match'])
                self.assertNotEqual(r['observed_transactions'],r['hypothetical_clipped_transactions'])
                self.assertEqual((r['padded_m'],r['tensors']['arg0']['excess_bytes'],r['tensors']['arg2']['excess_bytes']),expected)
                self.assertTrue(all(t['inside_validation_malloc'] for t in r['tensors'].values()))
                self.assertTrue(r['numerical_equal'])
                self.assertFalse(r['timing_accepted'])
                with self.assertRaises(DMABoundsError) as error:audit(root/saved['case'])
                self.assertEqual(error.exception.details,r['strict_rejection'])

    def test_affine_region_extrema_preserve_strides(self):
        node=dict(node_id=7,base_address='arg2',is_write=True,
                  loop_idx_list=['i'],loop_stride_list=[1],
                  tile_size=[2,3],tile_stride=[10,2])
        self.assertEqual(checked_region(node,{'i':1},16),(1,3,5,11,13,15))
        with self.assertRaises(DMABoundsError) as error:checked_region(node,{'i':1},15)
        self.assertEqual(error.exception.details['direction'],'write')
        self.assertEqual(error.exception.details['cell_interval'],[1,16])
        node['tile_stride']=[-10,-2]
        self.assertEqual(checked_region(node,{'i':15},16),(15,13,11,5,3,1))
        with self.assertRaises(DMABoundsError):checked_region(node,{'i':13},16)

if __name__=='__main__':unittest.main()
