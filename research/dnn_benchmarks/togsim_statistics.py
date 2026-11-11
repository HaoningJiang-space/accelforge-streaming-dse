"""Parse one completed pinned-TOGSim run, never an interval snapshot.

DramRamulator2::cycle emits `all N channels combined ... (interval ...)`.
DramRamulator2::print_stat emits `channels 0..N-1 combined` once at the end.
The old generic first-match expression confused the two for runs >= 10k cycles.
"""
import re


def parse_completed_statistics(log,expected_channels):
    final=list(re.finditer(
        r'^.*\[DRAM\] channels (\d+)\.\.(\d+) combined \| [^\n]*\| '
        r'(\d+) reads, (\d+) writes[ \t]*$',log,re.MULTILINE))
    completed=list(re.finditer(r'^.*\[info\] Total execution cycles: (\d+)[ \t]*$',log,re.MULTILINE))
    if len(final)!=1 or len(completed)!=1:
        raise ValueError('requires exactly one final cumulative DRAM record and completion marker')
    stats=final[0];end=completed[0]
    if stats.start()>=end.start():raise ValueError('cumulative DRAM statistics follow completion marker')
    if (int(stats[1]),int(stats[2]))!=(0,expected_channels-1):
        raise ValueError('cumulative DRAM channel range differs from hardware')
    intervals=list(re.finditer(r'^.*\[DRAM\] all \d+ channels combined [^\n]*\(interval \d+ cycles\)[ \t]*$',log,re.MULTILINE))
    if any(m.start()>stats.start() for m in intervals):
        raise ValueError('interval statistics follow final cumulative record')
    block=log[stats.end():end.start()]
    emitted={}
    for direction,op in [('read','MOVIN'),('write','MOVOUT')]:
        found=re.findall(rf'^.*Core \[0\] : {op}\s+inst_count: (\d+)[ \t]*$',block,re.MULTILINE)
        if len(found)!=1:raise ValueError('missing or ambiguous final DMA instruction counts')
        emitted[direction]=int(found[0])
    core_cycles=re.findall(r'^.*Core \[0\] : Total_cycles: (\d+)[ \t]*$',block,re.MULTILINE)
    cycles=int(end[1])
    if len(core_cycles)!=1 or int(core_cycles[0])!=cycles:
        raise ValueError('final core cycles disagree with completion marker')
    return dict(observed_transactions=dict(read=int(stats[3]),write=int(stats[4])),
        observed_dma=emitted,total_cycles=cycles,
        statistics_scope='final cumulative DRAM counters',
        ignored_interval_records=len(intervals),
        final_statistics_line=log.count('\n',0,stats.start())+1,
        completion_line=log.count('\n',0,end.start())+1)
