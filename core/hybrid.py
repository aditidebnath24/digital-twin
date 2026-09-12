"""
Hybrid digital-twin run.

Historical observations = ground truth.
Prediction equations = baseline forecast.
Simulation equations run twice (control + scenario) → delta.
Optional bias-correction fits affine map on last 48 h of (sim, obs).
"""

from __future__ import annotations

from typing import Any, Dict, List, Sequence

from core.predictor import run_prediction
from core.simulator import run_simulation
from data.observations import aqi_from_pm25, history, pollutant_value, snapshot


def _uses(ids: Sequence[str], key: str) -> bool:
    return any(key in i for i in ids)


def run_hybrid(
    location: str,
    species: str,
    traffic_mult: float,
    stubble_mult: float,
    horizon_hours: int,
    sim_eq_ids: Sequence[str],
    pred_eq_ids: Sequence[str],
) -> Dict[str, Any]:
    rows = history(location)
    last = snapshot(location)
    observed_now = pollutant_value(last, species)

    pred = run_prediction(location, species, pred_eq_ids, horizon_hours)
    sim_ctrl = run_simulation(location, species, 1.0, 1.0, sim_eq_ids, horizon_hours)
    sim_scen = run_simulation(
        location, species, traffic_mult, stubble_mult, sim_eq_ids, horizon_hours
    )

    use_bias = _uses(pred_eq_ids, "bias")
    a, b = 1.0, 0.0
    if use_bias:
        n = min(48, len(rows))
        sx = sy = sxy = sx2 = 0.0
        start = len(sim_ctrl["past"]) - n
        for i in range(n):
            x = sim_ctrl["past"][start + i]
            y = pollutant_value(rows[len(rows) - n + i], species)
            sx += x
            sy += y
            sxy += x * y
            sx2 += x * x
        den = n * sx2 - sx * sx
        if abs(den) > 1e-6:
            a = (n * sxy - sx * sy) / den
            b = (sy - a * sx) / n
            a = min(1.4, max(0.6, a))
            b = min(40.0, max(-40.0, b))

    series: List[Dict[str, Any]] = []
    hist_start = max(0, len(rows) - 48)
    for i in range(hist_start, len(rows)):
        obs = pollutant_value(rows[i], species)
        simulated = sim_ctrl["past"][i]
        predicted = pred["past_fit"][i]
        hybrid = a * simulated + b if use_bias else predicted
        series.append(
            {
                "ts": rows[i].ts.isoformat(),
                "hour": i - len(rows),
                "observed": obs,
                "predicted": predicted,
                "simulated": simulated,
                "hybrid": hybrid,
            }
        )

    for h in range(1, horizon_hours + 1):
        predicted = pred["future"][h - 1]
        simulated = sim_scen["future"][h - 1]
        delta = sim_scen["future"][h - 1] - sim_ctrl["future"][h - 1]
        hybrid = predicted + delta
        if use_bias:
            hybrid = 0.55 * hybrid + 0.45 * (a * simulated + b)
        series.append(
            {
                "ts": (last.ts.replace(tzinfo=last.ts.tzinfo) if last.ts.tzinfo else last.ts)
                .__class__.fromtimestamp(
                    last.ts.timestamp() + h * 3600, tz=last.ts.tzinfo
                )
                .isoformat()
                if hasattr(last.ts, "timestamp")
                else last.ts.isoformat(),
                "hour": h,
                "observed": None,
                "predicted": predicted,
                "simulated": simulated,
                "hybrid": round(max(5.0, hybrid), 1),
            }
        )

    # cleaner future timestamps
    from datetime import timedelta

    for h in range(1, horizon_hours + 1):
        series[-(horizon_hours - h + 1)]["ts"] = (last.ts + timedelta(hours=h)).isoformat()

    now_pred = pred["past_fit"][-1]
    now_sim = sim_scen["past"][-1]
    now_delta = sim_scen["past"][-1] - sim_ctrl["past"][-1]
    now_hybrid = round(observed_now + now_delta, 1)

    # Physics scenario delta = mean(sim_scenario − sim_control) over the forecast
    sim_deltas = [
        sim_scen["future"][i] - sim_ctrl["future"][i]
        for i in range(len(sim_scen["future"]))
    ]
    scenario_delta = round(sum(sim_deltas) / max(1, len(sim_deltas)), 1)

    aqi_val, aqi_label = aqi_from_pm25(
        now_hybrid if species.upper() in ("PM2.5", "PM25") else observed_now
    )

    notes = [
        f"Ground truth: {location} historical series ending 1 Jan 2025 00:00 IST.",
        "Prediction archive supplies the baseline forecast from station history.",
        "Simulation archive is run at control and scenario emission multipliers; difference is the scenario delta.",
    ]
    if use_bias:
        notes.append(f"Bias correction fitted on last 48 h: C ≈ {a:.2f}·C_sim + {b:.1f}.")
    if traffic_mult != 1.0 or stubble_mult != 1.0:
        notes.append(
            f"Scenario multipliers — traffic ×{traffic_mult:.2f}, stubble ×{stubble_mult:.2f}."
        )

    return {
        "location": location,
        "species": species,
        "traffic_mult": traffic_mult,
        "stubble_mult": stubble_mult,
        "horizon_hours": horizon_hours,
        "series": series,
        "now": {
            "observed": observed_now,
            "predicted": round(now_pred, 1),
            "simulated": round(now_sim, 1),
            "hybrid": now_hybrid,
            "aqi": aqi_val,
            "aqi_label": aqi_label,
        },
        "scenario_delta": scenario_delta,
        "method_notes": notes,
    }
