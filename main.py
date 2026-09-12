#!/usr/bin/env python3
"""
Delhi Air Quality Digital Twin – Dual-RAG (pure Python, offline)

Usage:
    python main.py
    python main.py -q "Forecast PM2.5 for 72h if stubble increases by 40%"
    python main.py --demo
    python main.py -q "..." --station "Anand Vihar" --traffic 0.7 --stubble 1.4
    python main.py --list-stations
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.pipeline import AQDigitalTwin
from data.observations import list_stations, snapshot


DEMO_QUERIES = [
    "Forecast PM2.5 for the next 72 hours and estimate the impact if stubble burning increases by 40%.",
    "What is the expected NO2 tomorrow under normal traffic at Connaught Place?",
    "City-scale mass balance for PM2.5 with a data-driven bias correction.",
    "How does reducing traffic 30% change Anand Vihar PM2.5 over 48 hours?",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="AQ Digital Twin dual-RAG (Python CLI)")
    parser.add_argument("--query", "-q", type=str, help="Natural language question")
    parser.add_argument("--demo", action="store_true", help="Run all demo queries")
    parser.add_argument("--station", "-s", type=str, help="Station name (exact or partial)")
    parser.add_argument("--traffic", type=float, default=None, help="Traffic multiplier (e.g. 0.7)")
    parser.add_argument("--stubble", type=float, default=None, help="Stubble multiplier (e.g. 1.4)")
    parser.add_argument("--horizon", type=int, default=None, help="Forecast horizon hours")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON result")
    parser.add_argument("--list-stations", action="store_true", help="List stations and snapshot values")
    args = parser.parse_args()

    if args.list_stations:
        print("Stations (snapshot 1 Jan 2025 00:00 IST):\n")
        for loc in list_stations():
            o = snapshot(loc)
            print(
                f"  {loc:20s}  PM2.5={o.pm25:6.1f}  NO2={o.no2:5.1f}  "
                f"AQI={o.aqi_reported}  T={o.temperature:4.1f}°C  wind={o.wind_speed} m/s"
            )
        return

    twin = AQDigitalTwin()

    location = None
    if args.station:
        stations = list_stations()
        matches = [s for s in stations if args.station.lower() in s.lower()]
        if not matches:
            print(f"Unknown station '{args.station}'. Choose from: {stations}")
            sys.exit(1)
        location = matches[0]

    if args.demo:
        queries = DEMO_QUERIES
    elif args.query:
        queries = [args.query]
    else:
        print("No query supplied – running first demo query.\n")
        queries = [DEMO_QUERIES[0]]

    for i, q in enumerate(queries, 1):
        print("\n" + "#" * 72)
        print(f"QUERY {i}: {q}")
        print("#" * 72)
        result = twin.query(
            q,
            location=location,
            traffic_mult=args.traffic,
            stubble_mult=args.stubble,
            horizon_hours=args.horizon,
            verbose=not args.json,
        )
        if args.json:
            # make JSON-serialisable
            out = {
                "decomposition": result["decomposition"],
                "simulation_hits": result["simulation_hits"],
                "prediction_hits": result["prediction_hits"],
                "package": result["package"],
                "run": {
                    **result["run"],
                    "series": result["run"]["series"][::6],  # downsample for JSON
                },
            }
            print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
