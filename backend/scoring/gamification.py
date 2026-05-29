"""
Gamification Engine for FleetShield AI Driver Portal.

Pure scoring engine that calculates points, badges, levels, daily challenges,
and rewards from seed data.

Points and badges are deterministic based on 90 days of seeded safety events
and trip days.

Ported from backend/src/scoring/gamification-engine.ts with high fidelity.
Dict keys are kept EXACTLY camelCase to match the driver-portal frontend's
JSON contract (frontend/src/types/fleet.ts).
"""

from __future__ import annotations

from datetime import timedelta, timezone
from typing import Optional

from backend.data.seed_data import (
    _now,
    _parse_dt,
    seed_drivers,
    seed_safety_events,
    seed_trip_days,
)


# ─── Time helper (mimics JS Date.prototype.toISOString) ──────

def _iso(dt) -> str:
    """Format a datetime as JS toISOString() does: UTC, milliseconds, Z."""
    dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def _now_ms() -> float:
    """Current time as epoch milliseconds (mimics JS Date.now())."""
    return _now().timestamp() * 1000.0


def _ms(dt) -> float:
    """Epoch milliseconds for a datetime (mimics Date.getTime())."""
    return dt.timestamp() * 1000.0


_DAY_MS = 86400000


# ─── Level System ────────────────────────────────────────────

# level, minPoints, title
_LEVELS = [
    {"level": 1, "minPoints": 0, "title": "Rookie"},
    {"level": 2, "minPoints": 200, "title": "Road Ready"},
    {"level": 3, "minPoints": 500, "title": "Safe Hauler"},
    {"level": 4, "minPoints": 1200, "title": "Shield Bearer"},
    {"level": 5, "minPoints": 2500, "title": "Road Guardian"},
    {"level": 6, "minPoints": 5000, "title": "Fleet Champion"},
    {"level": 7, "minPoints": 10000, "title": "Legend"},
]


def get_level_info(points: float) -> dict:
    current_level = _LEVELS[0]
    for lvl in _LEVELS:
        if points >= lvl["minPoints"]:
            current_level = lvl

    next_level = next((l for l in _LEVELS if l["level"] == current_level["level"] + 1), None)
    if not next_level:
        # Max level
        return {"level": current_level["level"], "title": current_level["title"],
                "pointsToNext": 0, "progress": 1}

    rng = next_level["minPoints"] - current_level["minPoints"]
    earned = points - current_level["minPoints"]
    progress = min(1, earned / rng)

    return {
        "level": current_level["level"],
        "title": current_level["title"],
        "pointsToNext": next_level["minPoints"] - points,
        "progress": progress,
    }


# ─── Streak Multiplier ──────────────────────────────────────

def get_streak_multiplier(streak: int) -> float:
    if streak >= 30:
        return 3.0
    if streak >= 14:
        return 2.0
    if streak >= 7:
        return 1.5
    return 1.0


# ─── Streak Calculation ─────────────────────────────────────

