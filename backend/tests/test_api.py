"""REST API contract tests (FastAPI TestClient)."""

import pytest

FLEET_GET_ROUTES = [
    "/api/health",
    "/api/fleet/overview", "/api/fleet/drivers", "/api/fleet/vehicles", "/api/fleet/events",
    "/api/fleet/score", "/api/fleet/risks", "/api/fleet/wellness", "/api/fleet/wellness-all",
    "/api/fleet/predictive/pre-shift", "/api/fleet/predictive/forecast",
    "/api/fleet/predictive/trends", "/api/fleet/predictive/corridors",
    "/api/fleet/alerts", "/api/fleet/alerts/briefing",
    "/api/fleet/roi", "/api/fleet/roi/before-after", "/api/fleet/roi/retention",
    "/api/fleet/what-if/defaults",
    "/api/fleet/sustainability", "/api/fleet/sustainability/drivers", "/api/fleet/sustainability/vehicles",
    "/api/fleet/map/live", "/api/fleet/map/hotspots",
    "/api/fleet/data-source", "/api/fleet/verify-integration",
    "/api/missions/active",
]


@pytest.mark.parametrize("path", FLEET_GET_ROUTES)
def test_fleet_get_routes_ok(client, path):
    assert client.get(path).status_code == 200


@pytest.mark.parametrize("driver_id,expected", [("d1", 200), ("d3", 200), ("d999", 404)])
def test_driver_scoped_routes(client, driver_id, expected):
    assert client.get(f"/api/fleet/risks/{driver_id}").status_code == expected
    assert client.get(f"/api/fleet/wellness/{driver_id}").status_code == expected


def test_unknown_mission_404(client):
    assert client.get("/api/missions/does-not-exist").status_code == 404


def test_events_filters(client):
    assert client.get("/api/fleet/events?driverId=d3&limit=5").status_code == 200
    assert client.get("/api/fleet/events?limit=99999").status_code == 200


def test_what_if_post(client):
    defaults = client.get("/api/fleet/what-if/defaults").json()
    r = client.post("/api/fleet/what-if", json={"scenarios": defaults})
    assert r.status_code == 200 and len(r.json()) == 5


def test_what_if_custom_post(client):
    r = client.post("/api/fleet/what-if/custom", json={"adjustments": {"speedingReduction": 30}})
    assert r.status_code == 200


def test_data_source_rebranded(client):
    d = client.get("/api/fleet/data-source").json()
    assert "Continuum" in str(d.get("provider", ""))


def test_overview_numbers(client):
    o = client.get("/api/fleet/overview").json()
    assert o["totalVehicles"] == 25 and o["totalDrivers"] == 30


def test_roi_route_calibrated(client):
    roi = client.get("/api/fleet/roi").json()
    assert 450_000 <= roi["totalAnnualSavings"] <= 600_000


# ── Driver portal ──
def test_driver_login_and_portal(client):
    r = client.post("/api/driver/login", json={"employeeNumber": "405", "pin": "7234"})
    assert r.status_code == 200
    did = r.json()["driverId"]
    for sub in ("dashboard", "load", "messages", "pre-shift-briefing", "hos",
                "wellness-trend", "gamification", "badges", "points-history",
                "rewards", "actions", "training"):
        assert client.get(f"/api/driver/{did}/{sub}").status_code == 200, sub
    assert client.get("/api/driver/leaderboard").status_code == 200


def test_driver_bad_pin_401(client):
    assert client.post("/api/driver/login", json={"employeeNumber": "405", "pin": "0000"}).status_code == 401
