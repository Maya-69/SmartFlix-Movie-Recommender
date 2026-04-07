from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from backend.models import Movie
from backend.services.movielens_service import load_movielens_tmdb_by_title, normalize_title


TMDB_API_BASE_URL = "https://api.themoviedb.org/3"
TMDB_POSTER_BASE_URL = "https://image.tmdb.org/t/p"
TMDB_POSTER_SIZE_DEFAULT = "w500"
TMDB_WEB_BASE_URL = "https://www.themoviedb.org"

_ALIAS_TITLE_HINTS = {
    "seven": ["Se7en"],
    "independence day": ["ID4"],
    "twelve monkeys": ["12 Monkeys"],
    "men in black": ["MIB"],
}


def _tmdb_api_key() -> str:
    return os.getenv("TMDB_API_KEY", "").strip()


def _tmdb_language() -> str:
    return os.getenv("TMDB_SEARCH_LANGUAGE", "en-US").strip() or "en-US"


def _tmdb_poster_size() -> str:
    return os.getenv("TMDB_POSTER_SIZE", TMDB_POSTER_SIZE_DEFAULT).strip() or TMDB_POSTER_SIZE_DEFAULT


def _looks_like_placeholder(url: str | None) -> bool:
    if not url:
        return True
    lowered = url.lower()
    return "placehold.co" in lowered or "placeholder" in lowered


def _request_json(url: str) -> dict:
    request = Request(url, headers={"Accept": "application/json"})
    with urlopen(request, timeout=10) as response:  # nosec B310 - TMDB is a trusted external API
        payload = response.read().decode("utf-8")
    return json.loads(payload)


def _request_text(url: str) -> str:
    request = Request(
        url,
        headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "User-Agent": "SmartFlix/1.0 (local-dev; poster-fallback)",
        },
    )
    timeout_seconds = float(os.getenv("TMDB_WEB_TIMEOUT_SECONDS", "4"))
    with urlopen(request, timeout=timeout_seconds) as response:  # nosec B310 - public TMDB pages are trusted external content
        return response.read().decode("utf-8", errors="ignore")


def _default_data_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "data"


def _strip_aka_segments(title: str) -> str:
    stripped = re.sub(r"\(a\.k\.a\.\s*[^)]*\)", "", title, flags=re.IGNORECASE)
    stripped = re.sub(r"\([^)]*\)", "", stripped)
    return " ".join(stripped.split()).strip()


def _title_lookup_candidates(title: str) -> list[str]:
    candidates: list[str] = []

    def add(value: str):
        clean = " ".join(value.split()).strip()
        if clean and clean not in candidates:
            candidates.append(clean)

    add(title)
    add(_strip_aka_segments(title))

    alias_match = re.search(r"\(a\.k\.a\.\s*([^)]+)\)", title, re.IGNORECASE)
    if alias_match:
        add(alias_match.group(1).strip())

    if ", The" in title:
        add(title.replace(", The", "").strip())
    if ", A" in title:
        add(title.replace(", A", "").strip())
    if ":" in title:
        add(title.split(":", 1)[0].strip())

    normalized_core = normalize_title(_strip_aka_segments(title))
    for alias in _ALIAS_TITLE_HINTS.get(normalized_core, []):
        add(alias)

    return candidates


@lru_cache(maxsize=256)
def search_tmdb_movie(title: str, api_key: str, language: str) -> dict | None:
    query = urlencode(
        {
            "api_key": api_key,
            "query": title,
            "language": language,
            "include_adult": "false",
        }
    )
    url = f"{TMDB_API_BASE_URL}/search/movie?{query}"
    try:
        payload = _request_json(url)
    except (HTTPError, URLError, json.JSONDecodeError, TimeoutError):
        return None

    results = payload.get("results") or []
    for result in results:
        if result.get("poster_path"):
            return result
    return results[0] if results else None


@lru_cache(maxsize=4096)
def get_tmdb_movie_by_id(tmdb_id: int, api_key: str, language: str) -> dict | None:
    query = urlencode(
        {
            "api_key": api_key,
            "language": language,
        }
    )
    url = f"{TMDB_API_BASE_URL}/movie/{tmdb_id}?{query}"
    try:
        payload = _request_json(url)
    except (HTTPError, URLError, json.JSONDecodeError, TimeoutError):
        return None

    return payload if isinstance(payload, dict) else None


