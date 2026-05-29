"""
Comprehensive mock fleet data for FleetShield AI.

25 vehicles, 30 drivers with varied risk profiles, 90 days of telematics
(safety events, daily trip summaries, fleet KPIs). 3 "problem" drivers carry
high risk + burnout signals so the demo always has something to surface.

This replaces the original Geotab-backed data layer with a self-contained,
deterministic mock dataset (seeded RNG -> identical fleet on every run).

Dataclass fields are intentionally camelCase to match the frontend JSON
contract (frontend/src/types/fleet.ts) so `asdict()` serializes directly.
"""

from __future__ import annotations

import math
import random
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

# Deterministic demo: identical fleet on every boot, stable pitch numbers.
_SEED = 42
_rng = random.Random(_SEED)

SafetyEventType = str  # one of the 10 types below
SAFETY_EVENT_TYPES = [
    "harsh_braking", "harsh_acceleration", "speeding", "seatbelt",
    "distracted_driving", "drowsy_driving", "lane_departure", "tailgating",
    "rolling_stop", "idle_excessive",
]


# ─── Dataclasses ──────────────────────────────────────────────

@dataclass
class SeedVehicle:
    id: str
    name: str
    vin: str
    licensePlate: str
    type: str
    year: int
    make: str
    model: str
    odometer: int
    activeFrom: str
    faultCount: int = 0
    activeFaultCount: int = 0
    fuelTankCapacity: int = 0


@dataclass
class SeedDriver:
    id: str
    firstName: str
    lastName: str
    name: str
    employeeNumber: str
    pin: str
    hireDate: str
    vehicleId: str
    riskProfile: str   # low | moderate | high | critical
    burnoutRisk: str   # low | moderate | high
    tenureYears: float


@dataclass
class SeedSafetyEvent:
    id: str
    driverId: str
    vehicleId: str
    type: str
    severity: str      # low | medium | high | critical
    dateTime: str
    latitude: float
    longitude: float
    details: str


@dataclass
class SeedTripDay:
    driverId: str
    vehicleId: str
    date: str
    trips: int
    totalDistance: float       # km
    drivingHours: float
    idlingMinutes: float
    maxSpeed: float
    avgSpeed: float
    events: int
    nightDrivingHours: float
    restHoursBetweenShifts: float


@dataclass
class SeedFleetKPI:
    date: str
    totalDistance: float
    totalTrips: int
    totalEvents: int
    avgSafetyScore: float
    activeVehicles: int
    activeDrivers: int
    fuelConsumed: float
    idlingPercent: float


# ─── Time / RNG helpers ───────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _days_ago(n: int) -> str:
    return (_now() - timedelta(days=n)).strftime("%Y-%m-%d")


def _iso_offset(days: float, extra_seconds: float = 0.0) -> str:
    dt = _now() - timedelta(days=days) - timedelta(seconds=extra_seconds)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _random_between(lo: float, hi: float) -> float:
    return round((lo + _rng.random() * (hi - lo)) * 100) / 100


def _parse_dt(s: str) -> datetime:
    """Parse an ISO timestamp or date-only string as an AWARE UTC datetime.

    Handles a trailing Z and naive date-only strings (e.g. '2026-05-01'),
    which are assumed to be UTC. Always returning an aware datetime lets
    callers compare freely against `_now()` without naive/aware errors.
    """
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


# ─── Static vehicles (25) ─────────────────────────────────────

