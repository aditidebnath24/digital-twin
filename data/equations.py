"""
Sample equation archives for the Delhi Air Quality Digital Twin application.
These are realistic, simplified entries that demonstrate the dual-archive design.
In production these would be curated from literature, model documentation, and expert input.
"""

from typing import List, Dict, Any

# ---------------------------------------------------------------------------
# Simulation Equations Archive (physics / process / mechanistic models)
# ---------------------------------------------------------------------------
SIMULATION_EQUATIONS: List[Dict[str, Any]] = [
    {
        "id": "sim_gauss_plume_01",
        "title": "Gaussian Plume Dispersion (point source)",
        "latex": r"C(x,y,z) = \frac{Q}{2\pi u \sigma_y \sigma_z} \exp\left(-\frac{y^2}{2\sigma_y^2}\right)\left[\exp\left(-\frac{(z-H)^2}{2\sigma_z^2}\right)+\exp\left(-\frac{(z+H)^2}{2\sigma_z^2}\right)\right]",
        "description": "Steady-state Gaussian plume model for continuous point-source emissions under constant wind. Suitable for industrial stacks and elevated sources in Delhi under moderate wind conditions.",
        "domain": "dispersion",
        "species": ["PM2.5", "PM10", "NO2", "SO2", "CO"],
        "scale": "local_to_urban",
        "temporal": "steady",
        "assumptions": "Constant wind speed and direction, flat terrain, no chemical transformation, neutral or slightly stable conditions.",
        "validity": "Best for wind > 1.5 m/s; limited under calm/low-wind Delhi winter nights and complex urban canopy.",
        "inputs_required": ["emission_rate_Q", "wind_speed_u", "stack_height_H", "stability_class"],
        "delhi_notes": "Frequently used for industrial permitting and what-if stack scenarios in Delhi-NCR.",
        "tags": ["gaussian", "plume", "point_source", "dispersion", "delhi"],
    },
    {
        "id": "sim_box_model_01",
        "title": "Single-box mass-balance model for urban background",
        "latex": r"V\frac{dC}{dt} = Q_{em} + Q_{in} - Q_{out} - k_{dep}C V - k_{chem}C V",
        "description": "Well-mixed box model for city-scale or ward-scale concentration evolution. Captures net emission, advection in/out, deposition and simple first-order chemistry/loss.",
        "domain": "mass_balance",
        "species": ["PM2.5", "PM10", "NO2", "O3"],
        "scale": "urban",
        "temporal": "transient",
        "assumptions": "Perfect mixing inside the box, uniform emission density, constant mixing height or prescribed time-varying height.",
        "validity": "Good for city-average or large-ward background; not for street-canyon gradients.",
        "inputs_required": ["box_volume_or_mixing_height", "emission_inventory", "wind_ventilation", "deposition_velocity"],
        "delhi_notes": "Useful for rapid scenario testing of city-wide emission reductions (traffic, stubble, industry).",
        "tags": ["box", "mass_balance", "urban", "transient", "delhi"],
    },
    {
        "id": "sim_traffic_emission_01",
        "title": "Traffic emission rate (fleet-averaged)",
        "latex": r"E_{traffic} = \sum_i (EF_i \times VKT_i \times f_{cong,i})",
        "description": "Bottom-up traffic emission calculation from emission factors, vehicle-kilometres travelled and congestion correction.",
        "domain": "emissions",
        "species": ["PM2.5", "NO2", "CO", "BC"],
        "scale": "street_to_urban",
        "temporal": "hourly",
        "assumptions": "Representative emission factors for Delhi fleet mix (petrol, diesel, CNG, EV share).",
        "validity": "Depends on quality of traffic counts and fleet composition data.",
        "inputs_required": ["traffic_volume", "fleet_composition", "emission_factors", "speed_or_congestion"],
        "delhi_notes": "Core input for any traffic-related scenario in Delhi.",
        "tags": ["traffic", "emission", "bottom_up", "delhi"],
    },
    {
    "id": "sim_traffic_source_coupling_01",
    "title": "Traffic-to-source emission coupling",
    "description": (
        "Couples traffic emission scenarios to the effective "
        "pollutant source emission used by the simulation."
    ),
    "latex": (
        r"Q_{traffic}=Q_{base}"
        r"\frac{E_{traffic,scenario}}{E_{traffic,base}}"
    ),
    "tags": [
        "traffic",
        "emission",
        "source",
        "coupling",
        "scenario",
        "PM2.5",
        "PM10",
        "NO2",
        "CO",
    ],
    "species": [
        "PM2.5",
        "PM10",
        "NO2",
        "CO",
    ],
    "domain": "emission coupling",
    "scale": "local_to_urban",
    "temporal": "scenario",
    "assumptions": [
        "Traffic emission changes proportionally affect the "
        "traffic-attributable source contribution.",
        "Other emission sources remain unchanged."
    ],
    "inputs": [
        "Q_base",
        "E_traffic_base",
        "E_traffic_scenario",
    ],
    "validity": (
        "Suitable for rapid traffic-control what-if scenarios "
        "when source apportionment is available."
    ),
},
    {
        "id": "sim_stubble_emission_01",
        "title": "Agricultural residue (stubble) burning emission",
        "latex": r"E_{stubble} = A_{burned} \times BL \times EF_{species}",
        "description": "Simple area-based emission estimate for stubble burning. Can be scaled by fire-count or satellite AOD proxies.",
        "domain": "emissions",
        "species": ["PM2.5", "PM10", "BC", "OC"],
        "scale": "regional",
        "temporal": "daily_to_episode",
        "assumptions": "Average fuel load and emission factor; neglects plume rise variability.",
        "validity": "Order-of-magnitude for regional contribution during Oct-Nov episodes.",
        "inputs_required": ["burned_area_or_fire_counts", "biomass_loading", "emission_factor"],
        "delhi_notes": "Critical for post-monsoon and early-winter peaks in Delhi.",
        "tags": ["stubble", "biomass", "emission", "seasonal", "delhi"],
    },
        {
        "id": "sim_stubble_source_coupling_01",
        "title": "Stubble-to-source emission coupling",
        "latex": (
            r"Q_{stubble}=Q_{base}"
            r"\frac{E_{stubble,scenario}}{E_{stubble,base}}"
        ),
        "description": (
            "Couples agricultural residue burning scenarios to the "
            "effective pollutant source emission used by the simulation."
        ),
        "domain": "emission_coupling",
        "species": ["PM2.5", "PM10", "BC", "OC"],
        "scale": "regional_to_urban",
        "temporal": "scenario",
        "assumptions": (
            "Stubble-burning emission changes proportionally affect "
            "the stubble-attributable pollutant source contribution; "
            "other sources remain unchanged."
        ),
        "validity": (
            "Suitable for rapid scenario analysis when regional "
            "burned-area, biomass-loading, and emission-factor estimates "
            "are available."
        ),
        "inputs_required": [
            "Q_base",
            "E_stubble_base",
            "E_stubble_scenario",
            "stubble_multiplier",
        ],
        "delhi_notes": (
            "Supports Delhi-NCR winter what-if scenarios involving "
            "changes in agricultural residue burning."
        ),
        "tags": [
            "stubble",
            "biomass",
            "source",
            "coupling",
            "scenario",
            "PM2.5",
            "Delhi-NCR",
        ],
    },
        {
        "id": "sim_total_source_aggregation_01",
        "title": "Total pollutant source emission aggregation",
        "latex": (
            r"Q_{total}=Q_{traffic}+Q_{stubble}+Q_{other}"
        ),
        "description": (
            "Aggregates traffic, stubble-burning and other emission "
            "source contributions into the effective pollutant source "
            "used by the concentration simulation."
        ),
        "domain": "emission_aggregation",
        "species": ["PM2.5", "PM10", "NO2", "CO", "BC"],
        "scale": "local_to_urban",
        "temporal": "hourly_to_scenario",
        "assumptions": (
            "Source contributions are additive and represent effective "
            "emission rates for the selected pollutant."
        ),
        "validity": (
            "Suitable for rapid scenario analysis when source-specific "
            "emission estimates or calibrated source fractions are available."
        ),
        "inputs_required": [
            "Q_traffic",
            "Q_stubble",
            "Q_other",
        ],
        "delhi_notes": (
            "Provides a common source term for combining traffic and "
            "agricultural-burning scenarios affecting Delhi-NCR."
        ),
        "tags": [
            "source",
            "aggregation",
            "traffic",
            "stubble",
            "emission",
            "PM2.5",
            "Delhi-NCR",
        ],
    },
        {
        "id": "sim_scenario_delta_01",
        "title": "Scenario concentration delta",
        "latex": (
            r"\Delta C_{scenario}(t)"
            r"=C_{sim,scenario}(t)-C_{sim,control}(t)"
        ),
        "description": (
            "Computes the concentration change caused by an emission "
            "scenario by comparing the scenario simulation with the "
            "corresponding control simulation."
        ),
        "domain": "scenario_analysis",
        "species": ["PM2.5", "PM10", "NO2", "SO2", "O3", "CO"],
        "scale": "station_to_urban",
        "temporal": "hourly_to_72h",
        "assumptions": (
            "Control and scenario simulations use the same meteorological "
            "conditions and model configuration, with only the specified "
            "scenario inputs changed."
        ),
        "validity": (
            "Useful for relative what-if analysis; absolute accuracy "
            "depends on the underlying emission and dispersion model."
        ),
        "inputs_required": [
            "control_simulation",
            "scenario_simulation",
        ],
        "delhi_notes": (
            "Directly supports Delhi traffic, stubble-burning and other "
            "emission-control what-if analyses."
        ),
        "tags": [
            "scenario",
            "delta",
            "what_if",
            "control",
            "simulation",
            "hybrid",
            "Delhi",
        ],
    },
    {
        "id": "sim_simple_chem_no2_o3",
        "title": "Simplified NOx-O3 photochemistry (null-cycle + titration)",
        "latex": r"\frac{d[O_3]}{dt} \approx j_{NO2}[NO_2] - k[NO][O_3] + P_{other} - L_{other}",
        "description": "Highly reduced photochemical scheme focusing on the NO-NO2-O3 triad. Useful for rapid urban photochemistry estimates.",
        "domain": "chemistry",
        "species": ["NO2", "O3", "NO"],
        "scale": "urban",
        "temporal": "diurnal",
        "assumptions": "Neglects most VOC chemistry; suitable only for first-order titration and photolysis effects.",
        "validity": "Qualitative to semi-quantitative under high-NOx Delhi conditions; not for detailed secondary organic aerosol.",
        "inputs_required": ["photolysis_rate", "NOx_emissions", "background_O3"],
        "delhi_notes": "Can illustrate weekend ozone effects or NOx-reduction scenarios.",
        "tags": ["chemistry", "photochemistry", "NOx", "ozone", "reduced", "delhi"],
    },
]

