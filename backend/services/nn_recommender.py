from __future__ import annotations

import csv
import importlib
import os
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import train_test_split
from sklearn.compose import TransformedTargetRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.preprocessing import MinMaxScaler

from backend.models import Interaction, Movie
from backend.services.movielens_service import build_app_movie_index, load_movielens_ratings_for_app_movies
from backend.services.profile_service import classify_user_profile, filter_movies_by_profile
from backend.services.svd_recommender import APP_USER_OFFSET, recommend_for_user

try:
    tf_module = importlib.import_module("tensorflow")
    keras_layers = importlib.import_module("tensorflow.keras.layers")
    keras_models = importlib.import_module("tensorflow.keras.models")

    TF_AVAILABLE = True
except Exception:
    tf_module = None
    keras_layers = None
    keras_models = None
    TF_AVAILABLE = False


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _duration_to_norm(duration: str) -> float:
    mapping = {
        "10": 10.0,
        "30": 30.0,
        "60": 60.0,
        "full": 90.0,
    }
    return mapping.get(str(duration).strip().lower(), 30.0) / 90.0


def _interaction_rating(interaction: Interaction) -> float:
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


def _load_movielens_feature_rows(data_dir: Path, allowed_movie_ids: set[int] | None = None) -> list[dict]:
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
                            "watch_duration_norm": 30.0 / 90.0,
                            "skipped_scenes": 0.0,
                            "skipped_music": 0.0,
                            "interest_level": 3.0,
                            "rating": float(rating),
                        }
                    )
                except (TypeError, ValueError):
                    continue

        if rows:
            return rows

    return []


def build_nn_training_dataframe(session, data_dir: Path, interactions: list[Interaction]) -> pd.DataFrame:
    app_movie_index = build_app_movie_index(session, data_dir)
    movielens_rows = load_movielens_ratings_for_app_movies(data_dir, app_movie_index)
    if movielens_rows:
        movielens_rows = [
            {
                "user_id": row["user_id"],
                "movie_id": row["movie_id"],
                "watch_duration_norm": 30.0 / 90.0,
                "skipped_scenes": 0.0,
                "skipped_music": 0.0,
                "interest_level": 3.0,
                "rating": row["rating"],
            }
            for row in movielens_rows
        ]
    else:
        app_movie_ids = {int(movie.movie_id) for movie in Movie.query.all()}
        movielens_rows = _load_movielens_feature_rows(data_dir, allowed_movie_ids=app_movie_ids)

    interaction_rows = [
        {
            "user_id": APP_USER_OFFSET + int(interaction.user_id),
            "movie_id": int(interaction.movie_id),
            "watch_duration_norm": _duration_to_norm(interaction.watch_duration),
            "skipped_scenes": float(bool(interaction.skipped_scenes)),
            "skipped_music": float(bool(interaction.skipped_music)),
            "interest_level": float(interaction.interest_level),
            "rating": _interaction_rating(interaction),
        }
        for interaction in interactions
    ]

    rows = movielens_rows + interaction_rows
    if not rows:
        raise ValueError("No ratings data found. Add MovieLens ratings or create interactions first.")

    app_movie_ids = {int(movie.movie_id) for movie in Movie.query.all()}
    known_movie_ids = {int(row["movie_id"]) for row in rows}
    missing_movie_ids = sorted(app_movie_ids - known_movie_ids)
    if missing_movie_ids:
        global_rating = float(np.mean([float(row["rating"]) for row in rows]))
        synthetic_users = (-11, -12, -13)
        synthetic_behaviors = (
            (30.0 / 90.0, 0.0, 0.0, 3.0),
            (60.0 / 90.0, 0.0, 0.0, 4.0),
            (10.0 / 90.0, 1.0, 0.0, 2.0),
        )
        synthetic_offsets = (0.0, 0.25, -0.25)

        for movie_id in missing_movie_ids:
            for user_seed, behavior_seed, offset in zip(synthetic_users, synthetic_behaviors, synthetic_offsets):
                watch_duration_norm, skipped_scenes, skipped_music, interest_level = behavior_seed
                rows.append(
                    {
                        "user_id": int(user_seed),
                        "movie_id": int(movie_id),
                        "watch_duration_norm": float(watch_duration_norm),
                        "skipped_scenes": float(skipped_scenes),
                        "skipped_music": float(skipped_music),
                        "interest_level": float(interest_level),
                        "rating": _clamp(global_rating + float(offset), 1.0, 5.0),
                    }
                )

    frame = pd.DataFrame(rows)
    frame["user_id"] = frame["user_id"].astype(int)
    frame["movie_id"] = frame["movie_id"].astype(int)
    frame["rating"] = frame["rating"].astype(float)
    return frame


