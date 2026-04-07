from __future__ import annotations

import csv
import importlib
from pathlib import Path

import numpy as np
import pandas as pd

try:
    surprise_module = importlib.import_module("surprise")
    Dataset = getattr(surprise_module, "Dataset")
    Reader = getattr(surprise_module, "Reader")
    SVD = getattr(surprise_module, "SVD")

    SURPRISE_AVAILABLE = True
except Exception:
    Dataset = None
    Reader = None
    SVD = None
    SURPRISE_AVAILABLE = False

from backend.models import Interaction, Movie
from backend.services.movielens_service import build_app_movie_index, load_movielens_ratings_for_app_movies
from backend.services.profile_service import classify_user_profile, filter_movies_by_profile

APP_USER_OFFSET = 1_000_000


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def interaction_to_rating(interaction: Interaction) -> float:
    rating = float(interaction.interest_level)

    if interaction.watch_duration == "full":
        rating += 1.0
    if interaction.completed:
        rating += 0.5
    if interaction.skipped_scenes:
        rating -= 1.0
    if interaction.skipped_music:
        rating -= 0.5
    if interaction.watch_duration == "10":
        rating -= 1.5

    return _clamp(rating, 1.0, 5.0)


def _movielens_paths(data_dir: Path) -> list[Path]:
    return [
        data_dir / "ml-latest-small" / "ratings.csv",
        data_dir / "ratings.csv",
        data_dir / "movielens_ratings.csv",
    ]


