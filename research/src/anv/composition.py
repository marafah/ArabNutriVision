"""Recipe-based composition table for Arabic composite dishes.

Per-100 g cooked profile of dish d (any nutrient n):

    p_dn = 100 * sum_k(w_dk * c_kn * r_kn) / Y_d

w_dk  raw edible weight of ingredient k in the batch (g)
c_kn  nutrient n per gram of ingredient k (ingredients.csv / 100)
r_kn  retention factor (1.0 for energy and macronutrients; USDA tables for vitamins)
Y_d   cooked batch weight (g) -- yield accounts for water absorbed or lost.

Each dish has several preparation variants (home / restaurant / light). Their spread is
kept as an uncertainty range, so "hidden fat" becomes an interval instead of an error.
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path

NUTRIENTS = ["kcal", "protein_g", "fat_g", "carb_g", "fiber_g", "sodium_mg", "iron_mg", "calcium_mg"]
DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def load_ingredients(path: Path = DATA_DIR / "ingredients.csv") -> dict[str, dict[str, float]]:
    table: dict[str, dict[str, float]] = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            table[row["id"]] = {n: float(row[n]) for n in NUTRIENTS} | {"name": row["name"]}
    return table


def load_recipes(path: Path = DATA_DIR / "recipes.json") -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)["dishes"]


@dataclass
class DishProfile:
    id: str
    en: str
    ar: str
    category: str
    serving_g: float
    per100: dict[str, float]                      # mean over variants
    per100_low: dict[str, float]                  # min over variants
    per100_high: dict[str, float]                 # max over variants
    variants: dict[str, dict[str, float]] = field(default_factory=dict)
    energy_from_fat_pct: float = 0.0


def variant_per100(ing: dict[str, float], cooked_g: float, ingredients: dict,
                   retention: dict | None = None) -> dict[str, float]:
    retention = retention or {}
    totals = {n: 0.0 for n in NUTRIENTS}
    for k, grams in ing.items():
        if k not in ingredients:
            raise KeyError(f"Unknown ingredient '{k}' - add it to ingredients.csv")
        for n in NUTRIENTS:
            totals[n] += grams * ingredients[k][n] / 100.0 * retention.get((k, n), 1.0)
    return {n: round(100.0 * v / cooked_g, 2) for n, v in totals.items()}


def build_table(ingredients=None, recipes=None) -> list[DishProfile]:
    ingredients = ingredients or load_ingredients()
    recipes = recipes or load_recipes()
    out = []
    for d in recipes:
        vs = {name: variant_per100(v["ing"], v["cooked_g"], ingredients) for name, v in d["variants"].items()}
        mean = {n: round(sum(v[n] for v in vs.values()) / len(vs), 2) for n in NUTRIENTS}
        low = {n: min(v[n] for v in vs.values()) for n in NUTRIENTS}
        high = {n: max(v[n] for v in vs.values()) for n in NUTRIENTS}
        fat_pct = round(100 * 9 * mean["fat_g"] / mean["kcal"], 1) if mean["kcal"] else 0.0
        out.append(DishProfile(d["id"], d["en"], d["ar"], d["category"], d["serving_g"],
                               mean, low, high, vs, fat_pct))
    return out


def table_as_dict(table: list[DishProfile]) -> dict[str, DishProfile]:
    return {p.id: p for p in table}
