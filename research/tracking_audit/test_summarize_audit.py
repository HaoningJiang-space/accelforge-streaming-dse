import json

import summarize_audit


def test_partial_run_record_does_not_crash_summary(tmp_path, capsys):
    log = tmp_path / 'killed.log'
    log.write_text('CONFIG {}\nRUN {"repeat": 0,\n[watchdog] done rc=137\n')
    summarize_audit.show(log)
    output = capsys.readouterr().out
    assert 'no SUMMARY' in output
    assert 'incomplete/corrupt record' in output
    assert 'rc=137' in output


def test_old_logs_without_new_flags_are_unknown(tmp_path, capsys):
    log = tmp_path / 'old.log'
    summary = {'shape': [1, 2, 3], 'median_seconds': {'indep': 1.}, 'quality': {},
               'all_picks_valid': True, 'all_repeats_consistent': True}
    log.write_text('SUMMARY ' + json.dumps(summary) + '\n')
    summarize_audit.show(log)
    output = capsys.readouterr().out
    assert 'best_known=unknown' in output
    assert 'usage_checked=unknown' in output
    assert 'glu(1, 2, 3)' in output


def test_new_incomplete_run_does_not_reuse_previous_success(tmp_path):
    log = tmp_path / 'appended.log'
    log.write_text('CONFIG {}\nSUMMARY {"all_picks_valid":true}\n'
                   '[watchdog] done rc=0\nCONFIG {}\nRUN {\n')
    result = summarize_audit.read(log)
    assert 'SUMMARY' not in result
    assert result['watchdog'] is None
    assert len(result['parse_errors']) == 1
