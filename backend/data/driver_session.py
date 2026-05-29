"""
Driver Session & Load Management (Python port).

In-memory driver portal state: login/sessions, load assignments, dispatch
messages, safety scores, streaks, leaderboard rankings, HOS, action items
(with category/priority/missionId), and wellness check-ins.

Ported from existing-solution/backend/src/data/driver-session.ts with high
fidelity. Dict keys are kept EXACTLY camelCase to match the driver-portal
frontend's JSON contract (frontend/src/types/fleet.ts). Pure data + simple
module-level state, mirroring the TS Maps/counters.

NOTE: this mirrors the TS module's *behavior* but returns plain dicts (not
dataclasses) so the routes can serialize them directly. The seed data lives in
backend.data.seed_data (camelCase dataclass fields).
"""

from __future__ import annotations

import random
from datetime import timedelta, timezone
from typing import Optional

from backend.data.seed_data import (
    _now,
    _parse_dt,
    seed_drivers,
    seed_safety_events,
    seed_trip_days,
    seed_vehicles,
)

# Deterministic-ish RNG for the load/message generation. The TS used Math.random
# freely; we seed for stable demo data across boots (the routes don't depend on
# exact values, only shapes).
_rng = random.Random(1847)

_DAY_MS = 86400000


# ─── Time helpers (mimic JS Date.prototype.toISOString / Date.now) ───────────

def _iso(dt) -> str:
    """Format a datetime as JS toISOString(): UTC, milliseconds, Z."""
    dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def _now_iso() -> str:
    return _iso(_now())


def _now_ms() -> float:
    return _now().timestamp() * 1000.0


def _ms(dt) -> float:
    return dt.timestamp() * 1000.0


def _iso_from_ms(ms: float) -> str:
    from datetime import datetime

    return _iso(datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc))


# ─── In-memory stores (mirror the TS Maps/arrays/counters) ───────────────────

_active_sessions: dict[str, dict] = {}
_all_loads: list[dict] = []
_driver_messages: dict[str, list[dict]] = {}
_message_id_counter = 1
_driver_action_items: dict[str, list[dict]] = {}
_action_id_counter = 1
_driver_wellness_checkins: dict[str, list[dict]] = {}


# ─── Seed Data: Realistic city pairs ─────────────────────────────────────────

