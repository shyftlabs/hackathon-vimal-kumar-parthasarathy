"""
FleetShield AI — FastAPI REST server.

Serves the SAME REST contract the existing Next.js frontend expects
(frontend/src/types/fleet.ts), backed by the rebuilt Python data + scoring
engines under backend/data and backend/scoring.

This reimplements the *fleet/operator* data routes from the original Express
server (existing-solution/backend/src/index.ts). Driver-portal, chat/assistant,
voice/TTS, Twilio, and PDF report routes are intentionally NOT implemented here
(later phases) — except the small stubs explicitly requested.

Run target:
    uvicorn backend.api.server:app --port 3000

Responses are PLAIN dicts/lists. Our engines already emit camelCase keys that
match the frontend contract; dataclasses are serialized with dataclasses.asdict.
We deliberately do NOT use Pydantic response models (which could drop/rename
keys).
"""

from __future__ import annotations

import os
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv

load_dotenv()  # load .env before reading any settings (CORS origins, etc.)

from fastapi import FastAPI, Query  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402

# ─── Data layer ───────────────────────────────────────────────────────────────
from backend.data.seed_data import (
    get_driver_stats,
    get_fleet_summary,
    seed_drivers,
    seed_safety_events,
    seed_vehicles,
)
from backend.data import live_fleet

# ─── Scoring engines ──────────────────────────────────────────────────────────
from backend.scoring.driver_risk import (
    calculate_all_driver_risks,
    calculate_driver_risk,
)
from backend.scoring.insurance_score import calculate_insurance_score
from backend.scoring.wellness_predictor import (
    get_fleet_wellness_summary,
    predict_all_wellness,
    predict_wellness,
)
from backend.scoring.predictive_safety import (
    calculate_all_pre_shift_risks,
    calculate_pre_shift_risk,
    detect_deteriorating,
    get_dangerous_corridors,
    get_fleet_risk_forecast,
)
from backend.scoring.alert_triage import get_daily_briefing, get_triaged_alerts
from backend.scoring.roi_engine import (
    calculate_before_after,
    calculate_fleet_roi,
    calculate_retention_savings,
)
from backend.scoring.what_if import get_default_scenarios, simulate_what_if
from backend.scoring.green_score import get_green_fleet_dashboard


# ─── App + CORS ───────────────────────────────────────────────────────────────

app = FastAPI(title="FleetShield AI API", version="1.0.0")

# CORS restricted to the known frontend origins (the Next.js app proxies /api
# server-side, so browser->backend CORS is rarely exercised). Override for other
# hosts via ALLOWED_ORIGINS (comma-separated) — e.g. a deployed domain.
_default_origins = "http://localhost:3001,http://127.0.0.1:3001"
_allowed_origins = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", _default_origins).split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["*"],
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _not_found(message: str) -> JSONResponse:
    """404 with the same JSON shape as the original Express handlers."""
    return JSONResponse(status_code=404, content={"error": message})


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    # Data now flows through the AgentShyft Continuum platform (mock telematics).
    # `geotabConfigured` is kept as the frontend's "connected" flag (now always
    # true -> the sidebar shows the live/connected state, relabeled to Continuum).
    return {
        "status": "ok",
        "geotabConfigured": True,
        "connected": True,
        "provider": "AgentShyft Continuum",
        "timestamp": _now_iso(),
    }


# ─── Fleet overview / roster ──────────────────────────────────────────────────

@app.get("/api/fleet/overview")
def fleet_overview():
    return get_fleet_summary()


def _driver_with_stats(driver) -> dict:
    """Merge a driver dataclass with its 30-day stats, matching the frontend
    `Driver` type ({...driver, stats}). get_driver_stats embeds a redundant
    'driver' key inside its result — strip it so `stats` matches Driver.stats."""
    stats = get_driver_stats(driver.id) or {}
    stats = {k: v for k, v in stats.items() if k != "driver"}
    return {**asdict(driver), "stats": stats}


@app.get("/api/fleet/drivers")
def fleet_drivers():
    return [_driver_with_stats(d) for d in seed_drivers]


@app.get("/api/fleet/drivers/{driver_id}")
def fleet_driver(driver_id: str):
    driver = next((d for d in seed_drivers if d.id == driver_id), None)
    if not driver:
        return _not_found("Driver not found")
    return _driver_with_stats(driver)


@app.get("/api/fleet/vehicles")
def fleet_vehicles():
    return [asdict(v) for v in seed_vehicles]


@app.get("/api/fleet/events")
def fleet_events(
    driverId: Optional[str] = Query(default=None),
    limit: int = Query(default=100),
):
    events = seed_safety_events
    if driverId:
        events = [e for e in events if e.driverId == driverId]
    return [asdict(e) for e in events[:limit]]


