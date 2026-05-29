"""
Live Fleet Map helper — simplified, deterministic port of
existing-solution/backend/src/services/live-fleet.ts.

Provides simulated vehicle positions, GPS trails, and speeding hotspots for
the live-map routes. There is no external telematics provider here, so this is
always the "simulated Toronto-area" path from the original service.

Determinism: positions/speeds use the same seeded-random scheme as the TS
source (sin(seed) * 10000 fractional part). Per-call drift is keyed off a
1-minute time bucket so vehicles "move" slowly minute-to-minute while staying
stable within the same minute. `activeAlerts` is derived from the seed safety
events in the last 24 hours.

Returned dicts use camelCase keys to match frontend/src/types/fleet.ts
(LiveVehicle, GPSTrailPoint, SpeedingHotspot).
"""

from __future__ import annotations

import math
from datetime import timedelta

from backend.data.seed_data import (
    _now,
    _parse_dt,
    seed_drivers,
    seed_safety_events,
    seed_vehicles,
)


# ─── Seeded random helper (mirrors live-fleet.ts seededRandom) ────────────────

def _seeded_random(seed: float) -> float:
    """Deterministic pseudo-random in [0, 1) — JS-parity: frac(sin(seed)*10000)."""
    x = math.sin(seed) * 10000
    return x - math.floor(x)


# ─── Live fleet (simulated) ───────────────────────────────────────────────────

def get_live_fleet() -> list[dict]:
    """Current simulated positions for every seed vehicle."""
    now = _now()
    now_ms = now.timestamp() * 1000.0
    cutoff_24h = now - timedelta(hours=24)
    time_seed = math.floor(now_ms / 60000)  # changes every minute (slow drift)

    vehicles: list[dict] = []
    for i, seed_vehicle in enumerate(seed_vehicles):
        vehicle_id = seed_vehicle.id
        vehicle_name = seed_vehicle.name

        driver = next((d for d in seed_drivers if d.vehicleId == vehicle_id), None)
        driver_name = driver.name if driver else f"Driver {i + 1}"
        risk_level = driver.riskProfile if driver else "low"

        # Stable base position in the Toronto area, with slow per-minute drift.
        base_lat = 43.6 + _seeded_random(i * 1000 + 1) * 0.2
        base_lng = -79.5 + _seeded_random(i * 1000 + 2) * 0.3
        drift_lat = (_seeded_random(i * 1000 + time_seed) - 0.5) * 0.005
        drift_lng = (_seeded_random(i * 1000 + time_seed + 500) - 0.5) * 0.005

        is_driving = _seeded_random(i * 1000 + 3) < 0.6  # ~60% driving
        speed = round(_seeded_random(i * 1000 + time_seed + 4) * 100) if is_driving else 0
        bearing = round(_seeded_random(i * 1000 + 5) * 360)

        recent_events = [
            e for e in seed_safety_events
            if e.vehicleId == vehicle_id and _parse_dt(e.dateTime) > cutoff_24h
        ]

        last_update = now - timedelta(
            milliseconds=math.floor(_seeded_random(i * 1000 + 6) * 60000)
        )

        vehicles.append({
            "id": vehicle_id,
            "deviceId": f"simulated-{vehicle_id}",
            "name": vehicle_name,
            "driverName": driver_name,
            "latitude": round((base_lat + drift_lat) * 100000) / 100000,
            "longitude": round((base_lng + drift_lng) * 100000) / 100000,
            "speed": speed,
            "bearing": bearing,
            "isDriving": is_driving,
            "isOnline": True,
            "lastUpdate": last_update.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "riskLevel": risk_level,
            "activeAlerts": len(recent_events),
        })

    return vehicles


# ─── GPS trail (simulated random walk) ────────────────────────────────────────

def get_gps_trail(vehicle_id: str, hours: int = 4) -> list[dict]:
    """A simulated GPS trail (one point per minute) for the requested window."""
    now = _now()

    digits = "".join(ch for ch in vehicle_id if ch.isdigit())
    vehicle_index = int(digits) if digits else 1

    start_lat = 43.6 + _seeded_random(vehicle_index * 2000 + 1) * 0.2
    start_lng = -79.5 + _seeded_random(vehicle_index * 2000 + 2) * 0.3

    total_points = max(0, hours) * 60
    lat = start_lat
    lng = start_lng

    points: list[dict] = []
    for i in range(total_points):
        seed = vehicle_index * 2000 + i

        # Random walk: small steps.
        lat += (_seeded_random(seed + 100) - 0.5) * 0.002
        lng += (_seeded_random(seed + 200) - 0.5) * 0.002

        # Keep within Toronto bounds.
        lat = max(43.58, min(43.85, lat))
        lng = max(-79.55, min(-79.15, lng))

        is_moving = _seeded_random(seed + 300) > 0.2
        speed = round(30 + _seeded_random(seed + 400) * 80) if is_moving else 0

        dt = now - timedelta(milliseconds=(total_points - i) * 60000)
        points.append({
            "latitude": round(lat * 100000) / 100000,
            "longitude": round(lng * 100000) / 100000,
            "speed": speed,
            "dateTime": dt.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        })

    return points


# ─── Speeding hotspots (grid clustering of speeding events) ───────────────────

_SEVERITY_TO_SPEED = {"low": 75, "medium": 90, "high": 110, "critical": 130}


def get_speeding_hotspots() -> list[dict]:
    """Cluster seed speeding events into hotspots (grid cells of 0.05 degrees)."""
    speeding_events = [e for e in seed_safety_events if e.type == "speeding"]

    grid: dict[str, dict] = {}
    for event in speeding_events:
        grid_lat = round(event.latitude / 0.05) * 0.05
        grid_lng = round(event.longitude / 0.05) * 0.05
        key = f"{grid_lat:.2f},{grid_lng:.2f}"
        cell = grid.setdefault(key, {"events": [], "latSum": 0.0, "lngSum": 0.0})
        cell["events"].append(event)
        cell["latSum"] += event.latitude
        cell["lngSum"] += event.longitude

    hotspots: list[dict] = []
    for cell in grid.values():
        events = cell["events"]
        if len(events) < 2:  # only clusters with multiple events
            continue

        avg_lat = cell["latSum"] / len(events)
        avg_lng = cell["lngSum"] / len(events)

        driver_counts: dict[str, int] = {}
        for event in events:
            driver = next((d for d in seed_drivers if d.id == event.driverId), None)
            name = driver.name if driver else event.driverId
            driver_counts[name] = driver_counts.get(name, 0) + 1

        top_drivers = [
            name for name, _ in sorted(
                driver_counts.items(), key=lambda kv: kv[1], reverse=True
            )[:3]
        ]

        avg_speed = round(
            sum(_SEVERITY_TO_SPEED.get(e.severity, 80) for e in events) / len(events)
        )

        hotspots.append({
            "latitude": round(avg_lat * 100000) / 100000,
            "longitude": round(avg_lng * 100000) / 100000,
            "eventCount": len(events),
            "avgSpeed": avg_speed,
            "topDrivers": top_drivers,
            "description": (
                f"{len(events)} speeding events in this area, avg {avg_speed} km/h"
            ),
        })

    hotspots.sort(key=lambda h: h["eventCount"], reverse=True)
    return hotspots
