from flask import Blueprint, jsonify, request

from backend.models import Movie

movies_bp = Blueprint("movies", __name__)


@movies_bp.get("/movies")
def get_movies():
    search = request.args.get("search", type=str, default="").strip().lower()
    genre = request.args.get("genre", type=str, default="").strip().lower()

    query = Movie.query.order_by(Movie.title.asc())
    movies = query.all()

    if search:
        movies = [movie for movie in movies if search in movie.title.lower() or search in movie.genres.lower()]
    if genre:
        movies = [movie for movie in movies if genre in movie.genres.lower()]

    return jsonify({"movies": [movie.to_dict() for movie in movies], "count": len(movies)})
