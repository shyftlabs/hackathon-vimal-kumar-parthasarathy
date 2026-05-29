"""
Green Fleet Sustainability Score Engine.

Calculates environmental impact metrics and actionable recommendations for
fleet operators to reduce carbon footprint and transition to EV.

Components:
  Fuel Efficiency:  30% -- km/L performance vs vehicle class benchmarks
  Idle Reduction:   25% -- idle time as % of total, fuel wasted
  Eco Driving:      25% -- harsh events that waste fuel (braking, accel, speeding)
  Fleet Modernity:  20% -- vehicle age, maintenance, EV readiness

Grade scale: A+ (95-100), A (90-94), B+ (85-89), B (75-84), C+ (70-74),
             C (60-69), D (50-59), F (<50)

Ported from backend/src/scoring/green-score-engine.ts (1:1 fidelity).
"""

from __future__ import annotations

from datetime import timedelta
from typing import Optional

from backend.data.seed_data import (
    _now,
    _parse_dt,
    seed_drivers,
    seed_fleet_kpis,
    seed_safety_events,
    seed_trip_days,
    seed_vehicles,
)

# --- Constants ---
CO2_PER_LITER_DIESEL = 2.31      # kg CO2 per liter of diesel
IDLE_FUEL_BURN_PER_HOUR = 3.8    # liters per hour at idle
FUEL_COST_PER_LITER = 1.65
TREES_PER_TON_CO2 = 16.5         # trees needed to absorb 1 ton CO2/year

# Fuel efficiency benchmarks by vehicle class (km/L)
EFFICIENCY_BENCHMARKS: dict[str, dict[str, float]] = {
    "Class 8 Tractor": {"good": 3.4, "avg": 2.8, "poor": 2.2},
    "Class 6 Box": {"good": 5.1, "avg": 4.2, "poor": 3.5},
    "Class 5 Van": {"good": 6.8, "avg": 5.5, "poor": 4.5},
    "default": {"good": 4.5, "avg": 3.5, "poor": 2.8},
}

# EV replacement savings (annual) by vehicle class
EV_SAVINGS: dict[str, dict[str, float]] = {
    "Class 5 Van": {"fuelSaved": 8200, "maintenanceSaved": 2800, "co2Reduced": 18.5},
    "Class 6 Box": {"fuelSaved": 12500, "maintenanceSaved": 3500, "co2Reduced": 28.0},
    "Class 8 Tractor": {"fuelSaved": 22000, "maintenanceSaved": 5200, "co2Reduced": 52.0},
    "default": {"fuelSaved": 10000, "maintenanceSaved": 3000, "co2Reduced": 25.0},
}


# --- Helper functions ---
def _get_grade(score: float) -> str:
    if score >= 95:
        return "A+"
    if score >= 90:
        return "A"
    if score >= 85:
        return "B+"
    if score >= 75:
        return "B"
    if score >= 70:
        return "C+"
    if score >= 60:
        return "C"
    if score >= 50:
        return "D"
    return "F"


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


# --- Main Calculation Functions ---

