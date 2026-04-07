from pathlib import Path

from flask import Blueprint, jsonify, request

from backend.db import db
from backend.models import User
from backend.services.fuzzy_recommender import recommend_full_hybrid_for_user
from backend.services.nn_recommender import recommend_svd_nn_for_user
from backend.services.svd_recommender import recommend_for_user

recommend_bp = Blueprint("recommend", __name__)


@recommend_bp.get("/recommend/svd")
def recommend_svd():
    user_id = request.args.get("user_id", type=int)
    top_n = request.args.get("top_n", default=20, type=int)

    if user_id is None:
        return jsonify({"error": "user_id is required"}), 400
    if db.session.get(User, user_id) is None:
        return jsonify({"error": "User not found"}), 404
    if top_n < 1 or top_n > 100:
        return jsonify({"error": "top_n must be between 1 and 100"}), 400

    data_dir = Path(__file__).resolve().parents[1] / "data"
    try:
        payload = recommend_for_user(db.session, data_dir=data_dir, user_id=user_id, top_n=top_n)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    return jsonify(payload)


@recommend_bp.get("/recommend/svd-nn")
def recommend_svd_nn():
    user_id = request.args.get("user_id", type=int)
    top_n = request.args.get("top_n", default=20, type=int)

    if user_id is None:
        return jsonify({"error": "user_id is required"}), 400
    if db.session.get(User, user_id) is None:
        return jsonify({"error": "User not found"}), 404
    if top_n < 1 or top_n > 100:
        return jsonify({"error": "top_n must be between 1 and 100"}), 400

    data_dir = Path(__file__).resolve().parents[1] / "data"
    try:
        payload = recommend_svd_nn_for_user(db.session, data_dir=data_dir, user_id=user_id, top_n=top_n)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    return jsonify(payload)


@recommend_bp.get("/recommend/full")
def recommend_full():
    user_id = request.args.get("user_id", type=int)
    top_n = request.args.get("top_n", default=20, type=int)

    if user_id is None:
        return jsonify({"error": "user_id is required"}), 400
    if db.session.get(User, user_id) is None:
        return jsonify({"error": "User not found"}), 404
    if top_n < 1 or top_n > 100:
        return jsonify({"error": "top_n must be between 1 and 100"}), 400

    data_dir = Path(__file__).resolve().parents[1] / "data"
    try:
        payload = recommend_full_hybrid_for_user(db.session, data_dir=data_dir, user_id=user_id, top_n=top_n)
    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    return jsonify(payload)
