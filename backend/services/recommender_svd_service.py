from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.decomposition import TruncatedSVD

from backend.models import Interaction, Movie
from backend.services.movielens_service import build_app_movie_index, load_movielens_ratings_for_app_movies


@dataclass
class SvdModelArtifacts:
    user_ids: list[int]
    row_labels: list[int]
    movie_ids: list[int]
    user_factors: np.ndarray
    movie_factors: np.ndarray
    reconstructed_scores: np.ndarray


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


def behavior_weighted_score(interaction: Interaction) -> float:
    rating = _safe_float(interaction.rating, _safe_float(interaction.interest_level, 3.0))
    completion = _completion_ratio(interaction)

    score = rating
    score += completion * 1.0
    score += 0.3 if bool(interaction.watched_one_sitting) else 0.0
    score += 0.5 if bool(interaction.would_watch_again) else 0.0
    score -= min(1.0, _safe_float(interaction.skip_count) * 0.1)

    return max(1.0, min(5.0, score))


def _interaction_rows(interactions: Iterable[Interaction]) -> list[dict]:
    rows: list[dict] = []
    for interaction in interactions:
        rows.append(
            {
                "user_id": int(interaction.user_id),
                "movie_id": int(interaction.movie_id),
                "score": behavior_weighted_score(interaction),
                "created_at": interaction.created_at or datetime.now(timezone.utc),
            }
        )
    return rows


def _normalize_genres(genres: str) -> list[str]:
    return [genre.strip().lower() for genre in str(genres or "").split("|") if genre.strip()]


def _collect_user_preferred_genres(user_id: int) -> list[str]:
    interactions = Interaction.query.filter_by(user_id=user_id).all()
    if not interactions:
        return []

    counts: dict[str, float] = {}
    for interaction in interactions:
        movie = db_session_get_movie(int(interaction.movie_id))
        if not movie:
            continue

        preference_weight = behavior_weighted_score(interaction) / 5.0
        for genre in _normalize_genres(movie.genres):
            counts[genre] = counts.get(genre, 0.0) + preference_weight

    ranked = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    return [genre for genre, _ in ranked[:5]]


def db_session_get_movie(movie_id: int) -> Movie | None:
    return Movie.query.session.get(Movie, movie_id)


def _genre_affinity_bonus(movie: Movie, preferred_genres: list[str]) -> float:
    if not preferred_genres:
        return 0.0

    movie_genres = set(_normalize_genres(movie.genres))
    overlap = len(movie_genres.intersection(preferred_genres))
    if overlap == 0:
        return 0.0

    return min(1.0, overlap * 0.25)


def _movielens_rows(data_dir, app_movie_index: dict[int, int]) -> list[dict]:
    rows: list[dict] = []
    for rating_row in load_movielens_ratings_for_app_movies(data_dir, app_movie_index):
        raw_user_id = rating_row.get("user_id")
        raw_movie_id = rating_row.get("movie_id")
        raw_rating = rating_row.get("rating")
        if raw_user_id is None or raw_movie_id is None or raw_rating is None:
            continue
        try:
            user_id = 1_000_000 + int(raw_user_id)
            movie_id = int(raw_movie_id)
            rating = float(raw_rating)
        except (TypeError, ValueError):
            continue

        rows.append(
            {
                "user_id": user_id,
                "movie_id": movie_id,
                "score": max(1.0, min(5.0, rating)),
                "created_at": datetime.now(timezone.utc),
            }
        )

    return rows


def _default_data_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "data"


def _fallback_popular_movies(movies: list[Movie], interactions: list[Interaction], watched_movie_ids: set[int], top_n: int) -> list[dict]:
    if not movies:
        return []

    rows = _interaction_rows(interactions)
    if rows:
        frame = pd.DataFrame(rows)
        by_movie = (
            frame.groupby("movie_id", as_index=False)
            .agg(mean_score=("score", "mean"), count=("score", "count"))
            .assign(popularity=lambda df: df["mean_score"] + np.log1p(df["count"]))
            .sort_values(["popularity", "count"], ascending=False)
        )
        ranked_movie_ids = by_movie["movie_id"].astype(int).tolist()
    else:
        ranked_movie_ids = [int(movie.movie_id) for movie in movies]

    movie_by_id = {int(movie.movie_id): movie for movie in movies}
    recommendations: list[dict] = []
    for movie_id in ranked_movie_ids:
        if movie_id in watched_movie_ids:
            continue
        movie = movie_by_id.get(movie_id)
        if not movie:
            continue
        recommendations.append(
            {
                **movie.to_dict(),
                "svd_score": None,
                "source": "popular-fallback",
            }
        )
        if len(recommendations) >= top_n:
            break

    return recommendations