# ─── Scoring: insurance / risk / wellness ─────────────────────────────────────

@app.get("/api/fleet/score")
def fleet_score():
    return calculate_insurance_score()


@app.get("/api/fleet/risks")
def fleet_risks():
    return calculate_all_driver_risks()


@app.get("/api/fleet/risks/{driver_id}")
def fleet_risk(driver_id: str):
    result = calculate_driver_risk(driver_id)
    if result is None:
        return _not_found("Driver not found")
    return result


@app.get("/api/fleet/wellness")
def fleet_wellness():
    return get_fleet_wellness_summary()


@app.get("/api/fleet/wellness/{driver_id}")
def fleet_wellness_driver(driver_id: str):
    result = predict_wellness(driver_id)
    if result is None:
        return _not_found("Driver not found")
    return result


@app.get("/api/fleet/wellness-all")
def fleet_wellness_all():
    return predict_all_wellness()


# ─── Predictive safety ────────────────────────────────────────────────────────

@app.get("/api/fleet/predictive/pre-shift")
def predictive_pre_shift():
    return calculate_all_pre_shift_risks()


@app.get("/api/fleet/predictive/pre-shift/{driver_id}")
def predictive_pre_shift_driver(driver_id: str):
    result = calculate_pre_shift_risk(driver_id)
    if result is None:
        return _not_found("Driver not found")
    return result


@app.get("/api/fleet/predictive/forecast")
def predictive_forecast():
    return get_fleet_risk_forecast()


@app.get("/api/fleet/predictive/trends")
def predictive_trends():
    # Original /trends -> detectDeteriorating()
    return detect_deteriorating()


@app.get("/api/fleet/predictive/corridors")
def predictive_corridors():
    # Original /corridors -> detectDangerousZones() == get_dangerous_corridors()
    return get_dangerous_corridors()


# ─── Alert triage ─────────────────────────────────────────────────────────────

@app.get("/api/fleet/alerts")
def fleet_alerts(limit: int = Query(default=100)):
    return get_triaged_alerts(limit)


@app.get("/api/fleet/alerts/briefing")
def fleet_alerts_briefing():
    return get_daily_briefing()


# ─── ROI ──────────────────────────────────────────────────────────────────────

@app.get("/api/fleet/roi")
def fleet_roi():
    return calculate_fleet_roi()


@app.get("/api/fleet/roi/before-after")
def fleet_roi_before_after():
    return calculate_before_after()


@app.get("/api/fleet/roi/retention")
def fleet_roi_retention():
    return calculate_retention_savings()


# ─── What-If simulator ────────────────────────────────────────────────────────

@app.get("/api/fleet/what-if/defaults")
def what_if_defaults():
    return get_default_scenarios()


@app.post("/api/fleet/what-if")
async def what_if(body: dict):
    scenarios = body.get("scenarios") if isinstance(body, dict) else None
    if not isinstance(scenarios, list):
        return JSONResponse(status_code=400, content={"error": "scenarios array required"})
    return simulate_what_if(scenarios)


@app.post("/api/fleet/what-if/custom")
async def what_if_custom(body: dict):
    adjustments = body.get("adjustments") if isinstance(body, dict) else None
    if adjustments is None:
        return JSONResponse(status_code=400, content={"error": "adjustments object required"})
    scenario = {
        "id": "custom",
        "name": "Custom Scenario",
        "description": "Custom parameter adjustments",
        "adjustments": adjustments,
    }
    results = simulate_what_if([scenario])
    return results[0]


# ─── Sustainability / Green Fleet ─────────────────────────────────────────────
# Sub-routes mirror the original: /drivers -> dashboard.driverGreenRankings,
# /vehicles -> dashboard.evReadiness (per existing index.ts).

@app.get("/api/fleet/sustainability")
def sustainability():
    return get_green_fleet_dashboard()


@app.get("/api/fleet/sustainability/drivers")
def sustainability_drivers():
    dashboard = get_green_fleet_dashboard() or {}
    return dashboard.get("driverGreenRankings", [])


@app.get("/api/fleet/sustainability/vehicles")
def sustainability_vehicles():
    dashboard = get_green_fleet_dashboard() or {}
    return dashboard.get("evReadiness", {})


# ─── Live map ─────────────────────────────────────────────────────────────────

@app.get("/api/fleet/map/live")
def map_live():
    return live_fleet.get_live_fleet()


@app.get("/api/fleet/map/trail/{vehicle_id}")
def map_trail(vehicle_id: str, hours: int = Query(default=4)):
    return live_fleet.get_gps_trail(vehicle_id, hours)


@app.get("/api/fleet/map/hotspots")
def map_hotspots():
    return live_fleet.get_speeding_hotspots()


# ─── Ace NL analytics (stub) ──────────────────────────────────────────────────