def calculate_green_dashboard() -> dict:
    now = _now()
    thirty_days_ago = now - timedelta(days=30)
    sixty_days_ago = now - timedelta(days=60)
    # Date-only string cutoffs for date-only fields (trips, KPIs).
    thirty_date = thirty_days_ago.strftime("%Y-%m-%d")
    sixty_date = sixty_days_ago.strftime("%Y-%m-%d")

    # Recent data (last 30 days)
    recent_trips = [t for t in seed_trip_days if t.date > thirty_date]
    recent_kpis = [k for k in seed_fleet_kpis if k.date > thirty_date]
    prev_kpis = [k for k in seed_fleet_kpis if sixty_date < k.date <= thirty_date]
    recent_events = [e for e in seed_safety_events if _parse_dt(e.dateTime) > thirty_days_ago]

    # Fleet-level metrics
    total_distance = sum(k.totalDistance for k in recent_kpis)
    total_fuel = sum(k.fuelConsumed for k in recent_kpis)
    avg_idling_percent = (
        sum(k.idlingPercent for k in recent_kpis) / len(recent_kpis)
        if recent_kpis else 12
    )

    prev_total_fuel = sum(k.fuelConsumed for k in prev_kpis)

    # Carbon footprint
    total_co2_kg = total_fuel * CO2_PER_LITER_DIESEL
    total_co2_tons = total_co2_kg / 1000
    days_in_period = len(recent_kpis) or 30
    daily_avg_co2_kg = total_co2_kg / days_in_period
    vehicle_count = len(seed_vehicles)
    co2_per_vehicle_per_day = daily_avg_co2_kg / vehicle_count
    co2_per_km = total_co2_kg / total_distance if total_distance > 0 else 0
    trees_equivalent = round(total_co2_tons * TREES_PER_TON_CO2 * 12)  # Annualized

    prev_co2_tons = (prev_total_fuel * CO2_PER_LITER_DIESEL) / 1000
    month_over_month_change = (
        ((total_co2_tons - prev_co2_tons) / prev_co2_tons) * 100
        if prev_co2_tons > 0 else 0
    )

    carbon_footprint = {
        "totalCO2Tons": round(total_co2_tons * 10) / 10,
        "dailyAvgCO2Kg": round(daily_avg_co2_kg),
        "co2PerVehiclePerDay": round(co2_per_vehicle_per_day * 10) / 10,
        "co2PerKm": round(co2_per_km * 1000) / 1000,
        "treesEquivalent": trees_equivalent,
        "monthOverMonthChange": round(month_over_month_change * 10) / 10,
    }

    # Fuel efficiency
    fleet_avg_km_per_liter = total_distance / total_fuel if total_fuel > 0 else 0
    fuel_efficiency = calculate_fuel_efficiency(
        recent_trips, fleet_avg_km_per_liter, total_fuel, total_distance
    )

    # Idle waste
    idle_waste = calculate_idle_waste(recent_trips, avg_idling_percent)

    # Driver green rankings
    driver_green_rankings = calculate_driver_green_scores(
        recent_trips, recent_events, fleet_avg_km_per_liter
    )

    # EV readiness
    ev_readiness = calculate_ev_readiness(recent_trips)

    # Fleet green score
    fleet_score = calculate_fleet_green_score(
        fleet_avg_km_per_liter,
        avg_idling_percent,
        len(recent_events),
        total_distance,
        month_over_month_change,
    )

    # Recommendations
    recommendations = generate_recommendations(
        idle_waste, fuel_efficiency, ev_readiness, driver_green_rankings
    )

    # Monthly trend (last 3 months simulated from KPI data)
    monthly_trend = calculate_monthly_trend()

    return {
        "fleetScore": fleet_score,
        "carbonFootprint": carbon_footprint,
        "fuelEfficiency": fuel_efficiency,
        "idleWaste": idle_waste,
        "driverGreenRankings": driver_green_rankings,
        "evReadiness": ev_readiness,
        "recommendations": recommendations,
        "monthlyTrend": monthly_trend,
    }


