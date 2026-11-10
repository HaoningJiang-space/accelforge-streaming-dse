from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess, sys, time
while not Path('baseline/summary.json').exists():
    time.sleep(5)
Path('profiles').mkdir(exist_ok=True)
def run(item):
    name, alpha, independent = item
    child = """from argparse import Namespace
from pathlib import Path
from research.index_coupling.bench_solver_scaling import CASES, worker
CASES['dense_tiny'] = ('fork', (2, 2, 2, 2, 'kkkkkk'))
worker(Namespace(case='dense_tiny', variant='dp_projected', no_witness=False,
                 no_profile=False, canonical_spans=ALPHA, independent_ops=INDEPENDENT,
                 revision='0c7e2128', seconds=60, mem_gib=6,
                 out=Path('profiles/NAME.json')))
""".replace('ALPHA', repr(alpha)).replace('INDEPENDENT', repr(independent)).replace('NAME', name)
    subprocess.run([sys.executable, '-c', child], check=True, timeout=75)
with ThreadPoolExecutor(max_workers=2) as pool:
    list(pool.map(run, [('baseline',False,False),('alpha',True,False),
                        ('independent',False,True),('combined',True,True)]))
