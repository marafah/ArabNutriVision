"""Evaluation metrics used in the paper.

- MAE / MAPE per nutrient
- Bland-Altman bias and 95% limits of agreement
- Bootstrap 95% CI of the mean absolute error
- Paired Wilcoxon signed-rank test between two systems' absolute errors
- Prediction-interval coverage (RQ4)
"""
from __future__ import annotations

import numpy as np
from scipy import stats


def mae(pred, true) -> float:
    p, t = np.asarray(pred, float), np.asarray(true, float)
    return float(np.mean(np.abs(p - t)))


def mape(pred, true) -> float:
    p, t = np.asarray(pred, float), np.asarray(true, float)
    return float(100 * np.mean(np.abs(p - t) / t))


def bland_altman(pred, true) -> dict:
    p, t = np.asarray(pred, float), np.asarray(true, float)
    d = p - t
    bias, sd = float(d.mean()), float(d.std(ddof=1))
    return {"bias": bias, "loa_low": bias - 1.96 * sd, "loa_high": bias + 1.96 * sd,
            "mean_pairs": ((p + t) / 2).tolist(), "diff": d.tolist()}


def bootstrap_ci(pred, true, metric=mae, n_boot: int = 2000, seed: int = 0) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    p, t = np.asarray(pred, float), np.asarray(true, float)
    idx = rng.integers(0, len(p), size=(n_boot, len(p)))
    vals = np.array([metric(p[i], t[i]) for i in idx])
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def paired_wilcoxon(pred_a, pred_b, true) -> dict:
    t = np.asarray(true, float)
    ea, eb = np.abs(np.asarray(pred_a) - t), np.abs(np.asarray(pred_b) - t)
    res = stats.wilcoxon(ea, eb)
    return {"statistic": float(res.statistic), "p_value": float(res.pvalue)}


def interval_coverage(low, high, true) -> float:
    lo, hi, t = (np.asarray(x, float) for x in (low, high, true))
    return float(np.mean((t >= lo) & (t <= hi)))


def summary(pred, true, label: str = "") -> dict:
    lo, hi = bootstrap_ci(pred, true)
    return {"label": label, "n": len(true), "MAE": mae(pred, true), "MAE_CI95": (lo, hi),
            "MAPE": mape(pred, true), **{k: v for k, v in bland_altman(pred, true).items()
                                          if k in ("bias", "loa_low", "loa_high")}}
