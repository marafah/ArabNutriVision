import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from anv.composition import build_table, table_as_dict  # noqa: E402
from anv.estimate import estimate  # noqa: E402
from anv.evaluate import interval_coverage, mae, mape  # noqa: E402
from anv.portion import card_scaled, mm_per_px_from_card, prior_portion  # noqa: E402


def test_table_builds_and_is_plausible():
    t = table_as_dict(build_table())
    assert len(t) >= 20
    for p in t.values():
        assert 30 < p.per100["kcal"] < 500, p.id
        assert p.per100_low["kcal"] <= p.per100["kcal"] <= p.per100_high["kcal"]
        # Atwater check: 4/9/4 energy within 15% of the stored kcal
        atw = 4 * p.per100["protein_g"] + 9 * p.per100["fat_g"] + 4 * p.per100["carb_g"]
        assert abs(atw - p.per100["kcal"]) / p.per100["kcal"] < 0.15, p.id


def test_estimate_interval_contains_point():
    p = table_as_dict(build_table())["maqluba"]
    e = estimate(p, prior_portion(400))
    assert e.low["kcal"] <= e.point["kcal"] <= e.high["kcal"]


def test_card_scale():
    card = np.array([[0, 0], [856, 0], [856, 539.8], [0, 539.8]])
    assert abs(mm_per_px_from_card(card) - 0.1) < 1e-6
    mask = np.ones((1000, 1000))            # 100 x 100 mm = 100 cm^2
    g = card_scaled(mask, card, "hummus").grams
    assert abs(g - 100 * 1.5 * 1.05) < 1e-6


def test_metrics():
    assert mae([110, 90], [100, 100]) == 10
    assert mape([110, 90], [100, 100]) == 10
    assert interval_coverage([0, 0], [5, 1], [3, 3]) == 0.5
