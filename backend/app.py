from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify
from flask_cors import CORS
from sqlalchemy import text

from backend.db import db
from backend.routes.admin import admin_bp
from backend.routes.interact import interact_bp
from backend.routes.movies import movies_bp
from backend.routes.profile import profile_bp
from backend.routes.recommendations import recommendations_bp
from backend.routes.user import user_bp
from backend.services.movie_loader import ensure_movie_catalog, refresh_seed_movies_with_static_posters

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _ensure_interaction_behavior_columns(app: Flask) -> None:
    required_columns: dict[str, str] = {
        "rating": "INTEGER NOT NULL DEFAULT 3",
        "watch_duration_minutes": "INTEGER",
        "percent_completed": "REAL",
        "watched_one_sitting": "BOOLEAN NOT NULL DEFAULT 0",
        "skip_count": "INTEGER NOT NULL DEFAULT 0",
        "would_watch_again": "BOOLEAN NOT NULL DEFAULT 0",
        "time_of_day": "VARCHAR(16) NOT NULL DEFAULT 'night'",
    }

    with app.app_context():
        column_rows = db.session.execute(text("PRAGMA table_info(interactions)")).mappings().all()
        existing = {str(row["name"]) for row in column_rows}
        for column_name, definition in required_columns.items():
            if column_name in existing:
                continue
            db.session.execute(text(f"ALTER TABLE interactions ADD COLUMN {column_name} {definition}"))
        db.session.commit()


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
    app.register_blueprint(profile_bp)
    app.register_blueprint(recommendations_bp)

    @app.get("/")
    def root():
        return jsonify(
            {
                "message": "SmartFlix API is running",
                "phase": "phase-9",
                "endpoints": ["/movies", "/user", "/interact", "/admin/users/cleanup", "/profile/user", "/recommendations/svd", "/recommendations/content", "/recommendations/final"],
            }
        )

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    with app.app_context():
        db.create_all()
        _ensure_interaction_behavior_columns(app)
        if not app.config.get("SKIP_SEEDING") and not os.getenv("SKIP_SEEDING", "").strip():
            target_catalog_size = int(os.getenv("TARGET_CATALOG_SIZE", "50"))
            ensure_movie_catalog(db.session, BASE_DIR / "data" / "movies.csv", target_count=target_catalog_size)
        refresh_seed_movies_with_static_posters(db.session)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=os.getenv("FLASK_DEBUG", "1") == "1")