def calculate_fuel_efficiency(
    trips: list,
    fleet_avg: float,
    total_fuel: float,
    total_distance: float,
) -> dict:
    # Per-driver efficiency
    driver_efficiency: dict[str, dict] = {}

    for trip in trips:
        driver = next((d for d in seed_drivers if d.id == trip.driverId), None)
        if not driver:
            continue

        existing = driver_efficiency.get(
            trip.driverId, {"distance": 0, "fuel": 0, "name": driver.name}
        )
        existing["distance"] += trip.totalDistance
        # Estimate fuel per driver based on distance and vehicle type
        vehicle = next((v for v in seed_vehicles if v.id == trip.vehicleId), None)
        benchmark = EFFICIENCY_BENCHMARKS.get(
            vehicle.type if vehicle else "default", EFFICIENCY_BENCHMARKS["default"]
        )
        existing["fuel"] += trip.totalDistance / benchmark["avg"]
        driver_efficiency[trip.driverId] = existing

    best_driver = {"id": "", "name": "N/A", "kmPerLiter": 0}
    worst_driver = {"id": "", "name": "N/A", "kmPerLiter": float("inf")}

    for driver_id, data in driver_efficiency.items():
        eff = data["distance"] / data["fuel"] if data["fuel"] > 0 else 0
        if eff > best_driver["kmPerLiter"]:
            best_driver = {"id": driver_id, "name": data["name"], "kmPerLiter": round(eff * 10) / 10}
        if eff < worst_driver["kmPerLiter"] and eff > 0:
            worst_driver = {"id": driver_id, "name": data["name"], "kmPerLiter": round(eff * 10) / 10}

    if worst_driver["kmPerLiter"] == float("inf"):
        worst_driver = {"id": "", "name": "N/A", "kmPerLiter": 0}

    benchmark_comparison = (
        "above average" if fleet_avg >= 3.4
        else "average" if fleet_avg >= 2.8
        else "below average"
    )

    return {
        "fleetAvgKmPerLiter": round(fleet_avg * 10) / 10,
        "totalFuelConsumed": round(total_fuel),
        "totalDistance": round(total_distance),
        "bestDriver": best_driver,
        "worstDriver": worst_driver,
        "benchmarkComparison": benchmark_comparison,
    }


def calculate_idle_waste(trips: list, avg_idle_percent: float) -> dict:
    total_idle_minutes = sum(t.idlingMinutes for t in trips)
    total_idle_hours = total_idle_minutes / 60
    fuel_wasted_liters = total_idle_hours * IDLE_FUEL_BURN_PER_HOUR
    co2_from_idling = fuel_wasted_liters * CO2_PER_LITER_DIESEL
    cost_wasted = fuel_wasted_liters * FUEL_COST_PER_LITER

    # Per-driver idle stats
    driver_idle: dict[str, dict] = {}
    for trip in trips:
        driver = next((d for d in seed_drivers if d.id == trip.driverId), None)
        if not driver:
            continue
        existing = driver_idle.get(trip.driverId, {"minutes": 0, "name": driver.name})
        existing["minutes"] += trip.idlingMinutes
        driver_idle[trip.driverId] = existing

    top_offenders = [
        {
            "driverId": driver_id,
            "driverName": data["name"],
            "idleMinutes": round(data["minutes"]),
            "fuelWasted": round((data["minutes"] / 60) * IDLE_FUEL_BURN_PER_HOUR * 10) / 10,
            "co2Produced": round(
                (data["minutes"] / 60) * IDLE_FUEL_BURN_PER_HOUR * CO2_PER_LITER_DIESEL * 10
            ) / 10,
        }
        for driver_id, data in driver_idle.items()
    ]
    top_offenders.sort(key=lambda o: o["idleMinutes"], reverse=True)
    top_offenders = top_offenders[:5]

    return {
        "totalIdleHours": round(total_idle_hours * 10) / 10,
        "fuelWastedLiters": round(fuel_wasted_liters),
        "co2FromIdling": round(co2_from_idling * 10) / 10,
        "costWasted": round(cost_wasted),
        "avgIdlePercentage": round(avg_idle_percent * 10) / 10,
        "topOffenders": top_offenders,
    }