_CITY_PAIRS = [
    {"origin": {"city": "Toronto", "state": "ON", "address": "6900 Airport Rd, Mississauga"},
     "destination": {"city": "Montreal", "state": "QC", "address": "2100 Trans-Canada Hwy, Dorval"}, "distance": 541},
    {"origin": {"city": "Toronto", "state": "ON", "address": "1 York St, Toronto"},
     "destination": {"city": "Ottawa", "state": "ON", "address": "300 Coventry Rd, Ottawa"}, "distance": 450},
    {"origin": {"city": "Detroit", "state": "MI", "address": "1700 Fort St, Detroit"},
     "destination": {"city": "Chicago", "state": "IL", "address": "3901 S Ashland Ave, Chicago"}, "distance": 382},
    {"origin": {"city": "Toronto", "state": "ON", "address": "50 Eastern Ave, Toronto"},
     "destination": {"city": "Windsor", "state": "ON", "address": "1250 Walker Rd, Windsor"}, "distance": 376},
    {"origin": {"city": "Hamilton", "state": "ON", "address": "100 King St W, Hamilton"},
     "destination": {"city": "Buffalo", "state": "NY", "address": "500 Seneca St, Buffalo"}, "distance": 105},
    {"origin": {"city": "Montreal", "state": "QC", "address": "8585 Trans-Canada Hwy, Montreal"},
     "destination": {"city": "Quebec City", "state": "QC", "address": "770 Bouvier St, Quebec"}, "distance": 254},
    {"origin": {"city": "Toronto", "state": "ON", "address": "3600 Steeles Ave E, Markham"},
     "destination": {"city": "Sudbury", "state": "ON", "address": "280 Lorne St, Sudbury"}, "distance": 390},
    {"origin": {"city": "Kitchener", "state": "ON", "address": "1400 Weber St E, Kitchener"},
     "destination": {"city": "Toronto", "state": "ON", "address": "5800 Dixie Rd, Mississauga"}, "distance": 108},
    {"origin": {"city": "Chicago", "state": "IL", "address": "700 W 47th St, Chicago"},
     "destination": {"city": "Indianapolis", "state": "IN", "address": "3820 W Morris St, Indianapolis"}, "distance": 290},
    {"origin": {"city": "Toronto", "state": "ON", "address": "2900 Steeles Ave W, Concord"},
     "destination": {"city": "Thunder Bay", "state": "ON", "address": "500 Harbour Expy, Thunder Bay"}, "distance": 1370},
    {"origin": {"city": "London", "state": "ON", "address": "1680 Dundas St E, London"},
     "destination": {"city": "Toronto", "state": "ON", "address": "275 Front St E, Toronto"}, "distance": 191},
    {"origin": {"city": "Montreal", "state": "QC", "address": "1000 Rue de la Gauchetiere, Montreal"},
     "destination": {"city": "Moncton", "state": "NB", "address": "120 Mapleton Rd, Moncton"}, "distance": 1126},
    {"origin": {"city": "Detroit", "state": "MI", "address": "1 Auto Club Dr, Dearborn"},
     "destination": {"city": "Cleveland", "state": "OH", "address": "4800 Tiedeman Rd, Cleveland"}, "distance": 275},
    {"origin": {"city": "Toronto", "state": "ON", "address": "900 Derry Rd E, Mississauga"},
     "destination": {"city": "Barrie", "state": "ON", "address": "44 Cedar Pointe Dr, Barrie"}, "distance": 107},
    {"origin": {"city": "Brampton", "state": "ON", "address": "499 Main St S, Brampton"},
     "destination": {"city": "Kingston", "state": "ON", "address": "945 Midland Ave, Kingston"}, "distance": 284},
    {"origin": {"city": "Ottawa", "state": "ON", "address": "1355 Bank St, Ottawa"},
     "destination": {"city": "Toronto", "state": "ON", "address": "150 Consumers Rd, North York"}, "distance": 450},
    {"origin": {"city": "Buffalo", "state": "NY", "address": "200 Delaware Ave, Buffalo"},
     "destination": {"city": "Syracuse", "state": "NY", "address": "5801 Bridge St, Syracuse"}, "distance": 245},
    {"origin": {"city": "Windsor", "state": "ON", "address": "4555 Huron Church Rd, Windsor"},
     "destination": {"city": "Toronto", "state": "ON", "address": "1 Blue Jays Way, Toronto"}, "distance": 376},
]

_COMMODITIES = [
    "Dry Goods", "Auto Parts", "Building Materials", "Electronics",
    "Food & Beverage", "Paper Products", "Steel Coils", "Machinery",
    "Consumer Goods", "Pharmaceutical", "Agricultural Products", "Textiles",
    "Furniture", "Chemical Products", "Packaging Supplies",
]

_BROKERS = [
    {"name": "TQL Logistics", "phone": "(800) 580-3101"},
    {"name": "C.H. Robinson", "phone": "(855) 229-6128"},
    {"name": "Echo Global", "phone": "(800) 354-7993"},
    {"name": "XPO Logistics", "phone": "(844) 742-5976"},
    {"name": "Coyote Logistics", "phone": "(877) 626-9683"},
    {"name": "Transplace", "phone": "(866) 413-9266"},
    {"name": "Arrive Logistics", "phone": "(855) 454-6862"},
    {"name": "Redwood Logistics", "phone": "(844) 467-3396"},
]

_LOAD_STATUSES = [
    "assigned", "en_route", "at_pickup", "loaded", "in_transit", "at_delivery",
]


# ─── Initialization ──────────────────────────────────────────────────────────

