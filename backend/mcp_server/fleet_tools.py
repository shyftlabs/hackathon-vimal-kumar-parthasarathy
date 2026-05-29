"""
Fleet intelligence MCP server (FastMCP).

Exposes the scoring engines as MCP tools for the Continuum "Tasha" agent.
Tool NAMES are camelCase and chosen to match the frontend's ComponentRenderer
(frontend/src/components/assistant/ComponentRenderer.tsx) so each tool result
renders as its rich card unchanged (e.g. getFleetOverview -> KPI grid,
getDriverRiskScore -> RiskDriverMini, getFleetInsuranceScore -> ScoreCard).

Run standalone:  python -m backend.mcp_server.fleet_tools   (StreamableHTTP on :8765/mcp)
"""

from __future__ import annotations

from typing import Optional

from mcp.server.fastmcp import FastMCP

from backend.data.seed_data import (
    asdict_safe,
    get_driver,
    get_fleet_summary,
    seed_drivers,
    seed_safety_events,
    seed_vehicles,
)
from backend.scoring.alert_triage import get_daily_briefing
from backend.scoring.driver_risk import calculate_all_driver_risks, calculate_driver_risk
from backend.scoring.green_score import get_green_fleet_dashboard
from backend.scoring.insurance_score import calculate_insurance_score
from backend.scoring.predictive_safety import (
    calculate_all_pre_shift_risks,
    calculate_pre_shift_risk,
    detect_deteriorating,
    get_fleet_risk_forecast,
)
from backend.scoring.roi_engine import calculate_fleet_roi
from backend.scoring.wellness_predictor import (
    get_fleet_wellness_summary,
    predict_wellness,
)
from backend.missions.store import VALID_TYPES, meta_for, new_mission_id

mcp = FastMCP("fleet")

PORT = 8765


# ─── helpers ──────────────────────────────────────────────────

def _resolve_driver_id(driver_id: str = "", driver_name: str = "") -> Optional[str]:
    if driver_id:
        return driver_id if get_driver(driver_id) else None
    if driver_name:
        q = driver_name.lower()
        match = next((d for d in seed_drivers if q in d.name.lower()), None)
        return match.id if match else None
    return None


# ─── Fleet-wide tools ─────────────────────────────────────────

@mcp.tool(name="getFleetOverview",
          description="Get a comprehensive fleet overview: vehicle/driver counts, total safety events, "
                      "events per 1000 miles, average safety score, risk distribution, and top risk drivers. "
                      "Use when the user asks how the fleet is doing or wants a summary/KPIs.")
def fleet_overview() -> dict:
    return get_fleet_summary()


@mcp.tool(name="getFleetInsuranceScore",
          description="Get the Fleet Insurability Score (0-100, graded A+ to F) with its four weighted "
                      "components (safe driving, compliance, maintenance, driver quality), percentile, trend, "
                      "and estimated annual premium savings. Use for insurance, premiums, underwriting, score.")
def fleet_insurance_score() -> dict:
    return calculate_insurance_score()


@mcp.tool(name="getDriverRiskScore",
          description="Get driver risk scores (0-100, higher = riskier) with tier, annualized cost, and top "
                      "event types. Pass driverId or driverName for one driver; omit both for all drivers "
                      "ranked highest-risk first. Use for 'riskiest driver', risk analysis, who needs attention.")
def driver_risk_score(driver_id: str = "", driver_name: str = "") -> dict:
    rid = _resolve_driver_id(driver_id, driver_name)
    if rid:
        r = calculate_driver_risk(rid)
        return r or {"error": "Driver not found"}
    drivers = calculate_all_driver_risks()
    high = [d for d in drivers if d["tier"] in ("high", "critical")]
    return {"drivers": drivers, "totalDrivers": len(drivers), "highRiskCount": len(high)}


@mcp.tool(name="getDriverWellness",
          description="Driver wellness / burnout assessment from telematics fatigue signals. Pass driverId or "
                      "driverName for one driver (score, burnout risk, active warning signals); omit for a "
                      "fleet wellness summary (avg score, burnout counts, retention cost at risk). Use for "
                      "burnout, fatigue, tired drivers, retention, wellbeing.")
def driver_wellness(driver_id: str = "", driver_name: str = "") -> dict:
    rid = _resolve_driver_id(driver_id, driver_name)
    if rid:
        r = predict_wellness(rid)
        return r or {"error": "Driver not found"}
    return get_fleet_wellness_summary()


@mcp.tool(name="getSafetyEvents",
          description="Query recent safety events (harsh braking, speeding, distracted driving, etc.) with "
                      "severity, type, timestamp, and location. Optionally filter by driverId/driverName and "
                      "limit the count. Use for incident history, 'what happened', event details.")
