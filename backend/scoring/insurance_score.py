"""
Fleet Insurability Score Engine
Computes a 0-100 fleet-level score for insurance underwriting.

Components:
  Safe Driving:  35% -- event frequency, severity, trends
  Compliance:    25% -- HOS, seatbelt, speed compliance
  Maintenance:   20% -- fault codes, age, mileage
  Driver Quality: 20% -- tenure, training, risk distribution

Grade scale: A+ (95-100), A (90-94), B+ (85-89), B (75-84), C+ (70-74),
             C (60-69), D (50-59), F (<50)

Premium impact: (score - 50) * 0.3% per point above/below 50.
"""

from __future__ import annotations

from datetime import timedelta
from typing import List

from backend.data.seed_data import (
    SeedSafetyEvent,
    _now,
    _parse_dt,
    seed_drivers,
    seed_fleet_kpis,
    seed_safety_events,
    seed_trip_days,
    seed_vehicles,
)

KM_TO_MILES = 0.621371
_SEVERITY_WEIGHTS = {"low": 1, "medium": 3, "high": 7, "critical": 15}


def _clamp(val: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, val))


def _compute_severity_score(events: List[SeedSafetyEvent]) -> float:
    if len(events) == 0:
        return 100
    total_weight = sum(_SEVERITY_WEIGHTS[e.severity] for e in events)
    avg_weight = total_weight / len(events)
    return max(0, 100 - avg_weight * 10)


def _score_to_grade(score: float) -> str:
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


