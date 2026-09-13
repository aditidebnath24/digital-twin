#!/usr/bin/env python3
"""
Aether – Delhi Air Quality Digital Twin
Simple form UI: type any question → dual-RAG answer + hybrid numbers.

Run:
    streamlit run app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st

from core.pipeline import AQDigitalTwin
from data.observations import list_stations, snapshot

st.set_page_config(
    page_title="Delhi AQI Digital Twin",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Cache the twin so equation stores load once
# ---------------------------------------------------------------------------
@st.cache_resource
def get_twin() -> AQDigitalTwin:
    return AQDigitalTwin()


twin = get_twin()
stations = list_stations()

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("Delhi Air Quality Digital Twin")
st.caption(
    "Dual-RAG system: ask in natural language → technical decomposition → "
    "simulation + prediction equations → hybrid forecast / scenario."
)

# ---------------------------------------------------------------------------
# Snapshot strip
# ---------------------------------------------------------------------------
with st.expander("Current station snapshot (1 Jan 2025 00:00 IST)", expanded=False):
    cols = st.columns(3)
    for i, loc in enumerate(stations):
        o = snapshot(loc)
        with cols[i % 3]:
            st.metric(
                loc,
                f"PM2.5 {o.pm25:.0f}",
                f"AQI {o.aqi_reported} · NO₂ {o.no2:.0f} · {o.temperature:.0f}°C",
            )

# ---------------------------------------------------------------------------
# Input form
# ---------------------------------------------------------------------------
st.subheader("Ask a question")

examples = [
    "Forecast PM2.5 for the next 72 hours if stubble burning increases by 40%.",
    "How does reducing traffic 30% change Anand Vihar PM2.5 over 48 hours?",
    "What is the expected NO2 tomorrow at Connaught Place under normal traffic?",
    "City-scale mass balance for PM2.5 with a data-driven bias correction.",
    "If stubble increases 50% and traffic cuts 20%, what happens to Rohini PM2.5 in 24h?",
]

with st.form("query_form"):
    question = st.text_area(
        "Your question (natural language)",
        height=100,
        placeholder="e.g. Forecast PM2.5 for 72h if stubble increases by 40%",
        help="Write freely. The system will detect species, horizon, station, and scenarios.",
    )
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        station_opt = st.selectbox(
            "Station (optional)",
            options=["Auto (from question)"] + stations,
            index=0,
        )
    with c2:
        horizon_opt = st.selectbox(
            "Horizon (optional)",
            options=["Auto", "24 h", "48 h", "72 h"],
            index=0,
        )
    with c3:
        traffic_slider = st.slider("Traffic multiplier", 0.2, 2.0, 1.0, 0.05)
        use_traffic = st.checkbox("Override traffic", value=False)
    with c4:
        stubble_slider = st.slider("Stubble multiplier", 0.2, 2.5, 1.0, 0.05)
        use_stubble = st.checkbox("Override stubble", value=False)

    submitted = st.form_submit_button("▶ Run twin", type="primary", use_container_width=True)

# Quick example buttons outside the form
st.write("**Try an example:**")
ex_cols = st.columns(len(examples))
for i, ex in enumerate(examples):
    if ex_cols[i].button(f"Q{i+1}", help=ex, use_container_width=True):
        st.session_state["pending_query"] = ex
        st.rerun()

if "pending_query" in st.session_state and st.session_state["pending_query"]:
    question = st.session_state.pop("pending_query")
    submitted = True
    station_opt = "Auto (from question)"
    horizon_opt = "Auto"
    use_traffic = False
    use_stubble = False
    traffic_slider = 1.0
    stubble_slider = 1.0

# ---------------------------------------------------------------------------
# Run pipeline
# ---------------------------------------------------------------------------
if submitted:
    if not (question or "").strip():
        st.warning("Please enter a question first.")
        st.stop()

    location = None if station_opt.startswith("Auto") else station_opt
    horizon_hours = None
    if horizon_opt == "24 h":
        horizon_hours = 24
    elif horizon_opt == "48 h":
        horizon_hours = 48
    elif horizon_opt == "72 h":
        horizon_hours = 72
    traffic_mult = traffic_slider if use_traffic else None
    stubble_mult = stubble_slider if use_stubble else None

    with st.spinner("Decomposing → dual retrieval → hybrid run…"):
        result = twin.query(
            question.strip(),
            location=location,
            traffic_mult=traffic_mult,
            stubble_mult=stubble_mult,
            horizon_hours=horizon_hours,
            verbose=False,
        )

    decomp = result["decomposition"]
    tech = decomp["technical_description"]
    pack = result["package"]
    run = result["run"]

    # --- Decomposition ---
    st.markdown("---")
    st.subheader("1 · Technical decomposition")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Species", ", ".join(tech["target_species"]))
    m2.metric("Horizon", f"{tech['horizon_hours']} h")
    m3.metric("Station", run["location"])
    scen = tech["scenario_elements"]
    m4.metric(
        "Scenario",
        "Yes" if tech["scenario_requested"] else "No",
        f"stubble={scen.get('stubble_burning')} traffic={scen.get('traffic')}",
    )

    # --- Retrieval ---
    st.subheader("2 · Dual RAG retrieval")
    left, right = st.columns(2)
    with left:
        st.markdown("**Simulation archive**")
        for eq_id, score in result["simulation_hits"]:
            st.write(f"`{score:.3f}` · `{eq_id}`")
    with right:
        st.markdown("**Prediction archive**")
        for eq_id, score in result["prediction_hits"]:
            st.write(f"`{score:.3f}` · `{eq_id}`")

    # --- Equation package ---
    st.subheader("3 · Equation package")
    if isinstance(pack, dict):
        if pack.get("summary"):
            st.success("🤖 Gemini Digital Twin Explanation")
            st.info(pack["summary"])
        sim_eqs = pack.get("selected_simulation_equations") or []
        pred_eqs = pack.get("selected_prediction_equations") or []
        if sim_eqs:
            with st.expander("Simulation equations selected", expanded=True):
                for eq in sim_eqs:
                    st.markdown(f"**{eq.get('title', '')}** `{eq.get('id', '')}`")
                    if eq.get("latex"):
                        st.latex(eq["latex"])
                    if eq.get("why"):
                        st.caption(eq["why"])
        if pred_eqs:
            with st.expander("Prediction equations selected", expanded=True):
                for eq in pred_eqs:
                    st.markdown(f"**{eq.get('title', '')}** `{eq.get('id', '')}`")
                    if eq.get("latex"):
                        st.latex(eq["latex"])
                    if eq.get("why"):
                        st.caption(eq["why"])
        for c in pack.get("coupling_and_workflow") or []:
            st.write(f"• {c}")

    # --- Hybrid numbers ---
    st.subheader("4 · Hybrid twin run")
    n = run["now"]
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Observed", f"{n['observed']:.1f}")
    k2.metric("Predicted", f"{n['predicted']:.1f}")
    k3.metric("Simulated", f"{n['simulated']:.1f}")
    k4.metric("Hybrid", f"{n['hybrid']:.1f}", f"Δ scenario {run['scenario_delta']:+.1f}")
    k5.metric("AQI", n["aqi"], n["aqi_label"])

    st.caption(
        f"{run['location']} · {run['species']} · "
        f"traffic ×{run['traffic_mult']:.2f} · stubble ×{run['stubble_mult']:.2f} · "
        f"{run['horizon_hours']} h horizon"
    )

    # Forecast table
    future_rows = [p for p in run["series"] if p.get("hour") is not None and p["hour"] > 0]
    if future_rows:
        import pandas as pd

        sample = [p for p in future_rows if p["hour"] % 6 == 0 or p["hour"] == run["horizon_hours"]]
        df = pd.DataFrame(
            [
                {
                    "Hour": p["hour"],
                    "Predicted": p["predicted"],
                    "Simulated": p["simulated"],
                    "Hybrid": p["hybrid"],
                }
                for p in sample
            ]
        )
        st.markdown("**Forecast (sample every 6 h)**")
        st.dataframe(df, use_container_width=True, hide_index=True)

        chart_df = pd.DataFrame(
            [
                {
                    "Hour": p["hour"],
                    "Predicted": p["predicted"],
                    "Simulated": p["simulated"],
                    "Hybrid": p["hybrid"],
                }
                for p in future_rows
            ]
        ).set_index("Hour")
        st.line_chart(chart_df)

    for note in run.get("method_notes", []):
        st.caption(f"– {note}")

