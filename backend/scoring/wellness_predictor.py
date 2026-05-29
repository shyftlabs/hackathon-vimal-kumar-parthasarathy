"""
Driver Wellness / Burnout Predictor — detects burnout signals from telematics.

Signals:
  1. Shift Irregularity   -- std dev of driving hours (schedule variance)
  2. Consecutive Long Days -- days with >10hrs driving in a row
  3. Rest Compression     -- shrinking rest between shifts
  4. Event Escalation     -- increasing event count week-over-week
  5. Night Driving Creep  -- increasing night hours over the window
  6. Excessive Daily Hours -- share of days exceeding 11hrs driving

Retention cost: $35K * burnout_probability
"""

from __future__ import annotations

import math
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

REPLACEMENT_COST = 35000  # Average cost to replace a commercial driver


def predict_wellness(driver_id: str) -> Optional[dict]:
    driver = get_driver(driver_id)
    if not driver:
        return None

    now = _now()
    thirty_days_ago = now - timedelta(days=30)
    cutoff_date = thirty_days_ago.strftime("%Y-%m-%d")

    # trip dates are date-only strings -> compare/sort lexicographically (= chronologically)
    trips30 = sorted(
        (t for t in seed_trip_days
         if t.driverId == driver_id and t.date > cutoff_date),
        key=lambda t: t.date,
    )

    events30 = [e for e in seed_safety_events
                if e.driverId == driver_id and _parse_dt(e.dateTime) > thirty_days_ago]

    signals: list[dict] = []

    # 1. SHIFT IRREGULARITY (simulated via driving hours variance)
    hours = [t.drivingHours for t in trips30]
    avg_hours = sum(hours) / len(hours) if hours else 0
    std_dev = (
        math.sqrt(sum((h - avg_hours) ** 2 for h in hours) / (len(hours) - 1))
        if len(hours) > 1 else 0
    )
    irregularity = std_dev / max(avg_hours, 1)
    signals.append({
        "name": "Shift Irregularity",
        "severity": "critical" if irregularity > 0.35 else "warning" if irregularity > 0.2 else "normal",
        "value": round(irregularity * 100) / 100,
        "threshold": 0.35,
        "description": f"Schedule variance ratio: {irregularity * 100:.0f}% (threshold: 35%)",
    })

    # 2. CONSECUTIVE LONG DAYS (>10 hrs)
    max_consecutive = 0
    current_streak = 0
    for trip in trips30:
        if trip.drivingHours > 10:
            current_streak += 1
            max_consecutive = max(max_consecutive, current_streak)
        else:
            current_streak = 0
    signals.append({
        "name": "Consecutive Long Days",
        "severity": "critical" if max_consecutive >= 5 else "warning" if max_consecutive >= 3 else "normal",
        "value": max_consecutive,
        "threshold": 5,
        "description": f"{max_consecutive} consecutive days with >10hrs driving (threshold: 5)",
    })

    # 3. REST COMPRESSION
    rest_hours = [t.restHoursBetweenShifts for t in trips30]
    avg_rest = sum(rest_hours) / len(rest_hours) if rest_hours else 10
    recent_rest = rest_hours[-7:]
    recent_avg_rest = sum(recent_rest) / len(recent_rest) if recent_rest else 10
    rest_trend = avg_rest - recent_avg_rest  # Positive = rest shrinking
    signals.append({
        "name": "Rest Compression",
        "severity": "critical" if recent_avg_rest < 7 else "warning" if recent_avg_rest < 9 else "normal",
        "value": round(recent_avg_rest * 10) / 10,
        "threshold": 7,
        "description": (
            f"Recent avg rest: {recent_avg_rest:.1f}hrs (min: 7hrs). "
            f"Trend: {'compressing' if rest_trend > 1 else 'stable'}"
        ),
    })

    # 4. HARSH EVENT ESCALATION
    week1_events = len([e for e in events30
                        if _parse_dt(e.dateTime) > now - timedelta(days=7)])
    week2_events = len([e for e in events30
                        if now - timedelta(days=14) < _parse_dt(e.dateTime) <= now - timedelta(days=7)])
    escalation = (week1_events - week2_events) / week2_events if week2_events > 0 else 0
    signals.append({
        "name": "Event Escalation",
        "severity": "critical" if escalation > 0.5 else "warning" if escalation > 0.2 else "normal",
        "value": round(escalation * 100),
        "threshold": 50,
        "description": (
            f"Week-over-week event change: {'+' if escalation > 0 else ''}"
            f"{escalation * 100:.0f}% (threshold: 50%)"
        ),
    })

    # 5. NIGHT DRIVING CREEP
    night_hours = [t.nightDrivingHours for t in trips30]
    half = len(night_hours) // 2
    early_night = night_hours[:half]
    late_night = night_hours[half:]
    early_avg = sum(early_night) / len(early_night) if early_night else 0
    late_avg = sum(late_night) / len(late_night) if late_night else 0
    night_creep = late_avg - early_avg
    signals.append({
        "name": "Night Driving Creep",
        "severity": "critical" if night_creep > 1.5 else "warning" if night_creep > 0.5 else "normal",
        "value": round(night_creep * 10) / 10,
        "threshold": 1.5,
        "description": (
            f"Night driving increase: {'+' if night_creep > 0 else ''}"
            f"{night_creep:.1f}hrs/day (threshold: 1.5hrs)"
        ),
    })

    # 6. EXCESSIVE DAILY HOURS
    overworked_days = len([t for t in trips30 if t.drivingHours > 11])
    overworked_percent = overworked_days / len(trips30) if trips30 else 0
    signals.append({
        "name": "Excessive Daily Hours",
        "severity": "critical" if overworked_percent > 0.4 else "warning" if overworked_percent > 0.15 else "normal",
        "value": round(overworked_percent * 100),
        "threshold": 40,
        "description": f"{overworked_percent * 100:.0f}% of days exceed 11hrs driving (threshold: 40%)",
    })

    # === BURNOUT PROBABILITY ===
    critical_count = len([s for s in signals if s["severity"] == "critical"])
    warning_count = len([s for s in signals if s["severity"] == "warning"])
    burnout_probability = min(0.95, critical_count * 0.22 + warning_count * 0.12 + 0.03)

    burnout_risk = "high" if burnout_probability > 0.5 else "moderate" if burnout_probability > 0.25 else "low"
    retention_cost = round(REPLACEMENT_COST * burnout_probability)
    overall_wellness_score = round((1 - burnout_probability) * 100)

    # Days since last rest day (day off)
    today = _now()
    days_since_rest = 0
    for i in range(30):
        check_date = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        worked = any(t.date == check_date for t in trips30)
        if not worked and i > 0:
            break
        if worked:
            days_since_rest += 1

    # Recommendations
    recommendations: list[str] = []
    if burnout_risk == "high":
        recommendations.append("URGENT: Schedule immediate check-in with driver")
        recommendations.append("Review and reduce weekly driving hours")
    if max_consecutive >= 5:
        recommendations.append("Mandate 34-hour restart period")
    if recent_avg_rest < 8:
        recommendations.append("Adjust scheduling to ensure minimum 10hr rest periods")
    if night_creep > 1:
        recommendations.append("Reduce night driving assignments")
    if escalation > 0.3:
        recommendations.append("Review recent driving footage for fatigue indicators")
    if days_since_rest > 6:
        recommendations.append(f"Driver has worked {days_since_rest} consecutive days -- schedule day off")
    if not recommendations:
        recommendations.append("Wellness indicators normal -- continue monitoring")

    return {
        "driverId": driver_id,
        "driverName": driver.name,
        "burnoutProbability": round(burnout_probability * 100) / 100,
        "burnoutRisk": burnout_risk,
        "retentionCost": retention_cost,
        "signals": signals,
        "overallWellnessScore": overall_wellness_score,
        "recommendations": recommendations,
        "daysSinceLastRest": days_since_rest,
        "avgRestHours": round(avg_rest * 10) / 10,
        "consecutiveLongDays": max_consecutive,
    }


