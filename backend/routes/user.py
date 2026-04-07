from flask import Blueprint, jsonify, request

from backend.db import db
from backend.models import User

user_bp = Blueprint("user", __name__)


@user_bp.get("/user")
def get_user():
    user_id = request.args.get("user_id", type=int)
    username = request.args.get("username", type=str, default="").strip()

    user = None
    if user_id is not None:
        user = User.query.get(user_id)
    elif username:
        user = User.query.filter_by(username=username).first()

    if user is None:
        return jsonify({"error": "User not found"}), 404

    return jsonify({"user": user.to_dict()})


@user_bp.post("/user")
def create_or_get_user():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()

    if not username:
        return jsonify({"error": "username is required"}), 400

    user = User.query.filter_by(username=username).first()
    if user is None:
        user = User(username=username)
        db.session.add(user)
        db.session.commit()

    return jsonify({"user": user.to_dict()})
