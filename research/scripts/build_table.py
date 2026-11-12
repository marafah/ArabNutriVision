"""Build the Arabic Recipe Composition Table (CSV + JSON for the web app).

    python scripts/build_table.py
"""
import csv
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from anv.composition import NUTRIENTS, build_table  # noqa: E402

table = build_table()
out_csv = ROOT / "data" / "dish_table.csv"
with open(out_csv, "w", newline="", encoding="utf-8") as fh:
    w = csv.writer(fh)
    w.writerow(["id", "en", "ar", "category", "serving_g", "energy_from_fat_pct"]
               + [f"{n}_per100" for n in NUTRIENTS] + [f"{n}_low" for n in NUTRIENTS] + [f"{n}_high" for n in NUTRIENTS])
    for p in table:
        w.writerow([p.id, p.en, p.ar, p.category, p.serving_g, p.energy_from_fat_pct]
                   + [p.per100[n] for n in NUTRIENTS] + [p.per100_low[n] for n in NUTRIENTS]
                   + [p.per100_high[n] for n in NUTRIENTS])
(ROOT / "data" / "dish_table.json").write_text(
    json.dumps([asdict(p) for p in table], ensure_ascii=False, indent=1), encoding="utf-8")
print(f"{len(table)} dishes -> {out_csv.name}, dish_table.json")
for p in table:
    print(f"{p.id:22s} {p.per100['kcal']:6.0f} kcal/100g  ({p.per100_low['kcal']:.0f}-{p.per100_high['kcal']:.0f})  fat {p.energy_from_fat_pct}% kcal")