def _generate_load_note(commodity: str, status: str) -> str:
    notes = {
        "assigned": [
            f"{commodity} shipment ready for pickup.",
            "Pre-loaded trailer at dock 12. Seal #48291.",
            "Contact shipper 30 min before arrival.",
        ],
        "en_route": [
            "Driver en route to shipper. On time.",
            "ETA on track. Check in at arrival.",
        ],
        "at_pickup": [
            "Driver checked in at shipper. Loading in progress.",
            "Waiting for dock assignment. Estimated 45 min.",
        ],
        "loaded": [
            "Loaded and sealed. BOL signed. Ready to roll.",
            "Loaded 24 pallets. Weight verified. Depart when ready.",
        ],
        "in_transit": [
            "In transit. Last check-in on schedule.",
            "Running 15 min ahead of schedule. Good weather conditions.",
            "Fuel stop planned at next travel center.",
        ],
        "at_delivery": [
            "At receiver. Waiting for dock door.",
            "Checked in at delivery. Unloading estimated 1 hour.",
        ],
    }
    pool = notes.get(status) or notes["assigned"]
    return pool[int(_rng.random() * len(pool))]


def _generate_loads() -> None:
    _all_loads.clear()
    drivers = seed_drivers if len(seed_drivers) > 0 else []
    if not drivers:
        return
    num_loads = min(max(15, int(len(drivers) * 0.6)), 20)

    now = _now_ms()
    for i in range(num_loads):
        driver = drivers[i % len(drivers)]
        pair = _CITY_PAIRS[i % len(_CITY_PAIRS)]
        commodity = _COMMODITIES[i % len(_COMMODITIES)]
        broker = _BROKERS[i % len(_BROKERS)]
        status = _LOAD_STATUSES[i % len(_LOAD_STATUSES)]

        pickup_offset = int(_rng.random() * 12 - 2) * 3600000  # -2 to +10 hours
        transit_hours = round(pair["distance"] / 80)  # ~80 km/h average
        delivery_offset = pickup_offset + transit_hours * 3600000

        _all_loads.append({
            "id": f"LD-{1000 + i}",
            "driverId": driver.id,
            "status": status,
            "origin": pair["origin"],
            "destination": pair["destination"],
            "pickupTime": _iso_from_ms(now + pickup_offset),
            "deliveryTime": _iso_from_ms(now + delivery_offset),
            "commodity": commodity,
            "weight": round(20000 + _rng.random() * 25000),
            "rate": round(1200 + pair["distance"] * 2.5 + _rng.random() * 500),
            "distance": pair["distance"],
            "broker": broker,
            "notes": _generate_load_note(commodity, status),
        })


def _generate_driver_messages() -> None:
    global _message_id_counter
    _driver_messages.clear()
    drivers = seed_drivers if len(seed_drivers) > 0 else []
    now = _now_ms()

    for driver in drivers:
        messages: list[dict] = []
        driver_load = next((l for l in _all_loads if l["driverId"] == driver.id), None)

        if driver_load:
            messages.append({
                "id": f"msg-{_message_id_counter}",
                "from": "dispatch",
                "text": (
                    f"Load {driver_load['id']} assigned: {driver_load['origin']['city']} to "
                    f"{driver_load['destination']['city']}. {driver_load['commodity']}, "
                    f"{driver_load['weight']:,} lbs."
                ),
                "timestamp": _iso_from_ms(now - 4 * 3600000),
                "read": True,
            })
            _message_id_counter += 1

        messages.append({
            "id": f"msg-{_message_id_counter}",
            "from": "system",
            "text": "Daily check-in reminder: Please confirm your availability and vehicle condition before departure.",
            "timestamp": _iso_from_ms(now - 6 * 3600000),
            "read": True,
        })
        _message_id_counter += 1

        if _rng.random() > 0.5:
            messages.append({
                "id": f"msg-{_message_id_counter}",
                "from": "system",
                "text": (
                    "Weather Advisory: Freezing rain expected along Highway 401 corridor between "
                    "Kingston and Montreal. Reduce speed and increase following distance."
                ),
                "timestamp": _iso_from_ms(now - 2 * 3600000),
                "read": _rng.random() > 0.3,
            })
            _message_id_counter += 1

        if driver_load and _rng.random() > 0.4:
            messages.append({
                "id": f"msg-{_message_id_counter}",
                "from": "dispatch",
                "text": (
                    f"Hey {driver.firstName}, just checking in on Load {driver_load['id']}. "
                    "Any issues? Let us know if you need anything."
                ),
                "timestamp": _iso_from_ms(now - 1 * 3600000),
                "read": False,
            })
            _message_id_counter += 1

        if driver.riskProfile in ("high", "critical"):
            messages.append({
                "id": f"msg-{_message_id_counter}",
                "from": "system",
                "text": (
                    "Safety Reminder: Your recent driving events have been flagged for review. "
                    "Please focus on maintaining safe following distances and speed compliance."
                ),
                "timestamp": _iso_from_ms(now - 8 * 3600000),
                "read": False,
            })
            _message_id_counter += 1

        # Sort by timestamp descending
        messages.sort(key=lambda m: _ms(_parse_dt(m["timestamp"])), reverse=True)
        _driver_messages[driver.id] = messages


