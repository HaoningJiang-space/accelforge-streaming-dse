"""Explicit *conditional witness* for complete-T1 sequential barriers.

These events are constructed independently; they are not reconstructed FFM
physical events. A Storage declaration is not evidence that a copy exists.
The abstract oracle makes the chosen copy and no-recomputation assumptions
explicit and refuses to certify FFM branches or physical capacities.
"""


class CopyWitness:
    """Finite element/version state machine for a single X copy.

    An element's final value is produced before being copied, and a surviving
    copy is read only after the barrier. The producer's abstract value is not a
    modeled physical buffer and cannot serve the post-barrier consumer.
    """
    def __init__(self, m, n, location, *, capture_events=False):
        if any(type(x) is not int or x <= 0 for x in (m,n)):
            raise ValueError('positive integer dimensions required')
        if location not in ('MainMemory','GlobalBuffer'):
            raise ValueError('unsupported witness location')
        self.expected = {(i,j) for i in range(m) for j in range(n)}
        self.location = location
        self.phase = 'producer'
        self.produced = {}
        self.copies = {}  # copy_id -> (location, {index: version})
        self.consumed = set()
        self.writes = self.reads = 0
        self.events = [] if capture_events else None

    def _event(self, kind, **details):
        if self.events is not None:
            self.events.append(dict(kind=kind,**details))

    def produce(self, index, version, value=None):
        if self.phase != 'producer' or index not in self.expected or index in self.produced or version != 'final':
            raise ValueError('invalid or duplicate final production')
        self.produced[index] = (version,value)
        self._event('produce_final',tensor='T1',index=index,version=version,value=value)

    def create_copy(self, copy_id, location):
        if self.phase != 'producer' or self.copies or location != self.location:
            raise ValueError('invalid copy declaration')
        self.copies[copy_id] = (location,{})
        self._event('create_hypothetical_copy',copy_id=copy_id,location=location)

    def write(self, copy_id, index, version):
        if (self.phase != 'producer' or copy_id not in self.copies or version != 'final'
                or index not in self.produced or self.produced[index][0] != version):
            raise ValueError('write requires an already produced matching version')
        location, contents = self.copies[copy_id]
        if index in contents:
            raise ValueError('witness writes each element once')
        contents[index] = self.produced[index]
        self.writes += 1
        self._event('write_hypothetical_copy',copy_id=copy_id,location=location,index=index,version=version,
                    value=self.produced[index][1])

    def barrier(self):
        if self.phase != 'producer' or set(self.produced) != self.expected:
            raise ValueError('all final elements must be produced before the barrier')
        if any(not any(contents.get(idx, (None,None))[0] == 'final' for _,contents in self.copies.values()) for idx in self.expected):
            raise ValueError('every final element needs a surviving copy')
        self.phase = 'consumer'
        self._event('logical_barrier',live_values=len(self.expected),physical_copy_validity='assumed')

    def read(self, copy_id, index, version):
        if self.phase != 'consumer' or copy_id not in self.copies:
            raise ValueError('read requires a post-barrier copy')
        location,contents = self.copies[copy_id]
        payload = contents.get(index)
        if payload is None or payload[0] != version or version != 'final' or index in self.consumed:
            raise ValueError('missing, stale or duplicate consumption')
        self.consumed.add(index)
        self.reads += 1
        self._event('read_hypothetical_copy',copy_id=copy_id,location=location,index=index,version=version,value=payload[1])
        return payload[1]

    def finish(self):
        if self.phase != 'consumer' or self.consumed != self.expected:
            raise ValueError('consumer has not read every required final element')
        self.phase = 'finished'
        return dict(elements=len(self.expected),version='final',location=self.location,
                    copy_ids=list(self.copies),minimum_hypothetical_writes_bits=self.writes*8,
                    minimum_hypothetical_reads_bits=self.reads*8,
                    trace_kind='constructed witness; not the FFM execution trace',
                    physical_copy_identity='unproved',cut_occupancy='unknown',
                    safe_to_prune=False,events=self.events)


def make_witness(m,n,location,*,capture_events=False):
    oracle = CopyWitness(m,n,location,capture_events=capture_events)
    oracle.create_copy('witness-copy-0',location)
    # One concrete mathematical test input: A contains deterministic 8-bit
    # values and both square weight matrices are identities. This checks data
    # version integrity; it is not a trace of the FFM loop nest.
    source = [[(17*i+19*j)%251 for j in range(n)] for i in range(m)]
    x = [[sum(source[i][k] * int(k == j) for k in range(n)) for j in range(n)] for i in range(m)]
    received = [[None for _ in range(n)] for _ in range(m)]
    for i in range(m):
        for j in range(n):
            oracle.produce((i,j),'final',x[i][j])
            oracle.write('witness-copy-0',(i,j),'final')
    oracle.barrier()
    for i in range(m):
        for j in range(n):
            received[i][j] = oracle.read('witness-copy-0',(i,j),'final')
    result = oracle.finish()
    actual_y = [[sum(received[i][k] * int(k == j) for k in range(n)) for j in range(n)] for i in range(m)]
    expected_y = [[sum(x[i][k] * int(k == j) for k in range(n)) for j in range(n)] for i in range(m)]
    if received != x or actual_y != expected_y:
        raise AssertionError('identity-weight two-MatMul logical values differ')
    result['identity_weight_functional_check'] = True
    result['functional_check_scope'] = 'one concrete input; not an FFM loop or physical transfer trace'
    return result


def compare_main_actions(witness, observed):
    """Compare conditional mandatory counts to recorded per-tensor FFM actions.

    Recorded actions and the conditional minimum are not additive: they might
    be the very same traffic. Equality of counts is not an event-level match.
    """
    write = observed.get('Matmul0<SEP>action<SEP>MainMemory<SEP>T1<SEP>write',0.)
    read = observed.get('Matmul1<SEP>action<SEP>MainMemory<SEP>T1<SEP>read',0.)
    if witness['location'] == 'MainMemory':
        required_write = witness['minimum_hypothetical_writes_bits']
        required_read = witness['minimum_hypothetical_reads_bits']
        consistent = write >= required_write and read >= required_read
    else:
        required_write = required_read = 0
        consistent = True  # a GB witness does not forbid other MainMemory copies
    return dict(observed_producer_main_write_bits=write,observed_consumer_main_read_bits=read,
                conditional_min_write_bits=required_write,conditional_min_read_bits=required_read,
                counts_are_consistent=consistent,additional_lower_bound_proved_bits=0,
                explanation='conditional counts may overlap actions already charged; no extra traffic is proven')
