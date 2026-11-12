"""Computational analyses for Paper 1 that can be run BEFORE image data exist.

All numbers derive from the provisional standard recipes (data/recipes.json) and ingredient
table (data/ingredients.csv). They quantify how much of the energy of Arabic composite dishes
is set by preparation (hidden fat) rather than by what is visible, and what error budget that
implies for any image-based estimator. Re-run after Amna's weighed recipes replace the drafts.

    python scripts/paper_analysis.py            # -> results/analysis.json, results/*.csv, results/figures/*
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from anv.composition import NUTRIENTS, build_table, load_ingredients, load_recipes  # noqa: E402

OUT = ROOT / "results"
FIG = OUT / "figures"
FIG.mkdir(parents=True, exist_ok=True)

ADDED_FAT = {"veg_oil", "olive_oil", "ghee", "butter"}
FAT_RICH = {"tahini", "almonds", "pine_nuts", "coconut", "white_cheese"}
MEAT = {"chicken_skin_raw", "chicken_breast_raw", "chicken_thigh_raw", "lamb_raw", "beef_ground_raw", "lamb_ground_raw"}

ING = load_ingredients()
REC = {d["id"]: d for d in load_recipes()}
TAB = {p.id: p for p in build_table(ING, list(REC.values()))}


def boot_ci(x, n=5000, seed=0):
    x = np.asarray(x, float)
    rng = np.random.default_rng(seed)
    m = x[rng.integers(0, len(x), (n, len(x)))].mean(1)
    return float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def group(k):
    if k in ADDED_FAT:
        return "added_fat"
    if k in FAT_RICH:
        return "fat_rich_ingredients"
    if k in MEAT:
        return "meat_cut_and_amount"
    return "other"


# ---------------------------------------------------------------- A. composition table + variant spread
rows_a = []
for d, p in TAB.items():
    v = p.variants
    kc = {s: v[s]["kcal"] for s in v}
    rows_a.append({"dish": d, "en": p.en.split(" (")[0], "ar": p.ar, "category": p.category, "serving_g": p.serving_g,
                   "kcal_mean": p.per100["kcal"], "kcal_light": kc.get("light"), "kcal_home": kc.get("home"),
                   "kcal_restaurant": kc.get("restaurant"),
                   "fat_mean": p.per100["fat_g"], "fat_light": v["light"]["fat_g"], "fat_restaurant": v["restaurant"]["fat_g"],
                   "protein_mean": p.per100["protein_g"], "carb_mean": p.per100["carb_g"],
                   "energy_from_fat_pct": p.energy_from_fat_pct,
                   "rest_vs_light_pct": round(100 * (kc["restaurant"] - kc["light"]) / kc["light"], 1),
                   "spread_pct_of_mean": round(100 * (p.per100_high["kcal"] - p.per100_low["kcal"]) / p.per100["kcal"], 1),
                   "atwater_dev_pct": round(100 * ((4 * p.per100["protein_g"] + 9 * p.per100["fat_g"] + 4 * p.per100["carb_g"]) - p.per100["kcal"]) / p.per100["kcal"], 1)})

# ---------------------------------------------------------------- B. decomposition of restaurant-light gap
rows_b = []
for d, r in REC.items():
    hi, lo = r["variants"]["restaurant"], r["variants"]["light"]
    contrib = {g: 0.0 for g in ("added_fat", "fat_rich_ingredients", "meat_cut_and_amount", "other")}
    for k in set(hi["ing"]) | set(lo["ing"]):
        e = ING[k]["kcal"] / 100
        delta = 100 * (hi["ing"].get(k, 0) * e / hi["cooked_g"] - lo["ing"].get(k, 0) * e / lo["cooked_g"])
        contrib[group(k)] += delta
    tot = sum(contrib.values())
    rows_b.append({"dish": d, "gap_kcal_per100": round(tot, 1), **{g: round(c, 1) for g, c in contrib.items()},
                   "share_fat_sources_pct": round(100 * (contrib["added_fat"] + contrib["fat_rich_ingredients"] + contrib["meat_cut_and_amount"]) / tot, 1) if tot else None,
                   "share_added_fat_pct": round(100 * contrib["added_fat"] / tot, 1) if tot else None})

# ---------------------------------------------------------------- C. irreducible error of a preparation-blind estimator
rows_c = []
for d, p in TAB.items():
    for n in ("kcal", "fat_g", "protein_g", "carb_g"):
        apes = [abs(p.per100[n] - v[n]) / v[n] * 100 for v in p.variants.values() if v[n] > 0]
        rows_c.append({"dish": d, "nutrient": n, "ape_mean": round(float(np.mean(apes)), 1), "ape_max": round(float(np.max(apes)), 1)})


def summ(n):
    x = [r["ape_mean"] for r in rows_c if r["nutrient"] == n]
    lo, hi = boot_ci(x)
    return {"mean": round(float(np.mean(x)), 1), "ci95": [round(lo, 1), round(hi, 1)], "median": round(float(np.median(x)), 1),
            "max_dish": max((r for r in rows_c if r["nutrient"] == n), key=lambda r: r["ape_mean"])["dish"]}


floor = {n: summ(n) for n in ("kcal", "fat_g", "protein_g", "carb_g")}

# ---------------------------------------------------------------- D. Monte Carlo error budget
SIGMAS = [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40]
STYLE_ACC = [1 / 3, 0.6, 0.8, 1.0]          # probability the recogniser picks the true preparation
N = 4000
SEEDS = range(5)
FAT_JITTER = 0.15                            # within-variant log-sd of added fat (assumption; sensitivity below)


def per100_with_fat_scale(d, s, scale):
    v = REC[d]["variants"][s]
    ing = {k: (g * scale if k in ADDED_FAT else g) for k, g in v["ing"].items()}
    out = {n: 0.0 for n in NUTRIENTS}
    for k, g in ing.items():
        for n in NUTRIENTS:
            out[n] += g * ING[k][n] / 100
    return {n: 100 * out[n] / v["cooked_g"] for n in NUTRIENTS}


def simulate(seed, sigma, style_acc, estimator, fat_jitter=FAT_JITTER, interval_r=0.20):
    rng = np.random.default_rng(seed)
    ape_e, ape_f, cover = [], [], []
    for d, p in TAB.items():
        styles = list(p.variants)
        for _ in range(N // len(TAB)):
            s = styles[rng.integers(len(styles))]
            true100 = per100_with_fat_scale(d, s, float(np.exp(rng.normal(0, fat_jitter))))
            g_true = p.serving_g * float(np.exp(rng.normal(0, 0.30)))
            g_hat = g_true * float(np.exp(rng.normal(0, sigma))) if sigma is not None else p.serving_g
            if estimator == "mean_profile":
                base = p.per100
            elif estimator == "style":
                s_hat = s if rng.random() < style_acc else styles[rng.integers(len(styles))]
                base = p.variants[s_hat]
            else:   # oracle variant
                base = p.variants[s]
            e_t, e_h = g_true * true100["kcal"] / 100, g_hat * base["kcal"] / 100
            f_t, f_h = g_true * true100["fat_g"] / 100, g_hat * base["fat_g"] / 100
            ape_e.append(abs(e_h - e_t) / e_t * 100)
            ape_f.append(abs(f_h - f_t) / f_t * 100)
            lo = g_hat * (1 - interval_r) * p.per100_low["kcal"] / 100
            hi = g_hat * (1 + interval_r) * p.per100_high["kcal"] / 100
            cover.append(lo <= e_t <= hi)
    return float(np.mean(ape_e)), float(np.mean(ape_f)), float(np.mean(cover))


mc = []
for sigma in SIGMAS:
    for est, acc in [("mean_profile", None), ("style", 0.6), ("style", 0.8), ("oracle_variant", None)]:
        res = np.array([simulate(sd, sigma, acc, est) for sd in SEEDS])
        mc.append({"sigma": sigma, "estimator": est if acc is None else f"style_acc{acc}",
                   "energy_mape": round(res[:, 0].mean(), 1), "energy_mape_sd": round(res[:, 0].std(ddof=1), 2),
                   "fat_mape": round(res[:, 1].mean(), 1), "coverage_pm20": round(res[:, 2].mean(), 3)})
prior = np.array([simulate(sd, None, None, "mean_profile") for sd in SEEDS])
mc_prior = {"energy_mape": round(prior[:, 0].mean(), 1), "fat_mape": round(prior[:, 1].mean(), 1), "coverage_pm20": round(prior[:, 2].mean(), 3)}

# interval width needed for 80% coverage as function of sigma (mean-profile estimator)
calib = []
for sigma in [0.0, 0.10, 0.20, 0.30]:
    best = None
    for r in np.arange(0.0, 0.71, 0.05):
        cov = np.mean([simulate(sd, sigma, None, "mean_profile", interval_r=float(r))[2] for sd in range(2)])
        if cov >= 0.80:
            best = (round(float(r), 2), round(float(cov), 3))
            break
    calib.append({"sigma": sigma, "portion_halfwidth_for_80pct": best[0] if best else None, "coverage": best[1] if best else None})

sens = []
for fj in (0.0, 0.10, 0.15, 0.25):
    res = np.array([simulate(sd, 0.0, None, "mean_profile", fat_jitter=fj) for sd in SEEDS])
    sens.append({"fat_jitter": fj, "energy_mape_perfect_portion": round(res[:, 0].mean(), 1), "fat_mape": round(res[:, 1].mean(), 1)})

# ---------------------------------------------------------------- E. sensitivity: +10 g added fat per batch
rows_e = []
for d, r in REC.items():
    v = r["variants"]["home"]
    rows_e.append({"dish": d, "kcal_per100_per_10g_oil": round(100 * 10 * 8.84 / v["cooked_g"], 2),
                   "kcal_per_serving_per_10g_oil": round(r["serving_g"] * 10 * 8.84 / v["cooked_g"], 1),
                   "pct_of_serving_energy": round(100 * (10 * 8.84 / v["cooked_g"]) / (TAB[d].variants["home"]["kcal"] / 100), 1)})

# ---------------------------------------------------------------- write
for name, rows in [("table1_composition", rows_a), ("table2_gap_decomposition", rows_b), ("table3_preparation_blind_error", rows_c),
                   ("table4_montecarlo", mc), ("table5_oil_sensitivity", rows_e)]:
    with open(OUT / f"{name}.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

fs = [r["share_fat_sources_pct"] for r in rows_b]
ad = [r["share_added_fat_pct"] for r in rows_b]
rl = [r["rest_vs_light_pct"] for r in rows_a]
efp = [r["energy_from_fat_pct"] for r in rows_a]
summary = {
    "n_dishes": len(TAB), "n_ingredients": len(ING),
    "restaurant_vs_light_pct": {"mean": round(float(np.mean(rl)), 1), "ci95": [round(x, 1) for x in boot_ci(rl)], "min": min(rl), "max": max(rl),
                                "min_dish": min(rows_a, key=lambda r: r["rest_vs_light_pct"])["dish"], "max_dish": max(rows_a, key=lambda r: r["rest_vs_light_pct"])["dish"]},
    "energy_from_fat_pct": {"mean": round(float(np.mean(efp)), 1), "min": min(efp), "max": max(efp), "n_above_35": sum(e > 35 for e in efp)},
    "gap_share_from_fat_sources_pct": {"mean": round(float(np.mean(fs)), 1), "ci95": [round(x, 1) for x in boot_ci(fs)], "min": min(fs)},
    "gap_share_added_fat_pct": {"mean": round(float(np.mean(ad)), 1), "ci95": [round(x, 1) for x in boot_ci(ad)]},
    "preparation_blind_floor_ape": floor,
    "atwater_max_abs_dev_pct": max(abs(r["atwater_dev_pct"]) for r in rows_a),
    "montecarlo": {"settings": {"N_per_seed": N, "seeds": list(SEEDS), "true_portion_logsd": 0.30, "fat_jitter_logsd": FAT_JITTER},
                   "grid": mc, "prior_portion_only": mc_prior, "interval_calibration": calib, "fat_jitter_sensitivity": sens},
    "oil_sensitivity_pct_serving_energy": {"mean": round(float(np.mean([r["pct_of_serving_energy"] for r in rows_e])), 1),
                                           "max": max(r["pct_of_serving_energy"] for r in rows_e),
                                           "max_dish": max(rows_e, key=lambda r: r["pct_of_serving_energy"])["dish"]},
}
(OUT / "analysis.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")

# ---------------------------------------------------------------- figures
import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": "#e3e6ec", "grid.linewidth": 0.6, "axes.axisbelow": True})
C = {"light": "#56682b", "home": "#3e6f8e", "restaurant": "#9a2a3c", "grey": "#8a8f84"}


def save(fig, name):
    fig.tight_layout(rect=(0, 0.08, 1, 1) if name.startswith("fig4") else None)
    fig.savefig(FIG / f"{name}.png", dpi=300)
    fig.savefig(FIG / f"{name}.pdf")
    plt.close(fig)


# Fig 2: kcal/100 g by variant
order = sorted(rows_a, key=lambda r: r["kcal_mean"])
fig, ax = plt.subplots(figsize=(7.0, 6.4))
y = np.arange(len(order))
ax.hlines(y, [r["kcal_light"] for r in order], [r["kcal_restaurant"] for r in order], color=C["grey"], lw=2, alpha=.6)
for s in ("light", "home", "restaurant"):
    ax.scatter([r[f"kcal_{s}"] for r in order], y, s=22, color=C[s], label=s.capitalize(), zorder=3)
ax.set_yticks(y, [r["en"] for r in order])
ax.set_xlabel("Energy (kcal per 100 g cooked dish)")
ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.09), ncol=3)
ax.grid(axis="y", visible=False)
ax.set_xlim(0, 480)
save(fig, "fig2_energy_by_variant")

# Fig 3: decomposition of gap
ob = sorted(rows_b, key=lambda r: r["gap_kcal_per100"])
fig, ax = plt.subplots(figsize=(7.0, 6.8))
left = np.zeros(len(ob))
cols = {"added_fat": "#c98a14", "fat_rich_ingredients": "#9a2a3c", "meat_cut_and_amount": "#3e6f8e", "other": "#b9bdb2"}
labs = {"added_fat": "Added oil / ghee / butter", "fat_rich_ingredients": "Tahini, nuts, cheese", "meat_cut_and_amount": "Meat cut and amount", "other": "Other ingredients and yield"}
for g in cols:
    vals = np.array([r[g] for r in ob])
    pos = np.clip(vals, 0, None)
    ax.barh(np.arange(len(ob)), pos, left=left, color=cols[g], label=labs[g], height=.7)
    left += pos
neg = np.array([min(0, r["other"]) for r in ob])
ax.barh(np.arange(len(ob)), neg, color=cols["other"], height=.7)
ax.set_xlim(min(neg.min(), 0) * 1.1, left.max() * 1.05)
ax.set_yticks(np.arange(len(ob)), [TAB[r["dish"]].en.split(" (")[0] for r in ob])
ax.set_xlabel("Restaurant minus light recipe (kcal per 100 g)")
ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=2)
ax.grid(axis="y", visible=False)
ax.axvline(0, color="#333", lw=0.8)
save(fig, "fig3_gap_decomposition")

# Fig 4: error budget
fig, axs = plt.subplots(1, 2, figsize=(7.4, 3.9))
names = {"mean_profile": "Preparation-blind (mean recipe)", "style_acc0.6": "Recipe-aware, style 60% correct",
         "style_acc0.8": "Recipe-aware, style 80% correct", "oracle_variant": "Recipe-aware, true style"}
colr = {"mean_profile": "#9a2a3c", "style_acc0.6": "#c98a14", "style_acc0.8": "#3e6f8e", "oracle_variant": "#56682b"}
for est in names:
    xs = [r["sigma"] * 100 for r in mc if r["estimator"] == est]
    axs[0].plot(xs, [r["energy_mape"] for r in mc if r["estimator"] == est], marker="o", ms=3, color=colr[est], label=names[est])
    axs[1].plot(xs, [r["fat_mape"] for r in mc if r["estimator"] == est], marker="o", ms=3, color=colr[est])
for a, t in zip(axs, ("Energy", "Fat")):
    a.set_xlabel("Portion estimation error (log-SD, %)")
    a.set_ylabel(f"{t} MAPE (%)")
    a.set_title(f"({'a' if t == 'Energy' else 'b'}) {t}", fontsize=11, loc="left")
    a.axhline(20, color="#8a8f84", ls=":", lw=1)
h, l = axs[0].get_legend_handles_labels()
fig.legend(h, l, frameon=False, loc="lower center", ncol=2, bbox_to_anchor=(0.5, -0.01))
fig.subplots_adjust(bottom=0.3)
save(fig, "fig4_error_budget")

print(json.dumps({k: v for k, v in summary.items() if k != "montecarlo"}, indent=1, ensure_ascii=False))
print("prior-only:", mc_prior)
print("calib:", calib)
print("sens:", sens)
for r in mc:
    if r["sigma"] in (0.0, 0.2, 0.3):
        print(r)
