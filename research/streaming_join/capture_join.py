"""Export the first real, sufficiently large FFM join for controlled replay.

Only load the resulting pickle from this trusted experiment. Invoke with the
same limits required by compare_tag1.py and CAPTURE_FILE inside the experiment
folder. The rest of the full search remains the unmodified baseline.
"""
import json
import os
from pathlib import Path
import pickle
import runpy

from accelforge.mapper.FFM._join_pmappings.pmapping_dataframe import PmappingDataframe

original = PmappingDataframe.merge_next
captured = False
minimum = int(os.environ.get('CAPTURE_MIN_PAIRS', '10000'))
target = Path(os.environ['CAPTURE_FILE'])

def capture(self, right, *args, **kwargs):
    global captured
    product = len(self.data) * len(right.data)
    if not captured and product >= minimum and kwargs.get('_pmapping_row_filter_function') is None:
        with open(str(target) + '.tmp', 'wb') as f:
            pickle.dump((self, right, args, kwargs), f, protocol=pickle.HIGHEST_PROTOCOL)
        os.replace(str(target) + '.tmp', target)
        captured = True
        print('CAPTURE', json.dumps({'file': str(target), 'left_rows': len(self.data),
            'right_rows': len(right.data), 'pair_upper_bound': product,
            'input_dataframe_bytes': int(self.data.memory_usage(index=True, deep=True).sum()
                                         + right.data.memory_usage(index=True, deep=True).sum()),
            'pickle_bytes': target.stat().st_size}), flush=True)
    return original(self, right, *args, **kwargs)

PmappingDataframe.merge_next = capture
runpy.run_path(str(Path(__file__).with_name('compare_tag1.py')), run_name='__main__')
