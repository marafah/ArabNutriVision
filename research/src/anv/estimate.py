"""Recipe-aware nutrient estimation: grams x per-100 g recipe profile, with an interval.

The interval combines portion uncertainty and recipe (hidden-fat) uncertainty:
    low  = portion.low  * per100_low  / 100
    high = portion.high * per100_high / 100
If the recogniser reports a preparation style ("home", "restaurant", "light") with
confidence, the matching variant replaces the mean as the point estimate.
"""
from __future__ import annotations

from dataclasses import dataclass

from .composition import NUTRIENTS, DishProfile
from .portion import PortionEstimate


@dataclass
class NutrientEstimate:
    dish_id: str
    grams: float
    point: dict[str, float]
    low: dict[str, float]
    high: dict[str, float]
    method: str


def estimate(profile: DishProfile, portion: PortionEstimate, style: str | None = None) -> NutrientEstimate:
    base = profile.variants.get(style, profile.per100) if style else profile.per100
    point = {n: round(portion.grams * base[n] / 100, 1) for n in NUTRIENTS}
    low = {n: round(portion.low * profile.per100_low[n] / 100, 1) for n in NUTRIENTS}
    high = {n: round(portion.high * profile.per100_high[n] / 100, 1) for n in NUTRIENTS}
    return NutrientEstimate(profile.id, portion.grams, point, low, high,
                            f"recipe-aware/{portion.method}/{style or 'mean'}")


def combine_meal(items: list[NutrientEstimate]) -> dict[str, float]:
    """Sum a meal or a 24-h recall."""
    return {n: round(sum(i.point[n] for i in items), 1) for n in NUTRIENTS}
