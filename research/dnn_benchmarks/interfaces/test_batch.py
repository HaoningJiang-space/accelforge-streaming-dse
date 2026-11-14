import json,tempfile,unittest
from pathlib import Path
from .batch import run_batch
from .test_contract import request

class CandidateTests(unittest.TestCase):
    def test_full_mapping_candidates_are_retained_and_failures_charged(self):
        a=request();b=request(tile=(16,32,8));c=request(tile=(16,32,16))
        for i,r in enumerate((a,b,c)):r['mapping_id']=str(i)
        seen=[]
        def evaluate(path,out,bundle,source,seconds):
            r=json.loads(path.read_text());seen.append(r['mapping_id'])
            return dict(verdict='rejected' if len(seen)==2 else 'accepted',failure_stage='capacity' if len(seen)==2 else None,metrics=dict(cycles=100//len(seen)),costs=dict(evaluation_wall_seconds=1))
        with tempfile.TemporaryDirectory() as d:
            r=run_batch([a,b,c],Path(d)/'batch',Path('/unused'),Path('/unused'),evaluator=evaluate)
        self.assertEqual(seen,['0','1','2']);self.assertEqual(r['attempted'],3);self.assertEqual(r['best_observed']['mapping_id'],'2')
        self.assertEqual(r['rows'][1]['verdict'],'rejected')
    def test_expired_admission_budget_launches_nothing(self):
        def forbidden(*a,**kw):raise AssertionError('candidate launched after deadline')
        with tempfile.TemporaryDirectory() as d:
            r=run_batch([request()],Path(d)/'batch',None,None,wall_budget_seconds=1e-12,evaluator=forbidden)
        self.assertEqual(r['attempted'],0);self.assertEqual(r['not_started'],1)
    def test_mismatched_hardware_cannot_share_comparison(self):
        a=request();b=request(capacity=2048);b['mapping_id']='second'
        with self.assertRaisesRegex(ValueError,'same operator'):run_batch([a,b],Path('/unused'),None,None)
    def test_same_identity_cannot_be_overwritten(self):
        with self.assertRaisesRegex(ValueError,'unique'):run_batch([request(),request()],Path('/unused'),None,None)

if __name__=='__main__':unittest.main()