def calculate_driver_green_scores(
    trips: list,
    events: list,
    fleet_avg: float,
) -> list[dict]:
    driver_stats: dict[str, dict] = {}

    fuel_wasting_events = {"harsh_braking", "harsh_acceleration", "speeding", "idle_excessive"}

    for trip in trips:
        driver = next((d for d in seed_drivers if d.id == trip.driverId), None)
        if not driver:
            continue

        vehicle = next((v for v in seed_vehicles if v.id == trip.vehicleId), None)
        benchmark = EFFICIENCY_BENCHMARKS.get(
            vehicle.type if vehicle else "default", EFFICIENCY_BENCHMARKS["default"]
        )

        existing = driver_stats.get(trip.driverId, {
            "distance": 0, "fuel": 0, "idleMinutes": 0,
            "drivingMinutes": 0, "harshEvents": 0, "name": driver.name,
        })
        existing["distance"] += trip.totalDistance
        existing["fuel"] += trip.totalDistance / benchmark["avg"]
        existing["idleMinutes"] += trip.idlingMinutes
        existing["drivingMinutes"] += trip.drivingHours * 60
        driver_stats[trip.driverId] = existing

    # Count fuel-wasting events per driver
    for event in events:
        if event.type not in fuel_wasting_events:
            continue
        existing = driver_stats.get(event.driverId)
        if existing:
            existing["harshEvents"] += 1

    scores: list[dict] = []

    for driver_id, stats in driver_stats.items():
        km_per_liter = stats["distance"] / stats["fuel"] if stats["fuel"] > 0 else 0
        idle_percent = (
            (stats["idleMinutes"] / (stats["drivingMinutes"] + stats["idleMinutes"])) * 100
            if stats["drivingMinutes"] > 0 else 0
        )
        harsh_per_km = (stats["harshEvents"] / stats["distance"]) * 1000 if stats["distance"] > 0 else 0

        # Estimate CO2 per km for this driver
        fuel_per_km = stats["fuel"] / stats["distance"] if stats["distance"] > 0 else 0
        co2_per_km = fuel_per_km * CO2_PER_LITER_DIESEL

        # Fleet average CO2/km
        fleet_co2_per_km = (1 / fleet_avg) * CO2_PER_LITER_DIESEL if fleet_avg > 0 else 0
        co2_saved_vs_avg = (fleet_co2_per_km - co2_per_km) * stats["distance"]

        # Green score components (each 0-100)
        efficiency_score = _clamp(((km_per_liter / 3.5) * 70) + 15, 0, 100)
        idle_score = _clamp(100 - (idle_percent * 5), 0, 100)
        harsh_score = _clamp(100 - (harsh_per_km * 20), 0, 100)

        green_score = round(
            efficiency_score * 0.4 + idle_score * 0.35 + harsh_score * 0.25
        )

        scores.append({
            "driverId": driver_id,
            "driverName": stats["name"],
            "greenScore": _clamp(green_score, 0, 100),
            "grade": _get_grade(green_score),
            "rank": 0,  # Set after sorting
            "fuelEfficiency": round(km_per_liter * 10) / 10,
            "idlePercent": round(idle_percent * 10) / 10,
            "harshEventsPerKm": round(harsh_per_km * 100) / 100,
            "co2PerKm": round(co2_per_km * 1000) / 1000,
            "co2SavedVsAvg": round(co2_saved_vs_avg * 10) / 10,
        })

    scores.sort(key=lambda s: s["greenScore"], reverse=True)
    for i, s in enumerate(scores):
        s["rank"] = i + 1

    return scores


