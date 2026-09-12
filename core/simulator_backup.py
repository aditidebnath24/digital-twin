"""
Execute selected simulation equations against station meteorology.

Winter Delhi source split when emission equations are retrieved:
  traffic 0.22 | stubble 0.28 | other 0.50
"""

from __future__ import annotations

import math
from typing import Dict, List, Sequence

from data.observations import (
    history,
    mixing_height_m,
    pollutant_value,
    snapshot,
)


SHARE = {
    "traffic": 0.22,
    "stubble": 0.28,
    "other": 0.50,
}


def _uses(ids: Sequence[str], key: str) -> bool:
    return any(key in i for i in ids)


def emission_scale(
    ids: Sequence[str],
    traffic_mult: float,
    stubble_mult: float,
) -> float:

    t = traffic_mult if _uses(ids, "traffic") else 1.0
    s = stubble_mult if _uses(ids, "stubble") else 1.0

    if not _uses(ids, "traffic") and not _uses(ids, "stubble"):
        return (
            SHARE["other"]
            + SHARE["traffic"] * traffic_mult
            + SHARE["stubble"] * stubble_mult
        )

    return (
        SHARE["other"]
        + SHARE["traffic"] * t
        + SHARE["stubble"] * s
    )
def traffic_scenario_factor(
    traffic_mult: float,
) -> float:
    """
    Converts the traffic scenario multiplier
    into a relative traffic emission factor.

    Example:
        traffic_mult = 1.0  -> normal traffic
        traffic_mult = 0.7  -> 30% reduction
        traffic_mult = 1.3  -> 30% increase
    """

    return max(
        0.0,
        traffic_mult,
    )

def traffic_emission(
    emission_factors: Sequence[float],
    vkt: Sequence[float],
    congestion: Sequence[float],
) -> float:
    """
    Traffic emission equation:

        E_traffic = sum(EF_i * VKT_i * f_cong,i)

    emission_factors : emission factor for each vehicle class
    vkt              : vehicle-km travelled
    congestion       : congestion multiplier
    """

    if not (
        len(emission_factors)
        == len(vkt)
        == len(congestion)
    ):
        raise ValueError(
            "Traffic emission inputs must have equal length."
        )

    return sum(
        ef * distance * cong
        for ef, distance, cong
        in zip(
            emission_factors,
            vkt,
            congestion,
        )
    )
def traffic_source_coupling(
    q_base: float,
    traffic_base_emission: float,
    traffic_scenario_emission: float,
) -> float:
    """
    Couples traffic emission scenario to source emission.

    Q_traffic =
        Q_base * (E_traffic_scenario / E_traffic_base)
    """

    if traffic_base_emission <= 0.0:
        return q_base

    ratio = (
        traffic_scenario_emission
        / traffic_base_emission
    )

    return q_base * ratio

def species_factor(species: str) -> float:
    s = species.upper()

    if s == "NO2":
        return 0.92

    if s == "CO":
        return 0.85

    if s == "PM10":
        return 1.04

    return 1.0


def gaussian_plume_concentration(
    Q: float,
    u: float,
    H: float,
    sigma_y: float,
    sigma_z: float,
    x: float = 800.0,
    y: float = 0.0,
    z: float = 0.0,
) -> float:
    """
    Gaussian plume dispersion equation.

    C(x,y,z) =
        Q / (2*pi*u*sigma_y*sigma_z)
        * exp(-y^2 / (2*sigma_y^2))
        * [
            exp(-(z-H)^2 / (2*sigma_z^2))
            +
            exp(-(z+H)^2 / (2*sigma_z^2))
          ]
    """

    u = max(0.8, u)
    sigma_y = max(1.0, sigma_y)
    sigma_z = max(1.0, sigma_z)

    crosswind = math.exp(
        -(y ** 2) / (2.0 * sigma_y ** 2)
    )

    vertical = (
        math.exp(
            -((z - H) ** 2) / (2.0 * sigma_z ** 2)
        )
        +
        math.exp(
            -((z + H) ** 2) / (2.0 * sigma_z ** 2)
        )
    )

    concentration = (
        Q
        / (
            2.0
            * math.pi
            * u
            * sigma_y
            * sigma_z
        )
        * crosswind
        * vertical
    )

    return concentration