# ---------------------------------------------------------------------------
# Prediction Equations Archive (statistical / ML / reduced-order / assimilation)
# ---------------------------------------------------------------------------
PREDICTION_EQUATIONS: List[Dict[str, Any]] = [
    {
        "id": "pred_lstm_pm25_01",
        "title": "Multi-variate LSTM / sequence model for station PM2.5",
        "latex": r"\hat{C}_{t+h} = f_{\theta}(C_{t-w:t}, M_{t-w:t}, E_{t-w:t})",
        "description": "Sequence-to-sequence or direct multi-horizon neural forecast using past concentrations, meteorology and emission proxies.",
        "domain": "forecasting",
        "species": ["PM2.5"],
        "scale": "station",
        "temporal": "1h_to_72h",
        "assumptions": "Stationary enough relationship after seasonal normalisation; sufficient historical data.",
        "validity": "Strong on regular diurnal/weekly patterns; degrades during unprecedented stubble or dust events unless augmented.",
        "inputs_required": ["past_PM25", "wind", "temp", "RH", "boundary_layer", "traffic_or_fire_proxy"],
        "delhi_notes": "Typical architecture used by many Delhi forecasting systems; benefits from winter-specific fine-tuning.",
        "tags": ["lstm", "neural", "forecast", "pm25", "station", "delhi"],
    },
    {
        "id": "pred_gbrt_pm25_01",
        "title": "Gradient-boosted tree residual / direct forecast",
        "latex": r"\hat{C}_{t+h} = g( features_{t} ) + \epsilon",
        "description": "Tabular ML model (XGBoost/LightGBM style) using lag features, meteorology, calendar and emission proxies.",
        "domain": "forecasting",
        "species": ["PM2.5", "PM10", "NO2"],
        "scale": "station_or_ward",
        "temporal": "1h_to_48h",
        "assumptions": "Feature set captures main drivers; tree models handle non-linearities and missing values reasonably.",
        "validity": "Robust baseline; often competitive with deep models on Delhi station data.",
        "inputs_required": ["lags", "meteorology", "time_features", "traffic_fire_indices"],
        "delhi_notes": "Good default for operational nowcasting and short-term forecast at CPCB/DPCC stations.",
        "tags": ["gbrt", "xgboost", "tabular", "forecast", "delhi"],
    },
    {
        "id": "pred_bias_correction_01",
        "title": "Linear / ML bias correction of simulation baseline",
        "latex": r"C_{corrected} = a \cdot C_{sim} + b + \delta(features)",
        "description": "Post-processing that maps a physics-based simulation field or time series onto observations using additive/multiplicative bias and optional residual learner.",
        "domain": "data_assimilation",
        "species": ["PM2.5", "PM10", "NO2", "O3"],
        "scale": "station_to_urban",
        "temporal": "hourly",
        "assumptions": "Simulation captures the main spatial/temporal pattern; residual is learnable from available features.",
        "validity": "Works well when simulation is already reasonable; can hide structural model errors.",
        "inputs_required": ["simulation_output", "recent_observations", "meteorology"],
        "delhi_notes": "Standard hybrid pattern: run a simple box or Gaussian baseline then correct with station data.",
        "tags": ["bias_correction", "hybrid", "post_processing", "delhi"],
    },
    {
        "id": "pred_kalman_assimil_01",
        "title": "Simplified Kalman / sequential update",
        "latex": r"x_a = x_b + K (y - H x_b), \quad K = P H^T (H P H^T + R)^{-1}",
        "description": "Sequential data-assimilation step that blends a model forecast (background) with new observations.",
        "domain": "data_assimilation",
        "species": ["PM2.5", "NO2"],
        "scale": "station_network",
        "temporal": "hourly",
        "assumptions": "Linear observation operator, Gaussian errors, reasonably tuned error covariances.",
        "validity": "Useful for nowcasting and short-term state estimation across the Delhi station network.",
        "inputs_required": ["background_forecast", "observations", "error_covariances"],
        "delhi_notes": "Can be applied station-wise or with a simple spatial covariance model.",
        "tags": ["kalman", "assimilation", "nowcast", "delhi"],
    },
    {
        "id": "pred_land_use_reg_01",
        "title": "Land-use regression (LUR) spatial model",
        "latex": r"C_i = \beta_0 + \sum_k \beta_k L_{ik} + \epsilon_i",
        "description": "Statistical spatial model relating concentration to surrounding land-use, traffic, and geographic predictors.",
        "domain": "spatial",
        "species": ["PM2.5", "NO2"],
        "scale": "urban",
        "temporal": "long_term_average_or_seasonal",
        "assumptions": "Linear (or lightly non-linear) relationship; predictors are available at high resolution.",
        "validity": "Best for long-term or seasonal mean surfaces; weaker for acute episodes.",
        "inputs_required": ["land_use_layers", "traffic_density", "distance_to_roads", "population"],
        "delhi_notes": "Useful for exposure assessment and to fill gaps between monitoring stations.",
        "tags": ["lur", "spatial", "exposure", "delhi"],
    },
]


def get_all_equations():
    return {
        "simulation": SIMULATION_EQUATIONS,
        "prediction": PREDICTION_EQUATIONS,
    }