def calculate_ev_readiness(trips: list) -> dict:
    # Group trips by vehicle
    vehicle_trips: dict[str, dict] = {}

    for trip in trips:
        existing = vehicle_trips.get(trip.vehicleId, {"distances": [], "totalDays": 0})
        existing["distances"].append(trip.totalDistance)
        existing["totalDays"] += 1
        vehicle_trips[trip.vehicleId] = existing

    candidates: list[dict] = []

    for vehicle in seed_vehicles:
        v_trips = vehicle_trips.get(vehicle.id)
        if not v_trips or v_trips["totalDays"] == 0:
            continue

        avg_daily_distance = sum(v_trips["distances"]) / v_trips["totalDays"]

        # 2026 EV range reality: Class 5 vans ~320km, Class 6 ~400km, Class 8 ~500km
        ev_range = (
            320 if vehicle.type == "Class 5 Van"
            else 400 if vehicle.type == "Class 6 Box"
            else 500
        )

        ev_savings = EV_SAVINGS.get(vehicle.type, EV_SAVINGS["default"])

        # Readiness score: lower daily distance relative to range = higher readiness
        range_ratio = avg_daily_distance / ev_range
        readiness_score = 0
        reason = ""

        if range_ratio <= 0.6:
            readiness_score = 95
            reason = f"Avg daily {round(avg_daily_distance)}km well within {ev_range}km EV range — ideal candidate"
        elif range_ratio <= 0.8:
            readiness_score = 75
            reason = f"Avg daily {round(avg_daily_distance)}km manageable with {ev_range}km EV range"
        elif range_ratio <= 1.0:
            readiness_score = 50
            reason = f"Avg daily {round(avg_daily_distance)}km pushes {ev_range}km EV range — needs charging infra"
        else:
            readiness_score = 25
            reason = f"Avg daily {round(avg_daily_distance)}km exceeds current {ev_range}km EV range"

        # Older vehicles are better candidates for replacement
        age_bonus = max(0, (2026 - vehicle.year) * 3)
        readiness_score = _clamp(readiness_score + age_bonus, 0, 100)

        # Fuel cost estimate
        benchmark = EFFICIENCY_BENCHMARKS.get(vehicle.type, EFFICIENCY_BENCHMARKS["default"])
        daily_fuel_liters = avg_daily_distance / benchmark["avg"]
        annual_fuel_cost = daily_fuel_liters * 260 * FUEL_COST_PER_LITER

        candidates.append({
            "vehicleId": vehicle.id,
            "vehicleName": vehicle.name,
            "type": vehicle.type,
            "year": vehicle.year,
            "avgDailyDistance": round(avg_daily_distance),
            "currentFuelCost": round(annual_fuel_cost),
            "projectedEVSavings": round(ev_savings["fuelSaved"] + ev_savings["maintenanceSaved"]),
            "co2Reduction": ev_savings["co2Reduced"],
            "readinessScore": readiness_score,
            "reason": reason,
        })

    candidates.sort(key=lambda c: c["readinessScore"], reverse=True)

    top_candidates = [c for c in candidates if c["readinessScore"] >= 50]

    return {
        "totalCandidates": len(top_candidates),
        "projectedAnnualSavings": sum(c["projectedEVSavings"] for c in top_candidates),
        "projectedCO2Reduction": round(sum(c["co2Reduction"] for c in top_candidates) * 10) / 10,
        "vehicles": candidates,
    }


def calculate_fleet_green_score(
    avg_km_per_liter: float,
    avg_idle_percent: float,
    recent_events: int,
    total_distance: float,
    month_over_month_change: float,
) -> dict:
    # Fuel efficiency score (0-100): benchmark around 3.0 km/L for mixed fleet
    fuel_score = _clamp(round((avg_km_per_liter / 4.0) * 85 + 10), 0, 100)

    # Idle reduction score: lower idle = higher score
    idle_score = _clamp(round(100 - (avg_idle_percent * 4.5)), 0, 100)

    # Eco driving score: fewer fuel-wasting events per km
    fuel_wasting_types = {"harsh_braking", "harsh_acceleration", "speeding", "idle_excessive"}
    cutoff = _now() - timedelta(days=30)
    fuel_wasting_events = len([
        e for e in seed_safety_events
        if e.type in fuel_wasting_types and _parse_dt(e.dateTime) > cutoff
    ])
    events_per_km = (fuel_wasting_events / total_distance) * 1000 if total_distance > 0 else 0
    eco_score = _clamp(round(100 - (events_per_km * 15)), 0, 100)

    # Fleet modernity score: based on avg vehicle age
    avg_age = (
        sum(2026 - v.year for v in seed_vehicles) / len(seed_vehicles)
        if seed_vehicles else 3
    )
    modernity_score = _clamp(round(100 - (avg_age * 12)), 0, 100)

    overall_score = round(
        fuel_score * 0.30 + idle_score * 0.25 + eco_score * 0.25 + modernity_score * 0.20
    )

    trend = (
        "improving" if month_over_month_change < -3
        else "declining" if month_over_month_change > 3
        else "stable"
    )

    return {
        "overallScore": _clamp(overall_score, 0, 100),
        "grade": _get_grade(overall_score),
        "components": {
            "fuelEfficiency": {"score": fuel_score, "weight": 0.30, "weightedScore": round(fuel_score * 0.30 * 10) / 10},
            "idleReduction": {"score": idle_score, "weight": 0.25, "weightedScore": round(idle_score * 0.25 * 10) / 10},
            "ecoDriving": {"score": eco_score, "weight": 0.25, "weightedScore": round(eco_score * 0.25 * 10) / 10},
            "fleetModernity": {"score": modernity_score, "weight": 0.20, "weightedScore": round(modernity_score * 0.20 * 10) / 10},
        },
        "trend": trend,
    }


