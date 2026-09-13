"""
End-to-end orchestration: decompose → dual RAG → synthesise → hybrid execute.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from core.decomposer import decompose, parse_scenario_percents
from core.embeddings import build_dual_stores
from core.hybrid import run_hybrid
from core.synthesizer import render_text, synthesize
from data.equations import PREDICTION_EQUATIONS, SIMULATION_EQUATIONS
from data.observations import list_stations


class AQDigitalTwin:
    def __init__(self):
        self.sim_store, self.pred_store = build_dual_stores(
            SIMULATION_EQUATIONS, PREDICTION_EQUATIONS
        )
        stations = list_stations()
        print(
            f"[init] {len(SIMULATION_EQUATIONS)} simulation eqs, "
            f"{len(PREDICTION_EQUATIONS)} prediction eqs, "
            f"{len(stations)} stations: {', '.join(stations)}"
        )

    def query(
        self,
        user_question: str,
        location: Optional[str] = None,
        traffic_mult: Optional[float] = None,
        stubble_mult: Optional[float] = None,
        horizon_hours: Optional[int] = None,
        verbose: bool = True,
    ) -> Dict[str, Any]:
        decomp = decompose(user_question)
        tech = decomp["technical_description"]

        if verbose:
            print("\n[decomposition]")
            print(f"  Species : {tech['target_species']}")
            print(f"  Scale   : {tech['spatial_scale']}")
            print(f"  Horizon : {tech['temporal_horizon']} ({tech['horizon_hours']} h)")
            print(f"  Scenario: {tech['scenario_requested']}  {tech['scenario_elements']}")
            print(f"  Station : {tech.get('station_hint') or location or '(default)'}")
            print(f"  Sim qry : {decomp['simulation_query']}")
            print(f"  Pred qry: {decomp['prediction_query']}")

        sim_hits = self.sim_store.search(
            decomp["simulation_query"],
            top_k=decomp["top_k_sim"],
            filters=decomp.get("filters"),
        )
        pred_hits = self.pred_store.search(
            decomp["prediction_query"],
            top_k=decomp["top_k_pred"],
            filters=decomp.get("filters"),
        )

        if verbose:
            print("\n[retrieval]")
            print("  Simulation hits:")
            for eq, score in sim_hits:
                print(f"    {score:.3f}  {eq['id']}  – {eq['title']}")
            print("  Prediction hits:")
            for eq, score in pred_hits:
                print(f"    {score:.3f}  {eq['id']}  – {eq['title']}")

        pack = synthesize(decomp, sim_hits, pred_hits)

        parsed = parse_scenario_percents(user_question)
        stations = list_stations()
        loc = location or tech.get("station_hint") or stations[0]
        t_mult = traffic_mult if traffic_mult is not None else parsed["traffic_mult"]
        s_mult = stubble_mult if stubble_mult is not None else parsed["stubble_mult"]
        hours = horizon_hours if horizon_hours is not None else tech["horizon_hours"]
        species = tech["target_species"][0]

        # Retrieval provides candidates; execution selects equations
        # that are actually executable by the current simulation workflow.
        retrieved_sim_ids = [eq["id"] for eq, _ in sim_hits]

        sim_ids = []

        # Traffic scenario equations
        if tech["scenario_elements"].get("traffic"):
            sim_ids.extend([
                "sim_traffic_emission_01",
                "sim_traffic_source_coupling_01",
            ])

        # Stubble-burning scenario equations
        if tech["scenario_elements"].get("stubble_burning"):
            sim_ids.extend([
                "sim_stubble_emission_01",
                "sim_stubble_source_coupling_01",
            ])

        # Combined source aggregation
        if (
            tech["scenario_elements"].get("traffic")
            and tech["scenario_elements"].get("stubble_burning")
        ):
            sim_ids.append("sim_total_source_aggregation_01")

        # Box model is the executable concentration model for this
        # station/urban scenario workflow.
        if "sim_box_model_01" in retrieved_sim_ids:
            sim_ids.append("sim_box_model_01")

        # Remove duplicates while preserving order.
        sim_ids = list(dict.fromkeys(sim_ids))

        pred_ids = [eq["id"] for eq, _ in pred_hits[:2]]

        if verbose:
            print("\n[execution]")
            print(f"  Location : {loc}")
            print(f"  Species  : {species}")
            print(f"  Traffic × {t_mult:.2f} | Stubble × {s_mult:.2f} | Horizon {hours} h")
            print(f"  Sim IDs  : {sim_ids}")
            print(f"  Pred IDs : {pred_ids}")

        run = run_hybrid(
            location=loc,
            species=species,
            traffic_mult=t_mult,
            stubble_mult=s_mult,
            horizon_hours=hours,
            sim_eq_ids=sim_ids,
            pred_eq_ids=pred_ids,
        )
        pack = synthesize(
            decomp,
            sim_hits,
            pred_hits,
            run_result=run,
        )
        if verbose:
            print("\n" + render_text(pack))
            print("\n" + _render_run(run))

        return {
            "decomposition": decomp,
            "simulation_hits": [(eq["id"], score) for eq, score in sim_hits],
            "prediction_hits": [(eq["id"], score) for eq, score in pred_hits],
            "package": pack,
            "run": run,
        }


def _render_run(run: Dict[str, Any]) -> str:
    lines = ["=" * 72, "HYBRID TWIN RUN", "=" * 72]
    n = run["now"]
    lines.append(
        f"\n{run['location']} | {run['species']} | "
        f"traffic×{run['traffic_mult']:.2f} stubble×{run['stubble_mult']:.2f} | "
        f"{run['horizon_hours']} h"
    )
    lines.append(
        f"  Now  observed={n['observed']:.1f}  predicted={n['predicted']:.1f}  "
        f"simulated={n['simulated']:.1f}  hybrid={n['hybrid']:.1f}"
    )
    lines.append(f"  AQI  {n['aqi']} ({n['aqi_label']})")
    lines.append(
        f"  Physics scenario delta (sim_scenario - sim_control): "
        f"{run['scenario_delta']:+.1f} µg/m³"
    )
    lines.append("\n  Method notes:")
    for note in run["method_notes"]:
        lines.append(f"    – {note}")

    # print a short forecast table (every 6 h)
    lines.append("\n  Forecast (hybrid), sample every 6 h:")
    lines.append(f"  {'hour':>6}  {'observed':>10}  {'predicted':>10}  {'simulated':>10}  {'hybrid':>10}")
    for p in run["series"]:
        if p["hour"] is None:
            continue
        if p["hour"] > 0 and p["hour"] % 6 != 0 and p["hour"] != run["horizon_hours"]:
            continue
        if p["hour"] < 0:
            continue
        obs = f"{p['observed']:.1f}" if p["observed"] is not None else "—"
        lines.append(
            f"  {p['hour']:>6}  {obs:>10}  {p['predicted']:>10.1f}  "
            f"{p['simulated']:>10.1f}  {p['hybrid']:>10.1f}"
        )
    lines.append("=" * 72)
    return "\n".join(lines)
