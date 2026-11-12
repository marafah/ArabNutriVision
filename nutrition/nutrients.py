"""Nutrient catalogue shared by models, services, templates and exports."""
from dataclasses import dataclass

from django.utils.translation import gettext_lazy as _


@dataclass(frozen=True)
class Nutrient:
    key: str
    label: str
    label_ar: str
    unit: str
    group: str
    reference: float | None = None      # adult reference value for % display (FDA Daily Value unless noted)
    upper: bool = False                 # True when the reference is an upper limit (sodium, SFA...)


NUTRIENTS: list[Nutrient] = [
    Nutrient("kcal", "Energy", "الطاقة", "kcal", "energy", 2000),
    Nutrient("protein_g", "Protein", "البروتين", "g", "macro", 50),
    Nutrient("fat_g", "Total fat", "الدهون الكلية", "g", "macro", 78),
    Nutrient("carb_g", "Carbohydrate", "الكربوهيدرات", "g", "macro", 275),
    Nutrient("fiber_g", "Dietary fibre", "الألياف", "g", "macro", 28),
    Nutrient("sfa_g", "Saturated fat", "دهون مشبعة", "g", "fatty_acids", 20, upper=True),
    Nutrient("mufa_g", "Monounsaturated fat", "دهون أحادية", "g", "fatty_acids"),
    Nutrient("pufa_g", "Polyunsaturated fat", "دهون متعددة", "g", "fatty_acids"),
    Nutrient("cholesterol_mg", "Cholesterol", "الكوليسترول", "mg", "fatty_acids", 300, upper=True),
    Nutrient("sodium_mg", "Sodium", "الصوديوم", "mg", "minerals", 2300, upper=True),
    Nutrient("potassium_mg", "Potassium", "البوتاسيوم", "mg", "minerals", 4700),
    Nutrient("calcium_mg", "Calcium", "الكالسيوم", "mg", "minerals", 1300),
    Nutrient("iron_mg", "Iron", "الحديد", "mg", "minerals", 18),
    Nutrient("magnesium_mg", "Magnesium", "المغنيسيوم", "mg", "minerals", 420),
    Nutrient("zinc_mg", "Zinc", "الزنك", "mg", "minerals", 11),
    Nutrient("vitc_mg", "Vitamin C", "فيتامين C", "mg", "vitamins", 90),
    Nutrient("vita_rae_ug", "Vitamin A (RAE)", "فيتامين A", "µg", "vitamins", 900),
]
KEYS = [n.key for n in NUTRIENTS]
BY_KEY = {n.key: n for n in NUTRIENTS}
CORE = ["kcal", "protein_g", "fat_g", "carb_g", "fiber_g", "sodium_mg", "iron_mg", "calcium_mg"]
GROUP_LABELS = {
    "energy": _("Energy"), "macro": _("Macronutrients"), "fatty_acids": _("Fatty acids & cholesterol"),
    "minerals": _("Minerals"), "vitamins": _("Vitamins"),
}
STYLES = [("home", _("Home")), ("restaurant", _("Restaurant")), ("light", _("Light"))]
MEALS = [("breakfast", _("Breakfast")), ("lunch", _("Lunch")), ("dinner", _("Dinner")), ("snack", _("Snack"))]
ADDED_FAT = {"veg_oil", "olive_oil", "ghee", "butter"}
FAT_RICH = {"tahini", "almonds", "pine_nuts", "coconut", "white_cheese"}
MEAT = {"chicken_skin_raw", "chicken_breast_raw", "chicken_thigh_raw", "lamb_raw", "beef_ground_raw", "lamb_ground_raw"}
# Vitamin C retention for cooked dishes (approximation of USDA Table of Nutrient Retention Factors, Release 6).
VITC_RETENTION_COOKED = 0.5


def fmt(value: float, unit: str) -> str:
    if value is None:
        return "–"
    if unit in ("kcal", "mg", "µg"):
        return f"{value:,.0f}"
    return f"{value:,.1f}"
