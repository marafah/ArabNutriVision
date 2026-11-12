"""Recipe-aware composition: per-100 g profile of a cooked dish from its recipe variants.

    p_dn = 100 * sum_k(w_dk * c_kn * r_kn) / Y_d

w_dk raw edible grams of ingredient k in the batch, c_kn nutrient n per gram of k,
r_kn retention factor, Y_d cooked batch weight. The spread across preparation variants
(home / restaurant / light) is kept as the uncertainty interval for hidden fat.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from django.core.cache import cache

from ..models import Dish, RecipeVariant
from ..nutrients import ADDED_FAT, FAT_RICH, KEYS, MEAT, VITC_RETENTION_COOKED

CACHE_KEY = "anv-profiles-v1"


@dataclass
class Profile:
    dish_id: int
    code: str
    name: str
    name_ar: str
    category: str
    serving_g: float
    mean: dict[str, float]
    low: dict[str, float]
    high: dict[str, float]
    variants: dict[str, dict[str, float]] = field(default_factory=dict)
    gi: float | None = None
    gi_coverage: float = 0.0
    hidden_fat: list[str] = field(default_factory=list)
    has_estimates: bool = False

    @property
    def energy_from_fat_pct(self) -> float:
        return round(100 * 9 * self.mean["fat_g"] / self.mean["kcal"], 1) if self.mean["kcal"] else 0.0

    @property
    def spread_pct(self) -> float:
        return round(100 * (self.high["kcal"] - self.low["kcal"]) / self.mean["kcal"], 1) if self.mean["kcal"] else 0.0

    @property
    def bar(self) -> dict[str, float]:
        """Positions (% of a 0-500 kcal axis) for the range bar in tables."""
        s = 500.0
        return {"left": round(100 * self.low["kcal"] / s, 1), "width": round(100 * (self.high["kcal"] - self.low["kcal"]) / s, 1),
                "mean": round(100 * self.mean["kcal"] / s, 1)}

    def per100(self, style: str | None = None) -> dict[str, float]:
        return self.variants.get(style, self.mean) if style and style != "mean" else self.mean

    def gl_per_serving(self, grams: float | None = None, style: str | None = None) -> float | None:
        if self.gi is None:
            return None
        p = self.per100(style)
        g = grams if grams is not None else self.serving_g
        available = max(p["carb_g"] - p["fiber_g"], 0) * g / 100
        return round(self.gi * available / 100, 1)


def variant_per100(variant: RecipeVariant, is_raw: bool) -> tuple[dict[str, float], float, float]:
    """Return per-100 g nutrients plus (sum GI*available carb, sum available carb) for GI weighting."""
    totals = {k: 0.0 for k in KEYS}
    gi_num = gi_den = carb_all = 0.0
    for line in variant.lines.all():
        ing = line.ingredient
        f = line.grams / 100.0
        for k in KEYS:
            r = VITC_RETENTION_COOKED if (k == "vitc_mg" and not is_raw) else 1.0
            totals[k] += f * getattr(ing, k) * r
        avail = max(ing.carb_g - ing.fiber_g, 0) * f
        carb_all += avail
        if ing.gi is not None:
            gi_num += ing.gi * avail
            gi_den += avail
    per100 = {k: round(100 * v / variant.cooked_g, 3) for k, v in totals.items()}
    return per100, gi_num, gi_den, carb_all


def _build(dish: Dish) -> Profile | None:
    variants = list(dish.variants.all())
    if not variants:
        return None
    vs: dict[str, dict[str, float]] = {}
    gi_num = gi_den = carb_all = 0.0
    hidden: set[str] = set()
    estimates = False
    for v in variants:
        p, gn, gd, ca = variant_per100(v, dish.is_raw)
        vs[v.style] = p
        gi_num, gi_den, carb_all = gi_num + gn, gi_den + gd, carb_all + ca
        for line in v.lines.all():
            if line.ingredient.code in ADDED_FAT | FAT_RICH | MEAT:
                hidden.add(line.ingredient.name.split(",")[0].split(" (")[0])
            estimates = estimates or line.ingredient.is_estimate
    mean = {k: round(sum(v[k] for v in vs.values()) / len(vs), 2) for k in KEYS}
    low = {k: round(min(v[k] for v in vs.values()), 2) for k in KEYS}
    high = {k: round(max(v[k] for v in vs.values()), 2) for k in KEYS}
    gi = round(gi_num / gi_den) if gi_den > 0 and carb_all > 0 and gi_den / carb_all >= 0.6 else None
    return Profile(dish.pk, dish.code, dish.name_en, dish.name_ar, dish.category, dish.serving_g,
                   mean, low, high, vs, gi, round(gi_den / carb_all, 2) if carb_all else 0.0,
                   sorted(hidden), estimates)


def all_profiles(refresh: bool = False) -> dict[str, Profile]:
    profiles = None if refresh else cache.get(CACHE_KEY)
    if profiles is None:
        qs = Dish.objects.prefetch_related("variants__lines__ingredient")
        profiles = {d.code: p for d in qs if (p := _build(d))}
        cache.set(CACHE_KEY, profiles, 3600)
    return profiles


def profile_for(code: str) -> Profile | None:
    return all_profiles().get(code)


def invalidate():
    cache.delete(CACHE_KEY)


def gap_decomposition(dish: Dish) -> dict[str, float] | None:
    """Split the restaurant-minus-light energy gap (kcal/100 g) into ingredient groups."""
    vs = {v.style: v for v in dish.variants.prefetch_related("lines__ingredient")}
    if "restaurant" not in vs or "light" not in vs:
        return None
    hi, lo = vs["restaurant"], vs["light"]
    groups = {"Added oil / ghee / butter": 0.0, "Tahini, nuts, cheese": 0.0, "Meat cut and amount": 0.0, "Other ingredients and yield": 0.0}

    def grp(code):
        if code in ADDED_FAT:
            return "Added oil / ghee / butter"
        if code in FAT_RICH:
            return "Tahini, nuts, cheese"
        if code in MEAT:
            return "Meat cut and amount"
        return "Other ingredients and yield"

    lines = {}
    for v, sign in ((hi, 1), (lo, -1)):
        for line in v.lines.all():
            lines.setdefault(line.ingredient.code, [line.ingredient, 0.0, 0.0])
            lines[line.ingredient.code][1 if sign == 1 else 2] = line.grams
    for code, (ing, g_hi, g_lo) in lines.items():
        e = ing.kcal / 100
        groups[grp(code)] += 100 * (g_hi * e / hi.cooked_g - g_lo * e / lo.cooked_g)
    return {k: round(v, 1) for k, v in groups.items()}
