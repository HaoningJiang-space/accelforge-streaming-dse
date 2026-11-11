import re,unittest
from pathlib import Path
from .togsim_statistics import parse_completed_statistics

class FinalStatisticsTests(unittest.TestCase):
    root=Path(__file__).parent/'results/pytorchsim/scale_scan_ba6728f3'
    def log(self,case):return next((self.root/case/'result/logs').glob('*.log')).read_text()
    def test_real_long_runs_select_final_not_first_interval(self):
        for case,reads,writes,cycles,intervals in [
            ('sweepk_heuristic_128_256_3072',147456,4096,13906,1),
            ('heuristic_128_768_3072',393216,12288,33829,3),
            ('external_128_768_3072_t16_128_16',2654208,12288,1248930,124)]:
            with self.subTest(case=case):
                log=self.log(case);r=parse_completed_statistics(log,16)
                first=re.search(r'combined .*?\| (\d+) reads, (\d+) writes',log)
                self.assertNotEqual((int(first[1]),int(first[2])),(reads,writes))
                self.assertEqual(r['observed_transactions'],dict(read=reads,write=writes))
                self.assertEqual((r['total_cycles'],r['ignored_interval_records']),(cycles,intervals))
    def test_short_run_still_passes(self):
        r=parse_completed_statistics(self.log('sweepk_heuristic_128_256_2048'),16)
        self.assertEqual(r['observed_transactions'],dict(read=98304,write=4096))
        self.assertEqual((r['total_cycles'],r['ignored_interval_records']),(9411,0))
    def test_truncated_logs_rejected(self):
        log=self.log('sweepk_heuristic_128_256_3072')
        for marker in ('[DRAM] channels 0..15 combined','Total execution cycles:'):
            with self.subTest(marker=marker),self.assertRaises(ValueError):
                parse_completed_statistics(log[:log.index(marker)],16)
    def test_duplicate_final_records_rejected(self):
        log=self.log('sweepk_heuristic_128_256_3072')
        for text in ('[DRAM] channels 0..15 combined','Total execution cycles:'):
            line=next(x for x in log.splitlines() if text in x)
            with self.subTest(text=text),self.assertRaises(ValueError):parse_completed_statistics(log+'\n'+line+'\n',16)
    def test_malformed_final_block_rejected(self):
        log=self.log('sweepk_heuristic_128_256_3072')
        variants=[log.replace('Core [0] : Total_cycles: 13906','Core [0] : Total_cycles: 10000'),
            log.replace('Core [0] : MOVOUT   inst_count: 1','Core [0] : missing MOVOUT'),
            log+'\n'+next(x for x in log.splitlines() if '[DRAM] all 16 channels combined' in x)+'\n']
        for bad in variants:
            with self.subTest(),self.assertRaises(ValueError):parse_completed_statistics(bad,16)
        with self.assertRaises(ValueError):parse_completed_statistics(log,8)

if __name__=='__main__':unittest.main()
