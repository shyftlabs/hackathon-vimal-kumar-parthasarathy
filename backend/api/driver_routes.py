"""
Driver Portal REST routes (Python port of the /api/driver/* handlers from
existing-solution/backend/src/index.ts).

A FastAPI APIRouter (`router`) implementing the 22 driver-portal routes. Response
shapes match the original Express handlers exactly and the frontend contract in
frontend/src/types/fleet.ts (camelCase keys, plain dicts/lists).

State helpers live in backend.data.driver_session. Gamification delegates to
backend.scoring.gamification. Risk/wellness/predictive data is reused from the
existing scoring engines. Dispatch-call routes are STUBS (real Twilio comes in a
later phase).
"""

from __future__ import annotations


from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.data.seed_data import _now, _parse_dt, get_driver
from backend.data.driver_session import (
    complete_driver_action_item,
    dismiss_driver_action_item,
    get_driver_action_items,
    get_driver_hos,
    get_driver_leaderboard,
    get_driver_load,
    get_driver_messages,
    get_driver_session,
    get_wellness_trend,
    login_driver,
    login_driver_with_pin,
    submit_wellness_checkin,
    update_load_status,
)
from backend.scoring.gamification import (
    check_challenge_progress,
    get_daily_challenge,  # noqa: F401  (kept for parity; route uses state directly)
    get_driver_badges,
    get_gamification_state,
    get_points_history,
    get_rewards_catalog,
)
from backend.scoring.driver_risk import calculate_driver_risk
from backend.scoring.predictive_safety import (
    calculate_pre_shift_risk,
    get_dangerous_corridors,
)
from backend.scoring.wellness_predictor import predict_wellness

router = APIRouter()


def _not_found(message: str) -> JSONResponse:
    return JSONResponse(status_code=404, content={"error": message})


def _bad_request(message: str) -> JSONResponse:
    return JSONResponse(status_code=400, content={"error": message})


def _unauthorized(message: str) -> JSONResponse:
    return JSONResponse(status_code=401, content={"error": message})


def _server_error(message: str) -> JSONResponse:
    return JSONResponse(status_code=500, content={"error": message})


# ─── Login ───────────────────────────────────────────────────────────────────

@router.post("/api/driver/login")
async def driver_login(req: Request):
    try:
        body = await req.json()
    except Exception:
        body = {}
    driver_id = body.get("driverId")
    employee_number = body.get("employeeNumber")
    pin = body.get("pin")

    try:
        # PIN-based login
        if employee_number and pin:
            session = login_driver_with_pin(employee_number, pin)
            if not session:
                return _unauthorized("Invalid employee number or PIN")
            return session

        # Legacy driverId login
        if not driver_id:
            return _bad_request("employeeNumber and pin are required")
        session = login_driver(driver_id)
        if not session:
            return _not_found("Driver not found")
        return session
    except Exception:
        return _server_error("Failed to login driver")


# ─── Dashboard / Load / Messages ─────────────────────────────────────────────

@router.get("/api/driver/leaderboard")
def driver_leaderboard():
    try:
        return get_driver_leaderboard()
    except Exception:
        return _server_error("Failed to get driver leaderboard")


@router.get("/api/driver/{driver_id}/dashboard")
def driver_dashboard(driver_id: str):
    try:
        session = get_driver_session(driver_id)
        if not session:
            return _not_found("Driver not found")
        return session
    except Exception:
        return _server_error("Failed to get driver dashboard")


@router.get("/api/driver/{driver_id}/load")
def driver_load(driver_id: str):
    try:
        load = get_driver_load(driver_id)
        if not load:
            return {"hasLoad": False, "message": "No active load assigned."}
        return {"hasLoad": True, "load": load}
    except Exception:
        return _server_error("Failed to get driver load")


@router.put("/api/driver/{driver_id}/load/status")
async def driver_load_status(driver_id: str, req: Request):
    try:
        try:
            body = await req.json()
        except Exception:
            body = {}
        status = body.get("status")
        load_id = body.get("loadId")
        if not status:
            return _bad_request("status is required")
        allowed = ["assigned", "picked_up", "in_transit", "delivered", "completed"]
        if status not in allowed:
            return _bad_request("Invalid status")

        target_load_id = load_id
        if not target_load_id:
            load = get_driver_load(driver_id)
            if not load:
                return _not_found("No active load found for this driver")
            target_load_id = load["id"]

        updated = update_load_status(target_load_id, status)
        if not updated:
            return _not_found("Load not found")
        return updated
    except Exception:
        return _server_error("Failed to update load status")