def _train_with_tensorflow(frame: pd.DataFrame) -> dict:
    tf = tf_module
    layers = keras_layers
    models = keras_models
    if tf is None or layers is None or models is None:
        raise RuntimeError("TensorFlow unavailable")

    user_ids = sorted(frame["user_id"].unique().tolist())
    movie_ids = sorted(frame["movie_id"].unique().tolist())
    user_index = {uid: idx for idx, uid in enumerate(user_ids)}
    movie_index = {mid: idx for idx, mid in enumerate(movie_ids)}

    frame = frame.copy()
    frame["user_idx"] = frame["user_id"].map(user_index).astype(int)
    frame["movie_idx"] = frame["movie_id"].map(movie_index).astype(int)

    x_inputs = {
        "user_input": frame["user_idx"].to_numpy(),
        "movie_input": frame["movie_idx"].to_numpy(),
        "watch_duration_input": frame["watch_duration_norm"].to_numpy(),
        "skipped_scenes_input": frame["skipped_scenes"].to_numpy(),
        "skipped_music_input": frame["skipped_music"].to_numpy(),
        "interest_input": frame["interest_level"].to_numpy(),
    }
    y = frame["rating"].to_numpy(dtype=np.float32)

    user_input = layers.Input(shape=(1,), name="user_input")
    movie_input = layers.Input(shape=(1,), name="movie_input")
    watch_duration_input = layers.Input(shape=(1,), name="watch_duration_input")
    skipped_scenes_input = layers.Input(shape=(1,), name="skipped_scenes_input")
    skipped_music_input = layers.Input(shape=(1,), name="skipped_music_input")
    interest_input = layers.Input(shape=(1,), name="interest_input")

    user_embedding = layers.Embedding(input_dim=len(user_ids) + 1, output_dim=32)(user_input)
    movie_embedding = layers.Embedding(input_dim=len(movie_ids) + 1, output_dim=32)(movie_input)

    user_vec = layers.Flatten()(user_embedding)
    movie_vec = layers.Flatten()(movie_embedding)

    concatenated = layers.Concatenate()(
        [user_vec, movie_vec, watch_duration_input, skipped_scenes_input, skipped_music_input, interest_input]
    )
    dense_1 = layers.Dense(128, activation="relu")(concatenated)
    dense_2 = layers.Dense(64, activation="relu")(dense_1)
    dense_3 = layers.Dense(32, activation="relu")(dense_2)
    output = layers.Dense(1)(dense_3)

    model = models.Model(
        inputs=[user_input, movie_input, watch_duration_input, skipped_scenes_input, skipped_music_input, interest_input],
        outputs=output,
    )
    model.compile(optimizer="adam", loss="mse", metrics=["mae"])

    history = model.fit(
        x_inputs,
        y,
        validation_split=0.2 if len(frame) >= 20 else 0.1,
        epochs=12,
        verbose=0,
        batch_size=min(64, max(8, len(frame) // 4)),
    )

    return {
        "backend": "tensorflow",
        "model": model,
        "user_index": user_index,
        "movie_index": movie_index,
        "metrics": {
            "loss": [float(v) for v in history.history.get("loss", [])],
            "mae": [float(v) for v in history.history.get("mae", [])],
            "val_loss": [float(v) for v in history.history.get("val_loss", [])],
            "val_mae": [float(v) for v in history.history.get("val_mae", [])],
        },
    }


def _train_with_sklearn(frame: pd.DataFrame) -> dict:
    feature_frame = frame[["user_id", "movie_id", "watch_duration_norm", "skipped_scenes", "skipped_music", "interest_level"]]
    target = frame["rating"].to_numpy(dtype=float)

    x_train, x_val, y_train, y_val = train_test_split(
        feature_frame.to_numpy(dtype=float),
        target,
        test_size=0.2 if len(frame) >= 10 else 0.34,
        random_state=42,
    )

    base_model = Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            (
                "mlp",
                MLPRegressor(
                    hidden_layer_sizes=(48, 24),
                    random_state=42,
                    max_iter=400,
                    early_stopping=True,
                    n_iter_no_change=15,
                ),
            ),
        ]
    )
    model = TransformedTargetRegressor(regressor=base_model, transformer=MinMaxScaler())
    model.fit(x_train, y_train)
    predictions = model.predict(x_val)
    mae_value = float(mean_absolute_error(y_val, predictions))

    return {
        "backend": "sklearn-mlp",
        "model": model,
        "metrics": {
            "loss": [],
            "mae": [mae_value],
            "val_loss": [],
            "val_mae": [mae_value],
        },
    }


