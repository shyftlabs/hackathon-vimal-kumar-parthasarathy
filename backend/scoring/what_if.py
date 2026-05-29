"""
What-If Insurance Simulator — models the impact of safety interventions on
insurance premiums. Scenarios adjust behavior levers; the engine reprojects
the insurance score and premium delta.
"""

from __future__ import annotations

from backend.data.seed_data import seed_vehicles
from backend.scoring.insurance_score import calculate_insurance_score


def _score_to_grade(score: float) -> str:
    if score >= 95:
        return "A+"
    if score >= 90:
        return "A"
    if score >= 85:
        return "B+"
    if score >= 75:
        return "B"
    if score >= 70:
        return "C+"
    if score >= 60:
        return "C"
    if score >= 50:
        return "D"
    return "F"


def _score_to_premium(score: float) -> int:
    benchmark_premium = len(seed_vehicles) * 14200
    percent_change = (score - 50) * 0.3
    return round(benchmark_premium * (1 - percent_change / 100))


def get_default_scenarios() -> list[dict]:
    return [
        {"id": "harsh-braking", "name": "Reduce Harsh Braking 20%",
         "description": "Install forward collision warning systems and conduct defensive driving training to reduce harsh braking events by 20%.",
         "adjustments": {"harshBrakingReduction": 20}},
        {"id": "speed-compliance", "name": "Speed Compliance Program",
         "description": "Implement speed governors and real-time alerts to reduce speeding events by 30%. Add speed coaching program.",
         "adjustments": {"speedingReduction": 30, "complianceImprovement": 10}},
        {"id": "anti-idle", "name": "Anti-Idle Initiative",
         "description": "Deploy APU systems and idle-shutdown technology. Train drivers on anti-idle practices to cut idling by 40%.",
         "adjustments": {"idlingReduction": 40}},
        {"id": "night-driving", "name": "Night Driving Limits",
         "description": "Restructure scheduling to reduce night driving by 50%. Implement fatigue detection cameras.",
         "adjustments": {"nightDrivingReduction": 50}},
        {"id": "full-package", "name": "Full Safety Package",
         "description": "Comprehensive program: collision avoidance, speed governance, anti-idle, night limits, quarterly maintenance boost, and compliance training.",
         "adjustments": {"harshBrakingReduction": 25, "speedingReduction": 35, "idlingReduction": 30,
                          "nightDrivingReduction": 40, "complianceImprovement": 15, "maintenanceScoreBoost": 10}},
    ]


def simulate_what_if(scenarios: list[dict]) -> list[dict]:
    current_insurance = calculate_insurance_score()
    current_score = current_insurance["overallScore"]
    current_premium = _score_to_premium(current_score)

    results: list[dict] = []
    for scenario in scenarios:
        adj = scenario.get("adjustments", {})
        score_boost = 0.0

        if adj.get("harshBrakingReduction"):
            score_boost += (adj["harshBrakingReduction"] / 100) * 0.35 * 15
        if adj.get("speedingReduction"):
            score_boost += (adj["speedingReduction"] / 100) * 0.25 * 18
        if adj.get("idlingReduction"):
            score_boost += (adj["idlingReduction"] / 100) * 0.20 * 8
        if adj.get("nightDrivingReduction"):
            score_boost += (adj["nightDrivingReduction"] / 100) * 0.35 * 6
        if adj.get("complianceImprovement"):
            score_boost += (adj["complianceImprovement"] / 100) * 0.25 * 20
        if adj.get("maintenanceScoreBoost"):
            score_boost += (adj["maintenanceScoreBoost"] / 100) * 0.20 * 20

        projected_score = min(100, round(current_score + score_boost))
        projected_premium = _score_to_premium(projected_score)
        annual_savings = max(0, current_premium - projected_premium)

        positive_vals = [v for v in adj.values() if isinstance(v, (int, float)) and v > 0]
        adjustment_count = len(positive_vals)
        max_adjustment = max(positive_vals, default=0)
        difficulty = (
            "hard" if adjustment_count >= 4 or max_adjustment >= 40 else
            "moderate" if adjustment_count >= 2 or max_adjustment >= 25 else "easy"
        )
        time_to_impact = (
            "6-12 months" if difficulty == "hard" else
            "3-6 months" if difficulty == "moderate" else "1-3 months"
        )

        recommendations: list[str] = []
        if adj.get("harshBrakingReduction"):
            recommendations.append("Install forward collision warning on all vehicles")
        if adj.get("speedingReduction"):
            recommendations.append("Deploy speed governors set to posted speed limits")
        if adj.get("idlingReduction"):
            recommendations.append("Install APU systems on Class 8 tractors")
        if adj.get("nightDrivingReduction"):
            recommendations.append("Restructure dispatch scheduling to minimize night shifts")
        if adj.get("complianceImprovement"):
            recommendations.append("Quarterly compliance refresher training")
        if adj.get("maintenanceScoreBoost"):
            recommendations.append("Implement preventive maintenance scheduling system")

        results.append({
            "scenarioId": scenario["id"],
            "scenarioName": scenario["name"],
            "currentScore": current_score,
            "projectedScore": projected_score,
            "scoreDelta": projected_score - current_score,
            "currentGrade": _score_to_grade(current_score),
            "projectedGrade": _score_to_grade(projected_score),
            "currentPremium": current_premium,
            "projectedPremium": projected_premium,
            "annualSavings": annual_savings,
            "implementationDifficulty": difficulty,
            "timeToImpact": time_to_impact,
            "recommendations": recommendations,
        })

    return results