def run_simulation(
    location: str,
    species: str,
    traffic_mult: float,
    stubble_mult: float,
    sim_eq_ids: Sequence[str],
    hours: int,
) -> Dict[str, List[float]]:

    rows = history(location)
    last = snapshot(location)

    # --------------------------------
    # Traffic emission calculation
    # --------------------------------

    traffic_EF = [
        1.00,   # passenger vehicles
        1.25,   # diesel vehicles
        0.80,   # CNG / buses
    ]

    traffic_VKT = [
        1000.0,
        700.0,
        500.0,
    ]

    traffic_congestion = [
        1.00,
        1.00,
        1.00,
    ]

    traffic_base_emission = traffic_emission(
        emission_factors=traffic_EF,
        vkt=traffic_VKT,
        congestion=traffic_congestion,
    )

    traffic_factor = traffic_scenario_factor(
        traffic_mult
    )

    traffic_emission_scenario = (
        traffic_base_emission
        * traffic_factor
    )
    traffic_q_base = 180.0

    traffic_q_scenario = traffic_source_coupling(
        q_base=traffic_q_base,
        traffic_base_emission=traffic_base_emission,
        traffic_scenario_emission=traffic_emission_scenario,
    )

    # --------------------------------
    # Existing emission scale
    # --------------------------------

    scale = (
        emission_scale(
            sim_eq_ids,
            1.0,
            stubble_mult,
        )
        * species_factor(species)
    )

    use_box = (
        _uses(sim_eq_ids, "box")
        or _uses(sim_eq_ids, "mixing")
        or len(sim_eq_ids) == 0
    )

    use_gauss = _uses(sim_eq_ids, "gauss")

    use_chem = (
        _uses(sim_eq_ids, "chem")
        and species.upper() in ("NO2", "O3")
    )

    # -----------------------------
    # Historical simulation
    # -----------------------------

    past: List[float] = []

    for row in rows:
        past.append(
            _simulate_one(
                row,
                last,
                scale,
                traffic_q_scenario,
                use_box,
                use_gauss,
                use_chem,
                species,
                0,
            )
        )

    # -----------------------------
    # Future simulation
    # -----------------------------

    future: List[float] = []

    for h in range(1, hours + 1):

        hour = h % 24

        # Lightweight future meteorological template
        class _Tmp:
            pass

        fake = _Tmp()

        fake.wind_speed = (
            last.wind_speed
            * (
                0.75
                + 0.55
                * max(
                    0.0,
                    math.sin(
                        ((hour - 8) / 12)
                        * math.pi
                    ),
                )
            )
        )

        fake.temperature = (
            last.temperature
            + 7.4
            * (
                math.sin(
                    ((hour - 9) / 24)
                    * 2
                    * math.pi
                )
                - math.sin(
                    (-9 / 24)
                    * 2
                    * math.pi
                )
            )
        )

        fake.ts = last.ts

        future.append(
            _simulate_one(
                fake,
                last,
                scale,
                traffic_q_scenario,
                use_box,
                use_gauss,
                use_chem,
                species,
                h,
                hour_override=hour,
            )
        )

    return {
        "past": past,
        "future": future,
    }

def _simulate_one(
    row,
    snap,
    emission_scale_val: float,
    traffic_q_scenario: float,
    use_box: bool,
    use_gauss: bool,
    use_chem: bool,
    species: str,
    lead: int,
    hour_override: int | None = None,
) -> float:

    # -----------------------------
    # Local hour
    # -----------------------------

    if hour_override is not None:
        h_local = hour_override
    else:
        h_local = row.ts.hour

    # -----------------------------
    # Mixing / ventilation
    # -----------------------------

    H = mixing_height_m(
        h_local,
        row.wind_speed,
    )

    vent = max(
        0.08,
        (row.wind_speed * H) / 1400.0,
    )

    # Current observed pollutant
    obs0 = pollutant_value(
        snap,
        species,
    )

    # Snapshot mixing conditions
    H0 = mixing_height_m(
        0,
        snap.wind_speed,
    )

    vent0 = max(
        0.08,
        (snap.wind_speed * H0) / 1400.0,
    )

    # -----------------------------
    # Base box-model concentration
    # -----------------------------

    k_dep = 0.06

    Q = obs0 * (
        vent0 + k_dep
    )

    c = (
        Q
        * emission_scale_val
        / (vent + k_dep)
    )

    # -----------------------------
    # Gaussian plume
    # -----------------------------

    if use_gauss:

        u = max(
            0.8,
            row.wind_speed,
        )

        # Effective source / stack height
        H_stack = 40.0

        # Simplified dispersion coefficients
        sigma_y = (
            40.0
            + 0.08 * 800.0
        )

        sigma_z = (
            20.0
            + 0.04 * 800.0
        )

        # Prototype source emission rate
        Qp = traffic_q_scenario

        gauss = gaussian_plume_concentration(
            Q=Qp,
            u=u,
            H=H_stack,
            sigma_y=sigma_y,
            sigma_z=sigma_z,
            x=800.0,
            y=0.0,
            z=0.0,
        )

        # Convert plume contribution
        plume_concentration = (
            gauss * 1e6
        )

        # Couple plume with station background
        c = (
            0.82 * c
            + 0.18
            * (
                plume_concentration * 0.35
                + obs0 * 0.40
            )
        )

    # -----------------------------
    # NO2 chemistry
    # -----------------------------

    if (
        use_chem
        and species.upper() == "NO2"
    ):

        j = max(
            0.0,
            math.sin(
                ((h_local - 7) / 11)
                * math.pi
            ),
        )

        c *= (
            1.08
            - 0.16 * j
        )

    # -----------------------------
    # Fallback if no selected model
    # -----------------------------

    if (
        not use_box
        and not use_gauss
    ):

        c = (
            obs0
            * emission_scale_val
            * (
                0.92
                + 0.08
                * (1.0 / vent)
            )
        )

    # -----------------------------
    # Small temporal drift
    # -----------------------------

    drift = (
        1.0
        + 0.01
        * math.sin(
            lead / 9.0
        )
    )

    return round(
        max(
            8.0,
            c * drift,
        ),
        1,
    )