"""Time and peak memory of one FFN curve (server probe)."""
import resource
import sys
import time

from research.index_coupling.curve_model import curve
from research.index_coupling.nest_model import ffn

if __name__ == '__main__':
    kwargs = {'write_through': False} if 'nowt' in sys.argv else {}
    t = time.time()
    points = curve(ffn(8, 4, 8), **kwargs)
    print(len(points), f'{time.time() - t:.0f}s', f'peak {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2**20:.1f} GiB')