def _generate_vehicles() -> list[SeedVehicle]:
    rows = [
        ("v1", "Unit 101", "1HGBH41JXMN109186", "FL-2847", "Class 8 Tractor", 2022, "Freightliner", "Cascadia", 245000, "2022-03-15"),
        ("v2", "Unit 102", "2HGBH41JXMN109187", "FL-2848", "Class 8 Tractor", 2023, "Kenworth", "T680", 178000, "2023-01-10"),
        ("v3", "Unit 103", "3HGBH41JXMN109188", "FL-2849", "Class 8 Tractor", 2021, "Peterbilt", "579", 312000, "2021-06-20"),
        ("v4", "Unit 104", "4HGBH41JXMN109189", "FL-2850", "Class 8 Tractor", 2022, "Volvo", "VNL 860", 267000, "2022-08-01"),
        ("v5", "Unit 105", "5HGBH41JXMN109190", "FL-2851", "Class 8 Tractor", 2023, "International", "LT", 145000, "2023-04-15"),
        ("v6", "Unit 106", "6HGBH41JXMN109191", "FL-2852", "Class 6 Box", 2022, "Freightliner", "M2 106", 198000, "2022-02-28"),
        ("v7", "Unit 107", "7HGBH41JXMN109192", "FL-2853", "Class 6 Box", 2021, "Hino", "338", 289000, "2021-09-12"),
        ("v8", "Unit 108", "8HGBH41JXMN109193", "FL-2854", "Class 8 Tractor", 2024, "Kenworth", "W990", 67000, "2024-01-05"),
        ("v9", "Unit 109", "9HGBH41JXMN109194", "FL-2855", "Class 8 Tractor", 2022, "Mack", "Anthem", 234000, "2022-05-20"),
        ("v10", "Unit 110", "10HGBH41JXMN10919", "FL-2856", "Class 8 Tractor", 2023, "Freightliner", "Cascadia", 156000, "2023-02-14"),
        ("v11", "Unit 111", "11HGBH41JXMN10920", "FL-2857", "Class 5 Van", 2023, "Ford", "F-550", 123000, "2023-03-01"),
        ("v12", "Unit 112", "12HGBH41JXMN10921", "FL-2858", "Class 8 Tractor", 2021, "Peterbilt", "389", 345000, "2021-04-10"),
        ("v13", "Unit 113", "13HGBH41JXMN10922", "FL-2859", "Class 8 Tractor", 2022, "Volvo", "VNR 640", 278000, "2022-07-22"),
        ("v14", "Unit 114", "14HGBH41JXMN10923", "FL-2860", "Class 6 Box", 2023, "Isuzu", "FTR", 98000, "2023-06-15"),
        ("v15", "Unit 115", "15HGBH41JXMN10924", "FL-2861", "Class 8 Tractor", 2022, "Kenworth", "T680", 289000, "2022-01-08"),
        ("v16", "Unit 116", "16HGBH41JXMN10925", "FL-2862", "Class 8 Tractor", 2024, "Freightliner", "Cascadia", 45000, "2024-03-20"),
        ("v17", "Unit 117", "17HGBH41JXMN10926", "FL-2863", "Class 5 Van", 2022, "Ram", "5500", 167000, "2022-11-01"),
        ("v18", "Unit 118", "18HGBH41JXMN10927", "FL-2864", "Class 8 Tractor", 2023, "International", "LT", 134000, "2023-05-10"),
        ("v19", "Unit 119", "19HGBH41JXMN10928", "FL-2865", "Class 8 Tractor", 2021, "Mack", "Pinnacle", 356000, "2021-02-15"),
        ("v20", "Unit 120", "20HGBH41JXMN10929", "FL-2866", "Class 8 Tractor", 2022, "Peterbilt", "579", 245000, "2022-09-05"),
        ("v21", "Unit 121", "21HGBH41JXMN10930", "FL-2867", "Class 6 Box", 2023, "Hino", "L6", 89000, "2023-08-12"),
        ("v22", "Unit 122", "22HGBH41JXMN10931", "FL-2868", "Class 8 Tractor", 2022, "Volvo", "VNL 760", 267000, "2022-04-18"),
        ("v23", "Unit 123", "23HGBH41JXMN10932", "FL-2869", "Class 8 Tractor", 2024, "Kenworth", "T880", 34000, "2024-06-01"),
        ("v24", "Unit 124", "24HGBH41JXMN10933", "FL-2870", "Class 5 Van", 2023, "Ford", "E-450", 112000, "2023-10-20"),
        ("v25", "Unit 125", "25HGBH41JXMN10934", "FL-2871", "Class 8 Tractor", 2022, "Freightliner", "Cascadia", 298000, "2022-06-30"),
    ]
    return [
        SeedVehicle(id=r[0], name=r[1], vin=r[2], licensePlate=r[3], type=r[4],
                    year=r[5], make=r[6], model=r[7], odometer=r[8], activeFrom=r[9])
        for r in rows
    ]


# ─── Static drivers (30) ──────────────────────────────────────

