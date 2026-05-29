"""
Intelligent Alert Triage Engine
Transforms raw safety events into prioritized, clustered, actionable insights.

Pipeline:
  1. Cluster events by (driverId + eventType + 2-hour window)
  2. Score urgency: base severity + repeat offender + recency + pattern bonus
  3. Categorize: mechanical | compliance | behavioral | pattern
  4. Generate human-readable titles and suggested actions

Urgency scale: 0-100 (higher = more urgent)
Priority tiers: critical (75-100), high (50-74), medium (25-49), low (0-24)
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Optional

from backend.data.seed_data import (
    SeedSafetyEvent,
    _now,
    _parse_dt,
    seed_drivers,
    seed_safety_events,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SEVERITY_BASE: dict[str, int] = {
    "critical": 40,
    "high": 30,
    "medium": 20,
    "low": 10,
}

CATEGORY_MAP: dict[str, str] = {
    "harsh_braking": "behavioral",
    "harsh_acceleration": "behavioral",
    "speeding": "compliance",
    "seatbelt": "compliance",
    "distracted_driving": "behavioral",
    "drowsy_driving": "behavioral",
    "lane_departure": "behavioral",
    "tailgating": "behavioral",
    "rolling_stop": "compliance",
    "idle_excessive": "mechanical",
}

ACTION_MAP: dict[str, str] = {
    "harsh_braking": "Review dashcam footage and coach on following distance and anticipatory braking techniques.",
    "harsh_acceleration": "Coach on smooth acceleration patterns. Consider setting acceleration threshold alerts.",
    "speeding": "Review speed governor settings. Discuss route-specific speed limits and consequences.",
    "seatbelt": "Mandatory seatbelt compliance reminder. If repeated, escalate to formal write-up per company policy.",
    "distracted_driving": "Conduct distracted driving intervention. Review phone policy and install phone-blocking technology if available.",
    "drowsy_driving": "URGENT: Review recent rest hours and schedule. Mandate 34-hour restart if HOS allows. Consider fatigue management program.",
    "lane_departure": "Assess vehicle lane-departure warning system. If functional, coach driver on attentiveness. Check for fatigue patterns.",
    "tailgating": "Coach on safe following distance (7-second rule for trucks). Review recent close-call footage.",
    "rolling_stop": "Review intersection safety procedures. Coach on full-stop compliance at all stop signs and red lights.",
    "idle_excessive": "Review idling policy. Check for mechanical issues (stuck PTO, HVAC problems). Coach on anti-idle practices.",
}


# ---------------------------------------------------------------------------
# Helpers (JS-parity numeric / formatting)
# ---------------------------------------------------------------------------

def _epoch_ms(dt: datetime) -> float:
    """Milliseconds since epoch (mirrors JS Date.getTime())."""
    return dt.timestamp() * 1000.0


def _now_ms() -> float:
    """Mirrors JS Date.now()."""
    return _epoch_ms(_now())


def _event_ms(event: SeedSafetyEvent) -> float:
    return _epoch_ms(_parse_dt(event.dateTime))


def _round_half_up(x: float) -> int:
    """Mirror JS Math.round (round half toward +Infinity)."""
    return math.floor(x + 0.5)


def _to_fixed(x: float, digits: int) -> str:
    """Mirror JS Number.prototype.toFixed (round half away from zero)."""
    if x < 0:
        return "-" + _to_fixed(-x, digits)
    factor = 10 ** digits
    rounded = math.floor(x * factor + 0.5) / factor
    return f"{rounded:.{digits}f}"


def _to_locale_string(dt: datetime) -> str:
    """Approximate JS Date.toLocaleString() (en-US): M/D/YYYY, h:mm:ss AM/PM."""
    hour24 = dt.hour
    am_pm = "AM" if hour24 < 12 else "PM"
    hour12 = hour24 % 12
    if hour12 == 0:
        hour12 = 12
    return (
        f"{dt.month}/{dt.day}/{dt.year}, "
        f"{hour12}:{dt.minute:02d}:{dt.second:02d} {am_pm}"
    )


def _to_iso_string(ms: float) -> str:
    """Mirror JS Date(ms).toISOString() -> YYYY-MM-DDTHH:MM:SS.mmmZ (UTC)."""
    dt = datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


# ---------------------------------------------------------------------------
# Event Clustering
# ---------------------------------------------------------------------------

def _cluster_events(events: list[SeedSafetyEvent]) -> list[dict]:
    two_hours = 2 * 3600000
    clusters: list[dict] = []

    # Group by driverId + eventType first
    groups: dict[str, list[SeedSafetyEvent]] = {}
    for event in events:
        key = f"{event.driverId}_{event.type}"
        groups.setdefault(key, []).append(event)

    # Within each group, cluster by 2-hour windows
    for group_events in groups.values():
        sorted_events = sorted(group_events, key=_event_ms)

        current_cluster: list[SeedSafetyEvent] = [sorted_events[0]]
        window_start = _event_ms(sorted_events[0])

        for i in range(1, len(sorted_events)):
            event_time = _event_ms(sorted_events[i])
            if event_time - window_start <= two_hours:
                current_cluster.append(sorted_events[i])
            else:
                # Close current cluster and start new one
                clusters.append({
                    "driverId": current_cluster[0].driverId,
                    "eventType": current_cluster[0].type,
                    "events": current_cluster,
                    "windowStart": window_start,
                    "windowEnd": _event_ms(current_cluster[-1]),
                })
                current_cluster = [sorted_events[i]]
                window_start = event_time

        # Push last cluster
        if len(current_cluster) > 0:
            clusters.append({
                "driverId": current_cluster[0].driverId,
                "eventType": current_cluster[0].type,
                "events": current_cluster,
                "windowStart": window_start,
                "windowEnd": _event_ms(current_cluster[-1]),
            })

    return clusters


# ---------------------------------------------------------------------------
# Urgency Scoring
# ---------------------------------------------------------------------------

def _score_cluster(cluster: dict) -> int:
    now = _now_ms()

    # Base severity: use highest severity in cluster
    severities = [SEVERITY_BASE.get(e.severity, 10) for e in cluster["events"]]
    base_severity = max(severities)

    # Repeat offender multiplier: >3 same-type events in 24hrs from this driver
    twenty_four_hours_ago = now - 24 * 3600000
    same_type_24h = [
        e for e in seed_safety_events
        if e.driverId == cluster["driverId"]
        and e.type == cluster["eventType"]
        and _event_ms(e) > twenty_four_hours_ago
    ]
    repeat_bonus = 20 if len(same_type_24h) > 3 else 0

    # Recency bonus
    most_recent_time = cluster["windowEnd"]
    age_ms = now - most_recent_time
    recency_bonus = 15 if age_ms < 3600000 else (10 if age_ms < 4 * 3600000 else 0)

    # Pattern bonus: driver is already high/critical risk
    pattern_bonus = 0
    driver = next((d for d in seed_drivers if d.id == cluster["driverId"]), None)
    if driver and (driver.riskProfile == "high" or driver.riskProfile == "critical"):
        pattern_bonus = 15

    # Cluster size bonus (multi-event clusters are more concerning)
    n_events = len(cluster["events"])
    cluster_bonus = min(10, n_events * 2) if n_events > 1 else 0

    return min(100, base_severity + repeat_bonus + recency_bonus + pattern_bonus + cluster_bonus)


# ---------------------------------------------------------------------------
# Alert Generation
# ---------------------------------------------------------------------------

def _generate_title(cluster: dict, driver_name: str) -> str:
    event_type_pretty = cluster["eventType"].replace("_", " ")
    count = len(cluster["events"])

    if count == 1:
        severity = cluster["events"][0].severity
        return f"Driver {driver_name}: {severity} {event_type_pretty} event"

    # Timespan
    span_ms = cluster["windowEnd"] - cluster["windowStart"]
    if span_ms < 3600000:
        timespan = f"{_round_half_up(span_ms / 60000)} minutes"
    elif span_ms < 86400000:
        timespan = f"{_to_fixed(span_ms / 3600000, 1)} hours"
    else:
        timespan = f"{_to_fixed(span_ms / 86400000, 1)} days"

    return f"Driver {driver_name}: {count} {event_type_pretty} events in {timespan}"


def _generate_description(cluster: dict, urgency_score: int) -> str:
    severity_counts: dict[str, int] = {}
    for e in cluster["events"]:
        severity_counts[e.severity] = severity_counts.get(e.severity, 0) + 1
    severity_breakdown = ", ".join(
        f"{count} {sev}" for sev, count in severity_counts.items()
    )

    latest_event = cluster["events"][-1]
    return (
        f"{len(cluster['events'])} {cluster['eventType'].replace('_', ' ')} event(s) detected. "
        f"Severity breakdown: {severity_breakdown}. "
        f"Latest at {_to_locale_string(_parse_dt(latest_event.dateTime))}. "
        f"Urgency: {urgency_score}/100."
    )


def _categorize_cluster(cluster: dict) -> str:
    # Multi-event clusters get categorized as 'pattern'
    if len(cluster["events"]) >= 3:
        return "pattern"
    return CATEGORY_MAP.get(cluster["eventType"], "behavioral")


def _generate_action(cluster: dict) -> str:
    base_action = ACTION_MAP.get(
        cluster["eventType"], "Review event details and schedule coaching session."
    )

    if len(cluster["events"]) >= 3:
        return (
            f"PATTERN DETECTED: {len(cluster['events'])} occurrences. {base_action} "
            f"Escalate to safety manager for formal intervention."
        )

    return base_action


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_triaged_alerts(limit: Optional[int] = None) -> list[dict]:
    # Use events from last 7 days for triage
    now = _now_ms()
    seven_days_ago = now - 7 * 86400000
    recent_events = [e for e in seed_safety_events if _event_ms(e) > seven_days_ago]

    clusters = _cluster_events(recent_events)

    alerts: list[dict] = []
    for index, cluster in enumerate(clusters):
        driver = next((d for d in seed_drivers if d.id == cluster["driverId"]), None)
        driver_name = driver.name if driver else "Unknown"
        urgency_score = _score_cluster(cluster)

        priority = (
            "critical" if urgency_score >= 75
            else "high" if urgency_score >= 50
            else "medium" if urgency_score >= 25
            else "low"
        )

        alerts.append({
            "id": f"alert_{index + 1}",
            "priority": priority,
            "urgencyScore": urgency_score,
            "title": _generate_title(cluster, driver_name),
            "description": _generate_description(cluster, urgency_score),
            "category": _categorize_cluster(cluster),
            "relatedEvents": [e.id for e in cluster["events"]],
            "affectedDriver": {"id": cluster["driverId"], "name": driver_name},
            "affectedVehicle": cluster["events"][0].vehicleId,
            "suggestedAction": _generate_action(cluster),
            "timestamp": _to_iso_string(cluster["windowEnd"]),
        })

    # Sort by urgency (highest first)
    alerts.sort(key=lambda a: a["urgencyScore"], reverse=True)

    # Re-assign stable IDs after sorting
    for i, a in enumerate(alerts):
        a["id"] = f"alert_{i + 1}"

    return alerts[:limit] if limit else alerts


def get_daily_briefing() -> dict:
    all_alerts = get_triaged_alerts()

    critical_count = sum(1 for a in all_alerts if a["priority"] == "critical")
    high_count = sum(1 for a in all_alerts if a["priority"] == "high")
    medium_count = sum(1 for a in all_alerts if a["priority"] == "medium")
    top_alerts = all_alerts[:10]

    # Build fleet risk summary
    unique_drivers_at_risk = {
        a["affectedDriver"]["id"]
        for a in all_alerts
        if a["priority"] == "critical" or a["priority"] == "high"
    }

    category_counts: dict[str, int] = {}
    for alert in all_alerts:
        category_counts[alert["category"]] = category_counts.get(alert["category"], 0) + 1
    # Object.entries(...).sort((a, b) => b[1] - a[1])[0] — descending by count,
    # stable so ties keep first-insertion order.
    sorted_categories = sorted(
        category_counts.items(), key=lambda kv: kv[1], reverse=True
    )
    top_category = sorted_categories[0] if sorted_categories else None

    fleet_risk_summary = (
        f"Today's briefing: {critical_count} critical, {high_count} high, and "
        f"{medium_count} medium priority alerts across the fleet. "
        f"{len(unique_drivers_at_risk)} driver(s) require immediate attention. "
        f"Most common alert category: {top_category[0] if top_category else 'none'} "
        f"({top_category[1] if top_category else 0} alerts). "
        f"Total alerts triaged: {len(all_alerts)}."
    )

    return {
        "criticalCount": critical_count,
        "highCount": high_count,
        "topAlerts": top_alerts,
        "fleetRiskSummary": fleet_risk_summary,
    }