def _user_behavior_defaults(interactions: list[Interaction]) -> dict:
    if not interactions:
        return {
            "watch_duration_norm": 30.0 / 90.0,
            "skipped_scenes": 0.0,
            "skipped_music": 0.0,
            "interest_level": 3.0,
        }

    return {
        "watch_duration_norm": float(np.mean([_duration_to_norm(i.watch_duration) for i in interactions])),
        "skipped_scenes": float(np.mean([1.0 if i.skipped_scenes else 0.0 for i in interactions])),
        "skipped_music": float(np.mean([1.0 if i.skipped_music else 0.0 for i in interactions])),
        "interest_level": float(np.mean([float(i.interest_level) for i in interactions])),
    }


def _movie_prior_map(frame: pd.DataFrame) -> dict[int, float]:
    grouped = frame.groupby("movie_id")["rating"].mean()
    movie_ids = grouped.index.to_numpy(dtype=int)
    rating_values = grouped.to_numpy(dtype=float)
    return {int(movie_id): _clamp(float(value), 1.0, 5.0) for movie_id, value in zip(movie_ids, rating_values)}


def _fallback_nn_score(movie_id: int, svd_score: float, behavior: dict, movie_priors: dict[int, float], global_prior: float) -> float:
    prior = movie_priors.get(movie_id, global_prior)
    behavior_bonus = 0.15 * (float(behavior["interest_level"]) - 3.0)
    behavior_bonus += 0.1 * (float(behavior["watch_duration_norm"]) - (30.0 / 90.0))
    behavior_bonus -= 0.15 * float(behavior["skipped_scenes"])
    behavior_bonus -= 0.1 * float(behavior["skipped_music"])

    blended = 0.6 * float(prior) + 0.4 * float(svd_score)
    return _clamp(blended + behavior_bonus, 1.0, 5.0)


def _calibrate_nn_score(raw_nn_score: float, movie_id: int, svd_score: float, movie_priors: dict[int, float], global_prior: float) -> float:
    prior = movie_priors.get(movie_id, global_prior)
    anchor = _clamp((0.65 * float(prior)) + (0.35 * float(svd_score)), 1.0, 5.0)

    if float(raw_nn_score) <= 1.1:
        # Avoid degenerate floor predictions from sparse/cold user rows.
        return _clamp((0.2 * float(raw_nn_score)) + (0.8 * anchor), 1.0, 5.0)

    return _clamp((0.7 * float(raw_nn_score)) + (0.3 * anchor), 1.0, 5.0)


def _should_use_tensorflow() -> bool:
    if not TF_AVAILABLE:
        return False
    flag = os.getenv("SMARTFLIX_USE_TENSORFLOW_NN", "").strip().lower()
    return flag in {"1", "true", "yes", "on"}


