import os
from datetime import datetime, timezone
from urllib.parse import urlparse

from flask import has_request_context, request

from backend.db import db


class User(db.Model):
    __tablename__ = "users"

    user_id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    interactions = db.relationship("Interaction", backref="user", lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "username": self.username,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Movie(db.Model):
    __tablename__ = "movies"

    movie_id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False, index=True)
    genres = db.Column(db.String(255), nullable=False, default="Unknown")
    poster_url = db.Column(db.Text, nullable=False)

    interactions = db.relationship("Interaction", backref="movie", lazy=True, cascade="all, delete-orphan")

    def _offline_poster_url(self) -> str:
        # Always serve posters from local static files in offline mode.
        default_rel_path = f"/static/posters/movie_{int(self.movie_id)}.jpg"
        poster_value = (self.poster_url or "").strip()

        rel_path = default_rel_path
        if "/static/posters/" in poster_value:
            parsed = urlparse(poster_value)
            candidate_path = parsed.path.strip()
            if candidate_path:
                rel_path = candidate_path if candidate_path.startswith("/") else f"/{candidate_path}"

        if has_request_context():
            return f"{request.url_root.rstrip('/')}{rel_path}"

        public_base = os.getenv("SMARTFLIX_PUBLIC_BASE_URL", "").strip().rstrip("/")
        if public_base:
            return f"{public_base}{rel_path}"

        return rel_path

    def to_dict(self):
        return {
            "movie_id": self.movie_id,
            "title": self.title,
            "genres": self.genres,
            "poster_url": self._offline_poster_url(),
        }


class Interaction(db.Model):
    __tablename__ = "interactions"

    interaction_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False, index=True)
    movie_id = db.Column(db.Integer, db.ForeignKey("movies.movie_id"), nullable=False, index=True)
    watched = db.Column(db.Boolean, nullable=False, default=False)
    watch_duration = db.Column(db.String(16), nullable=False, default="10")
    completed = db.Column(db.Boolean, nullable=False, default=False)
    skipped_scenes = db.Column(db.Boolean, nullable=False, default=False)
    skipped_music = db.Column(db.Boolean, nullable=False, default=False)
    interest_level = db.Column(db.Integer, nullable=False)
    rating = db.Column(db.Integer, nullable=False, default=3)
    watch_duration_minutes = db.Column(db.Integer, nullable=True)
    percent_completed = db.Column(db.Float, nullable=True)
    watched_one_sitting = db.Column(db.Boolean, nullable=False, default=False)
    skip_count = db.Column(db.Integer, nullable=False, default=0)
    would_watch_again = db.Column(db.Boolean, nullable=False, default=False)
    time_of_day = db.Column(db.String(16), nullable=False, default="night")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def to_dict(self):
        return {
            "interaction_id": self.interaction_id,
            "user_id": self.user_id,
            "movie_id": self.movie_id,
            "watched": self.watched,
            "watch_duration": self.watch_duration,
            "completed": self.completed,
            "skipped_scenes": self.skipped_scenes,
            "skipped_music": self.skipped_music,
            "interest_level": self.interest_level,
            "rating": self.rating,
            "watch_duration_minutes": self.watch_duration_minutes,
            "percent_completed": self.percent_completed,
            "watched_one_sitting": self.watched_one_sitting,
            "skip_count": self.skip_count,
            "would_watch_again": self.would_watch_again,
            "time_of_day": self.time_of_day,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class RecommendationFeedback(db.Model):
    __tablename__ = "recommendation_feedback"

    feedback_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False, index=True)
    movie_id = db.Column(db.Integer, db.ForeignKey("movies.movie_id"), nullable=False, index=True)
    helpful = db.Column(db.Boolean, nullable=False, default=True)
    source = db.Column(db.String(32), nullable=False, default="final")
    svd_score = db.Column(db.Float, nullable=True)
    content_score = db.Column(db.Float, nullable=True)
    final_score = db.Column(db.Float, nullable=True)
    agreement = db.Column(db.String(32), nullable=False, default="single-engine")
    rank_score = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def to_dict(self):
        return {
            "feedback_id": self.feedback_id,
            "user_id": self.user_id,
            "movie_id": self.movie_id,
            "helpful": self.helpful,
            "source": self.source,
            "svd_score": self.svd_score,
            "content_score": self.content_score,
            "final_score": self.final_score,
            "agreement": self.agreement,
            "rank_score": self.rank_score,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