def _generate_drivers() -> list[SeedDriver]:
    rows = [
        ("d1", "James", "Wilson", "241", "1847", "2019-03-15", "v1", "low", "low", 7),
        ("d2", "Sarah", "Chen", "318", "2956", "2020-08-20", "v2", "low", "low", 5),
        ("d3", "Marcus", "Rivera", "405", "7234", "2023-11-01", "v3", "critical", "high", 1),
        ("d4", "Emily", "Davis", "127", "4081", "2021-02-10", "v4", "low", "low", 5),
        ("d5", "Robert", "Kim", "562", "3619", "2018-06-05", "v5", "low", "moderate", 8),
        ("d6", "Lisa", "Martinez", "293", "8472", "2022-04-12", "v6", "moderate", "low", 4),
        ("d7", "Jake", "Thompson", "714", "5190", "2024-02-15", "v7", "high", "high", 1),
        ("d8", "Maria", "Gonzalez", "186", "6328", "2020-11-20", "v8", "low", "low", 5),
        ("d9", "David", "Lee", "439", "2745", "2019-07-30", "v9", "low", "low", 6),
        ("d10", "Amanda", "Brown", "651", "9013", "2021-09-15", "v10", "moderate", "high", 4),
        ("d11", "Michael", "Taylor", "378", "4567", "2022-01-08", "v11", "low", "low", 4),
        ("d12", "Derek", "Shaw", "802", "1382", "2024-06-01", "v12", "high", "high", 0.5),
        ("d13", "Rachel", "White", "215", "7896", "2020-03-22", "v13", "low", "low", 6),
        ("d14", "Carlos", "Hernandez", "547", "3041", "2021-12-05", "v14", "low", "low", 4),
        ("d15", "Jennifer", "Clark", "163", "6754", "2019-10-18", "v15", "moderate", "high", 6),
        ("d16", "Thomas", "Wright", "429", "8215", "2023-03-20", "v16", "low", "low", 3),
        ("d17", "Nicole", "Adams", "681", "5937", "2022-07-14", "v17", "low", "low", 4),
        ("d18", "Brian", "Hall", "356", "2468", "2020-05-28", "v18", "moderate", "high", 6),
        ("d19", "Stephanie", "Young", "194", "7103", "2021-08-10", "v19", "low", "low", 5),
        ("d20", "Kevin", "King", "723", "4826", "2023-01-15", "v20", "low", "low", 3),
        ("d21", "Laura", "Scott", "467", "9351", "2022-10-05", "v21", "low", "low", 3),
        ("d22", "Andrew", "Green", "582", "1679", "2019-04-22", "v22", "low", "low", 7),
        ("d23", "Michelle", "Baker", "839", "5204", "2024-01-10", "v23", "moderate", "low", 2),
        ("d24", "Daniel", "Nelson", "310", "8647", "2021-06-18", "v24", "low", "low", 5),
        ("d25", "Angela", "Carter", "745", "3982", "2020-12-01", "v25", "low", "low", 5),
        ("d26", "Ryan", "Mitchell", "158", "6215", "2023-09-15", "v1", "low", "low", 2),
        ("d27", "Patricia", "Roberts", "624", "4738", "2022-03-28", "v5", "low", "low", 4),
        ("d28", "Eric", "Turner", "491", "1053", "2024-04-05", "v10", "moderate", "high", 1),
        ("d29", "Diana", "Phillips", "276", "8491", "2021-11-12", "v15", "low", "low", 4),
        ("d30", "Samuel", "Campbell", "853", "2176", "2023-07-22", "v20", "low", "low", 2),
    ]
    return [
        SeedDriver(id=r[0], firstName=r[1], lastName=r[2], name=f"{r[1]} {r[2]}",
                   employeeNumber=r[3], pin=r[4], hireDate=r[5], vehicleId=r[6],
                   riskProfile=r[7], burnoutRisk=r[8], tenureYears=r[9])
        for r in rows
    ]


# ─── Safety events (90 days, by risk profile) ─────────────────

# Demo calibration: the "before" period (days 46-90) is worse than "after"
# (days 1-45), so the ROI before/after comparison shows a real improvement and
# the headline savings land near the proven pitch figure. Tuned, not arbitrary.
BEFORE_EVENT_FACTOR = 2.6   # before-period events per day multiplier
BEFORE_SEVERITY_UPGRADE = 0.45  # P(bump severity one tier in the before period)
_SEVERITY_UP = {"low": "medium", "medium": "high", "high": "critical"}