def _build_svd_model(interactions: list[Interaction], n_components: int) -> SvdModelArtifacts | None:
    rows = _interaction_rows(interactions)
    if not rows:
        return None

    data_dir = _default_data_dir()
    app_movie_index = build_app_movie_index(Movie.query.session, data_dir)
    if app_movie_index:
        rows.extend(_movielens_rows(data_dir, app_movie_index))

    frame = pd.DataFrame(rows)
    aggregated = frame.groupby(["user_id", "movie_id"], as_index=False).agg(score=("score", "mean"))
    if aggregated.empty:
        return None

    real_user_ids = sorted({int(row["user_id"]) for row in rows})
    movie_ids = [int(movie.movie_id) for movie in Movie.query.order_by(Movie.movie_id.asc()).all()]
    if len(real_user_ids) == 0 or len(movie_ids) < 2:
        return None

    pivot = aggregated.pivot(index="user_id", columns="movie_id", values="score").reindex(
        index=real_user_ids,
        columns=movie_ids,
        fill_value=0.0,
    )
    pivot = pivot.fillna(0.0)
    pivot.loc[0] = 0.0
    pivot = pivot.sort_index()

    matrix = pivot.to_numpy(dtype=float)
    max_rank = min(matrix.shape[0] - 1, matrix.shape[1] - 1)
    latent_dims = max(1, min(n_components, max_rank))
    if latent_dims < 1:
        return None

    svd = TruncatedSVD(n_components=latent_dims, random_state=42)
    user_factors = svd.fit_transform(matrix)
    movie_factors = svd.components_.T
    reconstructed = user_factors @ movie_factors.T

    return SvdModelArtifacts(
        user_ids=[int(value) for value in real_user_ids],
        row_labels=[int(value) for value in pivot.index.tolist()],
        movie_ids=[int(value) for value in pivot.columns.tolist()],
        user_factors=user_factors,
        movie_factors=movie_factors,
        reconstructed_scores=reconstructed,
    )


def recommend_movies_svd(session, user_id: int, top_n: int = 10, n_components: int = 12, include_embeddings: bool = False) -> dict:
    del session

    # Keep ordering aligned with /movies endpoint so cold-start matches Featured picks.
    movies = Movie.query.order_by(Movie.title.asc()).all()
    interactions = Interaction.query.order_by(Interaction.created_at.desc()).all()
    watched_movie_ids = {
        int(interaction.movie_id)
        for interaction in Interaction.query.filter_by(user_id=user_id).all()
    }
    preferred_genres = _collect_user_preferred_genres(user_id)

    model = _build_svd_model(interactions, n_components=n_components)
    if model is None or user_id not in model.user_ids:
        return {
            "algorithm": "svd-collaborative",
            "mode": "cold-start-popular",
            "user_id": user_id,
            "top_n": top_n,
            "latent_dimensions": 0,
            # In cold-start mode, mirror Featured list ordering for consistent UX.
            "recommendations": _fallback_popular_movies(movies, [], watched_movie_ids, top_n),
        }

    user_index_by_id = {uid: index for index, uid in enumerate(model.row_labels)}
    movie_index_by_id = {mid: index for index, mid in enumerate(model.movie_ids)}
    movie_by_id = {int(movie.movie_id): movie for movie in movies}

    user_index = user_index_by_id[user_id]
    user_scores = model.reconstructed_scores[user_index]

    candidates: list[tuple[int, float]] = []
    for movie_id, score in zip(model.movie_ids, user_scores, strict=False):
        if movie_id in watched_movie_ids:
            continue
        if movie_id not in movie_by_id:
            continue
        movie = movie_by_id[movie_id]
        adjusted_score = float(score) + _genre_affinity_bonus(movie, preferred_genres)
        candidates.append((movie_id, adjusted_score))

    candidates.sort(key=lambda item: item[1], reverse=True)

    recommendations: list[dict] = []
    for movie_id, score in candidates[: max(top_n, 0)]:
        movie = movie_by_id[movie_id]
        payload = {
            **movie.to_dict(),
            "svd_score": round(score, 4),
            "source": "svd",
        }
        if include_embeddings:
            payload["movie_embedding"] = [
                round(float(value), 6) for value in model.movie_factors[movie_index_by_id[movie_id]].tolist()
            ]
        recommendations.append(payload)

    result = {
        "algorithm": "svd-collaborative",
        "mode": "svd",
        "user_id": user_id,
        "top_n": top_n,
        "latent_dimensions": int(model.user_factors.shape[1]),
        "users_modeled": len(model.user_ids),
        "movies_modeled": len(model.movie_ids),
        "already_watched_filtered": len(watched_movie_ids),
        "recommendations": recommendations,
    }
    if include_embeddings:
        result["user_embedding"] = [
            round(float(value), 6) for value in model.user_factors[user_index].tolist()
        ]

    return result
