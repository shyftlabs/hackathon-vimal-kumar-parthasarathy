"""
Mission runner — executes an autonomous mission as an async generator that
yields SSE-ready events (mission_progress / mission_finding / mission_complete).

Steps gather data deterministically from the ported scoring engines (fast,
reliable for a live demo); the executive summary is written by a Continuum LLM
call (graceful deterministic fallback if no key). Completed coaching/wellness/
safety missions auto-sync action items to the affected drivers' portals.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncGenerator

from backend.missions import store
from backend.scoring.alert_triage import get_daily_briefing
from backend.scoring.driver_risk import calculate_all_driver_risks, calculate_driver_risk
from backend.scoring.insurance_score import calculate_insurance_score
from backend.scoring.predictive_safety import (
    calculate_all_pre_shift_risks,
    detect_deteriorating,
    get_fleet_risk_forecast,
)
from backend.scoring.roi_engine import calculate_fleet_roi
from backend.scoring.wellness_predictor import (
    get_fleet_wellness_summary,
    predict_all_wellness,
    predict_wellness,
)
from backend.data.seed_data import seed_drivers, seed_safety_events, _now, _parse_dt

try:
    from orchestrator import get_logger
    logger = get_logger(__name__)
except Exception:  # pragma: no cover
    import logging
    logger = logging.getLogger(__name__)

_STEP_DELAY = 0.45  # seconds between steps, so the operator can watch the agent work


def _progress(mid, mtype, phase, step, total, msg) -> dict:
    return {"type": "mission_progress", "missionId": mid, "missionType": mtype,
            "phase": phase, "step": step, "totalSteps": total, "message": msg}


def _finding(mid, category, severity, title, detail, data=None) -> dict:
    return {"type": "mission_finding", "missionId": mid, "category": category,
            "severity": severity, "title": title, "detail": detail, "data": data or {}}


def _events30(driver_id: str) -> list:
    cutoff = _now().timestamp() - 30 * 86400
    return [e for e in seed_safety_events if e.driverId == driver_id and _parse_dt(e.dateTime).timestamp() > cutoff]


# ─── Public entry point ───────────────────────────────────────

async def run_mission(mission_id: str, mission_type: str, params: dict | None = None) -> AsyncGenerator[dict, None]:
    params = params or {}
    if store.get(mission_id) is None:
        store.register(mission_id, mission_type)
    raw = store._missions.get(mission_id)  # live dict to mutate
    meta = store.meta_for(mission_type)
    start = time.time()

    yield _progress(mission_id, mission_type, "starting", 0, 1, f"Initializing {meta['displayName']}...")
    await asyncio.sleep(_STEP_DELAY)

    runners = {
        "coaching_sweep": _coaching_sweep,
        "wellness_check": _wellness_check,
        "safety_investigation": _safety_investigation,
        "insurance_optimization": _insurance_optimization,
        "preshift_sweep": _preshift_sweep,
    }
    fn = runners.get(mission_type)
    recommendations: list[str] = []
    data: dict = {}
    try:
        if not fn:
            raise ValueError(f"Unknown mission type: {mission_type}")
        async for ev in fn(mission_id, params):
            if ev.get("_kind") == "result":
                recommendations = ev.get("recommendations", [])
                data = ev.get("data", {})
                continue
            if ev["type"] == "mission_finding":
                if raw is not None:
                    raw["findings"].append({k: v for k, v in ev.items() if k != "type"})
            elif ev["type"] == "mission_progress" and raw is not None:
                raw["progress"] = {k: v for k, v in ev.items() if k != "type"}
            yield ev
    except Exception as e:  # noqa: BLE001
        logger.error(f"Mission {mission_type} failed: {e}")
        if raw is not None:
            raw["status"] = "failed"
        yield {"type": "mission_complete", "missionId": mission_id, "missionType": mission_type,
               "status": "failed", "displayName": meta["displayName"],
               "summary": f"Mission failed: {e}", "findings": raw["findings"] if raw else [],
               "recommendations": [], "data": {}, "duration": round(time.time() - start, 1),
               "completedAt": _now().isoformat()}
        return

    findings = raw["findings"] if raw else []
    yield _progress(mission_id, mission_type, "summarizing", 99, 100, "Writing executive summary...")
    summary = await _generate_summary(mission_type, findings, meta["displayName"])
    duration = round(time.time() - start, 1)

    if raw is not None:
        raw.update(status="complete", summary=summary, recommendations=recommendations,
                   data=data, duration=duration, completedAt=_now().isoformat())

    # Sync coaching/wellness/safety findings to the affected drivers' portals.
    try:
        _sync_to_drivers(mission_type, mission_id, findings)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"driver sync skipped: {e}")

    yield {"type": "mission_complete", "missionId": mission_id, "missionType": mission_type,
           "status": "complete", "displayName": meta["displayName"], "summary": summary,
           "findings": findings, "recommendations": recommendations, "data": data,
           "duration": duration, "completedAt": _now().isoformat()}


# ─── Coaching Sweep ───────────────────────────────────────────

async def _coaching_sweep(mid, params) -> AsyncGenerator[dict, None]:
    top_n = int(params.get("topN", 5))
    all_risks = calculate_all_driver_risks()
    top = all_risks[:top_n]
    total_steps = top_n + 3
    total_cost = sum(d["annualizedCost"] for d in top)
    avg_risk = round(sum(d["riskScore"] for d in all_risks) / len(all_risks)) if all_risks else 0

    yield _progress(mid, "coaching_sweep", "running", 1, total_steps, f"Scanning fleet-wide risk for all {len(all_risks)} drivers...")
    yield _finding(mid, "fleet_overview", "info",
                   f"Fleet Risk Overview — {top_n} highest-risk drivers identified",
                   f"Scanned all {len(all_risks)} drivers. The top {top_n} account for ${total_cost:,}/year in risk cost. Fleet average risk score: {avg_risk}/100.",
                   {"totalDrivers": len(all_risks), "topN": top_n, "totalAnnualCostAtRisk": total_cost, "fleetAvgRiskScore": avg_risk})
    await asyncio.sleep(_STEP_DELAY)

    driver_plans = []
    for i, d in enumerate(top):
        yield _progress(mid, "coaching_sweep", "running", i + 2, total_steps, f"Building coaching plan for {d['driverName']} ({i+1}/{top_n})...")
        wellness = predict_wellness(d["driverId"])
        actions = []
        for evt in d["topEventTypes"][:3]:
            actions.append(f"Targeted coaching on {evt['type'].replace('_',' ')} ({evt['count']} incidents in 30 days)")
        if wellness and wellness["burnoutRisk"] != "low":
            actions.append(f"Wellness intervention: {wellness['burnoutRisk']} burnout risk")
        savings = round(d["annualizedCost"] * 0.3)
        plan = {"driverId": d["driverId"], "driverName": d["driverName"], "riskScore": d["riskScore"],
                "tier": d["tier"], "annualizedCost": d["annualizedCost"],
                "topIssues": [{"type": e["type"].replace("_", " "), "count": e["count"]} for e in d["topEventTypes"][:3]],
                "wellnessScore": wellness["overallWellnessScore"] if wellness else None,
                "burnoutRisk": wellness["burnoutRisk"] if wellness else None,
                "coachingActions": actions,
                "expectedImprovement": f"{min(15, round(d['riskScore']*0.2))} point risk reduction in 60 days",
                "estimatedSavings": f"${savings:,}/year"}
        driver_plans.append(plan)
        sev = "critical" if d["tier"] == "critical" else "warning" if d["tier"] == "high" else "info"
        yield _finding(mid, "driver_coaching_plan", sev,
                       f"{d['driverName']} — {d['tier'].upper()} risk ({d['riskScore']}/100) — ${d['annualizedCost']:,}/yr",
                       f"{len(_events30(d['driverId']))} safety events in 30 days. Top issues: " +
                       ", ".join(f"{e['type'].replace('_',' ')} ({e['count']})" for e in d["topEventTypes"][:3]) +
                       f". Coaching plan: {len(actions)} actions. Expected: {plan['expectedImprovement']}. Potential savings: {plan['estimatedSavings']}.",
                       plan)
        await asyncio.sleep(_STEP_DELAY)

    yield _progress(mid, "coaching_sweep", "running", top_n + 2, total_steps, "Cross-referencing deteriorating trends...")
    trends = detect_deteriorating()
    worsening = [t for t in trends if t.get("trendDirection") in ("declining", "rapidly_declining", "worsening")]
    if worsening:
        yield _finding(mid, "trend_alert", "warning", f"{len(worsening)} drivers with worsening trends detected",
                       ". ".join(f"{t['driverName']}: {t['trendDirection']}" for t in worsening[:5]),
                       {"worseningDrivers": [t["driverName"] for t in worsening]})
    await asyncio.sleep(_STEP_DELAY)

    recommendations = [f"{i+1}. {p['driverName']} (risk {p['riskScore']}) — {p['coachingActions'][0] if p['coachingActions'] else 'monitor'}"
                       for i, p in enumerate(sorted(driver_plans, key=lambda p: p["riskScore"], reverse=True))]
    yield {"_kind": "result", "recommendations": recommendations,
           "data": {"driversAnalyzed": len(top), "totalFleetDrivers": len(all_risks),
                    "totalAnnualCostAtRisk": total_cost, "potentialSavings": round(total_cost * 0.3),
                    "driverPlans": driver_plans}}


# ─── Wellness Check ───────────────────────────────────────────

async def _wellness_check(mid, params) -> AsyncGenerator[dict, None]:
    summary = get_fleet_wellness_summary()
    all_w = predict_all_wellness()
    high = [w for w in all_w if w["burnoutRisk"] == "high"]
    moderate = [w for w in all_w if w["burnoutRisk"] == "moderate"]
    total_ret = sum(w["retentionCost"] for w in all_w)

    yield _progress(mid, "wellness_check", "running", 1, 4, "Pulling fleet wellness overview...")
    sev = "critical" if len(high) > 3 else "warning" if high else "info"
    yield _finding(mid, "fleet_wellness_overview", sev,
                   f"Fleet Wellness Overview — {len(high)} critical, {len(moderate)} moderate burnout risk",
                   f"{len(all_w)} drivers scanned. Avg wellness score: {summary['avgWellnessScore']}/100. Total retention cost at risk: ${total_ret:,}. {len(high)} need immediate intervention.",
                   {"totalDrivers": len(all_w), "highRisk": len(high), "moderateRisk": len(moderate),
                    "avgWellnessScore": summary["avgWellnessScore"], "totalRetentionCost": total_ret})
    await asyncio.sleep(_STEP_DELAY)

    yield _progress(mid, "wellness_check", "running", 2, 4, f"Analyzing {len(high)} high-risk drivers...")
    for w in high:
        signals = [s for s in w.get("signals", []) if s.get("severity") != "normal"]
        yield _finding(mid, "burnout_critical", "critical",
                       f"{w['driverName']} — HIGH burnout risk ({round(w['burnoutProbability']*100)}% probability)",
                       f"Wellness score: {w['overallWellnessScore']}/100. {len(signals)} active warning signals. Retention cost at risk: ${w['retentionCost']:,}. Avg rest: {w['avgRestHours']:.1f}hrs.",
                       {"driverId": w["driverId"], "driverName": w["driverName"], "wellnessScore": w["overallWellnessScore"],
                        "burnoutProbability": w["burnoutProbability"], "retentionCost": w["retentionCost"],
                        "signals": signals, "urgency": "Within 48 hours"})
    await asyncio.sleep(_STEP_DELAY)

    yield _progress(mid, "wellness_check", "running", 3, 4, f"Reviewing {len(moderate)} moderate-risk drivers...")
    for w in moderate:
        yield _finding(mid, "burnout_moderate", "warning",
                       f"{w['driverName']} — MODERATE burnout risk ({round(w['burnoutProbability']*100)}%)",
                       f"Wellness: {w['overallWellnessScore']}/100. Retention cost: ${w['retentionCost']:,}. Recommended: 1-on-1 check-in within 7 days.",
                       {"driverId": w["driverId"], "driverName": w["driverName"], "retentionCost": w["retentionCost"], "urgency": "Within 7 days"})
    await asyncio.sleep(_STEP_DELAY)

    schedule = [f"URGENT (48hrs): {w['driverName']} — mandatory rest day + manager call" for w in high] + \
               [f"MONITOR (7 days): {w['driverName']} — schedule wellness check-in" for w in moderate]
    yield {"_kind": "result", "recommendations": schedule,
           "data": {"totalDrivers": len(all_w), "highBurnoutRisk": len(high), "moderateBurnoutRisk": len(moderate),
                    "totalRetentionCost": total_ret, "avgWellnessScore": summary["avgWellnessScore"]}}


# ─── Safety Investigation ─────────────────────────────────────

async def _safety_investigation(mid, params) -> AsyncGenerator[dict, None]:
    driver_id = params.get("driverId")
    if not driver_id and params.get("driverName"):
        q = params["driverName"].lower()
        match = next((d for d in seed_drivers if q in d.name.lower()), None)
        driver_id = match.id if match else None
    if not driver_id:
        ranked = calculate_all_driver_risks()
        driver_id = ranked[0]["driverId"] if ranked else None
    risk = calculate_driver_risk(driver_id) if driver_id else None
    if not risk:
        raise ValueError("No driver found to investigate")

    yield _progress(mid, "safety_investigation", "running", 1, 4, "Pulling complete risk profile...")
    last30 = _events30(driver_id)
    sev = "critical" if risk["tier"] == "critical" else "warning" if risk["tier"] == "high" else "info"
    yield _finding(mid, "risk_profile", sev,
                   f"{risk['driverName']} — Risk Profile: {risk['riskScore']}/100 ({risk['tier'].upper()})",
                   f"Annualized cost: ${risk['annualizedCost']:,}. {len(last30)} events in last 30 days. Trend: {risk['components']['trend']['direction']}.",
                   {"driverId": driver_id, "driverName": risk["driverName"], "riskScore": risk["riskScore"],
                    "tier": risk["tier"], "annualizedCost": risk["annualizedCost"], "components": risk["components"]})
    await asyncio.sleep(_STEP_DELAY)

    yield _progress(mid, "safety_investigation", "running", 2, 4, "Analyzing safety event patterns...")
    by_type: dict[str, int] = {}
    by_hour: dict[int, int] = {}
    for e in last30:
        by_type[e.type] = by_type.get(e.type, 0) + 1
        h = _parse_dt(e.dateTime).hour
        by_hour[h] = by_hour.get(h, 0) + 1
    peak = max(by_hour.items(), key=lambda kv: kv[1]) if by_hour else None
    yield _finding(mid, "event_patterns", "info", f"Event Pattern Analysis — {len(last30)} events in 30 days",
                   "By type: " + ", ".join(f"{t.replace('_',' ')} ({c})" for t, c in sorted(by_type.items(), key=lambda kv: kv[1], reverse=True)) +
                   (f". Peak incident hour: {peak[0]}:00 ({peak[1]} events)." if peak else ""),
                   {"eventsByType": by_type, "peakHour": peak[0] if peak else None})
    await asyncio.sleep(_STEP_DELAY)

    yield _progress(mid, "safety_investigation", "running", 3, 4, "Checking wellness & fatigue correlation...")
    wellness = predict_wellness(driver_id)
    root_causes = []
    if wellness and wellness["burnoutRisk"] != "low":
        root_causes.append(f"Driver fatigue/burnout ({wellness['burnoutRisk']} risk) likely contributing")
        yield _finding(mid, "wellness_correlation", "critical" if wellness["burnoutRisk"] == "high" else "warning",
                       f"Wellness Assessment: {wellness['overallWellnessScore']}/100 — {wellness['burnoutRisk']} burnout risk",
                       f"Burnout probability: {round(wellness['burnoutProbability']*100)}%. Avg rest: {wellness['avgRestHours']:.1f}hrs. Fatigue may be a root cause of elevated events.",
                       {"wellnessScore": wellness["overallWellnessScore"], "burnoutRisk": wellness["burnoutRisk"]})
    if risk["components"]["trend"]["direction"] == "worsening":
        root_causes.append("Worsening 30-day trend — behavior deteriorating, suggesting an unaddressed root cause")
    top_type = max(by_type.items(), key=lambda kv: kv[1]) if by_type else None
    if top_type and top_type[1] > len(last30) * 0.4:
        root_causes.append(f"{top_type[0].replace('_',' ')} dominant ({top_type[1]}/{len(last30)}) — needs targeted intervention")
    if not root_causes:
        root_causes.append("Multiple contributing factors — no single dominant root cause")
    yield _finding(mid, "root_cause", "warning", f"Root Cause Analysis — {len(root_causes)} factors identified",
                   ". ".join(root_causes), {"rootCauses": root_causes})
    await asyncio.sleep(_STEP_DELAY)

    action_plan = [f"IMMEDIATE: {risk['recommendations'][0] if risk['recommendations'] else 'Schedule safety review'}",
                   f"WEEK 1: Targeted coaching on {top_type[0].replace('_',' ') if top_type else 'top event type'}",
                   "WEEK 2: Follow-up ride-along assessment",
                   f"ONGOING: Monitor via Predictive Safety — flag if risk exceeds {risk['riskScore']}"]
    yield {"_kind": "result", "recommendations": action_plan,
           "data": {"driverId": driver_id, "driverName": risk["driverName"], "riskScore": risk["riskScore"], "rootCauses": root_causes}}


# ─── Insurance Optimization ───────────────────────────────────

async def _insurance_optimization(mid, params) -> AsyncGenerator[dict, None]:
    score = calculate_insurance_score()
    yield _progress(mid, "insurance_optimization", "running", 1, 4, "Analyzing insurance score components...")
    sev = "critical" if score["overallScore"] < 60 else "warning" if score["overallScore"] < 75 else "info"
    yield _finding(mid, "score_overview", sev,
                   f"Fleet Insurance Score: {score['overallScore']}/100 ({score['grade']}) — {score['trend']}",
                   f"Percentile: {score['percentile']}th. Estimated annual savings at current score: ${score['premiumImpact']['estimatedAnnualSavings']:,}.",
                   {"overallScore": score["overallScore"], "grade": score["grade"], "premiumImpact": score["premiumImpact"], "components": score["components"]})
    await asyncio.sleep(_STEP_DELAY)

    yield _progress(mid, "insurance_optimization", "running", 2, 4, "Identifying weakest components and quick wins...")
    comps = sorted(score["components"].items(), key=lambda kv: kv[1]["score"])
    for name, comp in comps:
        c_sev = "critical" if comp["score"] < 60 else "warning" if comp["score"] < 75 else "info"
        premium = round((100 - comp["score"]) * comp["weight"] * 0.5 * 200)
        yield _finding(mid, "component_analysis", c_sev,
                       f"{name}: {comp['score']}/100 (weight {round(comp['weight']*100)}%)",
                       (f"Below target — improving to 80 could save ~${premium:,}/year." if comp["score"] < 70 else "At or above target — maintain."),
                       {"component": name, "score": comp["score"], "weight": comp["weight"]})
    await asyncio.sleep(_STEP_DELAY)

    yield _progress(mid, "insurance_optimization", "running", 3, 4, "Calculating ROI and top offenders...")
    roi = calculate_fleet_roi()
    yield _finding(mid, "roi_analysis", "info", f"ROI Analysis — ${round(roi['totalAnnualSavings']):,}/year total savings",
                   f"Insurance: ${round(roi['insurancePremiumSavings']):,}. Accident prevention: ${round(roi['accidentPreventionSavings']):,}. Retention: ${round(roi['retentionSavings']):,}. ROI: {round(roi['roiPercent'])}%. Payback: {roi['paybackMonths']} months.",
                   {k: v for k, v in roi.items()})
    top_off = calculate_all_driver_risks()[:3]
    for d in top_off:
        yield _finding(mid, "top_offender", "critical" if d["tier"] == "critical" else "warning",
                       f"Score drag: {d['driverName']} — {d['riskScore']}/100 risk, ${d['annualizedCost']:,}/yr",
                       "Coaching this driver alone could lift fleet score 2-4 points.",
                       {"driverId": d["driverId"], "driverName": d["driverName"], "riskScore": d["riskScore"]})
    await asyncio.sleep(_STEP_DELAY)

    quick_wins = [f"Improve {n} from {c['score']} to 75+" for n, c in comps if c["score"] < 70] + \
                 [f"Coach {d['driverName']} — ~${round(d['annualizedCost']*0.3):,}/yr potential savings" for d in top_off] + \
                 ["Present this report to your underwriter at next renewal for preferred-rate consideration"]
    yield {"_kind": "result", "recommendations": quick_wins,
           "data": {"overallScore": score["overallScore"], "grade": score["grade"],
                    "totalSavings": round(roi["totalAnnualSavings"]), "roiPercent": round(roi["roiPercent"])}}


# ─── Pre-Shift Sweep ──────────────────────────────────────────

async def _preshift_sweep(mid, params) -> AsyncGenerator[dict, None]:
    all_risks = calculate_all_pre_shift_risks()
    critical = [r for r in all_risks if r.get("riskLevel") == "critical"]
    high = [r for r in all_risks if r.get("riskLevel") == "high"]
    elevated = [r for r in all_risks if r.get("riskLevel") == "elevated"]

    yield _progress(mid, "preshift_sweep", "running", 1, 3, "Calculating pre-shift risk for all drivers...")
    yield _finding(mid, "preshift_overview", "critical" if critical else "warning" if high else "info",
                   f"Pre-Shift Risk Overview — {len(critical)} critical, {len(high)} high, {len(elevated)} elevated",
                   f"{len(all_risks)} drivers assessed. {len(critical)+len(high)} need attention before their shift; {len(all_risks)-len(critical)-len(high)-len(elevated)} cleared for standard operations.",
                   {"totalDrivers": len(all_risks), "critical": len(critical), "high": len(high), "elevated": len(elevated)})
    await asyncio.sleep(_STEP_DELAY)

    yield _progress(mid, "preshift_sweep", "running", 2, 3, "Building risk profiles for flagged drivers...")
    for d in critical + high:
        yield _finding(mid, "flagged_driver", "critical" if d["riskLevel"] == "critical" else "warning",
                       f"{d['driverName']} — {d['riskLevel'].upper()} pre-shift risk ({d['riskScore']}/100)",
                       "Factors: " + ", ".join(f"{f['name']} (impact {f['impact']})" for f in d.get("factors", [])) + f". Action: {d.get('recommendation','')}",
                       {"driverId": d["driverId"], "driverName": d["driverName"], "riskScore": d["riskScore"],
                        "riskLevel": d["riskLevel"], "recommendation": d.get("recommendation")})
    await asyncio.sleep(_STEP_DELAY)

    forecast = get_fleet_risk_forecast()
    briefing = get_daily_briefing()
    yield _finding(mid, "fleet_forecast", "info", f"Weekly Forecast — {forecast['predictedEventsThisWeek']} predicted events",
                   f"High-risk drivers this week: {forecast['highRiskDrivers']}. Top factors: {', '.join(forecast['topRiskFactors'][:3])}.", forecast)

    morning = [f"BLOCK: do not dispatch {d['driverName']} without supervisor clearance (risk {d['riskScore']})" for d in critical] + \
              [f"REVIEW: talk to {d['driverName']} before shift — {d.get('recommendation','')}" for d in high] + \
              [f"FLEET: {forecast['predictedEventsThisWeek']} events predicted — focus on {forecast['topRiskFactors'][0] if forecast['topRiskFactors'] else 'general safety'}"]
    yield {"_kind": "result", "recommendations": morning,
           "data": {"totalDrivers": len(all_risks), "criticalCount": len(critical), "highCount": len(high),
                    "predictedEventsThisWeek": forecast["predictedEventsThisWeek"], "briefingCritical": briefing["criticalCount"]}}


# ─── Executive summary (Continuum LLM, with fallback) ─────────

_SUMMARY_SYS = (
    "You are a senior fleet safety analyst writing an executive summary. Be specific — name drivers, "
    "cite exact numbers, state dollar amounts. Write 3-5 sentences suitable for text-to-speech (a fleet "
    "manager listening on the go). Use natural number phrasing. End with the single most important action to take now."
)


async def _generate_summary(mission_type: str, findings: list[dict], display_name: str) -> str:
    fallback = _fallback_summary(display_name, findings)
    if not findings:
        return fallback
    findings_text = "\n".join(f"[{f['severity'].upper()}] {f['title']}: {f['detail']}" for f in findings)
    try:
        from orchestrator.core.container import get_container
        from orchestrator.llm.config import LLMConfig

        llm = get_container().llm_client
        import os
        model = os.environ.get("DEFAULT_LLM_MODEL", "claude-sonnet-4-5")
        resp = await llm.chat(
            messages=[{"role": "system", "content": _SUMMARY_SYS},
                      {"role": "user", "content": f"Mission: {display_name}\n\nFindings:\n{findings_text}\n\nWrite the executive summary:"}],
            config=LLMConfig(model=model, max_tokens=350),
            auto_session=False,
        )
        if resp and getattr(resp, "content", None):
            return resp.content.strip()
    except Exception as e:  # noqa: BLE001
        logger.warning(f"summary LLM unavailable ({e}); using deterministic fallback")
    return fallback


def _fallback_summary(display_name: str, findings: list[dict]) -> str:
    crit = sum(1 for f in findings if f["severity"] == "critical")
    warn = sum(1 for f in findings if f["severity"] == "warning")
    return (f"{display_name} complete. Analyzed {len(findings)} data points: {crit} critical issues and {warn} warnings "
            f"require attention. Review the detailed findings below for specific driver names, dollar impacts, and recommended actions.")


# ─── Mission -> driver action-item sync ───────────────────────

_SYNC_CATEGORY = {"coaching_sweep": "coaching", "wellness_check": "wellness", "safety_investigation": "safety"}


def _sync_to_drivers(mission_type: str, mission_id: str, findings: list[dict]) -> None:
    category = _SYNC_CATEGORY.get(mission_type)
    if not category:
        return
    from backend.data import driver_session as ds
    add = getattr(ds, "add_driver_action_item", None) or getattr(ds, "add_action_item", None)
    if not add:
        return
    for f in findings:
        data = f.get("data") or {}
        driver_id = data.get("driverId")
        if not driver_id:
            continue
        priority = "urgent" if f["severity"] == "critical" else "high" if f["severity"] == "warning" else "medium"
        title = f["title"]
        try:
            # Prefer the field-wise helper signature; fall back to a dict.
            add(driver_id, title, source=mission_id, category=category, priority=priority, mission_id=mission_id)
        except TypeError:
            try:
                add(driver_id, {"title": title, "category": category, "priority": priority,
                                "description": f["detail"], "missionId": mission_id, "status": "pending"})
            except Exception:  # noqa: BLE001
                pass