# ─── Score & Ranking Calculations ────────────────────────────────────────────

def calculate_safety_score(driver_id: str) -> int:
    cutoff = _now() - timedelta(days=30)
    events30 = [e for e in seed_safety_events
                if e.driverId == driver_id and _parse_dt(e.dateTime) > cutoff]
    trips30 = [t for t in seed_trip_days
               if t.driverId == driver_id and _parse_dt(t.date + "T00:00:00Z") > cutoff]

    total_distance = sum(t.totalDistance for t in trips30)
    if total_distance == 0:
        return 85  # Default for drivers with no data

    severity_weights = {"low": 1, "medium": 2, "high": 4, "critical": 8}
    weighted_events = sum(severity_weights.get(e.severity, 1) for e in events30)
    weighted_rate = (weighted_events / total_distance) * 1000
    return max(0, min(100, round(100 - weighted_rate * 3)))


def calculate_streak_days(driver_id: str) -> int:
    events = [e for e in seed_safety_events
              if e.driverId == driver_id and e.severity in ("high", "critical")]
    events.sort(key=lambda e: _ms(_parse_dt(e.dateTime)), reverse=True)

    if not events:
        return 90  # No critical/high events in 90 days

    last_bad_event = _parse_dt(events[0].dateTime)
    days_since = int((_now_ms() - _ms(last_bad_event)) // _DAY_MS)
    return days_since


def calculate_today_events(driver_id: str) -> int:
    today_start = _now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
    return len([e for e in seed_safety_events
                if e.driverId == driver_id and _parse_dt(e.dateTime) >= today_start])


# ─── Leaderboard (60s cache) ─────────────────────────────────────────────────

_cached_leaderboard: list[dict] = []
_leaderboard_cache_time = 0.0


def _build_leaderboard() -> list[dict]:
    global _cached_leaderboard, _leaderboard_cache_time
    now = _now_ms()
    if now - _leaderboard_cache_time < 60000 and _cached_leaderboard:
        return _cached_leaderboard

    drivers = seed_drivers if len(seed_drivers) > 0 else []
    rankings = [{
        "driverId": d.id,
        "name": d.name,
        "employeeNumber": d.employeeNumber,
        "score": calculate_safety_score(d.id),
        "rank": 0,
        "streak": calculate_streak_days(d.id),
    } for d in drivers]

    # Sort by score desc, then streak desc (higher = safer = better rank)
    rankings.sort(key=lambda r: (r["score"], r["streak"]), reverse=True)
    for i, r in enumerate(rankings):
        r["rank"] = i + 1

    _cached_leaderboard = rankings
    _leaderboard_cache_time = now
    return rankings


# ─── Public API ──────────────────────────────────────────────────────────────

def init_driver_sessions() -> None:
    """Generate loads, messages, and starter action items. Idempotent-ish:
    safe to call once at startup (mirrors initDriverSessions in the TS)."""
    _generate_loads()
    _generate_driver_messages()

    for driver in seed_drivers:
        if driver.riskProfile in ("high", "critical"):
            add_driver_action_item(
                driver.id, "Complete defensive driving refresher course", "system",
                category="coaching", priority="high")
            add_driver_action_item(
                driver.id, "Review safety event footage from this week", "system",
                category="safety", priority="high")
        add_driver_action_item(
            driver.id, "Submit daily vehicle inspection report", "system",
            category="general", priority="medium")
        if _rng.random() > 0.5:
            add_driver_action_item(
                driver.id, "Update emergency contact information", "system",
                category="general", priority="low")


def login_driver(driver_id: str) -> Optional[dict]:
    driver = next((d for d in seed_drivers if d.id == driver_id), None)
    if not driver:
        return None

    vehicle = next((v for v in seed_vehicles if v.id == driver.vehicleId), None)
    load = next((l for l in _all_loads
                 if l["driverId"] == driver_id and l["status"] != "delivered"), None)
    messages = _driver_messages.get(driver_id, [])
    leaderboard = _build_leaderboard()
    ranking = next((r for r in leaderboard if r["driverId"] == driver_id), None)

    session = {
        "driverId": driver.id,
        "driverName": driver.name,
        "employeeNumber": driver.employeeNumber,
        "vehicleId": driver.vehicleId,
        "vehicleName": vehicle.name if vehicle else driver.vehicleId,
        "loginTime": _now_iso(),
        "currentLoad": load,
        "recentMessages": messages[:10],
        "safetyScore": calculate_safety_score(driver_id),
        "streakDays": calculate_streak_days(driver_id),
        "todayEvents": calculate_today_events(driver_id),
        "weeklyRank": ranking["rank"] if ranking else 0,
    }

    _active_sessions[driver_id] = session
    return session


def login_driver_with_pin(employee_number: str, pin: str) -> Optional[dict]:
    driver = next((d for d in seed_drivers if d.employeeNumber == employee_number), None)
    if not driver or driver.pin != pin:
        return None
    return login_driver(driver.id)


def get_driver_session(driver_id: str) -> Optional[dict]:
    existing = _active_sessions.get(driver_id)
    if existing:
        return existing
    return login_driver(driver_id)


def get_active_loads() -> list[dict]:
    return [l for l in _all_loads if l["status"] != "delivered"]


def get_all_loads() -> list[dict]:
    return list(_all_loads)


def get_driver_load(driver_id: str) -> Optional[dict]:
    return next((l for l in _all_loads
                 if l["driverId"] == driver_id and l["status"] != "delivered"), None)


def update_load_status(load_id: str, status: str) -> Optional[dict]:
    load = next((l for l in _all_loads if l["id"] == load_id), None)
    if not load:
        return None

    load["status"] = status
    load["notes"] = _generate_load_note(load["commodity"], status)

    session = _active_sessions.get(load["driverId"])
    if session:
        session["currentLoad"] = None if status == "delivered" else load

    add_dispatch_message(load["driverId"], {
        "from": "system",
        "text": f'Load {load["id"]} status updated to "{status.replace("_", " ")}".',
        "read": False,
    })

    return load


def add_dispatch_message(driver_id: str, message: dict) -> None:
    """message is a dict with at least {from, text, read}; id+timestamp added here."""
    global _message_id_counter
    msg = {
        "id": f"msg-{_message_id_counter}",
        "timestamp": _now_iso(),
        **message,
    }
    _message_id_counter += 1

    existing = _driver_messages.get(driver_id, [])
    existing.insert(0, msg)  # newest first
    _driver_messages[driver_id] = existing

    session = _active_sessions.get(driver_id)
    if session:
        session["recentMessages"] = existing[:10]


def get_driver_messages(driver_id: str) -> list[dict]:
    return _driver_messages.get(driver_id, [])


def get_driver_leaderboard() -> list[dict]:
    return _build_leaderboard()


# ─── Action Items (with category/priority/missionId) ─────────────────────────

def get_driver_action_items(driver_id: str) -> list[dict]:
    """Pending action items only (matches the TS getDriverActionItems)."""
    return [a for a in _driver_action_items.get(driver_id, []) if a["status"] == "pending"]


def add_driver_action_item(
    driver_id: str,
    text: str,
    source: str = "system",
    *,
    category: str = "general",
    priority: str = "medium",
    mission_id: Optional[str] = None,
) -> dict:
    global _action_id_counter
    item = {
        "id": f"action-{_action_id_counter}",
        "driverId": driver_id,
        "text": text,
        "source": source,
        "status": "pending",
        "category": category,
        "priority": priority,
        "createdAt": _now_iso(),
        "missionId": mission_id,
    }
    _action_id_counter += 1
    existing = _driver_action_items.get(driver_id, [])
    existing.insert(0, item)
    _driver_action_items[driver_id] = existing
    return item


def add_action_item(driver_id: str, item: dict) -> dict:
    """Mission -> driver action-item sync hook.

    Accepts a pre-shaped action-item dict (e.g. produced by the mission system)
    and registers it for the driver. Missing fields are defaulted to mirror the
    ActionItem contract. This is the function the mission runner should call when
    syncing coaching/wellness/safety plans to a specific driver.
    """
    global _action_id_counter
    shaped = {
        "id": item.get("id") or f"action-{_action_id_counter}",
        "driverId": driver_id,
        "text": item.get("text", ""),
        "source": item.get("source", "mission"),
        "status": item.get("status", "pending"),
        "category": item.get("category", "general"),
        "priority": item.get("priority", "medium"),
        "createdAt": item.get("createdAt") or _now_iso(),
        "missionId": item.get("missionId"),
    }
    if "completedAt" in item:
        shaped["completedAt"] = item["completedAt"]
    if "steps" in item:
        shaped["steps"] = item["steps"]
    if not item.get("id"):
        _action_id_counter += 1
    existing = _driver_action_items.get(driver_id, [])
    existing.insert(0, shaped)
    _driver_action_items[driver_id] = existing
    return shaped


def get_all_driver_action_items(driver_id: str) -> list[dict]:
    return _driver_action_items.get(driver_id, [])


def complete_driver_action_item(driver_id: str, action_id: str) -> Optional[dict]:
    items = _driver_action_items.get(driver_id)
    if not items:
        return None
    item = next((a for a in items if a["id"] == action_id), None)
    if not item:
        return None
    item["status"] = "completed"
    item["completedAt"] = _now_iso()
    return item


def dismiss_driver_action_item(driver_id: str, action_id: str) -> Optional[dict]:
    items = _driver_action_items.get(driver_id)
    if not items:
        return None
    item = next((a for a in items if a["id"] == action_id), None)
    if not item:
        return None
    item["status"] = "dismissed"
    return item


# ─── HOS (Hours of Service) ──────────────────────────────────────────────────

def get_driver_hos(driver_id: str) -> Optional[dict]:
    driver = next((d for d in seed_drivers if d.id == driver_id), None)
    if not driver:
        return None

    today_start = _now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
    today_start_date = today_start.astimezone(timezone.utc).strftime("%Y-%m-%d")

    today_trips = [t for t in seed_trip_days
                   if t.driverId == driver_id and t.date >= today_start_date]

    today_driving_minutes = sum(t.drivingHours * 60 for t in today_trips)
    hour = _now().astimezone().hour
    simulated_driving_minutes = (
        today_driving_minutes if today_driving_minutes > 0
        else min(hour * 30 + int(_rng.random() * 60), 600)
    )

    MAX_DRIVE_MINUTES = 11 * 60
    MAX_DUTY_MINUTES = 14 * 60
    MAX_CYCLE_MINUTES = 70 * 60
    BREAK_INTERVAL_MINUTES = 8 * 60

    on_duty_minutes = int(simulated_driving_minutes * 1.2)

    seven_days_ago = _now() - timedelta(days=7)
    seven_cutoff_date = seven_days_ago.strftime("%Y-%m-%d")
    week_trips = [t for t in seed_trip_days
                  if t.driverId == driver_id and t.date >= seven_cutoff_date]
    week_driving_minutes = sum(t.drivingHours * 60 for t in week_trips) + simulated_driving_minutes

    drive_time_remaining = max(0, MAX_DRIVE_MINUTES - simulated_driving_minutes)
    on_duty_time_remaining = max(0, MAX_DUTY_MINUTES - on_duty_minutes)
    cycle_time_remaining = max(0, MAX_CYCLE_MINUTES - week_driving_minutes)

    minutes_since_last_break = min(simulated_driving_minutes, BREAK_INTERVAL_MINUTES)
    next_break_required = max(0, BREAK_INTERVAL_MINUTES - minutes_since_last_break)

    last_break_ms = _now_ms() - minutes_since_last_break * 60000
    last_break_time = _iso_from_ms(last_break_ms)

    current_duty_status = "off_duty"
    if 6 <= hour < 20:
        if simulated_driving_minutes > 0 and drive_time_remaining > 0:
            current_duty_status = "driving"
        else:
            current_duty_status = "on_duty"
    elif hour >= 20 or hour < 6:
        current_duty_status = "sleeper"

    violations: list[str] = []
    if drive_time_remaining <= 0:
        violations.append("11-hour driving limit reached")
    if on_duty_time_remaining <= 0:
        violations.append("14-hour duty window exceeded")
    if cycle_time_remaining <= 0:
        violations.append("70-hour/8-day cycle limit reached")
    if next_break_required <= 0 and simulated_driving_minutes >= BREAK_INTERVAL_MINUTES:
        violations.append("30-minute break required")

    return {
        "driveTimeRemaining": round(drive_time_remaining),
        "onDutyTimeRemaining": round(on_duty_time_remaining),
        "cycleTimeRemaining": round(cycle_time_remaining),
        "nextBreakRequired": round(next_break_required),
        "lastBreakTime": last_break_time,
        "currentDutyStatus": current_duty_status,
        "violations": violations,
    }


# ─── Wellness Check-In ───────────────────────────────────────────────────────

def submit_wellness_checkin(driver_id: str, mood: str, note: Optional[str] = None) -> dict:
    checkin = {
        "mood": mood,
        "timestamp": _now_iso(),
        "note": note,
    }

    existing = _driver_wellness_checkins.get(driver_id, [])
    existing.insert(0, checkin)
    _driver_wellness_checkins[driver_id] = existing

    messages = {
        "great": "Awesome! That positive energy keeps you sharp on the road. Keep it up!",
        "ok": "Steady and focused - that's a great mindset for driving. Have a good shift!",
        "tired": "Thanks for being honest. Consider a short break or a coffee stop soon. Your safety comes first.",
        "stressed": "We hear you. Take a few deep breaths. If you need to talk, Tasha is here anytime.",
        "not_good": (
            "Your wellbeing matters most. If you need support, talk to Tasha or call the driver "
            "assistance line at 1-800-555-0199."
        ),
    }

    return {"message": messages[mood], "checkin": checkin}


def get_wellness_trend(driver_id: str) -> dict:
    checkins = _driver_wellness_checkins.get(driver_id, [])

    week_ago = _now_ms() - 7 * _DAY_MS
    week_checkins = [c for c in checkins if _ms(_parse_dt(c["timestamp"])) >= week_ago]

    mood_scores = {"great": 5, "ok": 4, "tired": 2, "stressed": 2, "not_good": 1}
    avg_score = (
        sum(mood_scores[c["mood"]] for c in week_checkins) / len(week_checkins)
        if week_checkins else 4
    )

    suggestion = None
    if avg_score >= 4:
        weekly_average = "positive"
    elif avg_score >= 3:
        weekly_average = "neutral"
    else:
        weekly_average = "concerning"
        suggestion = (
            "Your recent check-ins suggest you may be going through a tough time. Consider talking "
            "to Tasha or reaching out to your support network."
        )

    return {"checkins": checkins[:14], "weeklyAverage": weekly_average, "suggestion": suggestion}


def get_latest_wellness_checkin(driver_id: str) -> Optional[dict]:
    checkins = _driver_wellness_checkins.get(driver_id, [])
    return checkins[0] if checkins else None


# Initialize on import so GET routes work for any driver id without an explicit
# server bootstrap step (mirrors the TS initDriverSessions() call at startup).
init_driver_sessions()