@lru_cache(maxsize=256)
def search_tmdb_movie_page(title: str) -> str | None:
    query = urlencode({"query": title})
    url = f"{TMDB_WEB_BASE_URL}/search?{query}"
    try:
        html = _request_text(url)
    except Exception:
        return None

    match = re.search(r'href="(/movie/\d+[^"?#]*)"', html)
    if match:
        return match.group(1)

    fallback_match = re.search(r'/movie/\d+[^"?#]*', html)
    return fallback_match.group(0) if fallback_match else None


@lru_cache(maxsize=256)
def get_tmdb_poster_from_web(movie_path: str) -> str | None:
    url = f"{TMDB_WEB_BASE_URL}{movie_path}"
    try:
        html = _request_text(url)
    except Exception:
        return None

    patterns = [
        r'https://media\.themoviedb\.org/t/p/w500/[^"\']+\.jpg',
        r'https://media\.themoviedb\.org/t/p/w300_and_h450_face/[^"\']+\.jpg',
        r'https://media\.themoviedb\.org/t/p/w220_and_h330_face/[^"\']+\.jpg',
    ]
    for pattern in patterns:
        match = re.search(pattern, html)
        if match:
            return match.group(0)

    return None


@lru_cache(maxsize=1)
def _tmdb_id_by_title_map_cached() -> dict[str, int]:
    return load_movielens_tmdb_by_title(_default_data_dir())


def build_tmdb_poster_url(poster_path: str | None, poster_size: str | None = None) -> str | None:
    if not poster_path:
        return None
    size = poster_size or _tmdb_poster_size()
    return f"{TMDB_POSTER_BASE_URL}/{size}{poster_path}"


def enrich_movie_poster_from_tmdb(movie: Movie, force: bool = False, tmdb_id_hint: int | None = None) -> str | None:
    if not force and not _looks_like_placeholder(movie.poster_url):
        return None

    api_key = _tmdb_api_key()
    direct_tmdb_id = tmdb_id_hint
    if direct_tmdb_id is None:
        tmdb_by_title = _tmdb_id_by_title_map_cached()
        for candidate in _title_lookup_candidates(movie.title):
            mapped = tmdb_by_title.get(normalize_title(candidate))
            if mapped is not None:
                direct_tmdb_id = int(mapped)
                break

    if api_key and direct_tmdb_id is not None:
        direct_payload = get_tmdb_movie_by_id(int(direct_tmdb_id), api_key, _tmdb_language())
        direct_poster_url = build_tmdb_poster_url(direct_payload.get("poster_path") if direct_payload else None)
        if direct_poster_url:
            movie.poster_url = direct_poster_url
            return direct_poster_url
    elif direct_tmdb_id is not None:
        # API key may be unavailable locally; use public TMDB web page by id.
        movie_path = f"/movie/{int(direct_tmdb_id)}"
        web_poster_url = get_tmdb_poster_from_web(movie_path)
        if web_poster_url:
            movie.poster_url = web_poster_url
            return web_poster_url

    search_terms = _title_lookup_candidates(movie.title)

    selected_result = None
    if api_key:
        for search_term in search_terms:
            selected_result = search_tmdb_movie(search_term, api_key, _tmdb_language())
            if selected_result:
                break

    poster_url = build_tmdb_poster_url(selected_result.get("poster_path") if selected_result else None)
    if not poster_url:
        for search_term in search_terms:
            movie_path = search_tmdb_movie_page(search_term)
            if not movie_path:
                continue

            web_poster_url = get_tmdb_poster_from_web(movie_path)
            if web_poster_url:
                movie.poster_url = web_poster_url
                return web_poster_url

        return None

    movie.poster_url = poster_url
    return poster_url


def sync_movie_posters_from_tmdb(session, force: bool = False, limit: int | None = None) -> dict:
    movies = Movie.query.order_by(Movie.movie_id.asc()).all()
    if limit is not None:
        movies = movies[: max(limit, 0)]

    updated_movies: list[dict] = []
    checked = 0
    for movie in movies:
        checked += 1
        poster_url = enrich_movie_poster_from_tmdb(movie, force=force)
        if not poster_url:
            continue

        updated_movies.append(
            {
                "movie_id": movie.movie_id,
                "title": movie.title,
                "poster_url": poster_url,
            }
        )

    if updated_movies:
        session.commit()

    return {
        "status": "synced",
        "checked": checked,
        "updated": len(updated_movies),
        "movies": updated_movies,
    }