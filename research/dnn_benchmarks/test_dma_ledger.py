import ast,json,shutil,tempfile,unittest
from pathlib import Path
from .audit_repaired_dma import audit

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

if __name__=='__main__':unittest.main()
