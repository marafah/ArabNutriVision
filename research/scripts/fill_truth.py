"""Fill ground-truth nutrients in data/annotations.csv from the weighed portion and the session's recipe variant.

    python scripts/fill_truth.py
"""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from anv.composition import build_table, table_as_dict  # noqa: E402

T = table_as_dict(build_table())
path = ROOT / "data" / "annotations.csv"
rows = list(csv.DictReader(open(path, encoding="utf-8")))
for r in rows:
    prof = T[r["dish_id"]]
    per100 = prof.variants.get(r.get("recipe_variant") or "", prof.per100)
    g = float(r["weight_g"])
    for n in ("kcal", "protein_g", "fat_g", "carb_g"):
        r[n] = round(g * per100[n] / 100, 1)
with open(path, "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
print(f"filled {len(rows)} rows")
