from datetime import datetime, timezone

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

    def to_dict(self):
        return {
            "movie_id": self.movie_id,
            "title": self.title,
            "genres": self.genres,
            "poster_url": self.poster_url,
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
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
