"""RQ1/RQ2 benchmark: zero-shot vision-language models vs the recipe-aware pipeline.

Input: data/annotations.csv (one row per image, weighed ground truth) + data/images/.
For each image, each system returns kcal, protein, fat, carbs. Results -> results/benchmark.csv,
then summary metrics (MAE, MAPE, bootstrap CI, Bland-Altman, Wilcoxon) -> results/summary.json.

    export ANTHROPIC_API_KEY=...   # and/or OPENAI_API_KEY, GOOGLE_API_KEY
    python scripts/benchmark_vlm.py --systems claude_zero,claude_hint,recipe_aware --limit 50
"""
from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from anv.composition import build_table, table_as_dict  # noqa: E402
from anv.estimate import estimate  # noqa: E402
from anv.evaluate import paired_wilcoxon, summary  # noqa: E402
from anv.portion import prior_portion  # noqa: E402

TABLE = table_as_dict(build_table())
DISH_LIST = ", ".join(f"{p.id} ({p.en} / {p.ar})" for p in TABLE.values())

ZERO_SHOT = ("Estimate the nutrition of the food on the plate in this photo. Reply with only JSON: "
             '{"dish": str, "grams": number, "kcal": number, "protein_g": number, "fat_g": number, "carb_g": number}')
HINT = ZERO_SHOT + " The dish is: {dish_en}. Account for oil, ghee and meat that may be hidden under rice or bread."
RECOG = ("Identify this Arabic dish and estimate the plated portion in grams. Choose dish_id from: " + DISH_LIST +
         '. Reply with only JSON: {"dish_id": str, "grams": number, "style": "home"|"restaurant"|"light"}')


def _claude(prompt: str, img_path: Path, model: str = "claude-sonnet-4-5") -> dict:
    import anthropic  # pip install anthropic
    client = anthropic.Anthropic()
    data = base64.standard_b64encode(img_path.read_bytes()).decode()
    media = "image/png" if img_path.suffix.lower() == ".png" else "image/jpeg"
    msg = client.messages.create(model=model, max_tokens=400, messages=[{"role": "user", "content": [
        {"type": "image", "source": {"type": "base64", "media_type": media, "data": data}},
        {"type": "text", "text": prompt}]}])
    text = msg.content[0].text
    return json.loads(text[text.find("{"): text.rfind("}") + 1])


def run_system(name: str, row: dict, img: Path) -> dict:
    if name == "claude_zero":
        return _claude(ZERO_SHOT, img)
    if name == "claude_hint":
        return _claude(HINT.format(dish_en=TABLE[row["dish_id"]].en), img)
    if name == "recipe_aware":
        r = _claude(RECOG, img)
        prof = TABLE.get(r.get("dish_id"), TABLE[row["dish_id"]])
        p = prior_portion(float(r.get("grams") or prof.serving_g))
        return estimate(prof, p, r.get("style")).point
    if name == "recipe_oracle":   # upper bound: true dish + true grams
        prof = TABLE[row["dish_id"]]
        return estimate(prof, prior_portion(float(row["weight_g"]), 0.0)).point
    raise ValueError(name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--systems", default="claude_zero,claude_hint,recipe_aware,recipe_oracle")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    systems = args.systems.split(",")
    rows = list(csv.DictReader(open(ROOT / "data" / "annotations.csv", encoding="utf-8")))
    rows = rows[: args.limit] if args.limit else rows
    out_dir = ROOT / "results"
    out_dir.mkdir(exist_ok=True)
    records = []
    for row in rows:
        img = ROOT / "data" / "images" / row["image_file"]
        for s in systems:
            try:
                r = run_system(s, row, img)
                records.append({"image": row["image_file"], "system": s, "true_kcal": row["kcal"],
                                "true_fat_g": row["fat_g"], "kcal": r.get("kcal"), "fat_g": r.get("fat_g"),
                                "protein_g": r.get("protein_g"), "carb_g": r.get("carb_g")})
            except Exception as e:  # keep going; record failure
                print(f"[{s}] {row['image_file']}: {e}")
    with open(out_dir / "benchmark.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(records[0]))
        w.writeheader()
        w.writerows(records)
    res = {}
    for s in systems:
        rs = [r for r in records if r["system"] == s and r["kcal"] is not None]
        res[s] = summary([float(r["kcal"]) for r in rs], [float(r["true_kcal"]) for r in rs], s)
    if "recipe_aware" in res and "claude_zero" in res:
        a = {r["image"]: float(r["kcal"]) for r in records if r["system"] == "recipe_aware"}
        b = {r["image"]: float(r["kcal"]) for r in records if r["system"] == "claude_zero"}
        t = {r["image"]: float(r["true_kcal"]) for r in records}
        common = sorted(set(a) & set(b))
        res["wilcoxon_recipe_vs_zero"] = paired_wilcoxon([a[i] for i in common], [b[i] for i in common], [t[i] for i in common])
    (out_dir / "summary.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
