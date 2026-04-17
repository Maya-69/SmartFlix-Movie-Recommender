from flask import Blueprint, jsonify, request

from backend.db import db
from backend.models import RecommendationFeedback, User
from backend.services.recommender_content_service import recommend_movies_content_based
from backend.services.recommender_hybrid_service import recommend_movies_hybrid
from backend.services.recommender_svd_service import recommend_movies_svd

recommendations_bp = Blueprint("recommendations", __name__)


def _to_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False


def _to_float(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@recommendations_bp.get("/recommendations/svd")
def get_svd_recommendations():
    user_id = request.args.get("user_id", type=int)
    if user_id is None:
        return jsonify({"error": "user_id is required"}), 400

    if db.session.get(User, user_id) is None:
        return jsonify({"error": "User not found"}), 404

    top_n = request.args.get("top_n", default=10, type=int)
    if top_n < 1 or top_n > 50:
        return jsonify({"error": "top_n must be between 1 and 50"}), 400

    latent_dims = request.args.get("latent_dims", default=12, type=int)
    if latent_dims < 1 or latent_dims > 64:
        return jsonify({"error": "latent_dims must be between 1 and 64"}), 400

    include_embeddings = _to_bool(request.args.get("include_embeddings", "false"))

    result = recommend_movies_svd(
        db.session,
        user_id=user_id,
        top_n=top_n,
        n_components=latent_dims,
        include_embeddings=include_embeddings,
    )
    return jsonify(result), 200


@recommendations_bp.get("/recommendations/content")
def get_content_recommendations():
    user_id = request.args.get("user_id", type=int)
    if user_id is None:
        return jsonify({"error": "user_id is required"}), 400

    if db.session.get(User, user_id) is None:
        return jsonify({"error": "User not found"}), 404

    top_n = request.args.get("top_n", default=10, type=int)
    if top_n < 1 or top_n > 50:
        return jsonify({"error": "top_n must be between 1 and 50"}), 400

    result = recommend_movies_content_based(db.session, user_id=user_id, top_n=top_n)
    return jsonify(result), 200


@recommendations_bp.get("/recommendations/final")
def get_final_recommendations():
    user_id = request.args.get("user_id", type=int)
    if user_id is None:
        return jsonify({"error": "user_id is required"}), 400

    if db.session.get(User, user_id) is None:
        return jsonify({"error": "User not found"}), 404

    top_n = request.args.get("top_n", default=10, type=int)
    if top_n < 1 or top_n > 50:
        return jsonify({"error": "top_n must be between 1 and 50"}), 400

    latent_dims = request.args.get("latent_dims", default=12, type=int)
    if latent_dims < 1 or latent_dims > 64:
        return jsonify({"error": "latent_dims must be between 1 and 64"}), 400

    result = recommend_movies_hybrid(
        db.session,
        user_id=user_id,
        top_n=top_n,
        n_components=latent_dims,
    )
    return jsonify(result), 200


@recommendations_bp.post("/recommendations/feedback")
def save_recommendation_feedback():
    payload = request.get_json(silent=True) or {}
    user_id = payload.get("user_id")
    movie_id = payload.get("movie_id")
    helpful = payload.get("helpful")

    if user_id is None or movie_id is None or helpful is None:
        return jsonify({"error": "user_id, movie_id, and helpful are required"}), 400

    try:
        user_id = int(user_id)
        movie_id = int(movie_id)
    except (TypeError, ValueError):
        return jsonify({"error": "user_id and movie_id must be valid numbers"}), 400

    if db.session.get(User, user_id) is None:
        return jsonify({"error": "User not found"}), 404

    feedback = RecommendationFeedback(
        user_id=user_id,
        movie_id=movie_id,
        helpful=_to_bool(helpful),
        source=str(payload.get("source", "final")).strip().lower() or "final",
        svd_score=_to_float(payload.get("svd_score")),
        content_score=_to_float(payload.get("content_score")),
        final_score=_to_float(payload.get("final_score")),
        agreement=str(payload.get("agreement", "single-engine")).strip().lower() or "single-engine",
        rank_score=_to_float(payload.get("rank_score")),
    )
    db.session.add(feedback)
    db.session.commit()

    return jsonify({"status": "ok", "feedback": feedback.to_dict()}), 201


@recommendations_bp.post("/recommendations/feedback/reset")
def reset_recommendation_feedback():
    payload = request.get_json(silent=True) or {}
    user_id = payload.get("user_id")

    if user_id is None:
        return jsonify({"error": "user_id is required"}), 400

    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return jsonify({"error": "user_id must be a valid number"}), 400

    if db.session.get(User, user_id) is None:
        return jsonify({"error": "User not found"}), 404

    deleted_feedback = RecommendationFeedback.query.filter_by(user_id=user_id).delete(synchronize_session=False)
    db.session.commit()

    return jsonify({"status": "ok", "deleted_feedback": int(deleted_feedback)}), 200