@app.post("/api/fleet/ace/query")
async def ace_query(body: dict):
    prompt = body.get("prompt") if isinstance(body, dict) else None
    if not prompt:
        return JSONResponse(status_code=400, content={"error": "prompt is required"})

    summary = get_fleet_summary()
    score = calculate_insurance_score()
    text = (
        f"Fleet snapshot: {summary['totalVehicles']} vehicles and "
        f"{summary['totalDrivers']} drivers over the {summary['period']} window. "
        f"{summary['totalSafetyEvents']} safety events logged "
        f"({summary['eventsPerThousandMiles']} per 1,000 miles); "
        f"average safety score {summary['avgSafetyScore']}. "
        f"Insurability score {score['overallScore']} (grade {score['grade']}). "
        f"{len(summary['topRiskDrivers'])} driver(s) flagged high/critical risk."
    )
    return {"text": text, "data": None, "charts": [], "status": "ok"}


# ─── Data source / integration info ───────────────────────────────────────────

@app.get("/api/fleet/data-source")
def data_source():
    # Frontend reads `isLiveData`; we no longer use Geotab. Keep that key plus
    # the new Continuum/mock descriptors.
    return {
        "isLiveData": True,
        "provider": "AgentShyft Continuum",
        "database": "fleetshield_mock",
    }


@app.get("/api/fleet/verify-integration")
def verify_integration():
    return {
        "timestamp": _now_iso(),
        "isLiveData": True,
        "dataSource": {
            "provider": "AgentShyft Continuum",
            "database": "fleetshield_mock",
            "mode": "mock",
            "vehicleCount": len(seed_vehicles),
            "driverCount": len(seed_drivers),
            "safetyEventCount": len(seed_safety_events),
        },
    }


# ─── Missions (stubs — implemented in a later phase) ──────────────────────────

@app.get("/api/missions/active")
def missions_active():
    from backend.missions import store as _store
    return _store.get_active()


@app.get("/api/missions/{mission_id}")
def mission_by_id(mission_id: str):
    from backend.missions import store as _store
    m = _store.get(mission_id)
    return m if m else _not_found("not found")


# ─── Tasha assistant (Continuum agent) — SSE chat/voice ───────
from backend.api.assistant_routes import router as assistant_router  # noqa: E402
from backend.api.driver_routes import router as driver_router  # noqa: E402
from backend.api.voice_routes import router as voice_router  # noqa: E402

app.include_router(assistant_router)
app.include_router(driver_router)
app.include_router(voice_router)


# ─── Voice WebSocket (hands-free: STT -> Tasha -> TTS; + Twilio dispatch) ──────
from fastapi import WebSocket  # noqa: E402


@app.websocket("/ws")
async def voice_ws(ws: WebSocket):
    from backend.voice.session import handle_voice_ws
    await handle_voice_ws(ws)


# ─── Twilio dispatch-call TwiML callbacks (real two-way phone call) ───────────
from fastapi import Request as _Request  # noqa: E402
from fastapi.responses import Response as _XMLResponse  # noqa: E402


def _twilio_pq(req: "_Request") -> str:
    return req.url.path + ("?" + req.url.query if req.url.query else "")


def _twilio_reject() -> "_XMLResponse":
    return _XMLResponse(content="<Response><Reject/></Response>", media_type="application/xml", status_code=403)


@app.post("/twilio/voice")
async def twilio_voice(req: _Request):
    from backend.voice import twilio_dispatch
    form = await req.form()
    if not twilio_dispatch.validate_request(_twilio_pq(req), dict(form), req.headers.get("X-Twilio-Signature")):
        return _twilio_reject()
    xml = await twilio_dispatch.opening_twiml(req.query_params.get("key", ""))
    return _XMLResponse(content=xml, media_type="application/xml")


@app.post("/twilio/gather")
async def twilio_gather(req: _Request):
    from backend.voice import twilio_dispatch
    form = await req.form()
    if not twilio_dispatch.validate_request(_twilio_pq(req), dict(form), req.headers.get("X-Twilio-Signature")):
        return _twilio_reject()
    xml = await twilio_dispatch.gather_twiml(req.query_params.get("key", ""), form.get("SpeechResult", ""))
    return _XMLResponse(content=xml, media_type="application/xml")


@app.post("/twilio/status")
async def twilio_status(req: _Request):
    from backend.voice import twilio_dispatch
    form = await req.form()
    if not twilio_dispatch.validate_request(_twilio_pq(req), dict(form), req.headers.get("X-Twilio-Signature")):
        return _twilio_reject()
    twilio_dispatch.mark_status(req.query_params.get("key", ""), form.get("CallStatus", ""))
    return _XMLResponse(content="<Response/>", media_type="application/xml")
