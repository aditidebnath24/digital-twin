"""
Delhi 6-station observations.

The CSV snapshot (1 Jan 2025 00:00 IST) is the only real observed row per station.
A 7-day hourly history is synthesised backwards from that snapshot using Delhi
winter climatology so prediction models have a series to roll on. The 00:00
endpoint is forced to the CSV values.
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

HISTORY_HOURS = 168
MAX_FORECAST_HOURS = 72
SNAPSHOT_TZ = timezone(timedelta(hours=5, minutes=30))
SNAPSHOT_DT = datetime(2025, 1, 1, 0, 0, tzinfo=SNAPSHOT_TZ)

STATION_META = {
    "Anand Vihar": {"id": "anand-vihar", "short": "AV", "character": "East Delhi transport hub"},
    "Connaught Place": {"id": "connaught-place", "short": "CP", "character": "Central business district"},
    "Dwarka": {"id": "dwarka", "short": "DW", "character": "Southwest planned suburb"},
    "Okhla Phase III": {"id": "okhla", "short": "OK", "character": "South industrial"},
    "Rohini": {"id": "rohini", "short": "RO", "character": "North-west residential"},
    "IGI Airport": {"id": "igi-airport", "short": "IGI", "character": "Open airfield / regional background"},
}


@dataclass
class Observation:
    ts: datetime
    location: str
    station_id: str
    lat: float
    lon: float
    temperature: float
    humidity: float
    pressure: float
    wind_speed: float
    condition: str
    description: str
    aqi_reported: Optional[int]
    pm25: float
    pm10: float
    co: float
    no2: float
    source: str  # observed | historical-synth


def _mulberry32(seed: int):
    a = seed & 0xFFFFFFFF

    def rng():
        nonlocal a
        a = (a + 0x6D2B79F5) & 0xFFFFFFFF
        t = ((a ^ (a >> 15)) * (1 | a)) & 0xFFFFFFFF
        t = ((t + ((t ^ (t >> 7)) * (61 | t))) & 0xFFFFFFFF) ^ t
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296.0

    return rng


def _hash_id(s: str) -> int:
    h = 2166136261
    for ch in s:
        h ^= ord(ch)
        h = (h * 16777619) & 0xFFFFFFFF
    return h


def pm_diurnal(hour: float) -> float:
    """Peak ~05:00 (inversion), trough ~15:00 (mixed)."""
    return 1.0 + 0.30 * math.cos(((hour - 5.0) / 24.0) * 2.0 * math.pi)


def mixing_height_m(hour: float, wind: float) -> float:
    day = max(0.0, math.sin(((hour - 7.0) / 11.0) * math.pi))
    return 160.0 + (1100.0 + 40.0 * wind) * (day ** 1.15)


def _round(n: float, d: int) -> float:
    p = 10 ** d
    return round(n * p) / p


def _load_snapshot_rows(csv_path: Path) -> List[dict]:
    rows = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)
    return rows


def _synth_at(snap: dict, offset_hours: int, rng) -> Observation:
    hour = ((offset_hours % 24) + 24) % 24
    d_pm = pm_diurnal(hour) / pm_diurnal(0)
    d_no = (1 + 0.22 * math.cos(((hour - 8) / 24) * 2 * math.pi)) / (
        1 + 0.22 * math.cos((-8 / 24) * 2 * math.pi)
    )
    episode = 1 + 0.05 * math.sin((offset_hours / 24) * 0.9)
    noise = 1 + 0.035 * (rng() * 2 - 1)

    t_base = float(snap["temperature"])
    temperature = t_base + 7.4 * (
        math.sin(((hour - 9) / 24) * 2 * math.pi) - math.sin((-9 / 24) * 2 * math.pi)
    )
    humidity = max(
        38.0,
        min(100.0, float(snap["humidity"]) - 48.0 * max(0.0, math.sin(((hour - 7) / 24) * math.pi))),
    )
    wind_speed = max(
        0.6,
        float(snap["wind_speed"])
        * (0.75 + 0.55 * max(0.0, math.sin(((hour - 8) / 12) * math.pi))),
    )
    pressure = float(snap["pressure"]) + 1.4 * math.sin((offset_hours / 12) * math.pi) + (rng() - 0.5) * 0.4

    pm25 = float(snap["pm25"]) * d_pm * episode * noise
    pm10 = float(snap["pm10"]) * d_pm * episode * (0.99 + 0.02 * rng())
    no2 = float(snap["no2"]) * d_no * (0.97 + 0.06 * rng())
    co = float(snap["co"]) * d_no * (0.97 + 0.05 * rng())

    is_night = hour < 7 or hour > 19
    condition = "Fog" if (is_night and humidity > 85) else ("Haze" if not is_night else snap["condition"])
    loc = snap["location"]
    meta = STATION_META[loc]
    ts = SNAPSHOT_DT + timedelta(hours=offset_hours)

    return Observation(
        ts=ts,
        location=loc,
        station_id=meta["id"],
        lat=float(snap["lat"]),
        lon=float(snap["lon"]),
        temperature=_round(temperature, 1),
        humidity=_round(humidity, 0),
        pressure=_round(pressure, 1),
        wind_speed=_round(wind_speed, 1),
        condition=condition,
        description=snap["description"],
        aqi_reported=int(snap["aqi"]) if offset_hours == 0 else None,
        pm25=_round(pm25, 1),
        pm10=_round(pm10, 1),
        co=_round(co, 0),
        no2=_round(no2, 1),
        source="observed" if offset_hours == 0 else "historical-synth",
    )


def build_catalog(csv_path: Optional[Path] = None) -> Dict[str, List[Observation]]:
    if csv_path is None:
        csv_path = Path(__file__).resolve().parent / "cleaned_delhi_weather_aqi.csv"
    snaps = _load_snapshot_rows(csv_path)
    catalog: Dict[str, List[Observation]] = {}
    for snap in snaps:
        loc = snap["location"]
        rng = _mulberry32(_hash_id(loc) ^ 20250101)
        series: List[Observation] = []
        for h in range(-HISTORY_HOURS, 1):
            if h == 0:
                meta = STATION_META[loc]
                series.append(
                    Observation(
                        ts=SNAPSHOT_DT,
                        location=loc,
                        station_id=meta["id"],
                        lat=float(snap["lat"]),
                        lon=float(snap["lon"]),
                        temperature=float(snap["temperature"]),
                        humidity=float(snap["humidity"]),
                        pressure=float(snap["pressure"]),
                        wind_speed=float(snap["wind_speed"]),
                        condition=snap["condition"],
                        description=snap["description"],
                        aqi_reported=int(snap["aqi"]),
                        pm25=float(snap["pm25"]),
                        pm10=float(snap["pm10"]),
                        co=float(snap["co"]),
                        no2=float(snap["no2"]),
                        source="observed",
                    )
                )
            else:
                series.append(_synth_at(snap, h, rng))
        catalog[loc] = series
    return catalog


# Module-level catalog (built once)
_CATALOG: Optional[Dict[str, List[Observation]]] = None


def get_catalog() -> Dict[str, List[Observation]]:
    global _CATALOG
    if _CATALOG is None:
        _CATALOG = build_catalog()
    return _CATALOG


def list_stations() -> List[str]:
    return list(get_catalog().keys())


def snapshot(location: str) -> Observation:
    return get_catalog()[location][-1]


def history(location: str) -> List[Observation]:
    return get_catalog()[location]


def pollutant_value(obs: Observation, species: str) -> float:
    s = species.upper().replace("₂", "2").replace("₃", "3")
    if s in ("PM2.5", "PM25"):
        return obs.pm25
    if s == "PM10":
        return obs.pm10
    if s == "NO2":
        return obs.no2
    if s == "CO":
        return obs.co
    return obs.pm25


def parse_station_hint(query: str) -> Optional[str]:
    q = query.lower()
    mapping = [
        ("anand", "Anand Vihar"),
        ("connaught", "Connaught Place"),
        ("dwarka", "Dwarka"),
        ("okhla", "Okhla Phase III"),
        ("rohini", "Rohini"),
        ("igi", "IGI Airport"),
        ("airport", "IGI Airport"),
    ]
    for key, loc in mapping:
        if key in q:
            return loc
    return None


def aqi_from_pm25(pm25: float) -> tuple[int, str]:
    """US EPA PM2.5 AQI breakpoints."""
    breaks = [
        (0, 12.0, 0, 50, "Good"),
        (12.1, 35.4, 51, 100, "Moderate"),
        (35.5, 55.4, 101, 150, "USG"),
        (55.5, 150.4, 151, 200, "Unhealthy"),
        (150.5, 250.4, 201, 300, "Very Unhealthy"),
        (250.5, 350.4, 301, 400, "Hazardous"),
        (350.5, 500.4, 401, 500, "Hazardous"),
    ]
    c = max(0.0, pm25)
    for c_lo, c_hi, i_lo, i_hi, label in breaks:
        if c <= c_hi:
            aqi = int(round(((i_hi - i_lo) / (c_hi - c_lo)) * (c - c_lo) + i_lo))
            return min(500, max(0, aqi)), label
    return 500, "Hazardous"
