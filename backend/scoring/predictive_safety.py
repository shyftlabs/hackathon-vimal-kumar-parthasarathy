"""
Predictive Safety Engine — pre-shift risk scoring, driver deterioration
detection, and dangerous corridor mapping.

Pre-Shift Risk Score (0-100, higher = more dangerous today):
  Fatigue Factor:    0-30  -- rest hours, consecutive days, night driving
  Behavior Trend:    0-25  -- events per day vs 30-day average
  Recent Severity:   0-25  -- critical/high events in last 48hrs or 7 days
  Workload Factor:   0-20  -- driving hours and distance per day

Risk levels: low (0-25), elevated (26-50), high (51-75), critical (76-100)
"""

from __future__ import annotations

from datetime import timedelta
from typing import Optional

from backend.data.seed_data import (
    _now,
    _parse_dt,
    get_driver,
    seed_drivers,
    seed_safety_events,
    seed_trip_days,
)


# ---------------------------------------------------------------------------
# Pre-Shift Risk
# ---------------------------------------------------------------------------

def calculate_pre_shift_risk(driver_id: str) -> Optional[dict]:
    driver = get_driver(driver_id)
    if not driver:
        return None

    now = _now()
    seven_days_ago = now - timedelta(days=7)
    thirty_days_ago = now - timedelta(days=30)
    forty_eight_hours_ago = now - timedelta(hours=48)

    seven_cutoff_date = seven_days_ago.strftime("%Y-%m-%d")
    thirty_cutoff_date = thirty_days_ago.strftime("%Y-%m-%d")

    # Last 7 days of trip data (newest first)
    trips7 = [t for t in seed_trip_days
              if t.driverId == driver_id and t.date > seven_cutoff_date]
    trips7.sort(key=lambda t: t.date, reverse=True)

    # Last 30 days of trip data (for baseline)
    trips30 = [t for t in seed_trip_days
               if t.driverId == driver_id and t.date > thirty_cutoff_date]

    # Last 7 days of events
    events7 = [e for e in seed_safety_events
               if e.driverId == driver_id and _parse_dt(e.dateTime) > seven_days_ago]

    # Last 30 days of events (for baseline)
    events30 = [e for e in seed_safety_events
                if e.driverId == driver_id and _parse_dt(e.dateTime) > thirty_days_ago]

    # Events in last 48 hours
    events48h = [e for e in seed_safety_events
                 if e.driverId == driver_id and _parse_dt(e.dateTime) > forty_eight_hours_ago]

    factors: list[dict] = []

    # === FATIGUE FACTOR (0-30) ===
    fatigue_factor = 0

    # Average rest hours in last 7 days
    avg_rest7 = (
        sum(t.restHoursBetweenShifts for t in trips7) / len(trips7)
        if trips7 else 10
    )
    if avg_rest7 < 7:
        fatigue_factor += 15
    elif avg_rest7 < 8:
        fatigue_factor += 10
    elif avg_rest7 < 9:
        fatigue_factor += 5

    # Consecutive days worked
    consecutive_days = len(trips7)  # approximate from 7-day window
    if consecutive_days > 6:
        fatigue_factor += 10
    elif consecutive_days > 5:
        fatigue_factor += 7
    elif consecutive_days > 4:
        fatigue_factor += 3

    # Night driving hours increasing (compare first half vs second half of 7 days)
    half = len(trips7) // 2
    first_half = trips7[half:]
    second_half = trips7[:half]
    first_night_avg = (
        sum(t.nightDrivingHours for t in first_half) / len(first_half)
        if first_half else 0
    )
    second_night_avg = (
        sum(t.nightDrivingHours for t in second_half) / len(second_half)
        if second_half else 0
    )
    if second_night_avg > first_night_avg + 0.5:
        fatigue_factor += 5

    fatigue_factor = min(30, fatigue_factor)
    factors.append({
        "name": "Fatigue Factor",
        "impact": fatigue_factor,
        "description": (
            f"Avg rest: {avg_rest7:.1f}hrs, {consecutive_days} days worked in last 7, "
            f"night driving {'increasing' if second_night_avg > first_night_avg + 0.5 else 'stable'}"
        ),
    })

    # === BEHAVIOR TREND (0-25) ===
    events_per_day7 = len(events7) / len(trips7) if trips7 else 0
    events_per_day30 = len(events30) / len(trips30) if trips30 else 0
    trend_ratio = events_per_day7 / events_per_day30 if events_per_day30 > 0 else 1

    if trend_ratio > 2.0:
        behavior_trend = 25
    elif trend_ratio > 1.5:
        behavior_trend = 20
    elif trend_ratio > 1.2:
        behavior_trend = 15
    elif trend_ratio > 1.0:
        behavior_trend = 8
    else:
        behavior_trend = 0

    factors.append({
        "name": "Behavior Trend",
        "impact": behavior_trend,
        "description": (
            f"{events_per_day7:.1f} events/day (7d) vs {events_per_day30:.1f} events/day (30d avg) -- "
            f"{'worsening' if trend_ratio > 1.2 else 'improving' if trend_ratio < 0.8 else 'stable'}"
        ),
    })

    # === RECENT SEVERITY (0-25) ===
    recent_severity = 0
    has_critical_48h = any(e.severity == "critical" for e in events48h)
    has_high_48h = any(e.severity == "high" for e in events48h)
    has_critical_7d = any(e.severity == "critical" for e in events7)
    has_high_7d = any(e.severity == "high" for e in events7)

    if has_critical_48h:
        recent_severity = 25
    elif has_high_48h:
        recent_severity = 20
    elif has_critical_7d:
        recent_severity = 15
    elif has_high_7d:
        recent_severity = 10

    if has_critical_48h:
        severity_desc = "Critical event in last 48 hours"
    elif has_high_48h:
        severity_desc = "High-severity event in last 48 hours"
    elif has_critical_7d:
        severity_desc = "Critical event in last 7 days"
    elif has_high_7d:
        severity_desc = "High-severity event in last 7 days"
    else:
        severity_desc = "No high/critical events recently"

    factors.append({
        "name": "Recent Severity",
        "impact": recent_severity,
        "description": severity_desc,
    })

    # === WORKLOAD FACTOR (0-20) ===
    workload_factor = 0
    avg_driving_hours7 = (
        sum(t.drivingHours for t in trips7) / len(trips7) if trips7 else 0
    )
    avg_distance7 = (
        sum(t.totalDistance for t in trips7) / len(trips7) if trips7 else 0
    )

    if avg_driving_hours7 > 11:
        workload_factor += 12
    elif avg_driving_hours7 > 10:
        workload_factor += 8
    elif avg_driving_hours7 > 9:
        workload_factor += 4

    if avg_distance7 > 600:
        workload_factor += 8
    elif avg_distance7 > 500:
        workload_factor += 5
    elif avg_distance7 > 400:
        workload_factor += 2

    workload_factor = min(20, workload_factor)
    factors.append({
        "name": "Workload Factor",
        "impact": workload_factor,
        "description": (
            f"Avg {avg_driving_hours7:.1f}hrs/day, {avg_distance7:.0f}km/day over last 7 days"
        ),
    })

    # === TOTAL RISK SCORE ===
    risk_score = min(100, fatigue_factor + behavior_trend + recent_severity + workload_factor)
    risk_level = (
        "critical" if risk_score >= 76 else
        "high" if risk_score >= 51 else
        "elevated" if risk_score >= 26 else
        "low"
    )

    # Recommendation
    if risk_level == "critical":
        recommendation = (
            "Do not assign shift until safety review is completed. Schedule immediate "
            "driver check-in and consider mandatory rest period."
        )
    elif risk_level == "high":
        recommendation = (
            "Assign shorter route only. Require check-in at midpoint. Monitor telematics "
            "in real-time during shift."
        )
    elif risk_level == "elevated":
        recommendation = (
            "Standard shift with additional monitoring. Schedule coaching session within 48 hours."
        )
    else:
        recommendation = "Clear for standard operations. Continue routine monitoring."

    return {
        "driverId": driver_id,
        "driverName": driver.name,
        "riskScore": risk_score,
        "riskLevel": risk_level,
        "factors": factors,
        "recommendation": recommendation,
    }


