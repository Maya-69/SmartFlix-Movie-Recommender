from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel

from backend.models import Interaction, Movie
from backend.services.profile_service import classify_user_profile


@dataclass
class ContentSeed:
    movie_id: int
    title: str
    weight: float


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _completion_ratio(interaction: Interaction) -> float:
    if interaction.percent_completed is not None:
        return max(0.0, min(1.0, _safe_float(interaction.percent_completed) / 100.0))

    minutes = _safe_float(interaction.watch_duration_minutes)
    if minutes <= 0:
        return 0.0
    return max(0.0, min(1.0, minutes / 120.0))


def _interaction_weight(interaction: Interaction) -> float:
    rating = _safe_float(interaction.rating, _safe_float(interaction.interest_level, 3.0))
    completion = _completion_ratio(interaction)
    weight = 0.5 + (rating / 5.0) + completion
    if interaction.watched_one_sitting:
        weight += 0.2
    if interaction.would_watch_again:
        weight += 0.3
    weight -= min(0.5, _safe_float(interaction.skip_count) * 0.05)
    return max(0.25, weight)


def _movie_text(movie: Movie) -> str:
    return f"{movie.title} {movie.genres}".strip()


def _collect_seed_movies(user_id: int) -> list[ContentSeed]:
    interactions = (
        Interaction.query.filter_by(user_id=user_id)
        .order_by(Interaction.created_at.desc())
        .all()
    )
    seeds: list[ContentSeed] = []
    for interaction in interactions:
        movie = Movie.query.session.get(Movie, int(interaction.movie_id))
        if not movie:
            continue

        completion = _completion_ratio(interaction)
        rating = _safe_float(interaction.rating, _safe_float(interaction.interest_level, 3.0))
        if rating < 4.0 and completion < 0.7 and not interaction.would_watch_again:
            continue

        seeds.append(
            ContentSeed(
                movie_id=int(movie.movie_id),
                title=movie.title,
                weight=_interaction_weight(interaction),
            )
        )

    if seeds:
        return seeds[:3]

    fallback_movies = (
        Interaction.query.filter_by(user_id=user_id)
        .order_by(Interaction.created_at.desc())
        .limit(3)
        .all()
    )
    for interaction in fallback_movies:
        movie = Movie.query.session.get(Movie, int(interaction.movie_id))
        if not movie:
            continue
        seeds.append(ContentSeed(movie_id=int(movie.movie_id), title=movie.title, weight=_interaction_weight(interaction)))

    return seeds[:3]


def _genre_overlap_bonus(movie: Movie, profile_genres: list[str]) -> float:
    if not profile_genres:
        return 0.0

    movie_genres = {genre.strip().lower() for genre in str(movie.genres or "").split("|") if genre.strip()}
    overlap = len(movie_genres.intersection({genre.lower() for genre in profile_genres}))
    return min(0.6, overlap * 0.15)


def recommend_movies_content_based(session, user_id: int, top_n: int = 10) -> dict:
    del session

    movies = Movie.query.order_by(Movie.title.asc()).all()
    watched_movie_ids = {
        int(interaction.movie_id)
        for interaction in Interaction.query.filter_by(user_id=user_id).all()
    }

    if not movies:
        return {
            "algorithm": "content-based",
            "mode": "empty-catalog",
            "user_id": user_id,
            "recommendations": [],
            "seeds": [],
        }

    profile_data = classify_user_profile(user_id)
    seeds = _collect_seed_movies(user_id)

    if not seeds:
        profile_genres = profile_data.get("filter_genres", [])
        fallback = []
        for movie in movies:
            if int(movie.movie_id) in watched_movie_ids:
                continue
            bonus = _genre_overlap_bonus(movie, profile_genres)
            if bonus > 0:
                fallback.append((movie, bonus))
        fallback.sort(key=lambda item: (item[1], item[0].title), reverse=True)

        recommendations = [
            {
                **movie.to_dict(),
                "content_score": round(score, 4),
                "matched_from": None,
                "source": "profile-content-fallback",
            }
            for movie, score in fallback[:top_n]
        ]
        return {
            "algorithm": "content-based",
            "mode": "profile-fallback",
            "user_id": user_id,
            "recommendations": recommendations,
            "seeds": [],
            "profile_tags": profile_data.get("profile_tags", []),
        }

    corpus = [_movie_text(movie) for movie in movies]
    vectorizer = TfidfVectorizer(stop_words="english")
    tfidf_matrix = vectorizer.fit_transform(corpus)
    movie_index_by_id = {int(movie.movie_id): index for index, movie in enumerate(movies)}
    movie_by_id = {int(movie.movie_id): movie for movie in movies}

    candidate_scores: dict[int, float] = defaultdict(float)
    candidate_sources: dict[int, tuple[str, float]] = {}
    seed_descriptions = []

    for seed in seeds:
        seed_movie = movie_by_id.get(seed.movie_id)
        if not seed_movie:
            continue
        seed_descriptions.append({"movie_id": seed.movie_id, "title": seed.title, "weight": round(seed.weight, 4)})

        seed_index = movie_index_by_id.get(seed.movie_id)
        if seed_index is None:
            continue

        similarities = linear_kernel(tfidf_matrix.getrow(seed_index), tfidf_matrix).flatten()
        for movie in movies:
            movie_id = int(movie.movie_id)
            if movie_id in watched_movie_ids or movie_id == seed.movie_id:
                continue

            similarity = float(similarities[movie_index_by_id[movie_id]])
            if similarity <= 0:
                continue

            adjusted = similarity * seed.weight + _genre_overlap_bonus(movie, profile_data.get("filter_genres", []))
            if adjusted <= 0:
                continue

            candidate_scores[movie_id] += adjusted
            current_source = candidate_sources.get(movie_id)
            if current_source is None or adjusted > current_source[1]:
                candidate_sources[movie_id] = (seed.title, adjusted)

    ranked_movie_ids = sorted(candidate_scores.items(), key=lambda item: item[1], reverse=True)

    recommendations = []
    for movie_id, score in ranked_movie_ids[: max(top_n, 0)]:
        movie = movie_by_id[movie_id]
        matched_from = candidate_sources.get(movie_id, (None, 0.0))[0]
        recommendations.append(
            {
                **movie.to_dict(),
                "content_score": round(score, 4),
                "matched_from": matched_from,
                "source": "content-based",
            }
        )

    return {
        "algorithm": "content-based",
        "mode": "tfidf",
        "user_id": user_id,
        "top_n": top_n,
        "recommendations": recommendations,
        "seeds": seed_descriptions,
        "profile_tags": profile_data.get("profile_tags", []),
        "profile": profile_data.get("profile"),
    }
