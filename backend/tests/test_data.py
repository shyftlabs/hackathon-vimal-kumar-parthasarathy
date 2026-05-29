"""Mock fleet data invariants (deterministic, seeded)."""

from backend.data import seed_data as s


def test_fleet_counts():
    assert len(s.seed_vehicles) == 25
    assert len(s.seed_drivers) == 30
    assert len(s.seed_fleet_kpis) == 90
    assert len(s.seed_safety_events) > 0
    assert len(s.seed_trip_days) > 0


def test_problem_drivers_present():
    marcus = s.get_driver("d3")
    assert marcus is not None and marcus.riskProfile == "critical"
    assert sum(1 for d in s.seed_drivers if d.burnoutRisk == "high") >= 5


def test_get_driver_invalid_returns_none():
    assert s.get_driver("d999") is None
    assert s.get_vehicle("v999") is None


def test_fleet_summary_shape():
    fs = s.get_fleet_summary()
    for key in ("totalVehicles", "totalDrivers", "totalSafetyEvents",
                "avgSafetyScore", "eventsPerThousandMiles", "riskDistribution"):
        assert key in fs
    assert fs["totalVehicles"] == 25


def test_driver_stats_invalid_returns_none():
    assert s.get_driver_stats("nope") is None
    stats = s.get_driver_stats("d3")
    assert stats and stats["totalEvents"] >= 0