def generate_recommendations(
    idle: dict,
    fuel: dict,
    ev: dict,
    drivers: list[dict],
) -> list[dict]:
    recs: list[dict] = []

    # Idle reduction recommendation
    if idle["avgIdlePercentage"] > 10:
        target_reduction = idle["avgIdlePercentage"] * 0.3  # 30% reduction
        fuel_saved = (target_reduction / 100) * idle["fuelWastedLiters"]
        co2_saved = fuel_saved * CO2_PER_LITER_DIESEL / 1000
        recs.append({
            "id": "idle-policy",
            "priority": "high",
            "category": "idle",
            "title": "Implement 5-minute idle shutoff policy",
            "description": (
                f"Fleet averages {idle['avgIdlePercentage']:.1f}% idle time. "
                f"A 5-min auto-shutoff policy could reduce idling by 30%, "
                f"saving {round(fuel_saved)} liters of fuel monthly."
            ),
            "projectedSavings": round(fuel_saved * FUEL_COST_PER_LITER * 12),
            "projectedCO2Reduction": round(co2_saved * 12 * 10) / 10,
            "difficulty": "easy",
            "timeToImpact": "1-2 weeks",
        })

    # Coach top idle offenders
    if len(idle["topOffenders"]) > 0:
        top_offender = idle["topOffenders"][0]
        recs.append({
            "id": "coach-idle-offenders",
            "priority": "high",
            "category": "idle",
            "title": f"Coach top idle offenders (starting with {top_offender['driverName']})",
            "description": (
                f"{top_offender['driverName']} has {top_offender['idleMinutes']} minutes of idle time, "
                f"wasting {top_offender['fuelWasted']}L of fuel and producing "
                f"{top_offender['co2Produced']}kg CO2 this month."
            ),
            "projectedSavings": round(top_offender["fuelWasted"] * FUEL_COST_PER_LITER * 0.5 * 12),
            "projectedCO2Reduction": round(top_offender["co2Produced"] * 0.5 * 12 / 1000 * 10) / 10,
            "difficulty": "easy",
            "timeToImpact": "2-4 weeks",
        })

    # EV transition recommendation
    if ev["totalCandidates"] > 0:
        top_candidate = ev["vehicles"][0]
        recs.append({
            "id": "ev-transition",
            "priority": "medium",
            "category": "ev",
            "title": f"Begin EV transition with {ev['totalCandidates']} ready vehicles",
            "description": (
                f"{top_candidate['vehicleName']} ({top_candidate['type']}, {top_candidate['year']}) "
                f"averages only {top_candidate['avgDailyDistance']}km/day — perfect for EV replacement. "
                f"{ev['totalCandidates']} vehicles total are EV-ready."
            ),
            "projectedSavings": ev["projectedAnnualSavings"],
            "projectedCO2Reduction": ev["projectedCO2Reduction"],
            "difficulty": "hard",
            "timeToImpact": "3-6 months",
        })

    # Eco-driving training for low-scoring drivers
    low_drivers = [d for d in drivers if d["greenScore"] < 60]
    if len(low_drivers) > 0:
        recs.append({
            "id": "eco-training",
            "priority": "medium",
            "category": "driving",
            "title": f"Eco-driving training for {len(low_drivers)} drivers",
            "description": (
                f"{len(low_drivers)} drivers score below 60 on eco-driving. "
                f"Training on smooth acceleration, anticipatory braking, and speed management "
                f"can improve fuel efficiency by 10-15%."
            ),
            "projectedSavings": round(len(low_drivers) * 1200),
            "projectedCO2Reduction": round(len(low_drivers) * 2.5 * 10) / 10,
            "difficulty": "moderate",
            "timeToImpact": "4-8 weeks",
        })

    # Route optimization
    recs.append({
        "id": "route-optimization",
        "priority": "low",
        "category": "route",
        "title": "Implement AI-powered route optimization",
        "description": (
            "Optimized routing can reduce total fleet distance by 8-12%, "
            "directly cutting fuel consumption and emissions proportionally."
        ),
        "projectedSavings": round(fuel["totalFuelConsumed"] * 0.10 * FUEL_COST_PER_LITER * 12),
        "projectedCO2Reduction": round(fuel["totalFuelConsumed"] * 0.10 * CO2_PER_LITER_DIESEL / 1000 * 12 * 10) / 10,
        "difficulty": "moderate",
        "timeToImpact": "2-3 months",
    })

    priority_order = {"high": 0, "medium": 1, "low": 2}
    recs.sort(key=lambda r: priority_order[r["priority"]])
    return recs


