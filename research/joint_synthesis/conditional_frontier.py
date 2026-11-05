"""Exact componentwise demand frontier; equal-vector sources may be folded."""


def frontier(states):
    kept=[]
    for state in states:
        v=state.vector
        if any(all(a<=b for a,b in zip(old.vector,v)) for old in kept):
            continue
        kept=[old for old in kept if not all(a<=b for a,b in zip(v,old.vector))]
        kept.append(state)
    return kept


def conditioned(states,property_key):
    groups={}
    for state in states:
        groups.setdefault(property_key(state),[]).append(state)
    return {key:frontier(group)for key,group in groups.items()}
