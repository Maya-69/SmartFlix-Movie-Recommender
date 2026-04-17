from __future__ import annotations

import csv
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

from backend.models import Movie


DEFAULT_MOVIES = [
    {"movie_id": 1, "title": "The Matrix", "genres": "Action|Sci-Fi", "poster_url": "/static/posters/movie_1.jpg"},
    {"movie_id": 2, "title": "Inception", "genres": "Action|Adventure|Sci-Fi", "poster_url": "/static/posters/movie_2.jpg"},
    {"movie_id": 3, "title": "Interstellar", "genres": "Adventure|Drama|Sci-Fi", "poster_url": "/static/posters/movie_3.jpg"},
    {"movie_id": 4, "title": "The Dark Knight", "genres": "Action|Crime|Drama", "poster_url": "/static/posters/movie_4.jpg"},
    {"movie_id": 5, "title": "Parasite", "genres": "Drama|Thriller", "poster_url": "/static/posters/movie_5.jpg"},
    {"movie_id": 6, "title": "Spirited Away", "genres": "Animation|Adventure|Fantasy", "poster_url": "/static/posters/movie_6.jpg"},
    {"movie_id": 7, "title": "The Godfather", "genres": "Crime|Drama", "poster_url": "/static/posters/movie_7.jpg"},
    {"movie_id": 8, "title": "Avengers: Endgame", "genres": "Action|Adventure|Drama", "poster_url": "/static/posters/movie_8.jpg"},
    {"movie_id": 9, "title": "Coco", "genres": "Animation|Family|Fantasy", "poster_url": "/static/posters/movie_9.jpg"},
    {"movie_id": 10, "title": "Whiplash", "genres": "Drama|Music", "poster_url": "/static/posters/movie_10.jpg"},
    {"movie_id": 11, "title": "La La Land", "genres": "Comedy|Drama|Music", "poster_url": "/static/posters/movie_11.jpg"},
    {"movie_id": 12, "title": "Titanic", "genres": "Drama|Romance", "poster_url": "/static/posters/movie_12.jpg"},
]

STATIC_POSTER_URLS = {movie["title"]: movie["poster_url"] for movie in DEFAULT_MOVIES}


def _normalize_title_key(title: str) -> str:
    lowered = re.sub(r"\s*\(\d{4}\)$", "", title).lower().strip()
    lowered = re.sub(r"[^a-z0-9]+", " ", lowered)
    return " ".join(lowered.split())


def _placeholder_url(title: str) -> str:
    del title
    return "/static/posters/placeholder.svg"


def _normalize_movie_row(row: dict) -> dict:
    raw_movie_id = row.get("movie_id") or row.get("movieId") or row.get("id")
    title = row.get("title") or row.get("original_title") or row.get("name") or "Untitled Movie"
    genres = row.get("genres") or row.get("genre") or "Unknown"

    movie_id = None
    if raw_movie_id not in (None, ""):
        try:
            movie_id = int(raw_movie_id)
        except (TypeError, ValueError):
            movie_id = None

    poster_url = (row.get("poster_url") or row.get("posterPath") or row.get("poster_path") or "").strip()
    if poster_url.startswith("/static/posters/"):
        normalized_poster_url = poster_url
    else:
        parsed = urlparse(poster_url) if poster_url else None
        if parsed and parsed.path.startswith("/static/posters/"):
            normalized_poster_url = parsed.path
        elif movie_id is not None:
            normalized_poster_url = f"/static/posters/movie_{movie_id}.jpg"
        else:
            normalized_poster_url = STATIC_POSTER_URLS.get(title, _placeholder_url(title))

    return {
        "movie_id": movie_id,
        "title": title,
        "genres": genres,
        "poster_url": normalized_poster_url,
    }


def load_movies_from_csv(csv_path: Path) -> list[dict]:
    if not csv_path.exists():
        return DEFAULT_MOVIES.copy()

    movies: list[dict] = []
    with csv_path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            normalized = _normalize_movie_row(row)
            if normalized["movie_id"] is None:
                normalized["movie_id"] = len(movies) + 1
            movies.append(normalized)

    return movies or DEFAULT_MOVIES.copy()