def calculate_all_pre_shift_risks() -> list[dict]:
    results = [calculate_pre_shift_risk(d.id) for d in seed_drivers]
    results = [r for r in results if r is not None]
    results.sort(key=lambda r: r["riskScore"], reverse=True)
    return results


def get_fleet_risk_forecast() -> dict:
    all_risks = calculate_all_pre_shift_risks()

    high_risk_drivers = sum(
        1 for r in all_risks if r["riskLevel"] in ("high", "critical")
    )

    # Predicted events: sum of (riskScore / 100) * baseline events per driver per week
    # Baseline: 7 days of recent events / driver count
    now = _now()
    seven_days_ago = now - timedelta(days=7)
    recent_events = [e for e in seed_safety_events if _parse_dt(e.dateTime) > seven_days_ago]
    baseline_events_per_week = len(recent_events)
    # Weight by risk: higher-risk drivers contribute proportionally more
    total_risk_weight = sum(r["riskScore"] for r in all_risks)
    avg_risk = total_risk_weight / len(all_risks) if all_risks else 50
    predicted_events_this_week = round(baseline_events_per_week * (avg_risk / 50) * 1.05)

    # Aggregate top risk factors across all drivers
    factor_counts: dict[str, int] = {}
    for risk in all_risks:
        for factor in risk["factors"]:
            if factor["impact"] > 5:
                factor_counts[factor["name"]] = factor_counts.get(factor["name"], 0) + factor["impact"]
    top_risk_factors = [
        name for name, _ in sorted(factor_counts.items(), key=lambda kv: kv[1], reverse=True)[:4]
    ]

    # Fleet recommendations
    recommendations: list[str] = []
    critical_drivers = [r for r in all_risks if r["riskLevel"] == "critical"]
    high_drivers = [r for r in all_risks if r["riskLevel"] == "high"]

    if critical_drivers:
        recommendations.append(
            f"Immediately review {len(critical_drivers)} critical-risk driver(s): "
            f"{', '.join(d['driverName'] for d in critical_drivers)}"
        )
    if high_drivers:
        recommendations.append(
            f"Schedule coaching for {len(high_drivers)} high-risk driver(s) before next shift"
        )
    if "Fatigue Factor" in top_risk_factors:
        recommendations.append("Fleet-wide fatigue management: enforce minimum 10-hour rest periods")
    if "Workload Factor" in top_risk_factors:
        recommendations.append("Review route assignments to balance workload across drivers")
    if "Behavior Trend" in top_risk_factors:
        recommendations.append("Deploy additional telematics coaching alerts for trending drivers")
    if not recommendations:
        recommendations.append("Fleet risk within normal parameters. Maintain current safety programs.")

    return {
        "highRiskDrivers": high_risk_drivers,
        "predictedEventsThisWeek": predicted_events_this_week,
        "topRiskFactors": top_risk_factors,
        "recommendations": recommendations,
    }


