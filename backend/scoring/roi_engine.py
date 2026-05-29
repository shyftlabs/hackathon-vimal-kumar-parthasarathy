"""
Fleet ROI Calculation Engine.

Quantifies fleet safety investment value in dollars.
Compares first 45 days vs last 45 days of 90-day seed data.

Ported faithfully from existing-solution/backend/src/scoring/roi-engine.ts.
All savings-category math, rates, and constants mirror the TypeScript source.
"""

from __future__ import annotations

import math
from datetime import timedelta

from backend.data.seed_data import (
    _now,
    _parse_dt,
    seed_drivers,
    seed_fleet_kpis,
    seed_safety_events,
    seed_trip_days,
    seed_vehicles,
)
from backend.scoring.insurance_score import calculate_insurance_score
from backend.scoring.wellness_predictor import predict_all_wellness

# ─── Constants (mirror roi-engine.ts) ─────────────────────────
AVG_ACCIDENT_COST = 91000
FLEET_INSURANCE_PER_VEHICLE = 12000
FUEL_COST_PER_LITER = 1.65
IDLE_FUEL_BURN_PER_HOUR = 3.8
PLATFORM_COST_PER_VEHICLE_MONTHLY = 45
TELEMATICS_COST_PER_VEHICLE_MONTHLY = 35
REPLACEMENT_COST_PER_DRIVER = 35000
INTERVENTION_SUCCESS_RATE = 0.65
PRODUCTIVITY_GAIN_PER_REDUCED_EVENT = 150


def _get_periods() -> dict:
    """First/last 45-day windows of the trailing 90-day dataset (UTC)."""
    now = _now()
    ninety_days_ago = now - timedelta(days=90)
    forty_five_days_ago = now - timedelta(days=45)
    return {
        "beforeStart": ninety_days_ago,
        "beforeEnd": forty_five_days_ago,
        "afterStart": forty_five_days_ago,
        "afterEnd": now,
    }


def _date_str(d) -> str:
    """ISO date portion (YYYY-MM-DD); matches TS toISOString().split('T')[0]."""
    return d.strftime("%Y-%m-%d")


