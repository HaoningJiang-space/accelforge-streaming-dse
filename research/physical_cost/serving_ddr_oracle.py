"""Check recorded command streams against Ramulator's DDR4 specification."""

from collections import defaultdict, deque


def check(trace, device):
    config = device.to_config()
    ids = {op: i for i, op in enumerate(device.commands)}
    ticks = dict(zip(device.timing_params, config["timing"], strict=True))
    incoming = defaultdict(list)
    for level, before, after, delay, *options in config["timing_constraints"]:
        if len(options) > 1 and options[1]:
            continue  # one rank
        window = options[0] if options else 1
        for a in after:
            incoming[a].extend((level, p, delay, window) for p in before)
    issued = defaultdict(lambda: deque(maxlen=4))
    opened = {}
    last_ca, last_data, last_refresh = -1, 0, 0
    transfers = []
    for event in trace:
        t, op = event.cycle, event.op
        loc = (event.group, event.bank)
        command = ids[op]
        scope = ((), (0,), (0, event.group), (0, *loc))
        assert t > last_ca
        assert t - last_refresh <= ticks["nREFI"]
        for level, prev, delay, window in incoming[command]:
            history = issued[scope[level], prev]
            assert len(history) < window or t - history[-window] >= delay, (event, delay, history)
        for key in scope:
            issued[key, command].append(t)
        last_ca = t
        if op == "ACT":
            assert loc not in opened
            opened[loc] = event.row
        elif op == "PREpb":
            assert opened.pop(loc) == event.row
        elif op == "PREab":
            opened.clear()
            # Rank-level PREab applies its precharge time to all banks.
            for group in range(4):
                for bank in range(4):
                    issued[(0, group, bank), ids["PREpb"]].append(t)
        elif op == "REFab":
            assert not opened
            last_refresh = t
        else:
            assert opened.get(loc) == event.row
            stripe = event.address // 128
            assert (stripe % 4, stripe // 4 % 4, event.address // 2048) == (*loc, event.row)
            ck = ticks["tCK_ps"]
            assert t * ck >= event.arrival_ps
            data = t + ticks["nCL" if op == "RD" else "nCWL"]
            assert data >= last_data
            last_data = data + ticks["nBL"]
            transfers.append((event.address, op, data * ck, last_data * ck))
    return transfers
