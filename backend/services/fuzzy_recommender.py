from __future__ import annotations

from pathlib import Path

from backend.models import Interaction
from backend.services.profile_service import classify_user_profile
from backend.services.nn_recommender import recommend_svd_nn_for_user


def _duration_label(duration_norm: float) -> str:
    minutes = duration_norm * 90.0
    if minutes <= 30.0:
        return "low"
    if minutes <= 60.0:
        return "medium"
    return "high"


def _interest_label(interest_level: float) -> str:
    if interest_level <= 2.0:
        return "low"
    if interest_level < 4.0:
        return "medium"
    return "high"


def _skipping_label(skipped_scenes_value: float, skipped_music_value: float) -> str:
    return "high" if skipped_scenes_value > 0.0 or skipped_music_value > 0.0 else "low"


def _user_behavior_profile(user_id: int) -> dict:
    interactions = Interaction.query.filter_by(user_id=user_id).all()
    if not interactions:
        return {
            "watch_duration_norm": 30.0 / 90.0,
            "skipped_scenes": 0.0,
            "skipped_music": 0.0,
            "interest_level": 3.0,
        }

    duration_map = {"10": 10.0, "30": 30.0, "60": 60.0, "full": 90.0}
    duration_values = [duration_map.get(i.watch_duration, 30.0) for i in interactions]
    skipped_scenes_values = [1.0 if i.skipped_scenes else 0.0 for i in interactions]
    skipped_music_values = [1.0 if i.skipped_music else 0.0 for i in interactions]
    interest_values = [float(i.interest_level) for i in interactions]

    return {
        "watch_duration_norm": (sum(duration_values) / len(duration_values)) / 90.0,
        "skipped_scenes": sum(skipped_scenes_values) / len(skipped_scenes_values),
        "skipped_music": sum(skipped_music_values) / len(skipped_music_values),
        "interest_level": sum(interest_values) / len(interest_values),
    }


def _fuzzy_decision(profile: dict) -> dict:
    duration = _duration_label(float(profile["watch_duration_norm"]))
    interest = _interest_label(float(profile["interest_level"]))
    skipping = _skipping_label(float(profile["skipped_scenes"]), float(profile["skipped_music"]))

    triggered_rules: list[dict] = []

    if duration == "high" and interest == "high" and skipping == "low":
        triggered_rules.append({"id": 1, "strength": "strong", "rule": "duration High AND interest High AND skipping Low"})
    if duration == "medium" and interest == "high":
        triggered_rules.append({"id": 2, "strength": "strong", "rule": "duration Medium AND interest High"})
    if duration == "low" and interest == "low":
        triggered_rules.append({"id": 3, "strength": "weak", "rule": "duration Low AND interest Low"})
    if skipping == "high":
        triggered_rules.append({"id": 4, "strength": "weak", "rule": "skipping High"})
    if duration == "medium" and interest == "medium":
        triggered_rules.append({"id": 5, "strength": "medium", "rule": "duration Medium AND interest Medium"})
    if duration == "high" and skipping == "high":
        triggered_rules.append({"id": 6, "strength": "medium", "rule": "duration High AND skipping High"})
    if interest == "high" and skipping == "low":
        triggered_rules.append({"id": 7, "strength": "strong", "rule": "interest High AND skipping Low"})

    if not triggered_rules:
        output = "medium"
    else:
        weights = {"strong": 1.0, "medium": 0.5, "weak": 0.25}
        average_strength = sum(weights[row["strength"]] for row in triggered_rules) / len(triggered_rules)
        if average_strength > 0.75:
            output = "strong"
        elif average_strength < 0.4:
            output = "weak"
        else:
            output = "medium"

    boost = {"strong": 0.4, "medium": 0.25, "weak": 0.1}[output]
    return {
        "inputs": {
            "duration": duration,
            "interest": interest,
            "skipping": skipping,
        },
        "triggered_rules": triggered_rules,
        "output": output,
        "boost": boost,
        "explanation": "Fuzzy logic turns behavior signals into a small positive uplift after SVD and NN score the movie.",
    }


def recommend_full_hybrid_for_user(session, data_dir: Path, user_id: int, top_n: int = 20) -> dict:
    svd_nn_payload = recommend_svd_nn_for_user(session, data_dir, user_id=user_id, top_n=100)
    profile_data = classify_user_profile(user_id)
    behavior = _user_behavior_profile(user_id)
    fuzzy = _fuzzy_decision(behavior)

    boosted = []
    for row in svd_nn_payload["recommendations"]:
        combined = float(row["combined_score"])
        final_score = max(1.0, min(5.0, combined + float(fuzzy["boost"])))
        boosted.append(
            {
                "movie": row["movie"],
                "svd_score": row["svd_score"],
                "nn_score": row["nn_score"],
                "combined_score": row["combined_score"],
                "fuzzy_boost": float(fuzzy["boost"]),
                "final_score": round(final_score, 4),
                "fuzzy": {
                    "inputs": fuzzy["inputs"],
                    "triggered_rules": fuzzy["triggered_rules"],
                    "output": fuzzy["output"],
                },
            }
        )

    boosted.sort(key=lambda item: item["final_score"], reverse=True)
    recommendations = boosted[:top_n]

    return {
        "user_id": user_id,
        "count": len(recommendations),
        "recommendations": recommendations,
        "training": {
            "svd_nn": svd_nn_payload["training"],
            "fuzzy": {
                "inputs": fuzzy["inputs"],
                "triggered_rules": fuzzy["triggered_rules"],
                "output": fuzzy["output"],
                "boost": fuzzy["boost"],
                "explanation": fuzzy["explanation"],
            },
            "profile": profile_data,
            "pipeline": {
                "svd": "SVD learns collaborative patterns from MovieLens ratings plus the app's generated interaction ratings.",
                "nn": "The neural network learns from user_id, movie_id, watch duration, skip behavior, and interest level.",
                "fuzzy": "Fuzzy logic reads the user's behavior profile and adds a small positive uplift to the combined score.",
            },
        },
    }
