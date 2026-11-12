"""grams x per-100 g profile -> nutrients with an interval (portion range x recipe-variant range)."""
from __future__ import annotations

from dataclasses import dataclass

from ..models import IntakeRecord
from ..nutrients import KEYS, MEALS, NUTRIENTS

MEAL_ORDER = {k: i for i, (k, _) in enumerate(MEALS)}
from .composition import Profile, all_profiles


@dataclass
class Estimate:
    grams: float
    point: dict[str, float]
    low: dict[str, float]
    high: dict[str, float]
    style: str


def estimate(profile: Profile, grams: float, style: str = "mean", portion_low: float | None = None,
             portion_high: float | None = None, rel_halfwidth: float = 0.20) -> Estimate:
    base = profile.per100(style)
    g_lo = min(grams, portion_low) if portion_low else grams * (1 - rel_halfwidth)
    g_hi = max(grams, portion_high) if portion_high else grams * (1 + rel_halfwidth)
    return Estimate(grams,
                    {k: grams * base[k] / 100 for k in KEYS},
                    {k: g_lo * profile.low[k] / 100 for k in KEYS},
                    {k: g_hi * profile.high[k] / 100 for k in KEYS}, style)


def item_nutrients(item, profiles=None) -> dict[str, float]:
    profiles = profiles or all_profiles()
    if item.dish_id:
        p = profiles.get(item.dish.code)
        if not p:
            return {k: 0.0 for k in KEYS}
        base = p.per100(item.style)
        return {k: item.grams * base[k] / 100 for k in KEYS}
    ing = item.ingredient
    return {k: item.grams * getattr(ing, k) / 100 for k in KEYS}


def record_summary(record: IntakeRecord) -> dict:
    """Totals per record, per meal, supplements, top contributors, % of reference values and macro split."""
    profiles = all_profiles()
    rows, meals, totals = [], {}, {k: 0.0 for k in KEYS}
    gl_total = 0.0
    items = sorted(record.items.select_related("dish", "ingredient"), key=lambda it: (MEAL_ORDER.get(it.meal, 9), it.created_at))
    for item in items:
        n = item_nutrients(item, profiles)
        gl = None
        if item.dish_id and (p := profiles.get(item.dish.code)):
            gl = p.gl_per_serving(item.grams, item.style)
        elif item.ingredient_id and item.ingredient.gi is not None:
            gl = item.ingredient.gi * max(item.ingredient.carb_g - item.ingredient.fiber_g, 0) * item.grams / 10000
        gl_total += gl or 0
        rows.append({"item": item, "n": n, "gl": gl})
        m = meals.setdefault(item.get_meal_display(), {k: 0.0 for k in KEYS})
        for k in KEYS:
            m[k] += n[k]
            totals[k] += n[k]
    supp_totals = {k: 0.0 for k in KEYS}
    supp_rows = []
    for s in record.supplements.select_related("supplement"):
        n = {k: getattr(s.supplement, k) * s.doses for k in KEYS}
        supp_rows.append({"s": s, "n": n})
        for k in KEYS:
            supp_totals[k] += n[k]
    with_supp = {k: totals[k] + supp_totals[k] for k in KEYS}
    target = record.participant.energy_target_kcal or 2000
    pct = []
    for nut in NUTRIENTS:
        ref = nut.reference
        if nut.key == "kcal":
            ref = target
        if ref:
            v = with_supp[nut.key]
            pct.append({"n": nut, "value": v, "ref": ref, "pct": 100 * v / ref, "food": totals[nut.key]})
    e = totals["kcal"] or 1
    macro = {"Protein": 4 * totals["protein_g"] / e * 100, "Fat": 9 * totals["fat_g"] / e * 100,
             "Carbohydrate": 4 * totals["carb_g"] / e * 100}
    fa = {"SFA": 9 * totals["sfa_g"] / e * 100, "MUFA": 9 * totals["mufa_g"] / e * 100, "PUFA": 9 * totals["pufa_g"] / e * 100}
    contrib = sorted(rows, key=lambda r: -r["n"]["kcal"])[:5]
    return {"rows": rows, "meals": meals, "totals": totals, "supp_rows": supp_rows, "supp_totals": supp_totals,
            "with_supp": with_supp, "pct": pct, "macro_pct": macro, "fa_pct_energy": fa, "gl_total": gl_total,
            "contributors": contrib}


def insights(summary: dict) -> list[dict]:
    """Rule-based interpretation of one intake record (no external AI): level is good / warn / crit."""
    t, w = summary["totals"], summary["with_supp"]
    out = []
    e = t["kcal"]
    if not summary["rows"]:
        return out
    fat_pct, sfa_pct = summary["macro_pct"]["Fat"], summary["fa_pct_energy"]["SFA"]
    if fat_pct > 35:
        out.append({"level": "warn", "icon": "droplet-half", "text": f"Fat supplies {fat_pct:.0f}% of energy, above the 20–35% range."})
    if sfa_pct > 10:
        out.append({"level": "crit", "icon": "exclamation-octagon", "text": f"Saturated fat is {sfa_pct:.1f}% of energy; the WHO recommends less than 10%."})
    if w["sodium_mg"] > 2300:
        out.append({"level": "crit", "icon": "moisture", "text": f"Sodium is {w['sodium_mg']:,.0f} mg, above the 2,300 mg upper limit."})
    if t["fiber_g"] < 25 and e > 1000:
        out.append({"level": "warn", "icon": "flower1", "text": f"Fibre is {t['fiber_g']:.0f} g; adults are advised 25–30 g a day."})
    if summary["gl_total"] > 120:
        out.append({"level": "warn", "icon": "graph-up-arrow", "text": f"Daily glycaemic load is {summary['gl_total']:.0f} (above 120 is considered high)."})
    hidden = [r for r in summary["rows"] if r["item"].dish_id and r["item"].style in ("restaurant", "mean")]
    if hidden:
        k = sum(r["n"]["kcal"] for r in hidden)
        out.append({"level": "warn", "icon": "eye-slash", "text": f"{len(hidden)} dish(es) are recorded as restaurant or unknown preparation ({k:,.0f} kcal). "
                    "Confirming the preparation narrows the hidden-fat range most."})
    top = summary["contributors"][:3]
    if top:
        names = ", ".join(f"{r['item'].food_name} ({100 * r['n']['kcal'] / e:.0f}%)" for r in top) if e else ""
        out.append({"level": "info", "icon": "pie-chart", "text": f"Largest energy sources: {names}."})
    for key, label in (("iron_mg", "Iron"), ("calcium_mg", "Calcium")):
        ref = 18 if key == "iron_mg" else 1300
        if w[key] < 0.5 * ref:
            out.append({"level": "warn", "icon": "capsule", "text": f"{label} is {w[key]:.0f} {'mg'} ({100 * w[key] / ref:.0f}% of the reference value)."})
    if not any(i["level"] in ("warn", "crit") for i in out):
        out.insert(0, {"level": "good", "icon": "check-circle", "text": "No nutrient exceeded the limits checked here."})
    return out