# ---------------------------------------------------------------------------
# Driver Deterioration Detection
# ---------------------------------------------------------------------------

def detect_deteriorating() -> list[dict]:
    now = _now()
    seven_days_ago = now - timedelta(days=7)
    fourteen_days_ago = now - timedelta(days=14)

    seven_cutoff_date = seven_days_ago.strftime("%Y-%m-%d")
    fourteen_cutoff_date = fourteen_days_ago.strftime("%Y-%m-%d")

    results: list[dict] = []
    for driver in seed_drivers:
        events_last7 = [e for e in seed_safety_events
                        if e.driverId == driver.id and _parse_dt(e.dateTime) > seven_days_ago]
        events_prev7 = [e for e in seed_safety_events
                        if e.driverId == driver.id
                        and fourteen_days_ago < _parse_dt(e.dateTime) <= seven_days_ago]

        trips_last7 = [t for t in seed_trip_days
                       if t.driverId == driver.id and t.date > seven_cutoff_date]
        trips_prev7 = [t for t in seed_trip_days
                       if t.driverId == driver.id
                       and fourteen_cutoff_date < t.date <= seven_cutoff_date]

        # Normalize by days worked to get event rate
        rate_last7 = len(events_last7) / len(trips_last7) if trips_last7 else 0
        rate_prev7 = len(events_prev7) / len(trips_prev7) if trips_prev7 else 0

        if rate_prev7 > 0:
            week_over_week_change = round(((rate_last7 - rate_prev7) / rate_prev7) * 100)
        else:
            week_over_week_change = 100 if rate_last7 > 0 else 0

        if week_over_week_change > 50:
            trend_direction = "rapidly_declining"
        elif week_over_week_change > 15:
            trend_direction = "declining"
        elif week_over_week_change < -15:
            trend_direction = "improving"
        else:
            trend_direction = "stable"

        details = (
            f"{len(events_last7)} events in last 7 days ({rate_last7:.1f}/day) vs "
            f"{len(events_prev7)} events prior 7 days ({rate_prev7:.1f}/day). "
            f"{'+' if week_over_week_change > 0 else ''}{week_over_week_change}% change."
        )

        results.append({
            "driverId": driver.id,
            "driverName": driver.name,
            "trendDirection": trend_direction,
            "weekOverWeekChange": week_over_week_change,
            "details": details,
        })

    results.sort(key=lambda r: r["weekOverWeekChange"], reverse=True)
    return results