@router.get("/api/driver/{driver_id}/messages")
def driver_messages(driver_id: str):
    try:
        return get_driver_messages(driver_id)
    except Exception:
        return _server_error("Failed to get driver messages")


# ─── Pre-Shift Briefing ──────────────────────────────────────────────────────

_FOCUS_AREA_MAP = {
    "harsh_braking": "Watch following distance - ease off the gas 3-4 seconds earlier",
    "speeding": "Mind your speed today - set cruise control on highways",
    "distracted_driving": "Secure your phone before departure - stay focused",
    "drowsy_driving": "Stay alert - take breaks every 2 hours, hydrate often",
    "lane_departure": "Check your lane position regularly - adjust mirrors before departure",
    "tailgating": "Maintain 4-second following distance at all speeds",
    "harsh_acceleration": "Smooth acceleration from stops - anticipate traffic flow",
    "seatbelt": "Buckle up before starting the engine",
    "rolling_stop": "Full stops at all intersections - no rolling through",
    "idle_excessive": "Minimize idling - turn off for stops longer than 2 minutes",
}

_WEATHER_CONDITIONS = [
    {"condition": "Clear skies", "temp": 45, "advisory": None},
    {"condition": "Partly cloudy", "temp": 52, "advisory": None},
    {"condition": "Light rain", "temp": 48, "advisory": "Wet roads - increase following distance"},
    {"condition": "Overcast", "temp": 42, "advisory": None},
    {"condition": "Light rain", "temp": 38, "advisory": "Wet roads ahead - reduce speed in curves"},
    {"condition": "Clear skies", "temp": 55, "advisory": None},
    {"condition": "Fog", "temp": 35, "advisory": "Low visibility - use fog lights, reduce speed"},
    {"condition": "Snow flurries", "temp": 28, "advisory": "Slippery conditions possible - extra caution on bridges"},
    {"condition": "Partly cloudy", "temp": 50, "advisory": None},
    {"condition": "Heavy rain", "temp": 44, "advisory": "Heavy rain expected - reduce speed, increase following distance"},
    {"condition": "Clear skies", "temp": 58, "advisory": None},
    {"condition": "Thunderstorms", "temp": 62, "advisory": "Thunderstorms forecast - pull over if visibility drops below 200ft"},
    {"condition": "Overcast", "temp": 40, "advisory": None},
    {"condition": "Clear skies", "temp": 48, "advisory": None},
]


