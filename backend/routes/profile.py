from flask import Blueprint, jsonify, request

from backend.db import db
from backend.models import User
from backend.services.profile_service import classify_user_profile

profile_bp = Blueprint("profile", __name__)


@profile_bp.get("/profile/user")
def get_user_profile():
    user_id = request.args.get("user_id", type=int)
    if user_id is None:
        return jsonify({"error": "user_id is required"}), 400
    if db.session.get(User, user_id) is None:
        return jsonify({"error": "User not found"}), 404

    return jsonify({"profile": classify_user_profile(user_id)})
