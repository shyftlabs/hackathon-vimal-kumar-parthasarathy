"""Autonomous mission runner tests (deterministic; summary falls back without a key)."""

import pytest

from backend.missions import runner, store

MISSION_TYPES = [
    "coaching_sweep", "wellness_check", "safety_investigation",
    "insurance_optimization", "preshift_sweep",
]


@pytest.mark.parametrize("mission_type", MISSION_TYPES)
async def test_mission_completes_with_findings(mission_type):
    mid = store.new_mission_id()
    store.register(mid, mission_type)
    events = [ev async for ev in runner.run_mission(mid, mission_type, {})]

    completes = [e for e in events if e["type"] == "mission_complete"]
    assert len(completes) == 1
    assert completes[0]["status"] == "complete"
    assert completes[0]["summary"]
    assert any(e["type"] == "mission_finding" for e in events)
    assert any(e["type"] == "mission_progress" for e in events)

    # store reflects completion
    stored = store.get(mid)
    assert stored["status"] == "complete"


async def test_safety_investigation_targets_named_driver():
    mid = store.new_mission_id()
    store.register(mid, "safety_investigation")
    events = [ev async for ev in runner.run_mission(mid, "safety_investigation", {"driverName": "Rivera"})]
    comp = next(e for e in events if e["type"] == "mission_complete")
    assert "Rivera" in comp["data"].get("driverName", "")
