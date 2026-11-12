"""Food Frequency Questionnaire import (CSV or Excel) -> average daily intake.

Expected columns (case-insensitive): food, frequency, portion_g
  food       dish code / ingredient code / English or Arabic name
  frequency  number with a unit: "2/day", "3/week", "1/month", "never", or a plain number = times per day
  portion_g  grams per eating occasion (blank -> the dish's typical serving)
"""
from __future__ import annotations

import csv
import io
import re

from ..models import Dish, Ingredient

PER_DAY = {"day": 1, "d": 1, "يوم": 1, "week": 1 / 7, "w": 1 / 7, "wk": 1 / 7, "أسبوع": 1 / 7, "month": 1 / 30.4, "m": 1 / 30.4, "شهر": 1 / 30.4}
TEMPLATE = "food,frequency,portion_g\nmaqluba,2/week,400\nhummus,4/week,150\nfalafel,3/week,100\nolive_oil,1/day,10\nknafeh,1/month,150\n"


def parse_frequency(text) -> float:
    s = str(text or "").strip().lower()
    if not s or s in ("never", "0", "أبدا"):
        return 0.0
    m = re.match(r"^\s*([0-9]*\.?[0-9]+)\s*(?:x|times)?\s*(?:/|per|في|بال)?\s*([a-zء-ي]+)?", s)
    if not m:
        raise ValueError(f"Cannot read frequency '{text}'")
    n, unit = float(m.group(1)), (m.group(2) or "day")
    for key, factor in PER_DAY.items():
        if unit.startswith(key):
            return n * factor
    raise ValueError(f"Unknown frequency unit '{unit}'")


def _rows_from_upload(upload) -> list[dict]:
    name = upload.name.lower()
    if name.endswith((".xlsx", ".xlsm")):
        from openpyxl import load_workbook
        ws = load_workbook(upload, read_only=True, data_only=True).active
        it = ws.iter_rows(values_only=True)
        head = [str(h or "").strip().lower() for h in next(it)]
        return [dict(zip(head, r)) for r in it if any(v not in (None, "") for v in r)]
    text = upload.read().decode("utf-8-sig")
    return [{(k or "").strip().lower(): v for k, v in r.items()} for r in csv.DictReader(io.StringIO(text))]


def match_food(token: str):
    t = str(token or "").strip()
    if not t:
        return None, None
    d = Dish.objects.filter(code__iexact=t).first() or Dish.objects.filter(name_en__iexact=t).first() \
        or Dish.objects.filter(name_ar=t).first() or Dish.objects.filter(name_en__istartswith=t).first()
    if d:
        return d, None
    i = Ingredient.objects.filter(code__iexact=t).first() or Ingredient.objects.filter(name__istartswith=t).first()
    return None, i


def parse(upload) -> tuple[list[dict], list[str]]:
    lines, errors = [], []
    for n, r in enumerate(_rows_from_upload(upload), start=2):
        try:
            dish, ing = match_food(r.get("food"))
            if not dish and not ing:
                raise ValueError(f"food '{r.get('food')}' is not in the composition table")
            per_day = parse_frequency(r.get("frequency"))
            portion = float(r.get("portion_g") or (dish.serving_g if dish else 100))
            if per_day > 0:
                lines.append({"dish": dish, "ingredient": ing, "per_day": per_day, "portion_g": portion,
                              "grams_per_day": per_day * portion})
        except (ValueError, TypeError) as e:
            errors.append(f"Row {n}: {e}")
    return lines, errors
