"""
Technical Decomposition Module (rule-based offline).
Replace `decompose` body with an LLM call in production.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

from data.observations import parse_station_hint


def decompose(user_query: str) -> Dict[str, Any]:
    q = user_query.lower()

    species = []
    for s in ["pm2.5", "pm25", "pm10", "no2", "so2", "o3", "ozone", "co", "nh3", "bc"]:
        if s in q.replace("₂", "2").replace("₃", "3"):
            if s in ("pm2.5", "pm25"):
                species.append("PM2.5")
            elif s == "pm10":
                species.append("PM10")
            elif s == "no2":
                species.append("NO2")
            elif s in ("o3", "ozone"):
                species.append("O3")
            elif s == "so2":
                species.append("SO2")
            elif s == "co":
                species.append("CO")
            else:
                species.append(s.upper())
    if not species:
        species = ["PM2.5"]

    horizon = "short_term"
    horizon_hours = 48
    if any(w in q for w in ["72", "3 day", "three day", "next 3"]):
        horizon, horizon_hours = "72h", 72
    elif any(w in q for w in ["48", "2 day", "two day"]):
        horizon, horizon_hours = "48h", 48
    elif any(w in q for w in ["24", "tomorrow", "next day"]):
        horizon, horizon_hours = "24h", 24
    elif any(w in q for w in ["nowcast", "current", "now", "real-time"]):
        horizon, horizon_hours = "nowcast", 6

    stubble = any(w in q for w in ["stubble", "burning", "biomass", "parali"])
    traffic = any(w in q for w in ["traffic", "vehicle", "diesel", "bus", "vkt", "fleet"])
    has_scenario = stubble or traffic or any(
        w in q for w in ["scenario", "what if", "impact if", "reduce", "increase", "cut by", "emission"]
    )

    scale = "station"
    if any(
        w in q.split()
        for w in ["city", "delhi", "ncr"]
    ) or "urban background" in q:
        scale = "urban"
    if any(w in q for w in ["street", "canyon", "roadside"]):
        scale = "street"

    sim_parts = []
    pred_parts = []
    if stubble:
        sim_parts.append("stubble burning agricultural residue emission biomass")
    if traffic:
        sim_parts.append(
            "traffic emission vehicle fleet source coupling scenario"
        )
    if has_scenario:
        sim_parts.append("emission scenario dispersion mass balance mixing height")
    sim_parts.append(" ".join(species))
    sim_parts.append("dispersion transport chemistry box model ventilation")

    pred_parts.append(" ".join(species))
    pred_parts.append("forecast prediction")
    if horizon_hours >= 24:
        pred_parts.append(f"{horizon_hours}h horizon sequence model")
    if has_scenario:
        pred_parts.append("bias correction hybrid residual kalman")
    else:
        pred_parts.append("lstm gradient boosting station forecast")

    technical_description = {
        "original_query": user_query,
        "target_species": list(dict.fromkeys(species)),
        "spatial_scale": scale,
        "temporal_horizon": horizon,
        "horizon_hours": horizon_hours,
        "scenario_requested": has_scenario,
        "scenario_elements": {"stubble_burning": stubble, "traffic": traffic},
        "station_hint": parse_station_hint(user_query),
        "required_outputs": ["concentration_forecast"]
        + (["scenario_delta"] if has_scenario else []),
        "delhi_context": True,
    }

    filters: Dict[str, Any] = {"species": species}
    if scale in ("urban", "street"):
        filters["scale"] = scale

    return {
        "technical_description": technical_description,
        "simulation_query": " ".join(sim_parts),
        "prediction_query": " ".join(pred_parts),
        "filters": filters,
        "top_k_sim": 7,
        "top_k_pred": 3,
    }


def _first_percent(pattern: str, text: str) -> Optional[float]:
    m = re.search(pattern, text, re.I)
    if not m:
        return None
    return float(m.group(1)) / 100.0


def parse_scenario_percents(query: str) -> Dict[str, float]:
    """Parse 'stubble increases by 40%' / 'reduce traffic 30%' into multipliers."""
    q = query.lower()
    traffic_mult = 1.0
    stubble_mult = 1.0
    mentions_stubble = bool(re.search(r"stubble|burning|biomass|parali", q))
    mentions_traffic = bool(re.search(r"traffic|vehicle|diesel|bus|fleet", q))

    inc = _first_percent(r"increas\w*(?:\s+\w+){0,3}\s+(\d{1,3})\s*%", q)
    dec = _first_percent(
        r"(?:reduc\w*|decreas\w*|cut)(?:\s+\w+){0,3}\s+(?:by\s+)?(\d{1,3})\s*%",
        q,
    )

    if mentions_stubble and inc is not None:
        stubble_mult = 1.0 + inc
    elif mentions_stubble and dec is not None and not mentions_traffic:
        stubble_mult = 1.0 - dec

    if mentions_traffic and dec is not None:
        traffic_mult = 1.0 - dec
    elif mentions_traffic and inc is not None and not mentions_stubble:
        traffic_mult = 1.0 + inc

    diesel = _first_percent(r"diesel[^%]{0,40}?(?:reduc\w*|cut)[^%]{0,12}?(\d{1,3})\s*%", q)
    if diesel is not None:
        traffic_mult = 1.0 - diesel * 0.6

    def clamp(x: float) -> float:
        return max(0.2, min(2.5, x))

    return {"traffic_mult": clamp(traffic_mult), "stubble_mult": clamp(stubble_mult)}


PRODUCTION_PROMPT_TEMPLATE = """
You are a technical analyst for an air-quality digital twin.
Given the user question, produce a JSON object with:
- technical_description (species, scale, horizon, scenario flags, required outputs)
- simulation_query (physics/process search string)
- prediction_query (forecasting / ML / assimilation search string)
- filters (species, scale, temporal constraints)

User question: {query}
"""
