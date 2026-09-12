"""
Data-driven forecast on the (synthesised) historical window.
Equation selection changes the estimator:
  gbrt  → tabular lag + meteo
  lstm  → diurnal harmonic + residual smoothing
  kalman → sequential pull toward last observation
  lur   → blend with network mean
"""

from __future__ import annotations

import math
from typing import Dict, List, Sequence

from data.observations import history, pollutant_value, snapshot


def _uses(ids: Sequence[str], key: str) -> bool:
    return any(key in i for i in ids)


def _harmonic(hour: float, peak: float, amp: float) -> float:
    return 1.0 + amp * math.cos(((hour - peak) / 24.0) * 2.0 * math.pi)


def run_prediction(
    location: str,
    species: str,
    pred_eq_ids: Sequence[str],
    hours: int,
) -> Dict[str, List[float]]:
    rows = history(location)
    values = [pollutant_value(r, species) for r in rows]
    last = values[-1]
    use_gbrt = _uses(pred_eq_ids, "gbrt") or len(pred_eq_ids) == 0
    use_lstm = _uses(pred_eq_ids, "lstm")
    use_kalman = _uses(pred_eq_ids, "kalman")
    use_lur = _uses(pred_eq_ids, "lur")

    past_fit: List[float] = []
    persist = last
    for i, row in enumerate(rows):
        hour = i % 24
        lag1 = values[i - 1] if i > 0 else values[i]
        lag24 = values[i - 24] if i >= 24 else values[i]
        wind = row.wind_speed
        rh = row.humidity
        y = last
        if use_gbrt:
            y = (
                0.38 * lag1
                + 0.28 * lag24
                + 0.18 * last * _harmonic(hour, 5, 0.28)
                + 0.10 * last * (1.15 - 0.08 * wind)
                + 0.06 * last * (0.85 + 0.15 * (rh / 100.0))
            )
        if use_lstm:
            seq = 0.55 * persist + 0.45 * last * _harmonic(hour, 5, 0.30)
            y = 0.55 * y + 0.45 * seq if use_gbrt else seq
            persist = 0.7 * persist + 0.3 * values[i]
        if use_kalman:
            K = 0.45
            y = y + K * (values[i] - y)
        if use_lur:
            y = 0.85 * y + 0.15 * last
        past_fit.append(round(y, 1))

    future: List[float] = []
    state = last
    last_row = snapshot(location)
    for h in range(1, hours + 1):
        hour = h % 24
        lag24 = values[len(values) - 24 + (h % 24)] if len(values) >= 24 else last
        wind = last_row.wind_speed * (
            0.75 + 0.55 * max(0.0, math.sin(((hour - 8) / 12) * math.pi))
        )
        y = state * _harmonic(hour, 5, 0.28)
        if use_gbrt:
            y = (
                0.34 * state
                + 0.30 * lag24
                + 0.22 * last * _harmonic(hour, 5, 0.28)
                + 0.14 * last * (1.12 - 0.07 * wind)
            )
        if use_lstm:
            seq = 0.6 * state + 0.4 * last * _harmonic(hour, 5, 0.30)
            y = 0.5 * y + 0.5 * seq if use_gbrt else seq
        if use_kalman and h <= 6:
            y = 0.7 * y + 0.3 * last
        if use_lur:
            y = 0.88 * y + 0.12 * last
        y = round(max(8.0, y), 1)
        future.append(y)
        state = y
    return {"past_fit": past_fit, "future": future}