def safety_events(driver_id: str = "", driver_name: str = "", limit: int = 25) -> dict:
    rid = _resolve_driver_id(driver_id, driver_name)
    events = seed_safety_events
    if rid:
        events = [e for e in events if e.driverId == rid]
    events = events[: max(1, min(limit, 200))]
    return {
        "count": len(events),
        "driverId": rid,
        "events": [asdict_safe(e) for e in events],
    }


@mcp.tool(name="getFinancialImpact",
          description="Quantify the fleet's total annual financial impact and savings: insurance premium "
                      "reduction, accident-prevention, fuel, retention, and productivity, with ROI %% and "
                      "payback months. Use for financial impact, savings potential, dollars, ROI, business case.")
def financial_impact() -> dict:
    return calculate_fleet_roi()


@mcp.tool(name="getFleetForecast",
          description="7-day fleet safety forecast: predicted events this week, number of high-risk drivers, "
                      "top risk factors, and recommendations. Use for weekly outlook, what's coming, forecast.")
def fleet_forecast() -> dict:
    return get_fleet_risk_forecast()


@mcp.tool(name="getAlertBriefing",
          description="Morning alert briefing with intelligently triaged alerts: critical/high counts, the top "
                      "alerts by urgency, and a fleet risk summary. Use for daily briefing, alerts, "
                      "what needs my attention today, command center.")
def alert_briefing() -> dict:
    return get_daily_briefing()


@mcp.tool(name="getPreShiftRisk",
          description="Predictive pre-shift risk assessment (0-100, higher = safer) from rest, recent hours, "
                      "weather, route, and recent events. Pass driverId/driverName for one driver; omit for all "
                      "drivers with high-risk count. Use for pre-shift, morning roster, today's risk, can they drive.")
def pre_shift_risk(driver_id: str = "", driver_name: str = "") -> dict:
    rid = _resolve_driver_id(driver_id, driver_name)
    if rid:
        r = calculate_pre_shift_risk(rid)
        return r or {"error": "Driver not found"}
    drivers = calculate_all_pre_shift_risks()
    high = [d for d in drivers if d.get("riskLevel") in ("high", "critical")]
    return {"drivers": drivers, "totalDrivers": len(drivers), "highRiskCount": len(high)}


@mcp.tool(name="getCoachingRecommendations",
          description="Prioritized coaching/intervention recommendations with expected score improvement and "
                      "dollar savings. Pass driverId/driverName for a targeted plan; omit for fleet-level "
                      "recommendations. Use for coaching, training, interventions, 'how do we improve?'.")
def coaching_recommendations(driver_id: str = "", driver_name: str = "") -> dict:
    rid = _resolve_driver_id(driver_id, driver_name)
    if rid:
        return _driver_coaching(rid)
    return _fleet_coaching()


@mcp.tool(name="getFleetComparison",
          description="Compare the fleet against industry benchmarks (small/medium/large/top-10%) on safety "
                      "score, event rate, turnover, and insurance cost per vehicle, plus strengths and "
                      "opportunities. Use for benchmarks, 'how do we compare', percentile ranking.")
def fleet_comparison() -> dict:
    return _fleet_comparison()


@mcp.tool(name="getGreenFleetMetrics",
          description="Sustainability / green fleet metrics: carbon footprint, fuel efficiency, idle waste, "
                      "EV transition readiness (incl. projected CO2 reduction), eco-driving scores, and "
                      "recommendations. Use for sustainability, emissions, CO2, fuel, ESG, EV readiness.")
def green_fleet_metrics() -> dict:
    return get_green_fleet_dashboard()


@mcp.tool(name="getFleetTrends",
          description="Detect drivers whose risk is deteriorating (worsening week-over-week) for early "
                      "intervention. Use for trends, who's getting worse, deteriorating drivers.")
def fleet_trends() -> dict:
    trends = detect_deteriorating()
    worsening = [t for t in trends if t.get("trendDirection") in ("declining", "rapidly_declining", "worsening")]
    return {"trends": trends, "worseningCount": len(worsening)}


@mcp.tool(name="deployMission",
          description="Deploy an autonomous background mission agent for deep, multi-step fleet analysis. "
                      "mission_type MUST be one of: 'coaching_sweep' (build coaching plans for riskiest drivers), "
                      "'wellness_check' (fleet burnout scan), 'safety_investigation' (deep-dive one driver — pass "
                      "driver_name), 'insurance_optimization' (find premium savings), 'preshift_sweep' (scan today's "
                      "roster). Call this ONLY after the operator explicitly confirms ('yes', 'do it', 'go ahead'). "
                      "Returns immediately with a running mission; results stream in afterward.")
