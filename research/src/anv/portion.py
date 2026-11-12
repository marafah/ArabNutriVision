"""Portion (grams) estimation from a single image.

Three estimators, in increasing order of required input:

1. prior_portion   - no geometry: the dish's typical serving size (baseline).
2. card_scaled     - a credit-card reference (85.6 x 53.98 mm) in the photo gives mm-per-pixel;
                     food area from a segmentation mask x a dish-specific height x density.
3. depth_volume    - a depth map (iPhone LiDAR / TrueDepth) integrated over the mask.

Dish heights and densities are calibrated on the weighed ArabFood-N training sessions
(see scripts/calibrate_density.py); the defaults below are placeholders.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

CARD_W_MM, CARD_H_MM = 85.6, 53.98

# Placeholder calibration: mean food height on the plate (cm) and bulk density (g/cm^3).
DEFAULT_GEOMETRY = {
    "maqluba": (3.5, 0.80), "mansaf": (4.0, 0.85), "kabsa": (3.5, 0.78), "musakhan": (2.0, 0.70),
    "mujaddara": (3.0, 0.82), "freekeh_chicken": (3.5, 0.80), "ruz_shaariyeh": (3.0, 0.75),
    "hummus": (1.5, 1.05), "mutabbal": (1.5, 0.98), "foul": (2.0, 1.02), "tabbouleh": (2.5, 0.55),
    "fattoush": (4.0, 0.35), "falafel": (3.0, 0.55), "warak_enab": (2.0, 0.95),
}


@dataclass
class PortionEstimate:
    grams: float
    low: float
    high: float
    method: str


def prior_portion(serving_g: float, rel_sd: float = 0.35) -> PortionEstimate:
    return PortionEstimate(serving_g, serving_g * (1 - rel_sd), serving_g * (1 + rel_sd), "prior")


def mm_per_px_from_card(card_corners_px: np.ndarray) -> float:
    """card_corners_px: 4x2 array (clockwise). Uses the mean of long and short edge scales."""
    c = np.asarray(card_corners_px, dtype=float)
    edges = [np.linalg.norm(c[i] - c[(i + 1) % 4]) for i in range(4)]
    long_px = (edges[0] + edges[2]) / 2 if edges[0] > edges[1] else (edges[1] + edges[3]) / 2
    short_px = (edges[1] + edges[3]) / 2 if edges[0] > edges[1] else (edges[0] + edges[2]) / 2
    return float(np.mean([CARD_W_MM / long_px, CARD_H_MM / short_px]))


def card_scaled(mask: np.ndarray, card_corners_px: np.ndarray, dish_id: str,
                geometry: dict = DEFAULT_GEOMETRY) -> PortionEstimate:
    mm_px = mm_per_px_from_card(card_corners_px)
    area_cm2 = mask.astype(bool).sum() * (mm_px / 10.0) ** 2
    h_cm, rho = geometry.get(dish_id, (3.0, 0.8))
    g = area_cm2 * h_cm * rho
    return PortionEstimate(g, g * 0.8, g * 1.2, "card")


def depth_volume(mask: np.ndarray, depth_m: np.ndarray, plate_depth_m: float,
                 fx: float, fy: float, dish_id: str, geometry: dict = DEFAULT_GEOMETRY) -> PortionEstimate:
    """Integrate height above the plate plane over the mask (pinhole camera model)."""
    m = mask.astype(bool)
    h = np.clip(plate_depth_m - depth_m, 0, None)               # metres above plate
    px_area = (depth_m / fx) * (depth_m / fy)                     # m^2 per pixel at that depth
    vol_cm3 = float((h * px_area)[m].sum() * 1e6)
    rho = geometry.get(dish_id, (3.0, 0.8))[1]
    g = vol_cm3 * rho
    return PortionEstimate(g, g * 0.88, g * 1.12, "depth")
