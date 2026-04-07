from __future__ import annotations

import csv
import re
from pathlib import Path

from backend.models import Movie


def normalize_title(title: str) -> str:
    cleaned_title = re.sub(r"\s*\(\d{4}\)$", "", title).lower().strip()
    cleaned_title = re.sub(r"[^a-z0-9]+", " ", cleaned_title)
    return " ".join(cleaned_title.split())


def _movielens_movies_paths(data_dir: Path) -> list[Path]:
    return [
        data_dir / "ml-latest-small" / "movies.csv",
        data_dir / "movies.csv",
    ]


def _movielens_ratings_paths(data_dir: Path) -> list[Path]:
    return [
        data_dir / "ml-latest-small" / "ratings.csv",
        data_dir / "ratings.csv",
        data_dir / "movielens_ratings.csv",
    ]


def _movielens_links_paths(data_dir: Path) -> list[Path]:
    return [
        data_dir / "ml-latest-small" / "links.csv",
        data_dir / "links.csv",
    ]


def load_movielens_movie_index(data_dir: Path) -> dict[str, int]:
    for csv_path in _movielens_movies_paths(data_dir):
        if not csv_path.exists():
            continue

        movie_index: dict[str, int] = {}
        with csv_path.open("r", encoding="utf-8", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            for row in reader:
                raw_movie_id = row.get("movieId")
                title = row.get("title")
                if raw_movie_id is None or title is None:
                    continue

                try:
                    movie_index[normalize_title(title)] = int(raw_movie_id)
                except (TypeError, ValueError):
                    continue

        if movie_index:
            return movie_index

    return {}


def load_movielens_tmdb_by_movie_id(data_dir: Path) -> dict[int, int]:
    for csv_path in _movielens_links_paths(data_dir):
        if not csv_path.exists():
            continue

        mapping: dict[int, int] = {}
        with csv_path.open("r", encoding="utf-8", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            for row in reader:
                raw_movie_id = row.get("movieId")
                raw_tmdb_id = row.get("tmdbId")
                if raw_movie_id is None or raw_tmdb_id in (None, ""):
                    continue

                try:
                    mapping[int(raw_movie_id)] = int(raw_tmdb_id)
                except (TypeError, ValueError):
                    continue

        if mapping:
            return mapping

    return {}


def load_movielens_tmdb_by_title(data_dir: Path) -> dict[str, int]:
    movie_index = load_movielens_movie_index(data_dir)
    if not movie_index:
        return {}

    tmdb_by_movie_id = load_movielens_tmdb_by_movie_id(data_dir)
    if not tmdb_by_movie_id:
        return {}

    tmdb_by_title: dict[str, int] = {}
    for normalized_title, movielens_movie_id in movie_index.items():
        tmdb_id = tmdb_by_movie_id.get(movielens_movie_id)
        if tmdb_id is not None:
            tmdb_by_title[normalized_title] = tmdb_id

    return tmdb_by_title


def build_app_movie_index(session, data_dir: Path) -> dict[int, int]:
    movielens_movie_index = load_movielens_movie_index(data_dir)
    if not movielens_movie_index:
        return {}

    app_movie_index: dict[int, int] = {}
    for movie in Movie.query.order_by(Movie.movie_id.asc()).all():
        normalized_title = normalize_title(movie.title)
        movie_id = movielens_movie_index.get(normalized_title)
        if movie_id is not None:
            app_movie_index[int(movie.movie_id)] = int(movie_id)

    return app_movie_index


def load_movielens_ratings_for_app_movies(data_dir: Path, app_movie_index: dict[int, int]) -> list[dict]:
    if not app_movie_index:
        return []

    movielens_to_app_movie = {movielens_id: app_id for app_id, movielens_id in app_movie_index.items()}

    for csv_path in _movielens_ratings_paths(data_dir):
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
                    movielens_movie_id = int(movie_id)
                    app_movie_id = movielens_to_app_movie.get(movielens_movie_id)
                    if app_movie_id is None:
                        continue

                    rows.append(
                        {
                            "user_id": int(user_id),
                            "movie_id": int(app_movie_id),
                            "rating": float(rating),
                        }
                    )
                except (TypeError, ValueError):
                    continue

        if rows:
            return rows

    return []