def calculate_fleet_roi() -> dict:
    """Annualized fleet ROI across all savings categories."""
    vehicle_count = len(seed_vehicles)
    p = _get_periods()
    before_start, before_end = p["beforeStart"], p["beforeEnd"]
    after_start, after_end = p["afterStart"], p["afterEnd"]

    events_before = [
        e for e in seed_safety_events
        if before_start <= _parse_dt(e.dateTime) < before_end
    ]
    events_after = [
        e for e in seed_safety_events
        if after_start <= _parse_dt(e.dateTime) < after_end
    ]

    high_severity_before = sum(
        1 for e in events_before if e.severity in ("high", "critical")
    )
    high_severity_after = sum(
        1 for e in events_after if e.severity in ("high", "critical")
    )

    trips_before = [
        t for t in seed_trip_days
        if before_start <= _parse_dt(t.date) < before_end
    ]
    trips_after = [
        t for t in seed_trip_days
        if after_start <= _parse_dt(t.date) < after_end
    ]

    avg_idling_before = (
        sum(t.idlingMinutes for t in trips_before) / len(trips_before)
        if trips_before else 0
    )
    avg_idling_after = (
        sum(t.idlingMinutes for t in trips_after) / len(trips_after)
        if trips_after else 0
    )

    # Safety net: if "before" period has no data but "after" does,
    # estimate "before" as 12% worse than "after" (conservative estimate)
    use_estimated_baseline = len(events_before) == 0 and len(events_after) > 0
    effective_events_before = (
        math.ceil(len(events_after) * 1.12)
        if use_estimated_baseline else len(events_before)
    )
    effective_high_before = (
        math.ceil(high_severity_after * 1.15)
        if use_estimated_baseline else high_severity_before
    )
    effective_avg_idling_before = (
        avg_idling_after * 1.10
        if use_estimated_baseline else avg_idling_before
    )

    # 1. Insurance Premium Savings
    insurance_score = calculate_insurance_score()
    baseline_premium = vehicle_count * FLEET_INSURANCE_PER_VEHICLE
    premium_reduction_percent = max(0, (insurance_score["overallScore"] - 60) * 0.4)
    insurance_premium_savings = round(baseline_premium * (premium_reduction_percent / 100))

    # 2. Accident Prevention Savings
    # Industry data: ~1 in 200 high-severity telematics events -> real accident
    high_severity_reduction = max(0, effective_high_before - high_severity_after)
    annualized_reduction = high_severity_reduction * (365 / 45)
    # Cap: max ~8% of fleet per year
    estimated_prevented_accidents = min(annualized_reduction / 200, vehicle_count * 0.12)
    accident_prevention_savings = round(estimated_prevented_accidents * AVG_ACCIDENT_COST)

    # 3. Fuel Savings
    idling_reduction_minutes = max(0, effective_avg_idling_before - avg_idling_after)
    idling_reduction_hours_per_day = idling_reduction_minutes / 60
    working_days_per_year = 260
    annual_fuel_liters_saved = (
        idling_reduction_hours_per_day
        * IDLE_FUEL_BURN_PER_HOUR
        * len(seed_drivers)
        * working_days_per_year
    )
    fuel_savings = round(annual_fuel_liters_saved * FUEL_COST_PER_LITER)

    # 4. Retention Savings
    retention_data = calculate_retention_savings()
    retention_savings = retention_data["projectedSavings"]

    # 5. Productivity Gains (fewer events = less downtime for reviews/coaching/admin)
    total_event_reduction = max(0, effective_events_before - len(events_after))
    annualized_event_reduction = total_event_reduction * (365 / 45)
    productivity_gains = min(
        round(annualized_event_reduction * PRODUCTIVITY_GAIN_PER_REDUCED_EVENT),
        vehicle_count * 3000,  # Cap: max $3K per vehicle per year
    )

    # Investment Cost
    investment_cost = (
        vehicle_count
        * (PLATFORM_COST_PER_VEHICLE_MONTHLY + TELEMATICS_COST_PER_VEHICLE_MONTHLY)
    ) * 12

    total_annual_savings = (
        insurance_premium_savings
        + accident_prevention_savings
        + fuel_savings
        + retention_savings
        + productivity_gains
    )
    net_savings = total_annual_savings - investment_cost
    roi_percent = round((net_savings / investment_cost) * 100) if investment_cost > 0 else 0
    payback_months = (
        round((investment_cost / total_annual_savings) * 12 * 10) / 10
        if total_annual_savings > 0 else 0
    )

    year1 = total_annual_savings - investment_cost
    year2 = total_annual_savings * 1.08 - investment_cost
    year3 = total_annual_savings * 1.08 * 1.08 - investment_cost
    projected_three_year_value = round(year1 + year2 + year3)

    return {
        "totalAnnualSavings": total_annual_savings,
        "insurancePremiumSavings": insurance_premium_savings,
        "accidentPreventionSavings": accident_prevention_savings,
        "fuelSavings": fuel_savings,
        "retentionSavings": retention_savings,
        "productivityGains": productivity_gains,
        "investmentCost": investment_cost,
        "roiPercent": roi_percent,
        "paybackMonths": payback_months,
        "projectedThreeYearValue": projected_three_year_value,
    }


