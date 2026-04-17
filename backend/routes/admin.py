from flask import Blueprint, jsonify, request
from sqlalchemy import func

from backend.db import db
from backend.models import Interaction, User

admin_bp = Blueprint("admin", __name__)


@admin_bp.post("/admin/users/cleanup")
def cleanup_users():
    payload = request.get_json(silent=True) or {}
    mode = str(payload.get("mode", "all")).strip().lower()
    if mode not in {"all", "inactive"}:
        return jsonify({"error": "mode must be 'all' or 'inactive'"}), 400

    deleted_interactions = 0
    deleted_users = 0

    if mode == "all":
        deleted_interactions = Interaction.query.delete(synchronize_session=False)
        deleted_users = User.query.delete(synchronize_session=False)
    else:
        inactive_user_ids = (
            db.session.query(User.user_id)
            .outerjoin(Interaction, Interaction.user_id == User.user_id)
            .group_by(User.user_id)
            .having(func.count(Interaction.interaction_id) == 0)
            .all()
        )
        ids = [row[0] for row in inactive_user_ids]
        if ids:
            deleted_users = User.query.filter(User.user_id.in_(ids)).delete(synchronize_session=False)

    db.session.commit()

    return (
        jsonify(
            {
                "status": "ok",
                "mode": mode,
                "deleted_users": int(deleted_users),
                "deleted_interactions": int(deleted_interactions),
            }
        ),
        200,
    )