@router.get("/api/driver/{driver_id}/pre-shift-briefing")
def driver_pre_shift_briefing(driver_id: str):
    try:
        driver = get_driver(driver_id)
        if not driver:
            return _not_found("Driver not found")

        pre_shift = calculate_pre_shift_risk(driver_id)
        driver_risk = calculate_driver_risk(driver_id)
        wellness = predict_wellness(driver_id)
        session = get_driver_session(driver_id)
        dangerous_zones = get_dangerous_corridors()

        risk_level = (pre_shift or {}).get("riskLevel") or "low"
        risk_score = (pre_shift or {}).get("riskScore") or 0

        now_local = _now().astimezone()
        hour = now_local.hour
        time_greeting = "Good morning" if hour < 12 else "Good afternoon" if hour < 17 else "Good evening"
        streak_days = (session or {}).get("streakDays") or 0
        greeting = f"{time_greeting}, {driver.firstName}!"
        if streak_days >= 30:
            greeting += f" Incredible {streak_days}-day safe streak!"
        elif streak_days >= 14:
            greeting += f" Amazing {streak_days}-day safe streak going!"
        elif streak_days >= 7:
            greeting += f" Nice {streak_days}-day streak - keep it up!"
        elif streak_days >= 3:
            greeting += f" {streak_days} days safe and counting!"
        else:
            greeting += " Let's make today a safe one."

        focus_areas: list[str] = []
        if driver_risk and driver_risk.get("topEventTypes"):
            for evt in driver_risk["topEventTypes"][:3]:
                tip = _FOCUS_AREA_MAP.get(evt["type"])
                if tip:
                    focus_areas.append(tip)
        if not focus_areas:
            focus_areas.extend(["Maintain safe following distance", "Stay within speed limits"])

        if wellness and wellness.get("burnoutRisk") == "high":
            focus_areas.append("Take extra rest breaks today - your fatigue indicators are elevated")
        elif wellness and wellness.get("avgRestHours", 0) < 8:
            focus_areas.append("You had limited rest - stay extra alert today")

        # Deterministic weather based on day of year (mimics JS getFullYear + day calc)
        start_of_year = now_local.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        day_of_year = int((now_local.timestamp() - (start_of_year.timestamp() - 86400)) // 86400)
        weather = _WEATHER_CONDITIONS[day_of_year % len(_WEATHER_CONDITIONS)]

        route_hazards: list[str] = []
        for zone in dangerous_zones[:3]:
            route_hazards.append(
                f"High {zone['topEventType'].replace('_', ' ')} area near "
                f"({zone['latitude']:.1f}°, {zone['longitude']:.1f}°) - "
                f"{zone['eventCount']} recent events"
            )

        if risk_level in ("critical", "high"):
            motivational = "Take it steady today. Your safety is the top priority. We believe in you."
        elif streak_days >= 30:
            motivational = f"{streak_days} days of excellence! You're an inspiration to the entire fleet."
        elif streak_days >= 14:
            motivational = "Your consistency is paying off. Keep this momentum going!"
        elif streak_days >= 7:
            motivational = "One week strong! Every safe mile counts. You're building something great."
        else:
            motivational = "Every journey starts with a single safe mile. Let's make today count!"

        if streak_days >= 30:
            streak_status = f"{streak_days} days strong! You've earned Monthly Master! Can you reach 60?"
        elif streak_days >= 14:
            streak_status = f"{streak_days} days! {30 - streak_days} more for the Monthly Master badge!"
        elif streak_days >= 7:
            streak_status = f"{streak_days} days! {14 - streak_days} more for the Fortnight Fighter badge!"
        else:
            streak_status = f"{streak_days} days. {7 - streak_days} more for the Week Warrior badge!"

        return {
            "riskLevel": risk_level,
            "riskScore": risk_score,
            "greeting": greeting,
            "focusAreas": focus_areas,
            "weather": {
                "condition": weather["condition"],
                "temp": weather["temp"],
                "advisory": weather["advisory"] or None,
            },
            "routeHazards": route_hazards,
            "motivational": motivational,
            "streakStatus": streak_status,
            "safetyScore": (session or {}).get("safetyScore") or 0,
            "streakDays": streak_days,
            "factors": (pre_shift or {}).get("factors") or [],
        }
    except Exception:
        return _server_error("Failed to generate pre-shift briefing")


# ─── HOS ─────────────────────────────────────────────────────────────────────

@router.get("/api/driver/{driver_id}/hos")
def driver_hos(driver_id: str):
    try:
        result = get_driver_hos(driver_id)
        if not result:
            return _not_found("Driver not found")
        return result
    except Exception:
        return _server_error("Failed to get HOS status")


# ─── Wellness Check-In ───────────────────────────────────────────────────────

@router.post("/api/driver/{driver_id}/wellness-checkin")
async def driver_wellness_checkin(driver_id: str, req: Request):
    try:
        try:
            body = await req.json()
        except Exception:
            body = {}
        mood = body.get("mood")
        note = body.get("note")
        if not mood:
            return _bad_request("mood is required")
        valid_moods = ["great", "ok", "tired", "stressed", "not_good"]
        if mood not in valid_moods:
            return _bad_request("Invalid mood")
        return submit_wellness_checkin(driver_id, mood, note)
    except Exception:
        return _server_error("Failed to submit wellness check-in")


@router.get("/api/driver/{driver_id}/wellness-trend")
def driver_wellness_trend(driver_id: str):
    try:
        return get_wellness_trend(driver_id)
    except Exception:
        return _server_error("Failed to get wellness trend")


# ─── Gamification ────────────────────────────────────────────────────────────

@router.get("/api/driver/{driver_id}/gamification")
def driver_gamification(driver_id: str):
    try:
        state = get_gamification_state(driver_id)
        if not state:
            return _not_found("Driver not found")
        return state
    except Exception:
        return _server_error("Failed to get gamification state")


@router.get("/api/driver/{driver_id}/points-history")
def driver_points_history(driver_id: str):
    try:
        return get_points_history(driver_id)
    except Exception:
        return _server_error("Failed to get points history")


@router.get("/api/driver/{driver_id}/badges")
def driver_badges(driver_id: str):
    try:
        return get_driver_badges(driver_id)
    except Exception:
        return _server_error("Failed to get badges")


@router.get("/api/driver/{driver_id}/rewards")
def driver_rewards(driver_id: str):
    try:
        return get_rewards_catalog(driver_id)
    except Exception:
        return _server_error("Failed to get rewards")


@router.post("/api/driver/{driver_id}/challenge/check")
def driver_challenge_check(driver_id: str):
    try:
        challenge = check_challenge_progress(driver_id)
        if not challenge:
            return {"message": "No active challenge"}
        return challenge
    except Exception:
        return _server_error("Failed to check challenge progress")


# ─── Action Items ────────────────────────────────────────────────────────────

@router.get("/api/driver/{driver_id}/actions")
def driver_actions(driver_id: str):
    try:
        return get_driver_action_items(driver_id)
    except Exception:
        return _server_error("Failed to get action items")


@router.post("/api/driver/{driver_id}/actions/{action_id}/complete")
def driver_action_complete(driver_id: str, action_id: str):
    try:
        item = complete_driver_action_item(driver_id, action_id)
        if not item:
            return _not_found("Action item not found")
        return item
    except Exception:
        return _server_error("Failed to complete action item")


@router.post("/api/driver/{driver_id}/actions/{action_id}/dismiss")
def driver_action_dismiss(driver_id: str, action_id: str):
    try:
        item = dismiss_driver_action_item(driver_id, action_id)
        if not item:
            return _not_found("Action item not found")
        return item
    except Exception:
        return _server_error("Failed to dismiss action item")


# ─── Training (mission-synced coaching programs) ─────────────────────────────

def _get_completed_missions() -> list[dict]:
    """Read completed missions from the mission store if available.

    Missions are implemented in a later phase. Until then this returns an empty
    list, so /training yields []. When the mission system lands, this should pull
    from the global mission store (mirrors getAllMissions().completed in the TS).
    """
    try:
        from backend.missions import get_all_missions  # type: ignore

        result = get_all_missions() or {}
        return result.get("completed", [])
    except Exception:
        return []


@router.get("/api/driver/{driver_id}/training")
def driver_training(driver_id: str):
    try:
        programs: list[dict] = []
        for mission in _get_completed_missions():
            if mission.get("status") != "complete":
                continue

            mtype = mission.get("type")
            data = mission.get("data", {}) or {}

            if mtype == "coaching_sweep":
                plans = data.get("driverPlans") or []
                driver_plan = next((p for p in plans if p.get("driverId") == driver_id), None)
                if driver_plan:
                    programs.append({
                        "missionId": mission.get("missionId"),
                        "missionType": mtype,
                        "source": mission.get("displayName"),
                        "completedAt": mission.get("completedAt"),
                        "driverName": driver_plan.get("driverName"),
                        "riskScore": driver_plan.get("riskScore"),
                        "tier": driver_plan.get("tier"),
                        "topIssues": driver_plan.get("topIssues"),
                        "coachingActions": driver_plan.get("coachingActions"),
                        "timeline": driver_plan.get("timeline"),
                        "expectedImprovement": driver_plan.get("expectedImprovement"),
                        "estimatedSavings": driver_plan.get("estimatedSavings"),
                        "wellnessScore": driver_plan.get("wellnessScore"),
                        "burnoutRisk": driver_plan.get("burnoutRisk"),
                    })
            elif mtype == "safety_investigation" and data.get("driverId") == driver_id:
                programs.append({
                    "missionId": mission.get("missionId"),
                    "missionType": mtype,
                    "source": mission.get("displayName"),
                    "completedAt": mission.get("completedAt"),
                    "driverName": data.get("driverName"),
                    "riskScore": data.get("riskScore"),
                    "rootCauses": data.get("rootCauses"),
                    "coachingActions": mission.get("recommendations"),
                    "timeline": [],
                    "expectedImprovement": "Focus on root causes for measurable improvement",
                    "estimatedSavings": "",
                })

        # Sort newest first (by completedAt timestamp)
        def _completed_ms(p):
            ts = p.get("completedAt")
            try:
                return _parse_dt(ts).timestamp() if ts else 0
            except Exception:
                return 0

        programs.sort(key=_completed_ms, reverse=True)
        return programs
    except Exception:
        return _server_error("Failed to get training programs")


# ─── Dispatch Call (real two-way Twilio call) ────────────────────────────────

@router.post("/api/driver/{driver_id}/dispatch-call")
async def driver_dispatch_call(driver_id: str, req: Request):
    from backend.voice import twilio_dispatch
    body = {}
    try:
        body = await req.json()
    except Exception:
        pass
    intent = (body.get("intent") or "").strip() or "a load update"
    return twilio_dispatch.start_call(driver_id, intent)


@router.get("/api/driver/{driver_id}/dispatch-call/{call_id}/status")
def driver_dispatch_call_status(driver_id: str, call_id: str):
    from backend.voice import twilio_dispatch
    return twilio_dispatch.call_status(driver_id, call_id)