def recommend_svd_nn_for_user(session, data_dir: Path, user_id: int, top_n: int = 20) -> dict:
    all_interactions = Interaction.query.all()
    user_interactions = [i for i in all_interactions if i.user_id == user_id]
    behavior = _user_behavior_defaults(user_interactions)
    profile_data = classify_user_profile(user_id)

    nn_frame = build_nn_training_dataframe(session, data_dir, all_interactions)
    movie_priors = _movie_prior_map(nn_frame)
    global_prior = _clamp(float(nn_frame["rating"].mean()), 1.0, 5.0)
    if _should_use_tensorflow():
        nn_artifacts = _train_with_tensorflow(nn_frame)
    else:
        nn_artifacts = _train_with_sklearn(nn_frame)

    svd_payload = recommend_for_user(session, data_dir, user_id=user_id, top_n=100)
    svd_map = {row["movie"]["movie_id"]: float(row["svd_score"]) for row in svd_payload["recommendations"]}

    scored = []
    for movie in filter_movies_by_profile(Movie.query.order_by(Movie.title.asc()).all(), profile_data):
        movie_id = int(movie.movie_id)
        if movie_id not in svd_map:
            continue

        svd_score = _clamp(float(svd_map[movie_id]), 1.0, 5.0)
        used_fallback = False

        if nn_artifacts["backend"] == "tensorflow":
            internal_user_id = APP_USER_OFFSET + int(user_id)
            has_user = internal_user_id in nn_artifacts["user_index"]
            has_movie = movie_id in nn_artifacts["movie_index"]
            if has_user and has_movie:
                user_idx = nn_artifacts["user_index"][internal_user_id]
                movie_idx = nn_artifacts["movie_index"][movie_id]
                prediction = nn_artifacts["model"].predict(
                    {
                        "user_input": np.array([user_idx]),
                        "movie_input": np.array([movie_idx]),
                        "watch_duration_input": np.array([behavior["watch_duration_norm"]]),
                        "skipped_scenes_input": np.array([behavior["skipped_scenes"]]),
                        "skipped_music_input": np.array([behavior["skipped_music"]]),
                        "interest_input": np.array([behavior["interest_level"]]),
                    },
                    verbose=0,
                )
                nn_score = _calibrate_nn_score(float(prediction[0][0]), movie_id, svd_score, movie_priors, global_prior)
            else:
                used_fallback = True
                nn_score = _fallback_nn_score(movie_id, svd_score, behavior, movie_priors, global_prior)
        else:
            if movie_id not in movie_priors:
                used_fallback = True
                nn_score = _fallback_nn_score(movie_id, svd_score, behavior, movie_priors, global_prior)
            else:
                nn_features = np.array(
                    [
                        [
                            float(APP_USER_OFFSET + int(user_id)),
                            float(movie_id),
                            behavior["watch_duration_norm"],
                            behavior["skipped_scenes"],
                            behavior["skipped_music"],
                            behavior["interest_level"],
                        ]
                    ],
                    dtype=float,
                )
                predicted = float(nn_artifacts["model"].predict(nn_features)[0])
                nn_score = _calibrate_nn_score(predicted, movie_id, svd_score, movie_priors, global_prior)

        if used_fallback:
            combined_score = _clamp((0.75 * svd_score) + (0.25 * nn_score), 1.0, 5.0)
        else:
            combined_score = _clamp((0.55 * svd_score) + (0.45 * nn_score), 1.0, 5.0)

        scored.append(
            {
                "movie": movie.to_dict(),
                "svd_score": round(svd_score, 4),
                "nn_score": round(nn_score, 4),
                "combined_score": round(combined_score, 4),
                "nn_fallback": bool(used_fallback),
            }
        )

    scored.sort(key=lambda item: item["combined_score"], reverse=True)
    recommendations = scored[:top_n]

    return {
        "user_id": user_id,
        "count": len(recommendations),
        "recommendations": recommendations,
        "training": {
            "backend": nn_artifacts["backend"],
            "rows": int(len(nn_frame)),
            "metrics": nn_artifacts["metrics"],
            "profile": profile_data,
            "features": [
                "user_id",
                "movie_id",
                "watch_duration_norm",
                "skipped_scenes",
                "skipped_music",
                "interest_level",
            ],
            "dataset_sources": [
                "MovieLens ratings aligned to the app movie catalog",
                "User interaction records saved in SQLite",
                "Synthetic bootstrap rows for app movies that have no historical ratings yet",
            ],
            "explanation": {
                "why_nn": "The NN learns nonlinear interactions between the user, the movie, and the explicit behavior signals.",
                "what_it_gets": "It receives user_id, movie_id, normalized watch duration, skip flags, and interest level.",
                "model": "TensorFlow/Keras dense network when available, otherwise a scikit-learn MLPRegressor fallback.",
            },
        },
    }
