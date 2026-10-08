"""Ensemble agreement: a simple, honest measure of forecast confidence.

This is NOT a calibrated probability that the forecast is right. It only says
how tightly the ensemble members cluster. A tight ensemble usually means a
more predictable situation, which is what ordinary users mean by "confidence".
Once observations are collected, these scores should be recalibrated against
real forecast error by lead time.

Scores run 0–100; levels are high / medium / low.
"""

import math
from typing import Literal

import numpy as np

ConfidenceLevel = Literal["high", "medium", "low"]

HIGH_THRESHOLD = 65.0
MEDIUM_THRESHOLD = 35.0

# P90 − P10 temperature spread (°C) below which members are considered to agree
# essentially perfectly. Beyond it, agreement decays with a 4 °C e-folding scale:
# 2 °C spread ≈ 78, 4 °C ≈ 47, 6 °C ≈ 29, 8 °C ≈ 17.
_TEMP_SPREAD_FLOOR_C = 1.0
_TEMP_SPREAD_SCALE_C = 4.0


def temperature_agreement(p10: np.ndarray | float, p90: np.ndarray | float) -> np.ndarray:
    spread = np.maximum(np.asarray(p90) - np.asarray(p10) - _TEMP_SPREAD_FLOOR_C, 0.0)
    return 100.0 * np.exp(-spread / _TEMP_SPREAD_SCALE_C)


def precip_agreement(probability: np.ndarray | float) -> np.ndarray:
    """Members agree when nearly all are wet or nearly all are dry.

    A 50% chance is maximal disagreement (score 0); 0% or 100% is full
    agreement (score 100).
    """
    return 100.0 * np.abs(2.0 * np.asarray(probability) - 1.0)


def combined_agreement(
    temp_score: np.ndarray | float, precip_score: np.ndarray | float
) -> np.ndarray:
    # Temperature is weighted a little higher: it matters to every forecast,
    # while rain agreement matters mostly when rain is plausible.
    return 0.6 * np.asarray(temp_score) + 0.4 * np.asarray(precip_score)


def level_for(score: float | None) -> ConfidenceLevel | None:
    if score is None or math.isnan(score):
        return None
    if score >= HIGH_THRESHOLD:
        return "high"
    if score >= MEDIUM_THRESHOLD:
        return "medium"
    return "low"
