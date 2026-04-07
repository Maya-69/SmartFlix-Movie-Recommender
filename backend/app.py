from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify
from flask_cors import CORS

from backend.db import db
from backend.routes.admin import admin_bp
from backend.routes.interact import interact_bp
from backend.routes.metrics import metrics_bp
from backend.routes.movies import movies_bp
from backend.routes.profile import profile_bp
from backend.routes.recommend import recommend_bp
from backend.routes.user import user_bp
from backend.services.movie_loader import ensure_movie_catalog, refresh_seed_movies_with_static_posters
from backend.services.tmdb_service import sync_movie_posters_from_tmdb

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)

    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'smartflix.db'}")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["JSON_SORT_KEYS"] = False

    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    CORS(app, resources={r"/*": {"origins": os.getenv("CORS_ORIGINS", "*")}})

    app.register_blueprint(movies_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(interact_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(recommend_bp)
    app.register_blueprint(metrics_bp)
    app.register_blueprint(profile_bp)

    @app.get("/")
    def root():
        return jsonify(
            {
                "message": "SmartFlix API is running",
                "phase": "phase-9",
                "endpoints": ["/movies", "/user", "/interact", "/admin/tmdb/sync-posters", "/recommend/svd", "/recommend/svd-nn", "/recommend/full", "/metrics/nn", "/profile/user"],
            }
        )

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    with app.app_context():
        db.create_all()
        if not app.config.get("SKIP_SEEDING") and not os.getenv("SKIP_SEEDING", "").strip():
            target_catalog_size = int(os.getenv("TARGET_CATALOG_SIZE", "50"))
            ensure_movie_catalog(db.session, BASE_DIR / "data" / "movies.csv", target_count=target_catalog_size)
        refresh_seed_movies_with_static_posters(db.session)
        enable_startup_poster_sync = os.getenv("ENABLE_STARTUP_POSTER_SYNC", "").strip().lower() in {"1", "true", "yes", "on"}
        if enable_startup_poster_sync and not app.config.get("SKIP_POSTER_SYNC") and not os.getenv("SKIP_POSTER_SYNC", "").strip():
            sync_movie_posters_from_tmdb(db.session)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=os.getenv("FLASK_DEBUG", "1") == "1")
