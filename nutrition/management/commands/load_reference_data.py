"""Load the Arabic Recipe Composition Table (ingredients, draft recipes, supplements).

    python manage.py load_reference_data          # idempotent: updates existing rows
"""
import csv
import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from nutrition.models import Dish, Ingredient, RecipeLine, RecipeVariant, Supplement
from nutrition.nutrients import KEYS
from nutrition.services.composition import invalidate

DATA = Path(__file__).resolve().parents[2] / "data"
RAW_DISHES = {"tabbouleh", "fattoush"}

SUPPLEMENTS = [
    ("Iron (ferrous sulfate 325 mg)", "1 tablet", {"iron_mg": 65}),
    ("Calcium carbonate 500 mg", "1 tablet", {"calcium_mg": 500}),
    ("Vitamin C 500 mg", "1 tablet", {"vitc_mg": 500}),
    ("Zinc 15 mg", "1 tablet", {"zinc_mg": 15}),
    ("Magnesium 250 mg", "1 tablet", {"magnesium_mg": 250}),
    ("Adult multivitamin-mineral (typical)", "1 tablet", {"vitc_mg": 90, "vita_rae_ug": 900, "iron_mg": 18, "zinc_mg": 11, "magnesium_mg": 50, "calcium_mg": 200}),
    ("Omega-3 fish oil 1 g", "1 capsule", {"kcal": 9, "fat_g": 1.0, "pufa_g": 0.6, "sfa_g": 0.3, "mufa_g": 0.1}),
]


class Command(BaseCommand):
    help = "Load ingredients, draft standard recipes and supplement presets"

    @transaction.atomic
    def handle(self, *args, **opts):
        ext = {r["id"]: r for r in csv.DictReader(open(DATA / "ingredients_ext.csv", encoding="utf-8"))}
        n_ing = 0
        for r in csv.DictReader(open(DATA / "ingredients.csv", encoding="utf-8")):
            e = ext.get(r["id"], {})
            vals = {k: float(r[k]) if k in r else float(e.get(k) or 0) for k in KEYS}
            note = r.get("source_note", "")
            Ingredient.objects.update_or_create(code=r["id"], defaults={
                "name": r["name"], **vals, "gi": float(e["gi"]) if e.get("gi") else None,
                "source_note": f"{note}; ext: {e.get('source_note', '')}".strip("; "),
                "is_estimate": "estimate" in (note + r["name"]).lower()})
            n_ing += 1
        recipes = json.load(open(DATA / "recipes.json", encoding="utf-8"))["dishes"]
        ings = {i.code: i for i in Ingredient.objects.all()}
        for d in recipes:
            dish, _ = Dish.objects.update_or_create(code=d["id"], defaults={
                "name_en": d["en"], "name_ar": d["ar"], "category": d["category"], "serving_g": d["serving_g"],
                "is_raw": d["id"] in RAW_DISHES, "is_custom": False})
            for style, v in d["variants"].items():
                var, _ = RecipeVariant.objects.update_or_create(dish=dish, style=style, defaults={"cooked_g": v["cooked_g"]})
                var.lines.all().delete()
                RecipeLine.objects.bulk_create([RecipeLine(variant=var, ingredient=ings[k], grams=g) for k, g in v["ing"].items()])
        for name, dose, vals in SUPPLEMENTS:
            Supplement.objects.update_or_create(name=name, defaults={"dose_label": dose, **{k: vals.get(k, 0) for k in KEYS}})
        invalidate()
        self.stdout.write(self.style.SUCCESS(f"{n_ing} ingredients, {len(recipes)} dishes, {len(SUPPLEMENTS)} supplements loaded"))