# ---------------------------------------------------------------------------
# Dangerous Corridor Detection
# ---------------------------------------------------------------------------

def get_dangerous_corridors() -> list[dict]:
    # Grid-based clustering: round lat/lng to 0.05 degree cells
    cell_size = 0.05
    cell_map: dict[str, dict] = {}

    for event in seed_safety_events:
        cell_lat = round(event.latitude / cell_size) * cell_size
        cell_lng = round(event.longitude / cell_size) * cell_size
        key = f"{cell_lat:.2f}_{cell_lng:.2f}"

        if key not in cell_map:
            cell_map[key] = {"events": [], "latSum": 0.0, "lngSum": 0.0}
        cell_map[key]["events"].append(event)
        cell_map[key]["latSum"] += event.latitude
        cell_map[key]["lngSum"] += event.longitude

    # Convert to zones, sort by event count, return top 10
    zones: list[dict] = []
    for index, (_key, cell) in enumerate(cell_map.items()):
        cell_events = cell["events"]
        avg_lat = cell["latSum"] / len(cell_events)
        avg_lng = cell["lngSum"] / len(cell_events)

        # Find top event type
        type_counts: dict[str, int] = {}
        driver_set: set[str] = set()
        for e in cell_events:
            type_counts[e.type] = type_counts.get(e.type, 0) + 1
            driver_set.add(e.driverId)
        top_type = sorted(type_counts.items(), key=lambda kv: kv[1], reverse=True)[0]

        zones.append({
            "id": f"zone_{index + 1}",
            "latitude": round(avg_lat * 10000) / 10000,
            "longitude": round(avg_lng * 10000) / 10000,
            "radius": round(cell_size * 111 / 2 * 10) / 10,  # approx km (1 degree ~ 111 km)
            "eventCount": len(cell_events),
            "topEventType": top_type[0],
            "affectedDrivers": list(driver_set),
            "description": (
                f"{len(cell_events)} events in area near ({avg_lat:.2f}, {avg_lng:.2f}). "
                f"Most common: {top_type[0].replace('_', ' ')} ({top_type[1]} occurrences). "
                f"{len(driver_set)} drivers affected."
            ),
        })

    zones.sort(key=lambda z: z["eventCount"], reverse=True)
    zones = zones[:10]

    # Re-assign stable IDs after sorting
    for i, z in enumerate(zones):
        z["id"] = f"zone_{i + 1}"

    return zones