def calculate_insurance_score() -> dict:
    now = _now()
    thirty_days_ago = now - timedelta(days=30)
    sixty_days_ago = now - timedelta(days=60)

    # Recent data
    events30 = [e for e in seed_safety_events if _parse_dt(e.dateTime) > thirty_days_ago]
    events_prev30 = [
        e for e in seed_safety_events
        if sixty_days_ago < _parse_dt(e.dateTime) <= thirty_days_ago
    ]

    cutoff_date = thirty_days_ago.strftime("%Y-%m-%d")
    trips30 = [t for t in seed_trip_days if t.date > cutoff_date]
    kpis30 = [k for k in seed_fleet_kpis if k.date > cutoff_date]
    total_distance = sum(k.totalDistance for k in kpis30)
    total_distance_miles = total_distance * KM_TO_MILES

    # === SAFE DRIVING (35%) ===
    event_rate = (len(events30) / total_distance_miles) * 1000 if total_distance_miles > 0 else 0
    severity_score = _compute_severity_score(events30)
    # If previous period has no data, don't penalize -- treat as stable
    trend_delta = len(events30) - len(events_prev30) if len(events_prev30) > 0 else 0
    if len(events_prev30) == 0:
        trend_score = 70
    elif trend_delta <= -5:
        trend_score = 95
    elif trend_delta <= 0:
        trend_score = 80
    elif trend_delta <= 5:
        trend_score = 65
    else:
        trend_score = 40

    event_rate_score = _clamp(100 - event_rate * 4, 0, 100)  # 4 per 1000mi deduction
    safe_driving_raw = event_rate_score * 0.5 + severity_score * 0.3 + trend_score * 0.2
    safe_driving_score = _clamp(safe_driving_raw, 0, 100)

    # === COMPLIANCE (25%) ===
    driver_count = len(seed_drivers)
    seatbelt_events = len([e for e in events30 if e.type == "seatbelt"])
    speeding_events = len([e for e in events30 if e.type == "speeding"])
    avg_daily_hours = (
        sum(t.drivingHours for t in trips30) / len(trips30) if len(trips30) > 0 else 0
    )
    hos_violations = len([t for t in trips30 if t.drivingHours > 11])

    # Normalize per driver for fleet-fair scoring
    seatbelt_rate = seatbelt_events / max(driver_count, 1)
    speed_rate = speeding_events / max(driver_count, 1)
    hos_rate = hos_violations / max(driver_count, 1)
    seatbelt_score = _clamp(100 - seatbelt_rate * 25, 0, 100)
    speed_score = _clamp(100 - speed_rate * 20, 0, 100)
    hos_score = _clamp(100 - hos_rate * 15, 0, 100)
    compliance_score = _clamp(
        seatbelt_score * 0.3 + speed_score * 0.4 + hos_score * 0.3, 0, 100
    )

    # === MAINTENANCE (20%) ===
    current_year = _now().year
    avg_age = sum(current_year - v.year for v in seed_vehicles) / len(seed_vehicles)
    avg_odometer = sum(v.odometer for v in seed_vehicles) / len(seed_vehicles)
    total_faults = sum((v.faultCount or 0) for v in seed_vehicles)
    total_active_faults = sum((v.activeFaultCount or 0) for v in seed_vehicles)
    faults_per_vehicle = total_faults / max(len(seed_vehicles), 1)
    active_faults_per_vehicle = total_active_faults / max(len(seed_vehicles), 1)
    age_score = max(0, 100 - (avg_age - 1) * 12)
    mileage_score = max(0, 100 - (avg_odometer / 400000) * 50)
    fault_score = _clamp(
        100 - faults_per_vehicle * 3 - active_faults_per_vehicle * 5, 0, 100
    )
    maintenance_score = _clamp(
        age_score * 0.3 + mileage_score * 0.3 + fault_score * 0.4, 0, 100
    )

    # === DRIVER QUALITY (20%) ===
    avg_tenure = sum(d.tenureYears for d in seed_drivers) / len(seed_drivers)
    risk_dist = {
        "low": len([d for d in seed_drivers if d.riskProfile == "low"]) / len(seed_drivers),
        "moderate": len([d for d in seed_drivers if d.riskProfile == "moderate"]) / len(seed_drivers),
        "high": len([d for d in seed_drivers if d.riskProfile == "high"]) / len(seed_drivers),
        "critical": len([d for d in seed_drivers if d.riskProfile == "critical"]) / len(seed_drivers),
    }
    tenure_score = min(100, avg_tenure * 15)
    risk_score = (
        risk_dist["low"] * 100
        + risk_dist["moderate"] * 60
        + risk_dist["high"] * 30
        + risk_dist["critical"] * 10
    )
    driver_quality_score = _clamp(tenure_score * 0.4 + risk_score * 0.6, 0, 100)

    # === WEIGHTED TOTAL ===
    overall_score = round(
        safe_driving_score * 0.35
        + compliance_score * 0.25
        + maintenance_score * 0.20
        + driver_quality_score * 0.20
    )

    # Grade
    grade = _score_to_grade(overall_score)

    # Premium impact: each point above 50 saves 0.3% of benchmark premium
    benchmark_premium = len(seed_vehicles) * 14200  # $14,200/vehicle avg Class 8 commercial
    percent_change = -((overall_score - 50) * 0.3)
    # Above 50 = savings (positive); below 50 = premium increase (negative)
    estimated_annual_savings = (
        round(benchmark_premium * abs(percent_change) / 100)
        if overall_score >= 50
        else -round(benchmark_premium * abs(percent_change) / 100)
    )

    # Percentile (simulated based on score)
    percentile = min(99, max(1, round(overall_score * 1.1 - 10)))

    # Trend
    trend = "improving" if trend_delta <= -3 else "declining" if trend_delta >= 3 else "stable"

    # Recommendations
    recommendations: List[str] = []
    if speeding_events > 10:
        recommendations.append("Implement speed governor policy to reduce speeding events")
    if seatbelt_events > 5:
        recommendations.append("Enforce seatbelt compliance training program")
    if hos_violations > 5:
        recommendations.append("Review scheduling to prevent HOS violations")
    if risk_dist["critical"] > 0:
        recommendations.append("Create intervention plan for critical-risk drivers")
    if risk_dist["high"] > 0.1:
        recommendations.append("Implement targeted coaching for high-risk drivers")
    if avg_age > 4:
        recommendations.append("Consider fleet renewal for vehicles over 4 years old")
    if total_active_faults > 5:
        recommendations.append(
            f"Address {total_active_faults} active fault codes across the fleet to improve maintenance score"
        )
    if len(recommendations) == 0:
        recommendations.append("Maintain current safety programs -- fleet performing well")

    return {
        "overallScore": overall_score,
        "grade": grade,
        "components": {
            "safeDriving": {
                "score": round(safe_driving_score),
                "weight": 0.35,
                "weightedScore": round(safe_driving_score * 0.35),
                "details": {
                    "eventRate": round(event_rate * 100) / 100,
                    "totalEvents": len(events30),
                    "severityScore": round(severity_score),
                    "trendDelta": trend_delta,
                },
            },
            "compliance": {
                "score": round(compliance_score),
                "weight": 0.25,
                "weightedScore": round(compliance_score * 0.25),
                "details": {
                    "seatbeltViolations": seatbelt_events,
                    "speedingEvents": speeding_events,
                    "hosViolations": hos_violations,
                    "avgDailyHours": round(avg_daily_hours * 10) / 10,
                },
            },
            "maintenance": {
                "score": round(maintenance_score),
                "weight": 0.20,
                "weightedScore": round(maintenance_score * 0.20),
                "details": {
                    "avgVehicleAge": round(avg_age * 10) / 10,
                    "avgOdometer": round(avg_odometer),
                    "totalFaults": total_faults,
                    "activeFaults": total_active_faults,
                    "faultsPerVehicle": round(faults_per_vehicle * 10) / 10,
                    "fleetSize": len(seed_vehicles),
                },
            },
            "driverQuality": {
                "score": round(driver_quality_score),
                "weight": 0.20,
                "weightedScore": round(driver_quality_score * 0.20),
                "details": {
                    "avgTenure": round(avg_tenure * 10) / 10,
                    "lowRiskPercent": f"{round(risk_dist['low'] * 100)}%",
                    "highRiskPercent": f"{round((risk_dist['high'] + risk_dist['critical']) * 100)}%",
                    "totalDrivers": len(seed_drivers),
                },
            },
        },
        "premiumImpact": {
            "percentChange": round(percent_change * 10) / 10,
            "estimatedAnnualSavings": estimated_annual_savings,
            "benchmarkPremium": benchmark_premium,
        },
        "percentile": percentile,
        "trend": trend,
        "recommendations": recommendations,
    }