def predict_all_wellness() -> list[dict]:
    """Predict wellness for all drivers, sorted by burnout probability (highest first)."""
    results = [predict_wellness(d.id) for d in seed_drivers]
    results = [r for r in results if r is not None]
    results.sort(key=lambda r: r["burnoutProbability"], reverse=True)
    return results


def get_fleet_wellness_summary() -> dict:
    """Summary: fleet-wide wellness stats."""
    all_results = predict_all_wellness()
    high_risk = [r for r in all_results if r["burnoutRisk"] == "high"]
    moderate_risk = [r for r in all_results if r["burnoutRisk"] == "moderate"]
    # Only sum retention cost for at-risk drivers (high + moderate), not the entire fleet
    at_risk_drivers = [r for r in all_results if r["burnoutRisk"] in ("high", "moderate")]
    total_retention_cost = sum(r["retentionCost"] for r in at_risk_drivers)

    return {
        "totalDrivers": len(all_results),
        "highBurnoutRisk": len(high_risk),
        "moderateBurnoutRisk": len(moderate_risk),
        "lowBurnoutRisk": len(all_results) - len(high_risk) - len(moderate_risk),
        "totalRetentionCostAtRisk": total_retention_cost,
        "avgWellnessScore": (
            round(sum(r["overallWellnessScore"] for r in all_results) / len(all_results))
            if all_results else 0
        ),
        "driversAtRisk": [
            {
                "id": r["driverId"],
                "name": r["driverName"],
                "burnoutProbability": r["burnoutProbability"],
                "retentionCost": r["retentionCost"],
                "topSignal": next(
                    (s["name"] for s in r["signals"] if s["severity"] == "critical"),
                    "Multiple warnings",
                ),
            }
            for r in high_risk
        ],
    }
