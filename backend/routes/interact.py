from flask import Blueprint, jsonify, request

from backend.db import db
from backend.models import Interaction, Movie, User

interact_bp = Blueprint("interact", __name__)
ALLOWED_DURATIONS = {"10", "30", "60", "full"}


def _to_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False


@interact_bp.get("/interact")
def get_interactions():
    user_id = request.args.get("user_id", type=int)
    movie_id = request.args.get("movie_id", type=int)

    query = Interaction.query.order_by(Interaction.created_at.desc())
    if user_id is not None:
        query = query.filter_by(user_id=user_id)
    if movie_id is not None:
        query = query.filter_by(movie_id=movie_id)

    interactions = query.all()
    serialized = []
    for interaction in interactions:
        row = interaction.to_dict()
        row["movie_title"] = interaction.movie.title if interaction.movie else None
        row["username"] = interaction.user.username if interaction.user else None
        serialized.append(row)

    return jsonify({"interactions": serialized, "count": len(serialized)})


@interact_bp.post("/interact")
def save_interaction():
    payload = request.get_json(silent=True) or {}

    user_id_value = payload.get("user_id")
    movie_id_value = payload.get("movie_id")
    interest_level_value = payload.get("interest_level")

    if user_id_value is None or movie_id_value is None or interest_level_value is None:
        return jsonify({"error": "user_id, movie_id, and interest_level are required"}), 400

    try:
        user_id = int(user_id_value)
        movie_id = int(movie_id_value)
        interest_level = int(interest_level_value)
    except (TypeError, ValueError):
        return jsonify({"error": "user_id, movie_id, and interest_level must be valid numbers"}), 400

    if db.session.get(User, user_id) is None:
        return jsonify({"error": "User not found"}), 404
    if db.session.get(Movie, movie_id) is None:
        return jsonify({"error": "Movie not found"}), 404
    if interest_level < 1 or interest_level > 5:
        return jsonify({"error": "interest_level must be between 1 and 5"}), 400

    watched = _to_bool(payload.get("watched", False))
    completed = _to_bool(payload.get("completed", False))
    watch_duration = str(payload.get("watch_duration", "10")).strip().lower()
    if watch_duration not in ALLOWED_DURATIONS:
        return jsonify({"error": "watch_duration must be one of 10, 30, 60, full"}), 400
    if completed and not watched:
        return jsonify({"error": "completed cannot be true when watched is false"}), 400

    interaction = Interaction(
        user_id=user_id,
        movie_id=movie_id,
        watched=watched,
        watch_duration=watch_duration,
        completed=completed,
        skipped_scenes=_to_bool(payload.get("skipped_scenes", False)),
        skipped_music=_to_bool(payload.get("skipped_music", False)),
        interest_level=interest_level,
    )

    db.session.add(interaction)
    db.session.commit()

    return jsonify({"message": "Interaction saved successfully", "interaction": interaction.to_dict()}), 201