def calculate_streak_days(driver_id: str) -> int:
    events = [e for e in seed_safety_events
              if e.driverId == driver_id and e.severity in ("high", "critical")]
    events.sort(key=lambda e: _ms(_parse_dt(e.dateTime)), reverse=True)

    if not events:
        return 90  # No critical/high events in 90 days

    last_bad_event = _parse_dt(events[0].dateTime)
    days_since = int((_now_ms() - _ms(last_bad_event)) // _DAY_MS)
    return days_since


# ─── Simple Hash Function (deterministic) ───────────────────

def simple_hash(s: str) -> int:
    """Deterministic 32-bit hash mirroring the TS implementation."""
    h = 0
    for ch in s:
        char = ord(ch)
        h = ((h << 5) - h) + char
        # Convert to signed 32-bit integer (JS `hash |= 0`)
        h &= 0xFFFFFFFF
        if h >= 0x80000000:
            h -= 0x100000000
    return abs(h)


# ─── Points Calculation ─────────────────────────────────────

def calculate_points(driver) -> dict:
    transactions: list[dict] = []
    total_points = 0
    tx_id = 1

    driver_events = [e for e in seed_safety_events if e.driverId == driver.id]
    driver_trips = [t for t in seed_trip_days if t.driverId == driver.id]

    # Build a set of dates with medium/high/critical events
    unsafe_days: set[str] = set()
    medium_days: set[str] = set()
    high_days: set[str] = set()
    critical_days: set[str] = set()

    for ev in driver_events:
        date_str = ev.dateTime.split("T")[0]
        if ev.severity in ("medium", "high", "critical"):
            unsafe_days.add(date_str)
        if ev.severity == "medium":
            medium_days.add(date_str + "|" + ev.id)
        if ev.severity == "high":
            high_days.add(date_str + "|" + ev.id)
        if ev.severity == "critical":
            critical_days.add(date_str + "|" + ev.id)

    # Build set of all dates in last 90 days
    all_dates: list[str] = []
    for day in range(90):
        d = _now() - timedelta(milliseconds=day * _DAY_MS)
        all_dates.append(d.astimezone(timezone.utc).strftime("%Y-%m-%d"))

    # +10 per safe driving day (no medium/high/critical severity events that day)
    safe_day_dates: list[str] = []
    for date_str in all_dates:
        if date_str not in unsafe_days:
            # Check if driver had trips that day
            had_trip = any(t.date == date_str for t in driver_trips)
            if had_trip:
                safe_day_dates.append(date_str)

    for date_str in safe_day_dates:
        pts = 10
        total_points += pts
        if tx_id <= 20:  # Only keep recent 20 for display
            transactions.append({
                "id": f"pt-{driver.id}-{tx_id}",
                "points": pts,
                "reason": "Safe driving day",
                "timestamp": _iso(_parse_dt(date_str + "T18:00:00Z")),
                "type": "earned",
            })
            tx_id += 1

    # +5 per trip day (completed trips from seed_trip_days)
    for trip in driver_trips:
        total_points += 5
        if tx_id <= 25:
            transactions.append({
                "id": f"pt-{driver.id}-{tx_id}",
                "points": 5,
                "reason": f"Completed {trip.trips} trips",
                "timestamp": _iso(_parse_dt(trip.date + "T17:00:00Z")),
                "type": "earned",
            })
            tx_id += 1

    # Deductions: -5 per medium event, -15 per high event, -30 per critical event
    medium_events = [e for e in driver_events if e.severity == "medium"]
    high_events = [e for e in driver_events if e.severity == "high"]
    critical_events = [e for e in driver_events if e.severity == "critical"]

    for ev in medium_events:
        total_points -= 5
        if tx_id <= 30:
            transactions.append({
                "id": f"pt-{driver.id}-{tx_id}",
                "points": -5,
                "reason": f"Medium severity: {ev.type.replace('_', ' ')}",
                "timestamp": ev.dateTime,
                "type": "deduction",
            })
            tx_id += 1

    for ev in high_events:
        total_points -= 15
        if tx_id <= 35:
            transactions.append({
                "id": f"pt-{driver.id}-{tx_id}",
                "points": -15,
                "reason": f"High severity: {ev.type.replace('_', ' ')}",
                "timestamp": ev.dateTime,
                "type": "deduction",
            })
            tx_id += 1

    for ev in critical_events:
        total_points -= 30
        if tx_id <= 40:
            transactions.append({
                "id": f"pt-{driver.id}-{tx_id}",
                "points": -30,
                "reason": f"Critical severity: {ev.type.replace('_', ' ')}",
                "timestamp": ev.dateTime,
                "type": "deduction",
            })
            tx_id += 1

    # +25 for completed daily challenges (simulate ~60% completion for low-risk, less for high-risk)
    challenge_completion_rate = (
        0.65 if driver.riskProfile == "low"
        else 0.45 if driver.riskProfile == "moderate"
        else 0.25 if driver.riskProfile == "high"
        else 0.15  # critical
    )

    num_challenges_completed = int(90 * challenge_completion_rate)
    challenge_points = num_challenges_completed * 25
    total_points += challenge_points

    if num_challenges_completed > 0:
        # Show a few representative transactions
        for i in range(min(5, num_challenges_completed)):
            transactions.append({
                "id": f"pt-{driver.id}-{tx_id}",
                "points": 25,
                "reason": "Daily challenge completed",
                "timestamp": _iso(_now() - timedelta(milliseconds=(i * 2 + 1) * _DAY_MS)),
                "type": "challenge",
            })
            tx_id += 1

    # +50 for each earned badge (calculated separately, but add to points)
    badges = calculate_badges(driver)
    earned_badges = [b for b in badges if b["earned"]]
    for badge in earned_badges:
        total_points += 50
        transactions.append({
            "id": f"pt-{driver.id}-{tx_id}",
            "points": 50,
            "reason": f"Badge earned: {badge['name']}",
            "timestamp": badge.get("earnedDate") or _iso(_now() - timedelta(milliseconds=30 * _DAY_MS)),
            "type": "badge",
        })
        tx_id += 1

    # Apply streak multiplier as a bonus on top of base safe-day points
    streak = calculate_streak_days(driver.id)
    multiplier = get_streak_multiplier(streak)
    if multiplier > 1.0:
        safe_day_base = len(safe_day_dates) * 10
        bonus_points = int(safe_day_base * (multiplier - 1.0))
        total_points += bonus_points
        transactions.append({
            "id": f"pt-{driver.id}-{tx_id}",
            "points": bonus_points,
            "reason": f"Streak bonus (x{_num(multiplier)}, {streak} days)",
            "timestamp": _iso(_now()),
            "type": "bonus",
        })
        tx_id += 1

    # Ensure minimum 0
    total_points = max(0, total_points)

    # Sort transactions by timestamp descending
    transactions.sort(key=lambda t: _ms(_parse_dt(t["timestamp"])), reverse=True)

    return {"totalPoints": total_points, "transactions": transactions}


def _num(n: float) -> str:
    """Mimic JS number-to-string for the streak multiplier (1.5, 2, 3)."""
    return str(int(n)) if float(n).is_integer() else str(n)


# ─── Badge Definitions & Calculation ────────────────────────

def get_leaderboard_rank(driver_id: str) -> dict:
    # Compute a simple rank based on risk profile and streak
    drivers = seed_drivers if len(seed_drivers) > 0 else []
    scores = [{"id": d.id, "score": calculate_simple_score(d)} for d in drivers]
    scores.sort(key=lambda s: s["score"], reverse=True)
    idx = next((i for i, s in enumerate(scores) if s["id"] == driver_id), -1)
    return {"rank": idx + 1, "total": len(scores)}


def calculate_simple_score(driver) -> int:
    thirty_ago = _now() - timedelta(milliseconds=30 * _DAY_MS)
    events30 = [e for e in seed_safety_events
                if e.driverId == driver.id and _parse_dt(e.dateTime) > thirty_ago]
    # NOTE: TS compares trip.date (a YYYY-MM-DD string) via `new Date(t.date)`,
    # i.e. midnight UTC of that day, against now-30d. Replicate by parsing the date.
    trips30 = [t for t in seed_trip_days
               if t.driverId == driver.id
               and _parse_dt(t.date + "T00:00:00Z") > thirty_ago]
    total_distance = sum(t.totalDistance for t in trips30)
    if total_distance == 0:
        return 85
    severity_weights = {"low": 1, "medium": 2, "high": 4, "critical": 8}
    weighted_events = sum(severity_weights.get(e.severity, 1) for e in events30)
    weighted_rate = (weighted_events / total_distance) * 1000
    return max(0, min(100, round(100 - weighted_rate * 3)))


# Each badge def has: id, name, description, icon, requirement, check.
# check(driver, events, trips, rank, total) -> {earned, progress, earnedDate?}

def _check_safe_day_1(driver, events, trips, rank, total):
    unsafe_days: set[str] = set()
    for e in events:
        if e.severity != "low":
            unsafe_days.add(e.dateTime.split("T")[0])
    trip_dates = {t.date for t in trips}
    safe_day_count = 0
    for date in trip_dates:
        if date not in unsafe_days:
            safe_day_count += 1
    earned = safe_day_count >= 1
    return {"earned": earned, "progress": min(1, safe_day_count / 1),
            "earnedDate": _iso(_now() - timedelta(milliseconds=80 * _DAY_MS)) if earned else None}


def _check_streak(threshold, days_ago):
    def check(driver, events, trips, rank, total):
        streak = calculate_streak_days(driver.id)
        earned = streak >= threshold
        return {"earned": earned, "progress": min(1, streak / threshold),
                "earnedDate": _iso(_now() - timedelta(milliseconds=days_ago * _DAY_MS)) if earned else None}
    return check


def _check_no_event_type(event_type, days_ago):
    def check(driver, events, trips, rank, total):
        typed = [e for e in events if e.type == event_type]
        typed.sort(key=lambda e: _ms(_parse_dt(e.dateTime)), reverse=True)
        days_since_last = 90
        if typed:
            days_since_last = int((_now_ms() - _ms(_parse_dt(typed[0].dateTime))) // _DAY_MS)
        earned = days_since_last >= 14
        return {"earned": earned, "progress": min(1, days_since_last / 14),
                "earnedDate": _iso(_now() - timedelta(milliseconds=days_ago * _DAY_MS)) if earned else None}
    return check


def _check_top_5(driver, events, trips, rank, total):
    earned = rank <= 5 and total > 0
    progress = min(1, max(0, (total - rank + 1) / (total - 4))) if total > 0 else 0
    return {"earned": earned, "progress": progress,
            "earnedDate": _iso(_now() - timedelta(milliseconds=15 * _DAY_MS)) if earned else None}


def _check_top_1(driver, events, trips, rank, total):
    earned = rank == 1 and total > 0
    progress = min(1, max(0, (total - rank + 1) / total)) if total > 0 else 0
    return {"earned": earned, "progress": progress,
            "earnedDate": _iso(_now() - timedelta(milliseconds=10 * _DAY_MS)) if earned else None}


def _check_perfect_week(driver, events, trips, rank, total):
    completion_rate = (
        0.65 if driver.riskProfile == "low"
        else 0.45 if driver.riskProfile == "moderate"
        else 0.2
    )
    earned = completion_rate >= 0.6
    return {"earned": earned, "progress": 1 if earned else completion_rate / 0.6,
            "earnedDate": _iso(_now() - timedelta(milliseconds=35 * _DAY_MS)) if earned else None}


def _check_night_safe_7(driver, events, trips, rank, total):
    event_days: set[str] = set()
    for e in events:
        if e.severity != "low":
            event_days.add(e.dateTime.split("T")[0])
    safe_night_count = 0
    for trip in trips:
        if trip.nightDrivingHours > 2 and trip.date not in event_days:
            safe_night_count += 1
    earned = safe_night_count >= 7
    return {"earned": earned, "progress": min(1, safe_night_count / 7),
            "earnedDate": _iso(_now() - timedelta(milliseconds=40 * _DAY_MS)) if earned else None}


def _check_fuel_efficient_7(driver, events, trips, rank, total):
    all_trips = seed_trip_days
    avg_idling = (
        sum(t.idlingMinutes for t in all_trips) / len(all_trips)
        if all_trips else 30
    )
    srt = sorted(trips, key=lambda t: _ms(_parse_dt(t.date + "T00:00:00Z")), reverse=True)
    consecutive_low_idle = 0
    max_consecutive = 0
    for trip in srt:
        if trip.idlingMinutes < avg_idling:
            consecutive_low_idle += 1
            max_consecutive = max(max_consecutive, consecutive_low_idle)
        else:
            consecutive_low_idle = 0
    earned = max_consecutive >= 7
    return {"earned": earned, "progress": min(1, max_consecutive / 7),
            "earnedDate": _iso(_now() - timedelta(milliseconds=22 * _DAY_MS)) if earned else None}


_BADGE_DEFS = [
    {"id": "safe_day_1", "name": "First Safe Day",
     "description": "Complete 1 day with no medium or higher severity events",
     "icon": "\U0001F6E1️", "requirement": "1 day no medium+ events",
     "check": _check_safe_day_1},
    {"id": "streak_7", "name": "Week Warrior",
     "description": "Achieve a 7-day streak with no high/critical events",
     "icon": "⚔️", "requirement": "7-day streak",
     "check": _check_streak(7, 60)},
    {"id": "streak_14", "name": "Fortnight Fighter",
     "description": "Achieve a 14-day streak with no high/critical events",
     "icon": "\U0001F5E1️", "requirement": "14-day streak",
     "check": _check_streak(14, 45)},
    {"id": "streak_30", "name": "Monthly Master",
     "description": "Achieve a 30-day streak with no high/critical events",
     "icon": "\U0001F451", "requirement": "30-day streak",
     "check": _check_streak(30, 20)},
    {"id": "no_speeding_14", "name": "Speed Angel",
     "description": "No speeding events for 14 consecutive days",
     "icon": "\U0001F607", "requirement": "No speeding for 14 days",
     "check": _check_no_event_type("speeding", 30)},
    {"id": "no_harsh_brake_14", "name": "Smooth Operator",
     "description": "No harsh braking events for 14 consecutive days",
     "icon": "\U0001F3B5", "requirement": "No harsh braking for 14 days",
     "check": _check_no_event_type("harsh_braking", 25)},
    {"id": "no_distracted_14", "name": "Focus Master",
     "description": "No distracted driving events for 14 consecutive days",
     "icon": "\U0001F3AF", "requirement": "No distracted driving for 14 days",
     "check": _check_no_event_type("distracted_driving", 28)},
    {"id": "top_5", "name": "Elite Five",
     "description": "Reach top 5 on the safety leaderboard",
     "icon": "⭐", "requirement": "Reach top 5 in leaderboard",
     "check": _check_top_5},
    {"id": "top_1", "name": "Number One",
     "description": "Reach #1 on the safety leaderboard",
     "icon": "\U0001F3C6", "requirement": "Reach #1 in leaderboard",
     "check": _check_top_1},
    {"id": "perfect_week", "name": "Perfect Week",
     "description": "Complete 5 out of 5 daily challenges in one week",
     "icon": "\U0001F48E", "requirement": "Complete 5/5 daily challenges in a week",
     "check": _check_perfect_week},
    {"id": "night_safe_7", "name": "Night Owl",
     "description": "Complete 7 safe night shifts (2+ night hours with no events)",
     "icon": "\U0001F989", "requirement": "7 safe night shifts",
     "check": _check_night_safe_7},
    {"id": "fuel_efficient_7", "name": "Eco Driver",
     "description": "Maintain below-average idling for 7 days",
     "icon": "\U0001F33F", "requirement": "Below-average idling for 7 days",
     "check": _check_fuel_efficient_7},
]


def calculate_badges(driver) -> list[dict]:
    events = [e for e in seed_safety_events if e.driverId == driver.id]
    trips = [t for t in seed_trip_days if t.driverId == driver.id]
    rank_info = get_leaderboard_rank(driver.id)
    rank, total = rank_info["rank"], rank_info["total"]

    badges = []
    for d in _BADGE_DEFS:
        result = d["check"](driver, events, trips, rank, total)
        badges.append({
            "id": d["id"],
            "name": d["name"],
            "description": d["description"],
            "icon": d["icon"],
            "earned": result["earned"],
            "earnedDate": result.get("earnedDate"),
            "progress": result["progress"],
            "requirement": d["requirement"],
        })
    return badges


# ─── Daily Challenge System ─────────────────────────────────

# Each challenge def: id, name, description, icon, pointsReward,
# targetEventType?, check_progress(driver_id)->{current,target}, weakAreas?

def _cp_no_event(event_type):
    def cp(driver_id):
        today_events = get_today_events(driver_id, event_type)
        return {"current": 1 if today_events == 0 else 0, "target": 1}
    return cp


def _cp_rest_champion(driver_id):
    today_trip = get_today_trip(driver_id)
    if not today_trip:
        return {"current": 0, "target": 8}
    return {"current": min(today_trip.restHoursBetweenShifts, 8), "target": 8}


def _cp_fuel_efficient(driver_id):
    today_trip = get_today_trip(driver_id)
    if not today_trip:
        return {"current": 15, "target": 15}  # No trip = goal met
    return {"current": max(0, 15 - today_trip.idlingMinutes), "target": 15}


def _cp_early_bird(driver_id):
    h = simple_hash(driver_id + "earlybird")
    started = h % 3 != 0  # ~66% chance
    return {"current": 1 if started else 0, "target": 1}


def _cp_perfect_delivery(driver_id):
    driver = next((d for d in seed_drivers if d.id == driver_id), None)
    on_time = driver is not None and driver.riskProfile in ("low", "moderate")
    return {"current": 1 if on_time else 0, "target": 1}


def _cp_zero_events(driver_id):
    today_start = _today_start()
    today_events = len([e for e in seed_safety_events
                        if e.driverId == driver_id and _parse_dt(e.dateTime) >= today_start])
    return {"current": 1 if today_events == 0 else 0, "target": 1}


def _cp_night_safe(driver_id):
    today_trip = get_today_trip(driver_id)
    if not today_trip or today_trip.nightDrivingHours < 1:
        return {"current": 0, "target": 1}
    today_start = _today_start()
    today_events = len([e for e in seed_safety_events
                        if e.driverId == driver_id and _parse_dt(e.dateTime) >= today_start])
    return {"current": 1 if today_events == 0 else 0, "target": 1}


_CHALLENGE_POOL = [
    {"id": "no_harsh_braking", "name": "Smooth Sailing",
     "description": "Zero harsh braking events today", "icon": "\U0001F6A2",
     "pointsReward": 25, "targetEventType": "harsh_braking",
     "weakAreas": ["harsh_braking"], "checkProgress": _cp_no_event("harsh_braking")},
    {"id": "speed_compliance", "name": "Speed Keeper",
     "description": "Stay within speed limits all day", "icon": "\U0001F3CE️",
     "pointsReward": 25, "targetEventType": "speeding",
     "weakAreas": ["speeding"], "checkProgress": _cp_no_event("speeding")},
    {"id": "no_distraction", "name": "Eyes on Road",
     "description": "No distracted driving events", "icon": "\U0001F440",
     "pointsReward": 25, "targetEventType": "distracted_driving",
     "weakAreas": ["distracted_driving"], "checkProgress": _cp_no_event("distracted_driving")},
    {"id": "rest_champion", "name": "Rest Well",
     "description": "Take at least 8 hours rest between shifts", "icon": "\U0001F634",
     "pointsReward": 25, "weakAreas": ["drowsy_driving"],
     "checkProgress": _cp_rest_champion},
    {"id": "fuel_efficient", "name": "Eco Mode",
     "description": "Keep idling under 15 minutes total", "icon": "\U0001F331",
     "pointsReward": 25, "weakAreas": ["idle_excessive"],
     "checkProgress": _cp_fuel_efficient},
    {"id": "early_bird", "name": "Early Bird",
     "description": "Start your shift before 7 AM", "icon": "\U0001F305",
     "pointsReward": 25, "checkProgress": _cp_early_bird},
    {"id": "perfect_delivery", "name": "On Time",
     "description": "Complete delivery within scheduled window", "icon": "\U0001F4E6",
     "pointsReward": 25, "checkProgress": _cp_perfect_delivery},
    {"id": "zero_events", "name": "Clean Sheet",
     "description": "Zero safety events of any severity", "icon": "✨",
     "pointsReward": 25, "checkProgress": _cp_zero_events},
    {"id": "night_safe", "name": "Night Guardian",
     "description": "Complete a night shift with zero events", "icon": "\U0001F319",
     "pointsReward": 25, "weakAreas": ["drowsy_driving", "lane_departure"],
     "checkProgress": _cp_night_safe},
    {"id": "short_following", "name": "Space Keeper",
     "description": "No tailgating events today", "icon": "\U0001F4CF",
     "pointsReward": 25, "targetEventType": "tailgating",
     "weakAreas": ["tailgating"], "checkProgress": _cp_no_event("tailgating")},
]


def _today_start():
    """Local midnight today, as an aware datetime (mimics setHours(0,0,0,0))."""
    return _now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)


def _today_end():
    """Local end-of-day today (mimics setHours(23,59,59,999))."""
    return _now().astimezone().replace(hour=23, minute=59, second=59, microsecond=999000)


def get_today_events(driver_id: str, event_type: Optional[str] = None) -> int:
    today_start = _today_start()
    count = 0
    for e in seed_safety_events:
        if e.driverId != driver_id:
            continue
        if _parse_dt(e.dateTime) < today_start:
            continue
        if event_type and e.type != event_type:
            continue
        count += 1
    return count


def get_today_trip(driver_id: str):
    today_str = _now().astimezone(timezone.utc).strftime("%Y-%m-%d")
    return next((t for t in seed_trip_days
                 if t.driverId == driver_id and t.date == today_str), None)


def select_daily_challenge(driver_id: str) -> Optional[dict]:
    today_str = _now().astimezone(timezone.utc).strftime("%Y-%m-%d")
    hash_key = driver_id + today_str
    h = simple_hash(hash_key)

    # Find driver's weak areas
    driver_events = [e for e in seed_safety_events if e.driverId == driver_id]
    event_type_counts: dict[str, int] = {}
    for e in driver_events:
        event_type_counts[e.type] = event_type_counts.get(e.type, 0) + 1

    # Sort challenge pool: prioritize challenges that match driver's weak areas.
    # Python's sort is stable, matching JS Array.sort for equal-relevance ties.
    def relevance(c):
        return sum(event_type_counts.get(area, 0) for area in c.get("weakAreas", []))

    sorted_challenges = sorted(_CHALLENGE_POOL, key=relevance, reverse=True)

    # Use hash to pick from top-weighted pool (top half gets 70% chance)
    top_half = -(-len(sorted_challenges) // 2)  # Math.ceil
    use_top_half = (h % 10) < 7
    pool = sorted_challenges[:top_half] if use_top_half else sorted_challenges[top_half:]
    selected_index = h % len(pool)
    challenge = pool[selected_index]

    progress = challenge["checkProgress"](driver_id)
    progress_fraction = progress["current"] / progress["target"] if progress["target"] > 0 else 0

    end_of_day = _today_end()

    return {
        "id": challenge["id"],
        "name": challenge["name"],
        "description": challenge["description"],
        "icon": challenge["icon"],
        "progress": min(1, progress_fraction),
        "target": progress["target"],
        "current": progress["current"],
        "pointsReward": challenge["pointsReward"],
        "completed": progress_fraction >= 1,
        "expiresAt": _iso(end_of_day),
    }


# ─── Rewards Catalog ────────────────────────────────────────

_REWARDS = [
    {"id": "r1", "name": "Coffee Gift Card", "icon": "☕", "pointsCost": 500,
     "category": "Gift Cards", "levelRequired": 1},
    {"id": "r2", "name": "Premium Parking Pass", "icon": "\U0001F17F️", "pointsCost": 1000,
     "category": "Perks", "levelRequired": 2},
    {"id": "r3", "name": "Fuel Card Bonus $50", "icon": "⛽", "pointsCost": 1500,
     "category": "Gift Cards", "levelRequired": 3},
    {"id": "r4", "name": "Extra PTO Day", "icon": "\U0001F3D6️", "pointsCost": 2000,
     "category": "Time Off", "levelRequired": 3},
    {"id": "r5", "name": "Fleet Champion Jacket", "icon": "\U0001F9E5", "pointsCost": 3000,
     "category": "Merchandise", "levelRequired": 4},
    {"id": "r6", "name": "Year-End Bonus +5%", "icon": "\U0001F4B0", "pointsCost": 5000,
     "category": "Financial", "levelRequired": 5},
]


def build_rewards_catalog(total_points: float, level: int) -> list[dict]:
    return [
        {**r, "available": total_points >= r["pointsCost"] and level >= r["levelRequired"]}
        for r in _REWARDS
    ]


# ─── Cache ──────────────────────────────────────────────────

_gamification_cache: dict[str, dict] = {}
_CACHE_TTL = 60000  # 60 seconds (milliseconds)


# ─── Exported Functions ─────────────────────────────────────

def get_gamification_state(driver_id: str) -> Optional[dict]:
    now = _now_ms()
    cached = _gamification_cache.get(driver_id)
    if cached and (now - cached["timestamp"]) < _CACHE_TTL:
        return cached["state"]

    driver = next((d for d in seed_drivers if d.id == driver_id), None)
    if not driver:
        return None

    points = calculate_points(driver)
    total_points = points["totalPoints"]
    transactions = points["transactions"]
    level_info = get_level_info(total_points)
    streak = calculate_streak_days(driver_id)
    multiplier = get_streak_multiplier(streak)
    badges = calculate_badges(driver)
    daily_challenge = select_daily_challenge(driver_id)
    rewards = build_rewards_catalog(total_points, level_info["level"])

    # Weekly stats (last 7 days of transactions)
    week_ago = now - 7 * _DAY_MS
    week_transactions = [t for t in transactions
                         if _ms(_parse_dt(t["timestamp"])) > week_ago]
    weekly_stats = {
        "pointsEarned": sum(t["points"] for t in week_transactions if t["points"] > 0),
        "challengesCompleted": len([t for t in week_transactions if t["type"] == "challenge"]),
        "badgesEarned": len([t for t in week_transactions
                             if t["type"] == "badge"
                             and _ms(_parse_dt(t["timestamp"])) > week_ago]),
    }

    state = {
        "driverId": driver.id,
        "driverName": driver.name,
        "totalPoints": total_points,
        "level": level_info["level"],
        "levelTitle": level_info["title"],
        "pointsToNextLevel": level_info["pointsToNext"],
        "levelProgress": level_info["progress"],
        "currentStreak": streak,
        "streakMultiplier": multiplier,
        "badges": badges,
        "recentPoints": transactions[:20],  # Recent 20 transactions
        "dailyChallenge": daily_challenge,
        "weeklyStats": weekly_stats,
        "rewards": rewards,
    }

    _gamification_cache[driver_id] = {"state": state, "timestamp": now}
    return state


def get_driver_badges(driver_id: str) -> list[dict]:
    driver = next((d for d in seed_drivers if d.id == driver_id), None)
    if not driver:
        return []
    return calculate_badges(driver)


def get_points_history(driver_id: str) -> list[dict]:
    driver = next((d for d in seed_drivers if d.id == driver_id), None)
    if not driver:
        return []
    return calculate_points(driver)["transactions"]


def get_daily_challenge(driver_id: str) -> Optional[dict]:
    driver = next((d for d in seed_drivers if d.id == driver_id), None)
    if not driver:
        return None
    return select_daily_challenge(driver_id)


def get_rewards_catalog(driver_id: str) -> list[dict]:
    driver = next((d for d in seed_drivers if d.id == driver_id), None)
    if not driver:
        return []
    total_points = calculate_points(driver)["totalPoints"]
    level_info = get_level_info(total_points)
    return build_rewards_catalog(total_points, level_info["level"])


def check_challenge_progress(driver_id: str) -> Optional[dict]:
    driver = next((d for d in seed_drivers if d.id == driver_id), None)
    if not driver:
        return None
    # Clear cache to get fresh progress
    _gamification_cache.pop(driver_id, None)
    return select_daily_challenge(driver_id)
