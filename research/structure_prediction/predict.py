"""Frozen structure-only and isolated-frontier hypotheses; standard library."""
def boundaries(ops, sizes):
    produced={t for op in ops for t in op['outputs']}
    users={t:{i for i,op in enumerate(ops) if t in op['inputs']} for t in sizes}
    live=set()
    rows=[]
    for i,op in enumerate(ops):
        passthrough=live-set(op['inputs'])
        rows.append(dict(op=op['name'],pass_tensors=sorted(passthrough),
                         pass_bytes=sum(sizes[t] for t in passthrough),
                         smallest_operand_bytes=min(sizes[t] for t in set(op['inputs'])|set(op['outputs']))))
        live.update(t for t in op['inputs'] if t not in produced)
        live.update(op['outputs'])
        live={t for t in live if any(j>i for j in users[t])}
    return rows


def predictions(boundary, locals_=None):
    def pack(candidates,plateau=None):
        values=sorted(set(candidates))
        return dict(plateau_bytes=max(values) if plateau is None else plateau,breakpoint_candidates=values)
    result=dict(P0=pack([r['smallest_operand_bytes'] for r in boundary]),
                P1=pack([r['pass_bytes']+r['smallest_operand_bytes'] for r in boundary]))
    if locals_ is not None:
        result['P2']=pack([r['pass_bytes']+p['capacity_bytes'] for r,curve in zip(boundary,locals_) for p in curve],
                          max(r['pass_bytes']+curve[-1]['capacity_bytes'] for r,curve in zip(boundary,locals_)))
    return result


def matching(predicted,actual,tolerance=.05):
    """Maximum cardinality bipartite matching; no cost-fitting or tolerance tuning."""
    assigned={}
    def assign(i,seen):
        neighbors=sorted((j for j,a in enumerate(actual) if abs(predicted[i]-a)/a<=tolerance),
                         key=lambda j:abs(predicted[i]-actual[j])/actual[j])
        for j in neighbors:
            if j in seen:
                continue
            seen.add(j)
            if j not in assigned or assign(assigned[j],seen):
                assigned[j]=i
                return True
        return False
    for i in range(len(predicted)):
        assign(i,set())
    pairs=[dict(predicted=predicted[i],actual=actual[j],relative_error=abs(predicted[i]-actual[j])/actual[j])
           for j,i in sorted(assigned.items())]
    return dict(predicted_count=len(predicted),actual_count=len(actual),matched=len(pairs),
                precision=len(pairs)/len(predicted) if predicted else None,
                recall=len(pairs)/len(actual) if actual else None,pairs=pairs)


def evaluate(predicted,curve):
    plateau=curve[-1]['capacity_bytes']
    knees=[b['capacity_bytes'] for a,b in zip(curve,curve[1:])
           if (a['traffic_bytes']-b['traffic_bytes'])/a['traffic_bytes']>=.05-1e-12]
    return {name:dict(plateau_prediction=p['plateau_bytes'],plateau_actual=plateau,
                      signed_relative_error=(p['plateau_bytes']-plateau)/plateau,
                      absolute_relative_error=abs(p['plateau_bytes']-plateau)/plateau,
                      breakpoints=matching(p['breakpoint_candidates'],knees)) for name,p in predicted.items()}