def _generate_safety_events(drivers: list[SeedDriver]) -> list[SeedSafetyEvent]:
    events: list[SeedSafetyEvent] = []
    event_id = 1
    for driver in drivers:
        rp = driver.riskProfile
        events_per_day = 3.5 if rp == "critical" else 2.2 if rp == "high" else 0.8 if rp == "moderate" else 0.3
        for day in range(90):
            is_before = day >= 45
            epd = events_per_day * (BEFORE_EVENT_FACTOR if is_before else 1.0)
            num_events = math.floor(epd + (_rng.random() - 0.3))
            for _ in range(max(0, num_events)):
                etype = SAFETY_EVENT_TYPES[math.floor(_rng.random() * len(SAFETY_EVENT_TYPES))]
                if rp == "critical":
                    severity = ["medium", "high", "critical"][math.floor(_rng.random() * 3)]
                elif rp == "high":
                    severity = ["low", "medium", "high"][math.floor(_rng.random() * 3)]
                else:
                    severity = ["low", "medium"][math.floor(_rng.random() * 2)]
                if is_before and severity != "critical" and _rng.random() < BEFORE_SEVERITY_UPGRADE:
                    severity = _SEVERITY_UP[severity]
                events.append(SeedSafetyEvent(
                    id=f"se{event_id}",
                    driverId=driver.id,
                    vehicleId=driver.vehicleId,
                    type=etype,
                    severity=severity,
                    dateTime=_iso_offset(day, _rng.random() * 86400),
                    latitude=round(33.7 + _rng.random() * 5, 6),
                    longitude=round(-84.4 + _rng.random() * 10, 6),
                    details=f"{etype.replace('_', ' ')} event detected",
                ))
                event_id += 1
    events.sort(key=lambda e: e.dateTime, reverse=True)
    return events


# ─── Daily trip summaries (90 days, burnout pattern) ──────────

def _generate_trip_days(drivers: list[SeedDriver]) -> list[SeedTripDay]:
    trip_days: list[SeedTripDay] = []
    for driver in drivers:
        is_burnout = driver.burnoutRisk == "high"
        is_high_risk = driver.riskProfile in ("high", "critical")
        for day in range(90):
            if not is_burnout and _rng.random() < 0.15:
                continue
            if is_burnout and _rng.random() < 0.03:
                continue

            driving_hours = (
                (12.5 if day % 2 == 0 else 9) + _rng.random() * 2
                if is_burnout else _random_between(6, 10)
            )
            rest_hours = (5 + _rng.random() * 1.5) if is_burnout else _random_between(9, 14)
            night_hours = (
                1 + (2.5 if day < 10 else 1.5 if day < 20 else 0.5) + _rng.random() * 0.3
                if is_burnout else _random_between(0, 1.5)
            )

            trip_days.append(SeedTripDay(
                driverId=driver.id,
                vehicleId=driver.vehicleId,
                date=_days_ago(day),
                trips=math.floor(_random_between(2, 6)),
                totalDistance=_random_between(200, 650),
                drivingHours=round(driving_hours, 2),
                idlingMinutes=round(_random_between(15, 90 if is_high_risk else 45) * (1.8 if day >= 45 else 1.0), 2),
                maxSpeed=_random_between(100 if is_high_risk else 85, 130 if is_high_risk else 105),
                avgSpeed=_random_between(55, 80),
                events=math.floor(_random_between(1, 5)) if is_high_risk else math.floor(_random_between(0, 2)),
                nightDrivingHours=round(night_hours, 2),
                restHoursBetweenShifts=round(rest_hours, 2),
            ))
    return trip_days


# ─── Fleet KPIs (90 days) ─────────────────────────────────────

def _generate_fleet_kpis() -> list[SeedFleetKPI]:
    kpis: list[SeedFleetKPI] = []
    for day in range(90):
        kpis.append(SeedFleetKPI(
            date=_days_ago(day),
            totalDistance=_random_between(8000, 14000),
            totalTrips=math.floor(_random_between(80, 140)),
            totalEvents=math.floor(_random_between(25, 65)),
            avgSafetyScore=_random_between(68, 82),
            activeVehicles=math.floor(_random_between(20, 25)),
            activeDrivers=math.floor(_random_between(22, 28)),
            fuelConsumed=_random_between(3200, 5800),
            idlingPercent=_random_between(8, 18),
        ))
    return kpis


# ─── Populate module-level datasets (deterministic order) ─────

seed_vehicles: list[SeedVehicle] = _generate_vehicles()
seed_drivers: list[SeedDriver] = _generate_drivers()
seed_safety_events: list[SeedSafetyEvent] = _generate_safety_events(seed_drivers)
seed_trip_days: list[SeedTripDay] = _generate_trip_days(seed_drivers)
seed_fleet_kpis: list[SeedFleetKPI] = _generate_fleet_kpis()


# ─── Lookups ──────────────────────────────────────────────────

def asdict_safe(obj) -> dict:
    """Serialize a seed dataclass to a plain dict (camelCase keys preserved)."""
    return asdict(obj)


