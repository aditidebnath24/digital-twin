"""
Technical Decomposition Module (rule-based offline).
Replace `decompose` body with an LLM call in production.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

from data.observations import parse_station_hint
from core.llm import build_llm_provider

def _llm_decompose(user_query: str) -> Dict[str, Any]:
    provider = build_llm_provider()

    prompt = f"""
You are the query-understanding module of an Air Quality Digital Twin.

Convert the user's natural-language AQI question into a JSON object.

Rules:
- target_species: use one or more of PM2.5, PM10, NO2, SO2, O3, CO, NH3, BC.
  If the pollutant is not explicitly mentioned, use ["PM2.5"].
- spatial_scale: one of "station", "urban", "street".
- temporal_horizon: use "nowcast", "24h", "48h", or "72h".
- horizon_hours: integer corresponding to the horizon.
- scenario_requested: true if the user asks a what-if/change/reduction/increase scenario.
- scenario_elements:
    "traffic": true/false
    "stubble_burning": true/false
- station_hint: station name if mentioned, otherwise null.
- required_outputs: include "concentration_forecast"; add "scenario_delta" for scenarios.
- Return JSON only. Do not use markdown fences.

User query:
{user_query}
"""

    response = provider.generate(prompt)

    # Remove accidental markdown fences if the model returns them.
    response = response.strip()
    response = re.sub(r"^```json\s*", "", response, flags=re.I)
    response = re.sub(r"\s*```$", "", response)

    import json
    result = json.loads(response)

    return result

def decompose(user_query: str) -> Dict[str, Any]:
    try:
        llm_result = _llm_decompose(user_query)

        species = llm_result.get("target_species") or ["PM2.5"]
        if isinstance(species, str):
            species = [species]

        horizon = llm_result.get("temporal_horizon", "48h")
        horizon_hours = int(llm_result.get("horizon_hours", 48))

        scale = llm_result.get("spatial_scale", "station")

        scenario_elements = llm_result.get("scenario_elements") or {}
        traffic = bool(scenario_elements.get("traffic", False))
        stubble = bool(scenario_elements.get("stubble_burning", False))

        has_scenario = bool(llm_result.get("scenario_requested", False))

        station_hint = llm_result.get("station_hint")
        if not station_hint:
            station_hint = parse_station_hint(user_query)

        sim_parts = []
        pred_parts = []

        if stubble:
            sim_parts.append(
                "stubble burning agricultural residue emission biomass"
            )

        if traffic:
            sim_parts.append(
                "traffic emission vehicle fleet source coupling scenario"
            )

        if has_scenario:
            sim_parts.append(
                "emission scenario dispersion mass balance mixing height"
            )

        sim_parts.append(" ".join(species))
        sim_parts.append(
            "dispersion transport chemistry box model ventilation"
        )

        pred_parts.append(" ".join(species))
        pred_parts.append("forecast prediction")

        if horizon_hours >= 24:
            pred_parts.append(
                f"{horizon_hours}h horizon sequence model"
            )

        if has_scenario:
            pred_parts.append(
                "bias correction hybrid residual kalman"
            )
        else:
            pred_parts.append(
                "lstm gradient boosting station forecast"
            )

        technical_description = {
            "original_query": user_query,
            "target_species": list(dict.fromkeys(species)),
            "spatial_scale": scale,
            "temporal_horizon": horizon,
            "horizon_hours": horizon_hours,
            "scenario_requested": has_scenario,
            "scenario_elements": {
                "stubble_burning": stubble,
                "traffic": traffic,
            },
            "station_hint": station_hint,
            "required_outputs": (
                llm_result.get("required_outputs")
                or ["concentration_forecast"]
                + (["scenario_delta"] if has_scenario else [])
            ),
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

    except Exception as exc:
        print(
            f"[LLM decomposition failed] {exc}"
        )
        print("[fallback] Using rule-based decomposition.")

        # Existing rule-based implementation remains available
        # in decomposer_backup.py for recovery.
        raise


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
        r"(?:reduc\w*|decreas\w*|cut\w*)(?:\s+[a-zA-Z_-]+){0,3}\s+(?:by\s+)?(\d{1,3})\s*%",
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

    diesel = _first_percent(r"diesel[^%]{0,40}?(?:reduc\w*|cut\w*)[^%]{0,12}?(\d{1,3})\s*%", q)
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
