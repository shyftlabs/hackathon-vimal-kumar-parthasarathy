"""
Driver Risk Score Engine — per-driver risk scoring (0-100, higher = riskier).

Components:
  Event Frequency: 40%  -- events per 1000 miles
  Severity:        25%  -- weighted severity of events
  Pattern:         20%  -- recurring event types, time-of-day patterns
  Trend:           15%  -- improving or worsening over time

Risk tiers: low (0-25), moderate (26-50), high (51-75), critical (76-100)
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

KM_TO_MILES = 0.621371
_SEVERITY_WEIGHTS = {"low": 1, "medium": 3, "high": 7, "critical": 15}
_COST_MAP = {"low": 2000, "moderate": 8000, "high": 25000, "critical": 65000}


def calculate_driver_risk(driver_id: str) -> Optional[dict]:
    driver = get_driver(driver_id)
    if not driver:
        return None

    now = _now()
    thirty = now - timedelta(days=30)
    sixty = now - timedelta(days=60)

    events30 = [e for e in seed_safety_events
                if e.driverId == driver_id and _parse_dt(e.dateTime) > thirty]
    events_prev30 = [e for e in seed_safety_events
                     if e.driverId == driver_id and sixty < _parse_dt(e.dateTime) <= thirty]
    cutoff_date = thirty.strftime("%Y-%m-%d")
    trips30 = [t for t in seed_trip_days
               if t.driverId == driver_id and t.date > cutoff_date]

    total_distance_km = sum(t.totalDistance for t in trips30)
    total_distance_miles = total_distance_km * KM_TO_MILES

    # === EVENT FREQUENCY (40%) ===
    events_per_k_miles = (len(events30) / total_distance_miles) * 1000 if total_distance_miles > 0 else 0
    frequency_score = min(100, events_per_k_miles * 10)

    # === SEVERITY (25%) ===
    total_severity = sum(_SEVERITY_WEIGHTS[e.severity] for e in events30)
    avg_severity = total_severity / len(events30) if events30 else 0
    severity_score = min(100, avg_severity * 12)

    # === PATTERN (20%) ===
    type_counts: dict[str, int] = {}
    for e in events30:
        type_counts[e.type] = type_counts.get(e.type, 0) + 1
    sorted_types = sorted(type_counts.items(), key=lambda kv: kv[1], reverse=True)
    top_type = sorted_types[0] if sorted_types else None
    concentration = (top_type[1] / len(events30)) if (top_type and events30) else 0
    diversity_penalty = 20 if (len(sorted_types) <= 2 and len(events30) > 5) else 0
    pattern_score = min(100, concentration * 60 + diversity_penalty)

    top_patterns: list[str] = []
    if concentration > 0.4 and top_type:
        top_patterns.append(f"Habitual {top_type[0].replace('_', ' ')}")
    night_trips = [t for t in trips30 if t.nightDrivingHours > 2]
    if len(night_trips) > len(trips30) * 0.3:
        top_patterns.append("Frequent night driving")
    long_days = [t for t in trips30 if t.drivingHours > 10]
    if len(long_days) > len(trips30) * 0.4:
        top_patterns.append("Excessive driving hours")
    if not top_patterns:
        top_patterns.append("No significant patterns")

    # === TREND (15%) ===
    delta = len(events30) - len(events_prev30)
    trend_score = 100 if delta >= 10 else 75 if delta >= 5 else 40 if delta >= 0 else 20 if delta >= -5 else 0
    direction = "worsening" if delta > 3 else "improving" if delta < -3 else "stable"

    # === TOTAL ===
    risk_score = round(
        frequency_score * 0.40 + severity_score * 0.25 + pattern_score * 0.20 + trend_score * 0.15
    )
    tier = "low" if risk_score <= 25 else "moderate" if risk_score <= 50 else "high" if risk_score <= 75 else "critical"
    annualized_cost = _COST_MAP[tier]

    recommendations: list[str] = []
    if frequency_score > 60:
        recommendations.append("Enroll in advanced defensive driving course")
    if severity_score > 60:
        recommendations.append("Review driving footage for high-severity events")
    if pattern_score > 50 and top_type:
        recommendations.append(f"Targeted coaching on {top_type[0].replace('_', ' ')}")
    if trend_score > 60:
        recommendations.append("Schedule driver wellness check-in -- performance declining")
    if len(long_days) > 5:
        recommendations.append("Review route assignments to reduce excessive hours")
    if not recommendations:
        recommendations.append("Continue current performance -- no interventions needed")

    return {
        "driverId": driver_id,
        "driverName": driver.name,
        "riskScore": risk_score,
        "tier": tier,
        "components": {
            "eventFrequency": {"score": round(frequency_score), "weight": 0.40,
                               "eventsPerThousandMiles": round(events_per_k_miles * 100) / 100},
            "severity": {"score": round(severity_score), "weight": 0.25,
                         "weightedAvg": round(avg_severity * 100) / 100},
            "pattern": {"score": round(pattern_score), "weight": 0.20, "topPatterns": top_patterns},
            "trend": {"score": round(trend_score), "weight": 0.15, "direction": direction, "delta": delta},
        },
        "topEventTypes": [{"type": t, "count": c} for t, c in sorted_types[:5]],
        "annualizedCost": annualized_cost,
        "recommendations": recommendations,
    }


def calculate_all_driver_risks() -> list[dict]:
    """Risk for all drivers, highest risk first."""
    results = [calculate_driver_risk(d.id) for d in seed_drivers]
    results = [r for r in results if r is not None]
    results.sort(key=lambda r: r["riskScore"], reverse=True)
    return results