def get_driver(driver_id: str) -> Optional[SeedDriver]:
    return next((d for d in seed_drivers if d.id == driver_id), None)


def get_vehicle(vehicle_id: str) -> Optional[SeedVehicle]:
    return next((v for v in seed_vehicles if v.id == vehicle_id), None)


def get_driver_stats(driver_id: str) -> Optional[dict]:
    driver = get_driver(driver_id)
    if not driver:
        return None

    cutoff = _now() - timedelta(days=30)
    cutoff_date = cutoff.strftime("%Y-%m-%d")

    events30 = [e for e in seed_safety_events
                if e.driverId == driver_id and _parse_dt(e.dateTime) > cutoff]
    trips30 = [t for t in seed_trip_days
               if t.driverId == driver_id and t.date > cutoff_date]

    total_distance = sum(t.totalDistance for t in trips30)
    total_hours = sum(t.drivingHours for t in trips30)
    avg_daily_hours = total_hours / len(trips30) if trips30 else 0
    avg_rest_hours = sum(t.restHoursBetweenShifts for t in trips30) / len(trips30) if trips30 else 0
    night_hours = sum(t.nightDrivingHours for t in trips30)

    severity_counts = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    for e in events30:
        severity_counts[e.severity] = severity_counts.get(e.severity, 0) + 1

    event_type_counts: dict[str, int] = {}
    for e in events30:
        event_type_counts[e.type] = event_type_counts.get(e.type, 0) + 1

    return {
        "driver": asdict(driver),
        "period": "30 days",
        "totalEvents": len(events30),
        "severityCounts": severity_counts,
        "eventTypeCounts": event_type_counts,
        "totalDistance": round(total_distance),
        "totalTrips": sum(t.trips for t in trips30),
        "totalDrivingHours": round(total_hours),
        "avgDailyHours": round(avg_daily_hours * 10) / 10,
        "avgRestHours": round(avg_rest_hours * 10) / 10,
        "nightDrivingHours": round(night_hours * 10) / 10,
        "maxSpeed": max([t.maxSpeed for t in trips30], default=0),
        "avgIdlingMinutes": round(sum(t.idlingMinutes for t in trips30) / len(trips30)) if trips30 else 0,
        "daysWorked": len(trips30),
    }


def get_fleet_summary() -> dict:
    cutoff = _now() - timedelta(days=30)
    cutoff_date = cutoff.strftime("%Y-%m-%d")

    kpis30 = [k for k in seed_fleet_kpis if k.date > cutoff_date]
    events30 = [e for e in seed_safety_events if _parse_dt(e.dateTime) > cutoff]

    total_distance = sum(k.totalDistance for k in kpis30)
    total_trips = sum(k.totalTrips for k in kpis30)
    total_events = len(events30)
    avg_safety_score = (
        round(sum(k.avgSafetyScore for k in kpis30) / len(kpis30) * 10) / 10
        if kpis30 else 0
    )
    n_kpis = max(len(kpis30), 1)
    miles = total_distance * 0.621371

    risk_distribution = {
        "low": sum(1 for d in seed_drivers if d.riskProfile == "low"),
        "moderate": sum(1 for d in seed_drivers if d.riskProfile == "moderate"),
        "high": sum(1 for d in seed_drivers if d.riskProfile == "high"),
        "critical": sum(1 for d in seed_drivers if d.riskProfile == "critical"),
    }

    return {
        "period": "30 days",
        "totalVehicles": len(seed_vehicles),
        "totalDrivers": len(seed_drivers),
        "activeVehicles": round(sum(k.activeVehicles for k in kpis30) / n_kpis),
        "activeDrivers": round(sum(k.activeDrivers for k in kpis30) / n_kpis),
        "totalDistance": round(total_distance),
        "totalTrips": total_trips,
        "totalSafetyEvents": total_events,
        "avgSafetyScore": avg_safety_score,
        "eventsPerMile": round(total_events / miles * 10000) / 10000 if miles > 0 else 0,
        "eventsPerThousandMiles": round(total_events / miles * 1000 * 100) / 100 if miles > 0 else 0,
        "fuelConsumed": round(sum(k.fuelConsumed for k in kpis30)),
        "avgIdlingPercent": round(sum(k.idlingPercent for k in kpis30) / len(kpis30) * 10) / 10 if kpis30 else 0,
        "riskDistribution": risk_distribution,
        "topRiskDrivers": [
            {"id": d.id, "name": d.name, "risk": d.riskProfile}
            for d in seed_drivers if d.riskProfile in ("high", "critical")
        ],
    }
