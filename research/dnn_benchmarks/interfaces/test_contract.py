import copy,tempfile,unittest
from pathlib import Path
from .contract import normalize,digest
from .receipts import capacity_verdict
from .evaluate import evaluate


def request(tile=(64,128,32),capacity=1024,mode='external',serial=True):
    mapping=dict(mode=mode,loop_order=['M','N','K'],strict=True)
    if mode=='external':mapping.update(tile=list(tile),subtile=list(tile))
    return dict(schema='gemm-evaluation-request.v1',operator_id='block0.gemm',mapping_id='candidate0',workload=dict(kind='plain_gemm',shape=[64,128,32],dtype='float32',layout='row_major_contiguous'),mapping=mapping,hardware=dict(sram_bytes_per_lane=capacity,serial_tiles=serial))


class ContractTests(unittest.TestCase):
    def test_semantic_identity_and_key_order(self):
        r=request();a=normalize(r);b=normalize(dict(reversed(list(r.items()))));self.assertEqual(digest(a),digest(b))
        r['operator_id']='block1.gemm';self.assertNotEqual(digest(a),digest(normalize(r)))
    def test_unsupported_inputs_fail_explicitly(self):
        for area,key,value in [('hardware','lanes',64),('hardware','sram_bytes_per_lane',1000),('mapping','strict',False),('mapping','subtile',[64,64,32]),('workload','dtype','float16'),('workload','kind','graph'),('mapping','loop_order',['K','M','N'])]:
            r=request();r[area][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):normalize(r)
    def test_capacity_requires_serial_scope_and_fits(self):
        r=normalize(request());hw=r['hardware']
        a=dict(schema='pytorchsim-allocation.v1',plain_gemm_scope=True,capacity_bytes_per_lane=1024,lanes=128,required_bytes_per_lane=800,static_extent_bytes_per_lane=640,kernel_stack_bytes_per_lane=160,static_object_bytes_per_lane=640,alignment_padding_bytes_per_lane=0,buffers=[dict(name='all',bytes_per_lane=640,offset_bytes=0,copies=1,lifetime='entire_kernel')])
        self.assertTrue(capacity_verdict(a,hw)['passed'])
        self.assertEqual(capacity_verdict(a,dict(hw,serial_tiles=False))['status'],'capacity_not_certified')
        self.assertEqual(capacity_verdict(dict(a,required_bytes_per_lane=1025,kernel_stack_bytes_per_lane=385),hw)['status'],'capacity_exceeded')
        self.assertEqual(capacity_verdict(dict(a,required_bytes_per_lane=0),hw)['status'],'invalid_allocation_receipt')
    def test_invalid_request_produces_result_without_process(self):
        import json
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);r=request();r['mapping']['strict']=False;(p/'request.json').write_text(json.dumps(r))
            result=evaluate(p/'request.json',p/'out',p/'no-runtime',p/'no-backend')
            self.assertEqual(result['failure_stage'],'request');self.assertIsNone(result['process_exitcode']);self.assertTrue((p/'out/evaluation.json').is_file())

if __name__=='__main__':unittest.main()
