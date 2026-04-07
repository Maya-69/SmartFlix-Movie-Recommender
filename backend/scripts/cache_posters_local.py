from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from backend.app import create_app
from backend.db import db
from backend.models import Movie


def _guess_extension(url: str, content_type: str | None) -> str:
    if content_type:
        lowered = content_type.lower()
        if "png" in lowered:
            return ".png"
        if "webp" in lowered:
            return ".webp"
        if "jpeg" in lowered or "jpg" in lowered:
            return ".jpg"

    path = urlparse(url).path.lower()
    if path.endswith(".png"):
        return ".png"
    if path.endswith(".webp"):
        return ".webp"
    return ".jpg"


def _download_bytes(url: str) -> tuple[bytes, str | None]:
    request = Request(
        url,
        headers={
            "User-Agent": "SmartFlix/1.0 (local-poster-cache)",
            "Accept": "image/*,*/*;q=0.8",
        },
    )
    with urlopen(request, timeout=12) as response:  # nosec B310 - URLs are controlled movie poster sources
        content_type = response.headers.get("Content-Type")
        data = response.read()
    return data, content_type


def main() -> None:
    app = create_app({"SKIP_SEEDING": True, "SKIP_POSTER_SYNC": True})
    public_base = os.getenv("POSTER_PUBLIC_BASE_URL", "http://localhost:5000").rstrip("/")
    posters_dir = Path(__file__).resolve().parents[1] / "static" / "posters"
    posters_dir.mkdir(parents=True, exist_ok=True)

    with app.app_context():
        movies = Movie.query.order_by(Movie.movie_id.asc()).all()
        print(f"movies={len(movies)}", flush=True)

        downloaded = 0
        reused = 0
        failed = 0
        for movie in movies:
            source_url = (movie.poster_url or "").strip()
            if not source_url:
                failed += 1
                print(f"[skip] {movie.movie_id}: {movie.title} (empty poster_url)", flush=True)
                continue

            try:
                existing_candidates = sorted(posters_dir.glob(f"movie_{movie.movie_id}.*"))
                if existing_candidates and existing_candidates[0].is_file() and existing_candidates[0].stat().st_size > 0:
                    filename = existing_candidates[0].name
                    reused += 1
                    action = "reuse"
                else:
                    blob, content_type = _download_bytes(source_url)
                    ext = _guess_extension(source_url, content_type)
                    filename = f"movie_{movie.movie_id}{ext}"
                    target_path = posters_dir / filename
                    target_path.write_bytes(blob)
                    downloaded += 1
                    action = "download"

                movie.poster_url = f"{public_base}/static/posters/{filename}"
                db.session.commit()
                print(f"[{action}] {movie.movie_id}: {movie.title}", flush=True)
            except Exception as error:
                db.session.rollback()
                failed += 1
                print(f"[fail] {movie.movie_id}: {movie.title} -> {error}", flush=True)

        print(f"downloaded={downloaded}", flush=True)
        print(f"reused={reused}", flush=True)
        print(f"failed={failed}", flush=True)
        print(f"stored_at={posters_dir}", flush=True)


if __name__ == "__main__":
    main()