def deploy_mission(mission_type: str, driver_name: str = "") -> dict:
    if mission_type not in VALID_TYPES:
        return {"error": f"Unknown mission type '{mission_type}'. Valid: {', '.join(sorted(VALID_TYPES))}"}
    meta = meta_for(mission_type)
    return {
        "missionId": new_mission_id(),
        "type": mission_type,
        "displayName": meta["displayName"],
        "agentName": meta["agentName"],
        "description": meta["description"],
        "status": "running",
        "driverName": driver_name or None,
    }


@mcp.tool(name="callDispatch",
          description="Place a REAL outbound phone call to the human dispatcher ON BEHALF OF the driver. "
                      "Use this whenever a driver asks you to call / contact / notify / reach / let dispatch know "
                      "(e.g. stuck, breakdown, accident, running late, load or route problem). Pass a concise "
                      "'intent' describing exactly what to tell dispatch, including the situation and location. "
                      "Do NOT merely say you'll notify dispatch — you MUST call this tool to actually place the call.")
def call_dispatch(intent: str = "") -> dict:
    return {"action": "dispatch_call", "intent": (intent or "a load update").strip(), "status": "placing"}


# ─── coaching / comparison logic (ported from the original tools) ──

_BENCHMARKS = {
    "small": {"label": "Small Fleet (1-25 trucks)", "avgScore": 62, "eventRate": 3.2, "turnoverRate": 73, "premiumPerVehicle": 15800},
    "medium": {"label": "Medium Fleet (26-100 trucks)", "avgScore": 68, "eventRate": 2.5, "turnoverRate": 82, "premiumPerVehicle": 13500},
    "large": {"label": "Large Fleet (100+ trucks)", "avgScore": 74, "eventRate": 1.8, "turnoverRate": 94, "premiumPerVehicle": 11200},
    "topPerformer": {"label": "Top 10% Fleets", "avgScore": 89, "eventRate": 0.8, "turnoverRate": 35, "premiumPerVehicle": 8500},
}


def _action(priority, action, score_imp, savings, timeline, category):
    return {"priority": priority, "action": action, "expectedScoreImprovement": score_imp,
            "expectedCostSavings": savings, "timeline": timeline, "category": category}


def _to_recs(actions: list[dict], driver_name: str = "") -> list[dict]:
    """Map coaching actions -> ComponentRenderer 'recommendations' shape."""
    recs = []
    for a in actions:
        impact_bits = []
        if a["expectedScoreImprovement"]:
            impact_bits.append(f"+{a['expectedScoreImprovement']} pts")
        if a["expectedCostSavings"]:
            impact_bits.append(f"${a['expectedCostSavings']:,} saved")
        recs.append({"title": a["action"], "action": a["action"],
                     "expectedImpact": " · ".join(impact_bits) or a["timeline"],
                     "driver": driver_name})
    return recs


def _driver_coaching(driver_id: str) -> dict:
    risk = calculate_driver_risk(driver_id)
    wellness = predict_wellness(driver_id)
    if not risk or not wellness:
        return {"error": "Driver not found"}
    actions: list[dict] = []
    if risk["tier"] in ("critical", "high"):
        actions.append(_action(1, "Immediate ride-along with safety supervisor", 15,
                                round(risk["annualizedCost"] * 0.35), "1 week", "risk"))
    if risk["components"]["eventFrequency"]["eventsPerThousandMiles"] > 5:
        actions.append(_action(2, "Enroll in Smith System defensive driving course", 10,
                                round(risk["annualizedCost"] * 0.25), "2 weeks", "risk"))
    if risk["topEventTypes"] and risk["topEventTypes"][0]["type"] == "speeding":
        actions.append(_action(2, "Implement speed governor at 68 mph", 8, 3500, "Immediate", "risk"))
    if wellness["burnoutRisk"] == "high":
        actions.append(_action(1, "Mandatory wellness check-in + schedule review", 0,
                                wellness["retentionCost"], "This week", "wellness"))
        actions.append(_action(2, "Reduce weekly hours to max 55 and ensure 10hr rest minimum", 5,
                                round(wellness["retentionCost"] * 0.5), "2 weeks", "wellness"))
    if wellness.get("consecutiveLongDays", 0) >= 5:
        actions.append(_action(1, "Schedule 34-hour restart within next 48 hours", 3, 5000, "Immediate", "wellness"))
    if not actions:
        actions.append(_action(3, "Continue monitoring -- no interventions needed", 0, 0, "Ongoing", "risk"))
    actions.sort(key=lambda a: a["priority"])
    return {
        "driverId": driver_id, "driverName": risk["driverName"],
        "currentRiskScore": risk["riskScore"], "currentRiskTier": risk["tier"],
        "burnoutRisk": wellness["burnoutRisk"],
        "totalPotentialSavings": sum(a["expectedCostSavings"] for a in actions),
        "actions": actions, "recommendations": _to_recs(actions, risk["driverName"]),
    }


