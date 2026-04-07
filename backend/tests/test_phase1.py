import os
import tempfile
import unittest
from pathlib import Path
from typing import cast
from unittest.mock import patch

from backend.app import create_app
from backend.db import db
from backend.models import Interaction, Movie, User
from backend.services.movielens_service import build_app_movie_index, load_movielens_ratings_for_app_movies
from backend.services.tmdb_service import sync_movie_posters_from_tmdb


class Phase1ApiTestCase(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        self.app = create_app(
            {
                "TESTING": True,
                "SKIP_SEEDING": True,
                "SKIP_POSTER_SYNC": True,
                "SQLALCHEMY_DATABASE_URI": f"sqlite:///{self.db_path}",
                "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            }
        )
        self.client = self.app.test_client()

        with self.app.app_context():
            db.drop_all()
            db.create_all()
            movie_rows = [
                (1, "Test Movie", "Drama", "https://placehold.co/300x450?text=Test"),
                (2, "Another Test", "Action", "https://placehold.co/300x450?text=Another"),
                (3, "Sci-Fi Test", "Sci-Fi", "https://placehold.co/300x450?text=Sci-Fi"),
                (4, "Drama Test", "Drama", "https://placehold.co/300x450?text=Drama"),
                (5, "Comedy Test", "Comedy", "https://placehold.co/300x450?text=Comedy"),
                (6, "Adventure Test", "Adventure", "https://placehold.co/300x450?text=Adventure"),
            ]
            for movie_id, title, genres, poster_url in movie_rows:
                movie = Movie()
                movie.movie_id = movie_id
                movie.title = title
                movie.genres = genres
                movie.poster_url = poster_url
                db.session.add(movie)
            db.session.commit()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_login_creates_user(self):
        response = self.client.post("/user", json={"username": "maya"})
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["user"]["username"], "maya")

    def test_movies_endpoint_returns_movies(self):
        response = self.client.get("/movies")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertGreaterEqual(payload["count"], 1)
        titles = [movie["title"] for movie in payload["movies"]]
        self.assertIn("Test Movie", titles)

    def test_interaction_is_saved(self):
        user_response = self.client.post("/user", json={"username": "maya"})
        user_id = user_response.get_json()["user"]["user_id"]

        response = self.client.post(
            "/interact",
            json={
                "user_id": user_id,
                "movie_id": 1,
                "watched": True,
                "watch_duration": "full",
                "completed": True,
                "skipped_scenes": False,
                "skipped_music": False,
                "interest_level": 5,
            },
        )

        self.assertEqual(response.status_code, 201)
        payload = response.get_json()
        self.assertEqual(payload["interaction"]["watch_duration"], "full")

        with self.app.app_context():
            self.assertEqual(Interaction.query.count(), 1)
            self.assertEqual(User.query.count(), 1)

    def test_interactions_can_be_retrieved_for_user(self):
        user_response = self.client.post("/user", json={"username": "maya"})
        user_id = user_response.get_json()["user"]["user_id"]

        self.client.post(
            "/interact",
            json={
                "user_id": user_id,
                "movie_id": 1,
                "watched": True,
                "watch_duration": "60",
                "completed": False,
                "skipped_scenes": True,
                "skipped_music": False,
                "interest_level": 4,
            },
        )

        response = self.client.get(f"/interact?user_id={user_id}")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["interactions"][0]["movie_title"], "Test Movie")
        self.assertEqual(payload["interactions"][0]["username"], "maya")

    def test_completed_without_watched_is_rejected(self):
        user_response = self.client.post("/user", json={"username": "maya"})
        user_id = user_response.get_json()["user"]["user_id"]

        response = self.client.post(
            "/interact",
            json={
                "user_id": user_id,
                "movie_id": 1,
                "watched": False,
                "watch_duration": "10",
                "completed": True,
                "skipped_scenes": False,
                "skipped_music": False,
                "interest_level": 2,
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("completed", response.get_json()["error"])

    def test_svd_recommendations_endpoint_returns_items(self):
        user_response = self.client.post("/user", json={"username": "maya"})
        user_id = user_response.get_json()["user"]["user_id"]

        self.client.post(
            "/interact",
            json={
                "user_id": user_id,
                "movie_id": 1,
                "watched": True,
                "watch_duration": "full",
                "completed": True,
                "skipped_scenes": False,
                "skipped_music": False,
                "interest_level": 5,
            },
        )

        response = self.client.get(f"/recommend/svd?user_id={user_id}&top_n=5")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertGreater(payload["count"], 0)
        self.assertIn("svd_score", payload["recommendations"][0])

    def test_svd_recommendations_change_by_user_profile(self):
        user_a_response = self.client.post("/user", json={"username": "maya"})
        user_b_response = self.client.post("/user", json={"username": "alex"})
        user_a_id = user_a_response.get_json()["user"]["user_id"]
        user_b_id = user_b_response.get_json()["user"]["user_id"]

        self.client.post(
            "/interact",
            json={
                "user_id": user_a_id,
                "movie_id": 1,
                "watched": True,
                "watch_duration": "full",
                "completed": True,
                "skipped_scenes": False,
                "skipped_music": False,
                "interest_level": 5,
            },
        )
        self.client.post(
            "/interact",
            json={
                "user_id": user_a_id,
                "movie_id": 2,
                "watched": True,
                "watch_duration": "10",
                "completed": False,
                "skipped_scenes": True,
                "skipped_music": True,
                "interest_level": 1,
            },
        )
        self.client.post(
            "/interact",
            json={
                "user_id": user_a_id,
                "movie_id": 3,
                "watched": True,
                "watch_duration": "full",
                "completed": True,
                "skipped_scenes": False,
                "skipped_music": False,
                "interest_level": 5,
            },
        )
        self.client.post(
            "/interact",
            json={
                "user_id": user_b_id,
                "movie_id": 2,
                "watched": True,
                "watch_duration": "full",
                "completed": True,
                "skipped_scenes": False,
                "skipped_music": False,
                "interest_level": 5,
            },
        )
        self.client.post(
            "/interact",
            json={
                "user_id": user_b_id,
                "movie_id": 1,
                "watched": True,
                "watch_duration": "10",
                "completed": False,
                "skipped_scenes": True,
                "skipped_music": True,
                "interest_level": 1,
            },
        )
        self.client.post(
            "/interact",
            json={
                "user_id": user_b_id,
                "movie_id": 5,
                "watched": True,
                "watch_duration": "full",
                "completed": True,
                "skipped_scenes": False,
                "skipped_music": False,
                "interest_level": 5,
            },
        )

        response_a = self.client.get(f"/recommend/svd?user_id={user_a_id}&top_n=20")
        response_b = self.client.get(f"/recommend/svd?user_id={user_b_id}&top_n=20")
        self.assertEqual(response_a.status_code, 200)
        self.assertEqual(response_b.status_code, 200)

        recommendations_a = response_a.get_json()["recommendations"]
        recommendations_b = response_b.get_json()["recommendations"]
        top_ids_a = [row["movie"]["movie_id"] for row in recommendations_a[:3]]
        top_ids_b = [row["movie"]["movie_id"] for row in recommendations_b[:3]]

        self.assertNotEqual(top_ids_a, top_ids_b)

    def test_svd_nn_endpoint_returns_combined_scores(self):
        user_response = self.client.post("/user", json={"username": "maya"})
        user_id = user_response.get_json()["user"]["user_id"]

        self.client.post(
            "/interact",
            json={
                "user_id": user_id,
                "movie_id": 1,
                "watched": True,
                "watch_duration": "full",
                "completed": True,
                "skipped_scenes": False,
                "skipped_music": False,
                "interest_level": 5,
            },
        )

        response = self.client.get(f"/recommend/svd-nn?user_id={user_id}&top_n=5")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertGreater(payload["count"], 0)
        self.assertIn("svd_score", payload["recommendations"][0])
        self.assertIn("nn_score", payload["recommendations"][0])
        self.assertIn("combined_score", payload["recommendations"][0])

    def test_tmdb_sync_uses_web_fallback_without_api_key(self):
        with self.app.app_context():
            with patch("backend.services.tmdb_service.search_tmdb_movie_page") as mock_search_page:
                with patch("backend.services.tmdb_service.get_tmdb_poster_from_web") as mock_web_poster:
                    mock_search_page.return_value = "/movie/123-test-movie"
                    mock_web_poster.return_value = "https://media.themoviedb.org/t/p/w500/web-poster.jpg"
                    result = sync_movie_posters_from_tmdb(db.session, force=True, limit=1)

        self.assertEqual(result["status"], "synced")
        self.assertEqual(result["updated"], 1)

    def test_tmdb_sync_updates_placeholder_posters(self):
        with self.app.app_context():
            with patch("backend.services.tmdb_service.search_tmdb_movie") as mock_search:
                mock_search.return_value = {"poster_path": "/poster.jpg"}
                with patch.dict(os.environ, {"TMDB_API_KEY": "test-key", "TMDB_POSTER_SIZE": "w500"}, clear=False):
                    result = sync_movie_posters_from_tmdb(db.session, force=True, limit=1)

            movie = db.session.get(Movie, 1)

        self.assertEqual(result["status"], "synced")
        self.assertEqual(result["updated"], 1)
        self.assertIsNotNone(movie)
        movie_record = cast(Movie, movie)
        self.assertEqual(movie_record.poster_url, "https://image.tmdb.org/t/p/w500/poster.jpg")

    def test_tmdb_sync_endpoint_returns_result(self):
        with patch("backend.routes.admin.sync_movie_posters_from_tmdb") as mock_sync:
            mock_sync.return_value = {
                "status": "synced",
                "checked": 1,
                "updated": 1,
                "movies": [{"movie_id": 1, "title": "Test Movie", "poster_url": "https://image.tmdb.org/t/p/w500/poster.jpg"}],
            }

            response = self.client.post("/admin/tmdb/sync-posters", json={"force": True, "limit": 1})

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["updated"], 1)

    def test_tmdb_enrich_uses_tmdb_id_hint(self):
        with self.app.app_context():
            movie = db.session.get(Movie, 1)
            self.assertIsNotNone(movie)
            movie_record = cast(Movie, movie)

            with patch("backend.services.tmdb_service.get_tmdb_movie_by_id") as mock_get_by_id:
                mock_get_by_id.return_value = {"poster_path": "/hint.jpg"}
                with patch.dict(os.environ, {"TMDB_API_KEY": "test-key", "TMDB_POSTER_SIZE": "w500"}, clear=False):
                    from backend.services.tmdb_service import enrich_movie_poster_from_tmdb

                    poster_url = enrich_movie_poster_from_tmdb(movie_record, force=True, tmdb_id_hint=299534)

            self.assertEqual(poster_url, "https://image.tmdb.org/t/p/w500/hint.jpg")

    def test_movielens_title_mapping_uses_normalized_titles(self):
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            movielens_dir = temp_dir / "ml-latest-small"
            movielens_dir.mkdir(parents=True, exist_ok=True)
            (movielens_dir / "movies.csv").write_text(
                "movieId,title,genres\n"
                "101,Test Movie,Drama\n"
                "102,Another Test,Action\n",
                encoding="utf-8",
            )
            (movielens_dir / "ratings.csv").write_text(
                "userId,movieId,rating,timestamp\n"
                "1,101,4.5,1\n"
                "2,102,5.0,2\n",
                encoding="utf-8",
            )

            with self.app.app_context():
                app_movie_index = build_app_movie_index(db.session, temp_dir)
                rows = load_movielens_ratings_for_app_movies(temp_dir, app_movie_index)

        self.assertEqual(app_movie_index[1], 101)
        self.assertEqual(app_movie_index[2], 102)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["movie_id"], 1)
        self.assertEqual(rows[1]["movie_id"], 2)

    def test_full_hybrid_endpoint_returns_fuzzy_adjusted_scores(self):
        user_response = self.client.post("/user", json={"username": "maya"})
        user_id = user_response.get_json()["user"]["user_id"]

        self.client.post(
            "/interact",
            json={
                "user_id": user_id,
                "movie_id": 1,
                "watched": True,
                "watch_duration": "full",
                "completed": True,
                "skipped_scenes": False,
                "skipped_music": False,
                "interest_level": 5,
            },
        )

        response = self.client.get(f"/recommend/full?user_id={user_id}&top_n=5")
        self.assertEqual(response.status_code, 200)

        payload = response.get_json()
        self.assertGreater(payload["count"], 0)
        row = payload["recommendations"][0]
        self.assertIn("svd_score", row)
        self.assertIn("nn_score", row)
        self.assertIn("combined_score", row)
        self.assertIn("fuzzy_boost", row)
        self.assertIn("final_score", row)
        self.assertGreaterEqual(row["fuzzy_boost"], 0.0)
        self.assertLessEqual(row["fuzzy_boost"], 0.4)

    def test_svd_nn_training_exposes_model_explanation(self):
        user_response = self.client.post("/user", json={"username": "maya"})
        user_id = user_response.get_json()["user"]["user_id"]

        self.client.post(
            "/interact",
            json={
                "user_id": user_id,
                "movie_id": 1,
                "watched": True,
                "watch_duration": "full",
                "completed": True,
                "skipped_scenes": False,
                "skipped_music": False,
                "interest_level": 5,
            },
        )

        response = self.client.get(f"/recommend/svd-nn?user_id={user_id}&top_n=5")
        self.assertEqual(response.status_code, 200)

        payload = response.get_json()
        self.assertIn("training", payload)
        self.assertIn("features", payload["training"])
        self.assertIn("dataset_sources", payload["training"])
        self.assertIn("explanation", payload["training"])
        self.assertIn("why_nn", payload["training"]["explanation"])

    def test_nn_metrics_endpoint_returns_visual_assets(self):
        response = self.client.get("/metrics/nn")
        self.assertEqual(response.status_code, 200)

        payload = response.get_json()
        self.assertIn("metrics", payload)
        self.assertIn("plots", payload)
        self.assertIn("loss_curve", payload["plots"])
        self.assertIn("mae_curve", payload["plots"])
        self.assertIn("confusion_matrix", payload["plots"])
        self.assertIn("prediction_vs_actual", payload["plots"])
        self.assertGreater(len(payload["plots"]["loss_curve"]), 100)
        self.assertGreater(len(payload["prediction_samples"]), 0)

    def test_profile_endpoint_returns_classification(self):
        user_response = self.client.post("/user", json={"username": "maya"})
        user_id = user_response.get_json()["user"]["user_id"]

        self.client.post(
            "/interact",
            json={
                "user_id": user_id,
                "movie_id": 1,
                "watched": True,
                "watch_duration": "10",
                "completed": False,
                "skipped_scenes": False,
                "skipped_music": False,
                "interest_level": 3,
            },
        )

        response = self.client.get(f"/profile/user?user_id={user_id}")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()["profile"]
        self.assertEqual(payload["profile"], "Casual")
        self.assertIn("filter_genres", payload)

    def test_recommendations_are_filtered_by_profile(self):
        user_response = self.client.post("/user", json={"username": "maya"})
        user_id = user_response.get_json()["user"]["user_id"]

        for movie_id, watch_duration in [(1, "30"), (2, "30"), (3, "60")]:
            self.client.post(
                "/interact",
                json={
                    "user_id": user_id,
                    "movie_id": movie_id,
                    "watched": True,
                    "watch_duration": watch_duration,
                    "completed": False,
                    "skipped_scenes": False,
                    "skipped_music": False,
                    "interest_level": 4,
                },
            )

        response = self.client.get(f"/profile/user?user_id={user_id}")
        profile = response.get_json()["profile"]
        self.assertEqual(profile["profile"], "Genre-based")

        recommendations = self.client.get(f"/recommend/full?user_id={user_id}&top_n=20").get_json()["recommendations"]
        self.assertGreater(len(recommendations), 0)
        allowed_genres = [genre.lower() for genre in profile["filter_genres"]]
        for row in recommendations:
            movie_genres = [genre.strip().lower() for genre in row["movie"]["genres"].split("|")]
            self.assertTrue(any(genre in movie_genres for genre in allowed_genres))


if __name__ == "__main__":
    unittest.main()
