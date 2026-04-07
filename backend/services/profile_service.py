from __future__ import annotations

from collections import Counter

from backend.db import db
from backend.models import Interaction, Movie

DURATION_MAP = {"10": 10.0, "30": 30.0, "60": 60.0, "full": 90.0}
ACTION_GENRES = {"action", "adventure", "crime", "thriller"}
STORY_GENRES = {"drama", "romance", "mystery", "fantasy", "history"}
CASUAL_GENRES = {"comedy", "animation", "family", "music"}


def _normalize_genres(genres: str) -> list[str]:
    return [genre.strip().lower() for genre in str(genres or "").split("|") if genre.strip()]


def _collect_preferred_genres(interactions: list[Interaction]) -> list[str]:
    counter: Counter[str] = Counter()
    for interaction in interactions:
        if interaction.interest_level < 4 and not interaction.completed:
            continue

        movie = db.session.get(Movie, interaction.movie_id)
        if not movie:
            continue

        for genre in _normalize_genres(movie.genres):
            counter[genre] += 1

    return [genre.title() for genre, _ in counter.most_common(3)]


def classify_user_profile(user_id: int) -> dict:
    interactions = Interaction.query.filter_by(user_id=user_id).all()
    if not interactions:
        return {
            "user_id": user_id,
            "profile": "Casual",
            "interaction_count": 0,
            "average_duration_minutes": 0.0,
            "average_interest_level": 0.0,
            "skip_rate": 0.0,
            "preferred_genres": [],
            "filter_genres": ["Comedy", "Animation", "Family", "Music"],
            "reason": "No interaction history yet",
        }

    duration_minutes = [DURATION_MAP.get(interaction.watch_duration, 30.0) for interaction in interactions]
    skip_rate = sum(1 for interaction in interactions if interaction.skipped_scenes or interaction.skipped_music) / len(interactions)
    average_interest = sum(float(interaction.interest_level) for interaction in interactions) / len(interactions)
    preferred_genres = _collect_preferred_genres(interactions)

    profile = "Genre-based"
    filter_genres = preferred_genres or ["Drama", "Action", "Comedy"]
    reason = "Dominant genre pattern in interaction history"

    if sum(duration_minutes) / len(duration_minutes) <= 30:
        profile = "Casual"
        filter_genres = ["Comedy", "Animation", "Family", "Music"]
        reason = "Average watch duration is low"
    elif skip_rate >= 0.5 and average_interest >= 4.0:
        profile = "Action-focused"
        filter_genres = ["Action", "Adventure", "Crime", "Thriller"]
        reason = "High skipping with high interest points to energetic content"
    elif sum(duration_minutes) / len(duration_minutes) >= 60 and skip_rate <= 0.3:
        profile = "Story-focused"
        filter_genres = ["Drama", "Romance", "Mystery", "Fantasy", "History"]
        reason = "Long watch duration with low skipping suggests story-driven preference"
    elif preferred_genres:
        profile = "Genre-based"
        filter_genres = preferred_genres
        reason = f"Repeated interest in {', '.join(preferred_genres)}"

    return {
        "user_id": user_id,
        "profile": profile,
        "interaction_count": len(interactions),
        "average_duration_minutes": round(sum(duration_minutes) / len(duration_minutes), 2),
        "average_interest_level": round(average_interest, 2),
        "skip_rate": round(skip_rate, 2),
        "preferred_genres": preferred_genres,
        "filter_genres": filter_genres,
        "reason": reason,
    }


def filter_movies_by_profile(movies, profile_data: dict):
    filter_genres = [genre.lower() for genre in profile_data.get("filter_genres", []) if genre]
    if not filter_genres:
        return movies

    filtered = []
    for movie in movies:
        movie_genres = _normalize_genres(movie.genres)
        if any(genre in movie_genres for genre in filter_genres):
            filtered.append(movie)

    return filtered or movies
