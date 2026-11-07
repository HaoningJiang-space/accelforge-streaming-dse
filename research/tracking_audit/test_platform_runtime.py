"""The mapper must remain importable where POSIX resource limits do not exist."""
from types import SimpleNamespace
import sys

import pytest

from accelforge.mapper.FFM._make_pmappings.make_pmappings_from_templates import make_tile_shapes as tiles
from research.tracking_audit import common


def test_tile_job_without_posix_limits_preserves_results_and_reports_limit_gap(monkeypatch):
    monkeypatch.setattr(tiles, 'resource', None)
    result = object()
    monkeypatch.setattr(tiles, '_make_tile_shapes', lambda job: result)
    job = SimpleNamespace(memory_limit=1024, time_limit=10)
    with pytest.warns(RuntimeWarning, match='without OS-enforced worker limits'):
        assert tiles.make_tile_shapes(job) is result


def test_tile_job_without_limits_preserves_kernel_exception(monkeypatch):
    monkeypatch.setattr(tiles, 'resource', None)
    def fail(job):
        raise ValueError('kernel failed')
    monkeypatch.setattr(tiles, '_make_tile_shapes', fail)
    job = SimpleNamespace(memory_limit=float('inf'), time_limit=float('inf'))
    with pytest.raises(ValueError, match='kernel failed'):
        tiles.make_tile_shapes(job)


@pytest.mark.skipif(sys.platform != 'win32', reason='native Windows working set API')
def test_windows_process_peak_is_measured_and_child_peak_is_unavailable():
    measured = common.peak_rss_gb()
    assert measured['main'] > 0
    assert measured['largest_worker'] is None