def calculate_before_after() -> dict:
    """Before vs after metric comparison with dollar impact per metric."""
    p = _get_periods()
    before_start, before_end = p["beforeStart"], p["beforeEnd"]
    after_start, after_end = p["afterStart"], p["afterEnd"]

    events_before = [
        e for e in seed_safety_events
        if before_start <= _parse_dt(e.dateTime) < before_end
    ]
    events_after = [
        e for e in seed_safety_events
        if after_start <= _parse_dt(e.dateTime) < after_end
    ]

    trips_before = [
        t for t in seed_trip_days
        if before_start <= _parse_dt(t.date) < before_end
    ]
    trips_after = [
        t for t in seed_trip_days
        if after_start <= _parse_dt(t.date) < after_end
    ]

    kpis_before = [
        k for k in seed_fleet_kpis
        if before_start <= _parse_dt(k.date) < before_end
    ]
    kpis_after = [
        k for k in seed_fleet_kpis
        if after_start <= _parse_dt(k.date) < after_end
    ]

    high_before = sum(1 for e in events_before if e.severity in ("high", "critical"))
    high_after = sum(1 for e in events_after if e.severity in ("high", "critical"))
    avg_idle_before = (
        round(sum(t.idlingMinutes for t in trips_before) / len(trips_before) * 10) / 10
        if trips_before else 0
    )
    avg_idle_after = (
        round(sum(t.idlingMinutes for t in trips_after) / len(trips_after) * 10) / 10
        if trips_after else 0
    )
    avg_score_before = (
        round(sum(k.avgSafetyScore for k in kpis_before) / len(kpis_before) * 10) / 10
        if kpis_before else 0
    )
    avg_score_after = (
        round(sum(k.avgSafetyScore for k in kpis_after) / len(kpis_after) * 10) / 10
        if kpis_after else 0
    )
    hos_before = sum(1 for t in trips_before if t.drivingHours > 11)
    hos_after = sum(1 for t in trips_after if t.drivingHours > 11)
    avg_hours_before = (
        round(sum(t.drivingHours for t in trips_before) / len(trips_before) * 10) / 10
        if trips_before else 0
    )
    avg_hours_after = (
        round(sum(t.drivingHours for t in trips_after) / len(trips_after) * 10) / 10
        if trips_after else 0
    )

    # Safety net: if before period has no data, estimate baseline 10-12% worse.
    use_estimate = len(events_before) == 0 and len(events_after) > 0
    est_events_before = (
        math.ceil(len(events_after) * 1.12) if use_estimate else len(events_before)
    )
    est_high_before = math.ceil(high_after * 1.15) if use_estimate else high_before
    est_idle_before = (
        round(avg_idle_after * 1.10 * 10) / 10 if use_estimate else avg_idle_before
    )
    est_score_before = (
        round((avg_score_after - 5) * 10) / 10 if use_estimate else avg_score_before
    )
    est_hos_before = (
        max(hos_before, math.floor(hos_after * 1.05)) if use_estimate else hos_before
    )
    est_hours_before = (
        round((avg_hours_after * 1.03) * 10) / 10 if use_estimate else avg_hours_before
    )

    def metric(name: str, before: float, after: float, cost_per_unit: float) -> dict:
        change = round((after - before) * 10) / 10
        change_percent = round((change / before) * 1000) / 10 if before != 0 else 0
        dollar_impact = round(abs(change) * cost_per_unit)
        return {
            "name": name,
            "before": before,
            "after": after,
            "change": change,
            "changePercent": change_percent,
            "dollarImpact": dollar_impact,
        }

    return {
        "periods": [
            {
                "label": "Before (Days 46-90)",
                "startDate": _date_str(before_start),
                "endDate": _date_str(before_end),
            },
            {
                "label": "After (Days 1-45)",
                "startDate": _date_str(after_start),
                "endDate": _date_str(after_end),
            },
        ],
        "metrics": [
            metric("Total Safety Events", est_events_before, len(events_after), 450),
            metric("High/Critical Events", est_high_before, high_after, 1820),
            metric("Avg Safety Score", est_score_before, avg_score_after, 850),
            metric("Avg Daily Idling (min)", est_idle_before, avg_idle_after, 95),
            metric("Avg Daily Driving Hours", est_hours_before, avg_hours_after, 180),
            metric("HOS Violations", est_hos_before, hos_after, 2500),
        ],
    }


def calculate_retention_savings() -> dict:
    """Projected driver-retention savings from wellness interventions."""
    all_wellness = predict_all_wellness()
    at_risk = [w for w in all_wellness if w["burnoutRisk"] in ("high", "moderate")]

    details = [
        {
            "driverId": w["driverId"],
            "driverName": w["driverName"],
            "burnoutRisk": w["burnoutRisk"],
            "retentionCost": w["retentionCost"],
        }
        for w in at_risk
    ]

    total_retention_cost_at_risk = sum(d["retentionCost"] for d in details)
    projected_savings = round(total_retention_cost_at_risk * INTERVENTION_SUCCESS_RATE)

    return {
        "driversAtRisk": len(at_risk),
        "avgReplacementCost": REPLACEMENT_COST_PER_DRIVER,
        "totalRetentionCostAtRisk": total_retention_cost_at_risk,
        "interventionSuccessRate": INTERVENTION_SUCCESS_RATE,
        "projectedSavings": projected_savings,
        "details": details,
    }
