from flask import Blueprint, jsonify, request

from backend.db import db
from backend.services.tmdb_service import sync_movie_posters_from_tmdb

admin_bp = Blueprint("admin", __name__)


@admin_bp.post("/admin/tmdb/sync-posters")
def sync_tmdb_posters():
    payload = request.get_json(silent=True) or {}
    force = bool(payload.get("force", False))

    raw_limit = payload.get("limit")
    limit = None
    if raw_limit not in (None, ""):
        try:
            limit = int(raw_limit)
        except (TypeError, ValueError):
            return jsonify({"error": "limit must be an integer"}), 400
        if limit < 1:
            return jsonify({"error": "limit must be greater than 0"}), 400

    result = sync_movie_posters_from_tmdb(db.session, force=force, limit=limit)
    return jsonify(result), 200