def calculate_monthly_trend() -> list[dict]:
    months: list[dict] = []
    now = _now()

    for i in range(2, -1, -1):
        # Month start = first day of (current month - i)
        month = now.month - i
        year = now.year
        while month <= 0:
            month += 12
            year -= 1
        month_start = now.replace(year=year, month=month, day=1, hour=0, minute=0,
                                  second=0, microsecond=0)
        # Month end = last day of that month
        if month == 12:
            next_start = month_start.replace(year=year + 1, month=1)
        else:
            next_start = month_start.replace(month=month + 1)
        month_end = next_start - timedelta(days=1)
        month_label = month_start.strftime("%b %Y")
        start_date = month_start.strftime("%Y-%m-%d")
        end_date = month_end.strftime("%Y-%m-%d")

        month_kpis = [
            k for k in seed_fleet_kpis
            if start_date <= k.date <= end_date
        ]

        total_fuel = sum(k.fuelConsumed for k in month_kpis)
        total_dist = sum(k.totalDistance for k in month_kpis)
        co2_tons = (total_fuel * CO2_PER_LITER_DIESEL) / 1000
        avg_idle = (
            sum(k.idlingPercent for k in month_kpis) / len(month_kpis)
            if month_kpis else 12
        )
        efficiency = total_dist / total_fuel if total_fuel > 0 else 3.0

        # Simulated improvement over time
        improvement_factor = 1 + (2 - i) * 0.02

        months.append({
            "month": month_label,
            "co2Tons": (round(co2_tons * 10) / 10) or (round((85 + i * 5) * 10) / 10),
            "fuelEfficiency": (round(efficiency * improvement_factor * 10) / 10)
                              or (round((2.8 + (2 - i) * 0.1) * 10) / 10),
            "idlePercent": (round((avg_idle / improvement_factor) * 10) / 10)
                           or (round((14 - (2 - i)) * 10) / 10),
            "greenScore": round(65 + (2 - i) * 4),
        })

    return months


# Public alias matching the camelCase -> snake_case convention for the
# dashboard entry point (frontend Sustainability page / mission system).
def get_green_fleet_dashboard() -> Optional[dict]:
    """Top-level green fleet dashboard. Returns None only on unexpected failure."""
    return calculate_green_dashboard()
