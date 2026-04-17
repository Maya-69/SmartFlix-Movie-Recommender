from flask import Blueprint, jsonify, request

from backend.db import db
from backend.models import Interaction, Movie, User

interact_bp = Blueprint("interact", __name__)
ALLOWED_DURATIONS = {"10", "30", "60", "full"}
ALLOWED_TIME_OF_DAY = {"morning", "afternoon", "night"}


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
    rating_value = payload.get("rating")
    watch_duration_minutes_value = payload.get("watch_duration_minutes")
    percent_completed_value = payload.get("percent_completed")
    watched_one_sitting = _to_bool(payload.get("watched_one_sitting", False))
    skip_count_value = payload.get("skip_count", 0)
    would_watch_again = _to_bool(payload.get("would_watch_again", False))
    time_of_day = str(payload.get("time_of_day", "night")).strip().lower()

    if user_id_value is None or movie_id_value is None or rating_value is None:
        return jsonify({"error": "user_id, movie_id, and rating are required"}), 400

    try:
        user_id = int(user_id_value)
        movie_id = int(movie_id_value)
        rating = int(rating_value)
    except (TypeError, ValueError):
        return jsonify({"error": "user_id, movie_id, and rating must be valid numbers"}), 400

    if db.session.get(User, user_id) is None:
        return jsonify({"error": "User not found"}), 404
    if db.session.get(Movie, movie_id) is None:
        return jsonify({"error": "Movie not found"}), 404
    if rating < 1 or rating > 5:
        return jsonify({"error": "rating must be between 1 and 5"}), 400

    watch_duration_minutes = None
    if watch_duration_minutes_value not in (None, ""):
        try:
            watch_duration_minutes = int(watch_duration_minutes_value)
        except (TypeError, ValueError):
            return jsonify({"error": "watch_duration_minutes must be an integer"}), 400
        if watch_duration_minutes < 0:
            return jsonify({"error": "watch_duration_minutes must be >= 0"}), 400

    percent_completed = None
    if percent_completed_value not in (None, ""):
        try:
            percent_completed = float(percent_completed_value)
        except (TypeError, ValueError):
            return jsonify({"error": "percent_completed must be a number"}), 400
        if percent_completed < 0 or percent_completed > 100:
            return jsonify({"error": "percent_completed must be between 0 and 100"}), 400

    if watch_duration_minutes is None and percent_completed is None:
        return jsonify({"error": "Provide either watch_duration_minutes or percent_completed"}), 400

    try:
        skip_count = int(skip_count_value)
    except (TypeError, ValueError):
        return jsonify({"error": "skip_count must be an integer"}), 400

    if skip_count < 0:
        return jsonify({"error": "skip_count must be >= 0"}), 400

    if time_of_day not in ALLOWED_TIME_OF_DAY:
        return jsonify({"error": "time_of_day must be one of morning, afternoon, night"}), 400

    # Keep legacy fields populated for profile/backward compatibility.
    watched = True
    completed = watched_one_sitting
    if percent_completed is not None:
        watch_duration = "full" if percent_completed >= 95 else "60" if percent_completed >= 66 else "30" if percent_completed >= 33 else "10"
    elif watch_duration_minutes is not None:
        watch_duration = "full" if watch_duration_minutes >= 90 else "60" if watch_duration_minutes >= 60 else "30" if watch_duration_minutes >= 30 else "10"
    else:
        watch_duration = "10"

    if watch_duration not in ALLOWED_DURATIONS:
        watch_duration = "10"

    skipped_scenes = skip_count > 0
    skipped_music = False
    interest_level = rating

    interaction = Interaction(
        user_id=user_id,
        movie_id=movie_id,
        watched=watched,
        watch_duration=watch_duration,
        completed=completed,
        skipped_scenes=skipped_scenes,
        skipped_music=skipped_music,
        interest_level=interest_level,
        rating=rating,
        watch_duration_minutes=watch_duration_minutes,
        percent_completed=percent_completed,
        watched_one_sitting=watched_one_sitting,
        skip_count=skip_count,
        would_watch_again=would_watch_again,
        time_of_day=time_of_day,
    )

    db.session.add(interaction)
    db.session.commit()

    return jsonify({"message": "Interaction saved successfully", "interaction": interaction.to_dict()}), 201
