"""
Mission store — in-memory registry of autonomous missions.

A mission is deployed by Tasha (the Continuum agent) calling the deployMission
tool, then executed in-process by the runner, which streams progress/finding/
complete events. The store keeps live state so /api/missions/active (the
notification bell) and /api/missions/{id} (the assistant result view) work, and
so the driver /training route can surface completed coaching/wellness missions.
"""

from __future__ import annotations

import time
import uuid

MISSION_META = {
    "coaching_sweep": {
        "displayName": "Coaching Sweep", "agentName": "Coaching Agent",
        "description": "Analyzing your riskiest drivers and building personalized coaching plans.",
    },
    "wellness_check": {
        "displayName": "Wellness Check", "agentName": "Wellness Agent",
        "description": "Scanning the fleet for burnout and fatigue risk.",
    },
    "safety_investigation": {
        "displayName": "Safety Investigation", "agentName": "Safety Agent",
        "description": "Investigating a driver's safety event patterns and root causes.",
    },
    "insurance_optimization": {
        "displayName": "Insurance Optimization", "agentName": "Insurance Agent",
        "description": "Finding insurance premium savings opportunities across the fleet.",
    },
    "preshift_sweep": {
        "displayName": "Pre-Shift Sweep", "agentName": "Pre-Shift Agent",
        "description": "Scanning today's roster for high-risk shifts before drivers roll out.",
    },
}

VALID_TYPES = set(MISSION_META.keys())

# missionId -> mission dict (live state, updated in place by the runner)
_missions: dict[str, dict] = {}


def new_mission_id() -> str:
    return f"mission-{uuid.uuid4().hex[:10]}"


def meta_for(mission_type: str) -> dict:
    return MISSION_META.get(
        mission_type,
        {"displayName": mission_type, "agentName": "Agent", "description": ""},
    )


def register(mission_id: str, mission_type: str) -> dict:
    m = meta_for(mission_type)
    mission = {
        "missionId": mission_id,
        "type": mission_type,
        "displayName": m["displayName"],
        "agentName": m["agentName"],
        "description": m["description"],
        "status": "running",
        "findings": [],
        "recommendations": [],
        "progress": None,
        "summary": None,
        "data": {},
        "duration": 0,
        "completedAt": None,
        "_started_ts": time.time(),
    }
    _missions[mission_id] = mission
    return mission


def get(mission_id: str) -> dict | None:
    m = _missions.get(mission_id)
    if not m:
        return None
    return {k: v for k, v in m.items() if not k.startswith("_")}


def get_active() -> dict:
    active = [m for m in _missions.values() if m["status"] == "running"]
    completed = [m for m in _missions.values() if m["status"] != "running"]
    completed.sort(key=lambda m: m["_started_ts"], reverse=True)

    def clean(m: dict) -> dict:
        return {k: v for k, v in m.items() if not k.startswith("_")}

    return {"active": [clean(m) for m in active], "completed": [clean(m) for m in completed[:10]]}


def get_all_missions() -> list[dict]:
    """All missions (used by the driver /training route to surface coaching work)."""
    return [{k: v for k, v in m.items() if not k.startswith("_")} for m in _missions.values()]
