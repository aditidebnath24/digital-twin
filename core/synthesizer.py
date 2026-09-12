"""
LLM Synthesis Module.

Takes the technical description + retrieved equations and produces a
coherent, grounded answer package.

In production replace `synthesize` with a real LLM call that is strictly
grounded on the provided context. The template below shows the expected
structure and style.
"""

from __future__ import annotations
from typing import Dict, Any, List, Tuple


def synthesize(
    technical: Dict[str, Any],
    sim_results: List[Tuple[Dict, float]],
    pred_results: List[Tuple[Dict, float]],
) -> Dict[str, Any]:
    """
    Returns a structured response that can be rendered to the user.
    """
    tech = technical["technical_description"]
    species = ", ".join(tech["target_species"])
    horizon = tech["temporal_horizon"]
    scenario = tech["scenario_requested"]

    # --- select primary equations (already ranked by retrieval) ---
    primary_sim = [eq for eq, _ in sim_results]
    primary_pred = [eq for eq, _ in pred_results[:2]]

    # Build human-readable sections
    sim_section = []
    for eq in primary_sim:
        sim_section.append(
            {
                "id": eq["id"],
                "title": eq["title"],
                "latex": eq["latex"],
                "why": eq.get("delhi_notes") or eq["description"][:160],
                "assumptions": eq.get("assumptions"),
                "validity": eq.get("validity"),
                "inputs": eq.get("inputs_required", []),
            }
        )

    pred_section = []
    for eq in primary_pred:
        pred_section.append(
            {
                "id": eq["id"],
                "title": eq["title"],
                "latex": eq["latex"],
                "why": eq.get("delhi_notes") or eq["description"][:160],
                "assumptions": eq.get("assumptions"),
                "validity": eq.get("validity"),
                "inputs": eq.get("inputs_required", []),
            }
        )

    # Coupling logic (heuristic for the prototype)
    coupling = []
    if scenario and primary_sim and primary_pred:
        coupling.append(
            "Recommended hybrid workflow: "
            "(1) Use the selected simulation emission / dispersion equations to compute a scenario delta "
            "(e.g. +40 % stubble or traffic change). "
            "(2) Run the selected prediction model for the baseline forecast. "
            "(3) Add the simulation-derived delta (optionally after a simple bias-correction step) "
            "to obtain the scenario-adjusted forecast."
        )
    elif primary_pred:
        coupling.append(
            "Primary path is data-driven prediction. "
            "Simulation equations can be used optionally for sensitivity or to supply missing emission features."
        )
    else:
        coupling.append("Only simulation equations were retrieved; treat results as scenario / process estimates.")

    # Limitations
    limitations = []
    for eq in primary_sim + primary_pred:
        if eq.get("validity"):
            limitations.append(f"{eq['id']}: {eq['validity']}")

    response = {
        "summary": _make_summary(tech, primary_sim, primary_pred),
        "technical_description": tech,
        "selected_simulation_equations": sim_section,
        "selected_prediction_equations": pred_section,
        "coupling_and_workflow": coupling,
        "limitations_and_validity": limitations,
        "next_steps": [
            "Pull latest station + meteorology data from Delhi connectors (CPCB/DPCC, IMD/ERA5).",
            "Instantiate the selected prediction model with recent history.",
            "If scenario requested, evaluate the simulation emission term and apply the delta.",
            "Optionally run a short assimilation / bias-correction update.",
            "Return time series + uncertainty band to the user.",
        ],
        "provenance": {
            "simulation_ids": [eq["id"] for eq in primary_sim],
            "prediction_ids": [eq["id"] for eq in primary_pred],
        },
    }
    return response


def _make_summary(tech: Dict, sim_eqs: List, pred_eqs: List) -> str:
    species = ", ".join(tech["target_species"])
    parts = [
        f"For the request targeting {species} at {tech['spatial_scale']} scale "
        f"(horizon: {tech['temporal_horizon']})"
    ]
    if tech["scenario_requested"]:
        elems = [k for k, v in tech["scenario_elements"].items() if v]
        parts.append(f" with scenario elements {elems}")
    parts.append(".")
    if pred_eqs:
        parts.append(f" Primary prediction model(s): {', '.join(e['title'] for e in pred_eqs)}.")
    if sim_eqs:
        parts.append(f" Supporting simulation equation(s): {', '.join(e['title'] for e in sim_eqs)}.")
    return "".join(parts)


def render_text(response: Dict[str, Any]) -> str:
    """Pretty-print the structured response for console / simple UI."""
    lines = []
    lines.append("=" * 72)
    lines.append("AQ DIGITAL TWIN – EQUATION PACKAGE")
    lines.append("=" * 72)
    lines.append("\nSUMMARY\n" + response["summary"])

    lines.append("\n\nSELECTED SIMULATION EQUATIONS")
    for eq in response["selected_simulation_equations"]:
        lines.append(f"\n• {eq['title']}  [{eq['id']}]")
        lines.append(f"  LaTeX: {eq['latex']}")
        lines.append(f"  Why: {eq['why']}")
        lines.append(f"  Assumptions: {eq['assumptions']}")
        lines.append(f"  Validity: {eq['validity']}")

    lines.append("\n\nSELECTED PREDICTION EQUATIONS")
    for eq in response["selected_prediction_equations"]:
        lines.append(f"\n• {eq['title']}  [{eq['id']}]")
        lines.append(f"  LaTeX: {eq['latex']}")
        lines.append(f"  Why: {eq['why']}")
        lines.append(f"  Assumptions: {eq['assumptions']}")
        lines.append(f"  Validity: {eq['validity']}")

    lines.append("\n\nCOUPLING / WORKFLOW")
    for c in response["coupling_and_workflow"]:
        lines.append(f"  – {c}")

    lines.append("\n\nLIMITATIONS")
    for lim in response["limitations_and_validity"]:
        lines.append(f"  – {lim}")

    lines.append("\n\nNEXT STEPS")
    for i, step in enumerate(response["next_steps"], 1):
        lines.append(f"  {i}. {step}")

    lines.append("\n" + "=" * 72)
    return "\n".join(lines)
