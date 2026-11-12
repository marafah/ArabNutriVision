"""Validation metrics used in the paper (pure Python, no numpy dependency)."""
from __future__ import annotations

import math
import random
import statistics as st


def mae(pred, true):
    return sum(abs(p - t) for p, t in zip(pred, true)) / len(true) if true else None


def mape(pred, true):
    pairs = [(p, t) for p, t in zip(pred, true) if t]
    return 100 * sum(abs(p - t) / t for p, t in pairs) / len(pairs) if pairs else None


def bootstrap_ci(pred, true, metric=mape, n_boot=1000, seed=0):
    if len(true) < 3:
        return None
    rng = random.Random(seed)
    idx = range(len(true))
    vals = []
    for _ in range(n_boot):
        s = [rng.choice(idx) for _ in idx]
        vals.append(metric([pred[i] for i in s], [true[i] for i in s]))
    vals.sort()
    return vals[int(0.025 * n_boot)], vals[int(0.975 * n_boot) - 1]


def bland_altman(pred, true):
    d = [p - t for p, t in zip(pred, true)]
    if len(d) < 2:
        return None
    bias, sd = st.mean(d), st.stdev(d)
    return {"bias": bias, "loa_low": bias - 1.96 * sd, "loa_high": bias + 1.96 * sd,
            "points": [{"x": (p + t) / 2, "y": p - t} for p, t in zip(pred, true)]}


def summary(pred, true):
    if not true:
        return None
    ci = bootstrap_ci(pred, true)
    return {"n": len(true), "mae": mae(pred, true), "mape": mape(pred, true), "mape_ci": ci,
            "ba": bland_altman(pred, true)}


def coverage(lows, highs, true):
    return 100 * sum(lo <= t <= hi for lo, hi, t in zip(lows, highs, true)) / len(true) if true else None


def safe_round(x, nd=1):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(x, nd)