def _load_movielens_rows(data_dir: Path, allowed_movie_ids: set[int] | None = None) -> list[dict]:
    for csv_path in _movielens_paths(data_dir):
        if not csv_path.exists():
            continue

        rows: list[dict] = []
        with csv_path.open("r", encoding="utf-8", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            for row in reader:
                user_id = row.get("userId")
                movie_id = row.get("movieId")
                rating = row.get("rating")
                if user_id is None or movie_id is None or rating is None:
                    continue

                try:
                    movie_id_int = int(movie_id)
                    if allowed_movie_ids is not None and movie_id_int not in allowed_movie_ids:
                        continue

                    rows.append(
                        {
                            "user_id": int(user_id),
                            "movie_id": movie_id_int,
                            "rating": float(rating),
                        }
                    )
                except (TypeError, ValueError):
                    continue

        if rows:
            return rows

    return []


def build_training_dataframe(session, data_dir: Path, interactions: list[Interaction]) -> pd.DataFrame:
    app_movie_index = build_app_movie_index(session, data_dir)
    movielens_rows = load_movielens_ratings_for_app_movies(data_dir, app_movie_index)
    if not movielens_rows:
        app_movie_ids = {int(movie.movie_id) for movie in Movie.query.all()}
        movielens_rows = _load_movielens_rows(data_dir, allowed_movie_ids=app_movie_ids)

    generated_rows = [
        {
            "user_id": APP_USER_OFFSET + int(interaction.user_id),
            "movie_id": int(interaction.movie_id),
            "rating": interaction_to_rating(interaction),
        }
        for interaction in interactions
    ]

    merged_rows = movielens_rows + generated_rows
    if not merged_rows:
        raise ValueError("No ratings data found. Add MovieLens ratings or create interactions first.")

    frame = pd.DataFrame(merged_rows)
    frame["user_id"] = frame["user_id"].astype(int)
    frame["movie_id"] = frame["movie_id"].astype(int)
    frame["rating"] = frame["rating"].astype(float)
    return frame


def _fit_svd(training_frame: pd.DataFrame):
    if not SURPRISE_AVAILABLE:
        raise RuntimeError("Surprise not available")

    reader_cls = Reader
    dataset_cls = Dataset
    svd_cls = SVD
    if reader_cls is None or dataset_cls is None or svd_cls is None:
        raise RuntimeError("Surprise symbols are unavailable")

    reader = reader_cls(rating_scale=(1, 5))
    dataset = dataset_cls.load_from_df(training_frame[["user_id", "movie_id", "rating"]], reader)
    trainset = dataset.build_full_trainset()

    model = svd_cls(n_factors=60, n_epochs=20, random_state=42)
    model.fit(trainset)
    return model


class _Prediction:
    def __init__(self, est: float):
        self.est = est


class _NumpySVDModel:
    def __init__(self, training_frame: pd.DataFrame):
        self.global_mean = float(training_frame["rating"].mean())
        self.user_ids = sorted(training_frame["user_id"].unique().tolist())
        self.movie_ids = sorted(training_frame["movie_id"].unique().tolist())

        self.user_index = {uid: idx for idx, uid in enumerate(self.user_ids)}
        self.movie_index = {mid: idx for idx, mid in enumerate(self.movie_ids)}

        matrix = np.full((len(self.user_ids), len(self.movie_ids)), self.global_mean, dtype=float)
        counts = np.zeros_like(matrix)

        user_indices = training_frame["user_id"].map(self.user_index).to_numpy(dtype=int)
        movie_indices = training_frame["movie_id"].map(self.movie_index).to_numpy(dtype=int)
        rating_values = training_frame["rating"].to_numpy(dtype=float)

        np.add.at(matrix, (user_indices, movie_indices), rating_values)
        np.add.at(counts, (user_indices, movie_indices), 1.0)

        observed = counts > 0
        matrix[observed] = matrix[observed] / (counts[observed] + 1.0)

        centered = matrix - self.global_mean
        u_mat, singular_values, v_t = np.linalg.svd(centered, full_matrices=False)
        latent_k = max(2, min(20, len(singular_values)))
        sigma = np.diag(singular_values[:latent_k])
        reconstructed = u_mat[:, :latent_k] @ sigma @ v_t[:latent_k, :]
        self.reconstructed = reconstructed + self.global_mean

    def predict(self, uid: int, iid: int):
        u_idx = self.user_index.get(uid)
        m_idx = self.movie_index.get(iid)
        if u_idx is None or m_idx is None:
            return _Prediction(_clamp(self.global_mean, 1.0, 5.0))

        return _Prediction(_clamp(float(self.reconstructed[u_idx, m_idx]), 1.0, 5.0))


def recommend_for_user(session, data_dir: Path, user_id: int, top_n: int = 20) -> dict:
    interactions = Interaction.query.all()
    training_frame = build_training_dataframe(session, data_dir, interactions)
    if SURPRISE_AVAILABLE:
        model = _fit_svd(training_frame)
        model_backend = "surprise"
    else:
        model = _NumpySVDModel(training_frame)
        model_backend = "numpy-fallback"

    internal_user_id = APP_USER_OFFSET + int(user_id)
    user_seen_movie_ids = {interaction.movie_id for interaction in interactions if interaction.user_id == user_id}

    profile_data = classify_user_profile(user_id)
    movies = filter_movies_by_profile(Movie.query.order_by(Movie.title.asc()).all(), profile_data)
    candidate_movies = [movie for movie in movies if movie.movie_id not in user_seen_movie_ids]
    if not candidate_movies:
        candidate_movies = movies

    scored = []
    for movie in candidate_movies:
        prediction = model.predict(uid=internal_user_id, iid=int(movie.movie_id))
        scored.append(
            {
                "movie": movie.to_dict(),
                "svd_score": round(float(prediction.est), 4),
            }
        )

    scored.sort(key=lambda item: item["svd_score"], reverse=True)
    recommendations = scored[:top_n]

    return {
        "user_id": user_id,
        "recommendations": recommendations,
        "count": len(recommendations),
        "training": {
            "total_rows": int(len(training_frame)),
            "movielens_rows": int(len(training_frame) - len(interactions)),
            "interaction_rows": int(len(interactions)),
            "candidate_movies": len(candidate_movies),
            "model_backend": model_backend,
            "profile": profile_data,
        },
    }