def seed_movies_if_empty(session, csv_path: Path) -> int:
    if Movie.query.count() > 0:
        return 0

    rows = load_movies_from_csv(csv_path)
    inserted = 0
    for row in rows:
        movie = Movie.query.filter_by(movie_id=row["movie_id"]).first()
        if movie is None:
            session.add(Movie(**row))
            inserted += 1

    session.commit()
    return inserted


def _movielens_movie_rows(data_dir: Path) -> list[dict]:
    movies_csv = data_dir / "ml-latest-small" / "movies.csv"
    ratings_csv = data_dir / "ml-latest-small" / "ratings.csv"
    if not movies_csv.exists() or not ratings_csv.exists():
        return []

    rating_counts: Counter[int] = Counter()
    with ratings_csv.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            try:
                rating_counts[int(row.get("movieId", "0"))] += 1
            except (TypeError, ValueError):
                continue

    rows: list[dict] = []
    with movies_csv.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            raw_movie_id = row.get("movieId")
            title = row.get("title")
            if raw_movie_id is None or title is None:
                continue
            try:
                movie_id = int(raw_movie_id)
            except (TypeError, ValueError):
                continue

            rows.append(
                {
                    "movie_id": movie_id,
                    "title": title,
                    "genres": (row.get("genres") or "Unknown").replace("(no genres listed)", "Unknown"),
                    "rating_count": int(rating_counts.get(movie_id, 0)),
                }
            )

    rows.sort(key=lambda item: (item["rating_count"], item["title"]), reverse=True)
    return rows


def ensure_movie_catalog(session, csv_path: Path, target_count: int = 50) -> int:
    inserted = 0
    newly_inserted: list[Movie] = []
    existing_movies = Movie.query.order_by(Movie.movie_id.asc()).all()
    existing_movie_ids = {int(movie.movie_id) for movie in existing_movies}
    existing_title_keys = {_normalize_title_key(movie.title) for movie in existing_movies}

    base_rows = load_movies_from_csv(csv_path)
    for row in base_rows:
        title_key = _normalize_title_key(row["title"])
        if int(row["movie_id"]) in existing_movie_ids or title_key in existing_title_keys:
            continue

        movie = Movie(**row)
        session.add(movie)
        newly_inserted.append(movie)
        existing_movie_ids.add(int(row["movie_id"]))
        existing_title_keys.add(title_key)
        inserted += 1

    current_count = len(existing_movie_ids)
    if current_count < target_count:
        next_movie_id = max(existing_movie_ids) if existing_movie_ids else 0
        for row in _movielens_movie_rows(csv_path.parent):
            if current_count >= target_count:
                break

            title = re.sub(r"\s*\(\d{4}\)$", "", row["title"]).strip()
            title_key = _normalize_title_key(title)
            if title_key in existing_title_keys:
                continue

            next_movie_id += 1
            movie = Movie()
            movie.movie_id = next_movie_id
            movie.title = title
            movie.genres = row["genres"] or "Unknown"
            movie.poster_url = _placeholder_url(title)
            session.add(movie)
            newly_inserted.append(movie)
            existing_title_keys.add(title_key)
            current_count += 1
            inserted += 1

    for movie in newly_inserted:
        if "/static/posters/" not in (movie.poster_url or ""):
            movie.poster_url = f"/static/posters/movie_{int(movie.movie_id)}.jpg"

    if inserted:
        session.commit()

    return inserted


def refresh_seed_movies_with_static_posters(session) -> int:
    updated = 0
    for movie in Movie.query.all():
        poster_url = STATIC_POSTER_URLS.get(movie.title)
        if poster_url and movie.poster_url != poster_url:
            current_url = (movie.poster_url or "").strip().lower()
            if "/static/posters/" in current_url:
                continue
            movie.poster_url = poster_url
            updated += 1

    if updated:
        session.commit()

    return updated