def _fleet_coaching() -> dict:
    insurance = calculate_insurance_score()
    all_risks = calculate_all_driver_risks()
    high = [r for r in all_risks if r["tier"] in ("high", "critical")]
    actions: list[dict] = []
    if high:
        names = ", ".join(d["driverName"] for d in high)
        actions.append(_action(1, f"Create intervention plans for {len(high)} high-risk drivers ({names})", 5,
                                sum(round(d["annualizedCost"] * 0.35) for d in high), "2 weeks", "risk"))
    if insurance["components"]["compliance"]["score"] < 70:
        actions.append(_action(2, "Fleet-wide compliance refresh training (speeding, seatbelt, HOS)", 8,
                                round(insurance["premiumImpact"]["estimatedAnnualSavings"] * 0.15), "1 month", "score"))
    actions.append(_action(2, "Implement monthly driver scorecards with peer benchmarking", 3, 8000, "1 month", "score"))
    actions.append(_action(3, "Share FleetShield AI report with insurance broker for premium renegotiation", 0,
                            insurance["premiumImpact"]["estimatedAnnualSavings"], "Next renewal", "score"))
    actions.sort(key=lambda a: a["priority"])
    return {
        "currentFleetScore": insurance["overallScore"], "currentGrade": insurance["grade"],
        "highRiskDrivers": len(high),
        "totalPotentialSavings": sum(a["expectedCostSavings"] for a in actions),
        "actions": actions, "recommendations": _to_recs(actions),
    }


def _fleet_comparison() -> dict:
    insurance = calculate_insurance_score()
    fleet = get_fleet_summary()
    our = {
        "label": "Your Fleet", "size": len(seed_vehicles), "drivers": len(seed_drivers),
        "score": insurance["overallScore"], "grade": insurance["grade"],
        "eventRate": fleet["eventsPerThousandMiles"], "estimatedTurnoverRate": 15,
        "premiumPerVehicle": round(insurance["premiumImpact"]["benchmarkPremium"] / len(seed_vehicles)),
    }
    results = []
    for bench in _BENCHMARKS.values():
        results.append({"benchmark": bench["label"], "comparison": {
            "score": {"yours": our["score"], "benchmark": bench["avgScore"], "delta": our["score"] - bench["avgScore"], "better": our["score"] > bench["avgScore"]},
            "eventRate": {"yours": round(our["eventRate"] * 100) / 100, "benchmark": bench["eventRate"], "delta": round((our["eventRate"] - bench["eventRate"]) * 100) / 100, "better": our["eventRate"] < bench["eventRate"]},
            "turnoverRate": {"yours": our["estimatedTurnoverRate"], "benchmark": bench["turnoverRate"], "delta": our["estimatedTurnoverRate"] - bench["turnoverRate"], "better": our["estimatedTurnoverRate"] < bench["turnoverRate"]},
            "premiumPerVehicle": {"yours": our["premiumPerVehicle"], "benchmark": bench["premiumPerVehicle"], "delta": our["premiumPerVehicle"] - bench["premiumPerVehicle"], "better": our["premiumPerVehicle"] < bench["premiumPerVehicle"]},
        }})
    medium = _BENCHMARKS["medium"]
    strengths, opportunities = [], []
    if our["score"] > medium["avgScore"]:
        strengths.append(f"Fleet score {our['score']} exceeds medium fleet average ({medium['avgScore']})")
    else:
        opportunities.append(f"Fleet score {our['score']} trails medium fleet average ({medium['avgScore']})")
    if our["estimatedTurnoverRate"] < medium["turnoverRate"]:
        strengths.append(f"Turnover rate {our['estimatedTurnoverRate']}% is well below industry {medium['turnoverRate']}%")
    gap = _BENCHMARKS["topPerformer"]["avgScore"] - our["score"]
    if gap > 0:
        opportunities.append(f"{gap} points away from top 10% performance (score {_BENCHMARKS['topPerformer']['avgScore']})")
    return {"yourFleet": our, "benchmarks": results, "strengths": strengths,
            "opportunities": opportunities, "percentile": insurance["percentile"]}


if __name__ == "__main__":
    import uvicorn

    app = mcp.streamable_http_app()
    print(f"Fleet MCP server running at http://localhost:{PORT}/mcp")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
