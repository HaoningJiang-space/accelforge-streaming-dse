"""Stable dense and tiled softmax attention for the serving workload."""

from math import exp, fsum, sqrt


def dense(query, keys, values):
    scale = sqrt(len(query))
    logits = [fsum(q * k for q, k in zip(query, key, strict=True)) / scale for key in keys]
    peak = max(logits)
    weights = [exp(score - peak) for score in logits]
    denom = fsum(weights)
    return tuple(fsum(w * v for w, v in zip(weights, column, strict=True)) / denom
                 for column in zip(*values, strict=True))


def online(query, keys, values, tile):
    """Merge block maxima, normalizers and unnormalized value sums."""
    scale = sqrt(len(query))
    peak, denom = -float("inf"), 0.0
    weighted = [0.0] * len(values[0])
    for lo in range(0, len(keys), tile):
        hi = lo + tile
        scores = [sum(q * k for q, k in zip(query, key, strict=True)) / scale
                  for key in keys[lo:hi]]
        next_peak = max(peak, max(scores))
        old_weight = exp(peak - next_peak)
        weights = [exp(score - next_peak) for score in scores]
        denom = old_weight * denom + sum(weights)
        for i, column in enumerate(zip(*values[lo:hi], strict=True)):
            weighted[i] = old_weight * weighted[i] + sum(w * v for w, v in zip(weights, column, strict=True))
        peak = next_peak
    return tuple(v / denom for v in weighted)
