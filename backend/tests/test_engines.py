"""Scoring-engine contracts: shapes, invariants, edge cases, no exceptions."""

import pytest

from backend.data.seed_data import seed_drivers
from backend.scoring import (
    alert_triage,
    driver_risk,
    gamification,
    green_score,
    insurance_score,
    predictive_safety,
    roi_engine,
    wellness_predictor,
    what_if,
)

ALL_IDS = [d.id for d in seed_drivers]


def test_driver_risk_shape():
    r = driver_risk.calculate_driver_risk("d3")
    assert r["driverName"] == "Marcus Rivera"
    assert 0 <= r["riskScore"] <= 100
    assert r["tier"] in ("low", "moderate", "high", "critical")
    assert set(r["components"]) == {"eventFrequency", "severity", "pattern", "trend"}
    assert isinstance(r["topEventTypes"], list)


def test_driver_risk_invalid_is_none():
    assert driver_risk.calculate_driver_risk("nope") is None


def test_all_driver_risks_sorted_desc():
    rs = driver_risk.calculate_all_driver_risks()
    assert len(rs) == 30
    assert all(rs[i]["riskScore"] >= rs[i + 1]["riskScore"] for i in range(len(rs) - 1))


def test_insurance_score_contract():
    s = insurance_score.calculate_insurance_score()
    assert 0 <= s["overallScore"] <= 100
    assert s["grade"]
    assert "estimatedAnnualSavings" in s["premiumImpact"]
    assert set(s["components"]) == {"safeDriving", "compliance", "maintenance", "driverQuality"}


def test_roi_calibrated_to_proven_range():
    """ROI calibrated to the proven pitch figure (~$521.6K)."""
    roi = roi_engine.calculate_fleet_roi()
    assert 450_000 <= roi["totalAnnualSavings"] <= 600_000
    assert roi["roiPercent"] > 0 and roi["paybackMonths"] > 0


def test_before_after_metrics():
    ba = roi_engine.calculate_before_after()
    assert len(ba["metrics"]) == 6
    assert all({"name", "before", "after", "dollarImpact"} <= set(m) for m in ba["metrics"])


def test_wellness_fleet_summary():
    fw = wellness_predictor.get_fleet_wellness_summary()
    assert fw["totalDrivers"] == 30
    assert fw["highBurnoutRisk"] >= 1
    assert fw["totalRetentionCostAtRisk"] > 0


def test_predictive_engines():
    assert len(predictive_safety.calculate_all_pre_shift_risks()) == 30
    fc = predictive_safety.get_fleet_risk_forecast()
    assert "predictedEventsThisWeek" in fc
    assert isinstance(predictive_safety.get_dangerous_corridors(), list)


def test_alert_briefing():
    b = alert_triage.get_daily_briefing()
    assert {"criticalCount", "highCount", "topAlerts", "fleetRiskSummary"} <= set(b)


def test_green_dashboard():
    g = green_score.get_green_fleet_dashboard()
    assert g is not None
    assert g["evReadiness"]["projectedCO2Reduction"] > 0


def test_gamification_contract():
    state = gamification.get_gamification_state("d1")
    assert state["level"] >= 1
    assert isinstance(state["badges"], list)
    assert gamification.get_gamification_state("nope") is None


def test_what_if_projects_improvement():
    res = what_if.simulate_what_if(what_if.get_default_scenarios())
    assert len(res) == 5
    assert all(r["projectedScore"] >= r["currentScore"] for r in res)
    assert all(r["annualSavings"] >= 0 for r in res)


@pytest.mark.parametrize("driver_id", ALL_IDS)
def test_every_driver_through_every_engine(driver_id):
    """No engine raises for any real driver."""
    driver_risk.calculate_driver_risk(driver_id)
    wellness_predictor.predict_wellness(driver_id)
    predictive_safety.calculate_pre_shift_risk(driver_id)
    gamification.get_gamification_state(driver_id)
