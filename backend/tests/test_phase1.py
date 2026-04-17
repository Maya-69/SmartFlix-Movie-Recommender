import os
import tempfile
import unittest

from backend.app import create_app
from backend.db import db
from backend.models import Interaction, Movie, RecommendationFeedback, User


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
                (1, "Test Movie", "Drama", "/static/posters/movie_1.jpg"),
                (2, "Another Test", "Action", "/static/posters/movie_2.jpg"),
                (3, "Sci-Fi Test", "Sci-Fi", "/static/posters/movie_3.jpg"),
                (4, "Drama Test", "Drama", "/static/posters/movie_4.jpg"),
                (5, "Comedy Test", "Comedy", "/static/posters/movie_5.jpg"),
                (6, "Adventure Test", "Adventure", "/static/posters/movie_6.jpg"),
                (7, "Animated Test", "Animation|Family", "/static/posters/movie_7.jpg"),
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

    def test_movies_endpoint_returns_offline_posters(self):
        response = self.client.get("/movies")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertGreater(payload["count"], 0)
        for movie in payload["movies"]:
            self.assertIn("/static/posters/", movie["poster_url"])
            self.assertNotIn("themoviedb", movie["poster_url"].lower())

    def test_interaction_is_saved(self):
        user_response = self.client.post("/user", json={"username": "maya"})
        user_id = user_response.get_json()["user"]["user_id"]

        response = self.client.post(
            "/interact",
            json={
                "user_id": user_id,
                "movie_id": 1,
                "rating": 5,
                "watch_duration_minutes": 95,
                "percent_completed": 100,
                "watched_one_sitting": True,
                "skip_count": 0,
                "would_watch_again": True,
                "time_of_day": "night",
            },
        )

        self.assertEqual(response.status_code, 201)
        payload = response.get_json()
        self.assertEqual(payload["interaction"]["rating"], 5)

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
                "rating": 4,
                "watch_duration_minutes": 60,
                "percent_completed": 66,
                "watched_one_sitting": False,
                "skip_count": 2,
                "would_watch_again": False,
                "time_of_day": "afternoon",
            },
        )

        response = self.client.get(f"/interact?user_id={user_id}")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["interactions"][0]["movie_title"], "Test Movie")
        self.assertEqual(payload["interactions"][0]["username"], "maya")

    def test_missing_duration_and_completion_percent_is_rejected(self):
        user_response = self.client.post("/user", json={"username": "maya"})
        user_id = user_response.get_json()["user"]["user_id"]

        response = self.client.post(
            "/interact",
            json={
                "user_id": user_id,
                "movie_id": 1,
                "rating": 2,
                "watched_one_sitting": True,
                "skip_count": 0,
                "would_watch_again": False,
                "time_of_day": "morning",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("watch_duration_minutes", response.get_json()["error"])

    def test_profile_endpoint_returns_classification(self):
        user_response = self.client.post("/user", json={"username": "maya"})
        user_id = user_response.get_json()["user"]["user_id"]

        self.client.post(
            "/interact",
            json={
                "user_id": user_id,
                "movie_id": 7,
                "rating": 5,
                "watch_duration_minutes": 120,
                "percent_completed": 100,
                "watched_one_sitting": True,
                "skip_count": 0,
                "would_watch_again": True,
                "time_of_day": "night",
            },
        )

        self.client.post(
            "/interact",
            json={
                "user_id": user_id,
                "movie_id": 6,
                "rating": 4,
                "watch_duration_minutes": 90,
                "percent_completed": 85,
                "watched_one_sitting": True,
                "skip_count": 0,
                "would_watch_again": True,
                "time_of_day": "night",
            },
        )

        response = self.client.get(f"/profile/user?user_id={user_id}")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()["profile"]
        self.assertIn("profile_tags", payload)
        self.assertIn("Animation Enjoyer", payload["profile_tags"])
        self.assertIn("One-Sitting Watcher", payload["profile_tags"])
        self.assertIn("filter_genres", payload)

    def test_tmdb_sync_endpoint_not_exposed(self):
        response = self.client.post("/admin/tmdb/sync-posters", json={"force": True, "limit": 1})
        self.assertEqual(response.status_code, 404)

    def test_admin_cleanup_users_all_mode(self):
        user_response = self.client.post("/user", json={"username": "maya"})
        user_id = user_response.get_json()["user"]["user_id"]

        self.client.post(
            "/interact",
            json={
                "user_id": user_id,
                "movie_id": 1,
                "rating": 3,
                "watch_duration_minutes": 30,
                "percent_completed": 30,
                "watched_one_sitting": False,
                "skip_count": 0,
                "would_watch_again": False,
                "time_of_day": "night",
            },
        )

        response = self.client.post("/admin/users/cleanup", json={"mode": "all"})
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["mode"], "all")
        self.assertGreaterEqual(payload["deleted_users"], 1)
        self.assertGreaterEqual(payload["deleted_interactions"], 1)

    def test_svd_recommendations_endpoint_returns_payload(self):
        maya_response = self.client.post("/user", json={"username": "maya"})
        maya_user_id = maya_response.get_json()["user"]["user_id"]
        alex_response = self.client.post("/user", json={"username": "alex"})
        alex_user_id = alex_response.get_json()["user"]["user_id"]

        self.client.post(
            "/interact",
            json={
                "user_id": maya_user_id,
                "movie_id": 1,
                "rating": 5,
                "watch_duration_minutes": 90,
                "percent_completed": 100,
                "watched_one_sitting": True,
                "skip_count": 0,
                "would_watch_again": True,
                "time_of_day": "night",
            },
        )
        self.client.post(
            "/interact",
            json={
                "user_id": maya_user_id,
                "movie_id": 2,
                "rating": 4,
                "watch_duration_minutes": 60,
                "percent_completed": 80,
                "watched_one_sitting": True,
                "skip_count": 1,
                "would_watch_again": True,
                "time_of_day": "afternoon",
            },
        )
        self.client.post(
            "/interact",
            json={
                "user_id": alex_user_id,
                "movie_id": 1,
                "rating": 4,
                "watch_duration_minutes": 70,
                "percent_completed": 85,
                "watched_one_sitting": False,
                "skip_count": 0,
                "would_watch_again": True,
                "time_of_day": "night",
            },
        )
        self.client.post(
            "/interact",
            json={
                "user_id": alex_user_id,
                "movie_id": 3,
                "rating": 5,
                "watch_duration_minutes": 80,
                "percent_completed": 90,
                "watched_one_sitting": True,
                "skip_count": 0,
                "would_watch_again": True,
                "time_of_day": "morning",
            },
        )

        response = self.client.get(f"/recommendations/svd?user_id={maya_user_id}&top_n=3")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["mode"], "svd")
        self.assertIn("recommendations", payload)
        self.assertLessEqual(len(payload["recommendations"]), 3)

    def test_svd_recommendations_requires_user_id(self):
        response = self.client.get("/recommendations/svd")
        self.assertEqual(response.status_code, 400)

    def test_svd_cold_start_matches_movies_ordering(self):
        user_response = self.client.post("/user", json={"username": "new-user"})
        user_id = user_response.get_json()["user"]["user_id"]

        movies_response = self.client.get("/movies")
        self.assertEqual(movies_response.status_code, 200)
        movies_payload = movies_response.get_json()
        expected_first_ids = [movie["movie_id"] for movie in movies_payload["movies"][:3]]

        rec_response = self.client.get(f"/recommendations/svd?user_id={user_id}&top_n=3")
        self.assertEqual(rec_response.status_code, 200)
        rec_payload = rec_response.get_json()

        self.assertEqual(rec_payload["mode"], "cold-start-popular")
        actual_first_ids = [movie["movie_id"] for movie in rec_payload["recommendations"]]
        self.assertEqual(actual_first_ids, expected_first_ids)

    def test_svd_recommendations_work_with_single_active_user(self):
        user_response = self.client.post("/user", json={"username": "solo"})
        user_id = user_response.get_json()["user"]["user_id"]

        self.client.post(
            "/interact",
            json={
                "user_id": user_id,
                "movie_id": 1,
                "rating": 5,
                "watch_duration_minutes": 120,
                "percent_completed": 100,
                "watched_one_sitting": True,
                "skip_count": 0,
                "would_watch_again": True,
                "time_of_day": "night",
            },
        )
        self.client.post(
            "/interact",
            json={
                "user_id": user_id,
                "movie_id": 2,
                "rating": 4,
                "watch_duration_minutes": 90,
                "percent_completed": 90,
                "watched_one_sitting": True,
                "skip_count": 0,
                "would_watch_again": True,
                "time_of_day": "afternoon",
            },
        )

        response = self.client.get(f"/recommendations/svd?user_id={user_id}&top_n=5")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["mode"], "svd")
        self.assertGreater(len(payload["recommendations"]), 0)
        recommended_ids = [movie["movie_id"] for movie in payload["recommendations"]]
        self.assertNotIn(1, recommended_ids)
        self.assertNotIn(2, recommended_ids)

    def test_content_recommendations_endpoint_returns_payload(self):
        user_response = self.client.post("/user", json={"username": "content-user"})
        user_id = user_response.get_json()["user"]["user_id"]

        self.client.post(
            "/interact",
            json={
                "user_id": user_id,
                "movie_id": 7,
                "rating": 5,
                "watch_duration_minutes": 120,
                "percent_completed": 100,
                "watched_one_sitting": True,
                "skip_count": 0,
                "would_watch_again": True,
                "time_of_day": "night",
            },
        )
        self.client.post(
            "/interact",
            json={
                "user_id": user_id,
                "movie_id": 6,
                "rating": 4,
                "watch_duration_minutes": 90,
                "percent_completed": 85,
                "watched_one_sitting": True,
                "skip_count": 0,
                "would_watch_again": True,
                "time_of_day": "night",
            },
        )

        response = self.client.get(f"/recommendations/content?user_id={user_id}&top_n=5")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["algorithm"], "content-based")
        self.assertEqual(payload["mode"], "tfidf")
        self.assertGreater(len(payload["recommendations"]), 0)
        self.assertGreater(len(payload["seeds"]), 0)
        recommended_ids = [movie["movie_id"] for movie in payload["recommendations"]]
        self.assertNotIn(7, recommended_ids)
        self.assertNotIn(6, recommended_ids)

    def test_final_recommendations_endpoint_returns_blended_payload(self):
        user_response = self.client.post("/user", json={"username": "hybrid-user"})
        user_id = user_response.get_json()["user"]["user_id"]

        self.client.post(
            "/interact",
            json={
                "user_id": user_id,
                "movie_id": 7,
                "rating": 5,
                "watch_duration_minutes": 120,
                "percent_completed": 100,
                "watched_one_sitting": True,
                "skip_count": 0,
                "would_watch_again": True,
                "time_of_day": "night",
            },
        )
        self.client.post(
            "/interact",
            json={
                "user_id": user_id,
                "movie_id": 6,
                "rating": 4,
                "watch_duration_minutes": 90,
                "percent_completed": 85,
                "watched_one_sitting": True,
                "skip_count": 0,
                "would_watch_again": True,
                "time_of_day": "night",
            },
        )

        response = self.client.get(f"/recommendations/final?user_id={user_id}&top_n=5")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["algorithm"], "hybrid-blend")
        self.assertEqual(payload["mode"], "hybrid-final")
        self.assertIn("blend", payload)
        self.assertIn("mode", payload["blend"])
        self.assertGreater(payload["blend"]["svd_weight"], 0)
        self.assertGreater(payload["blend"]["content_weight"], 0)
        self.assertIn("final_recommendations", payload)
        self.assertIn("svd_recommendations", payload)
        self.assertIn("content_recommendations", payload)
        self.assertGreater(len(payload["final_recommendations"]), 0)
        self.assertIn("final_score", payload["final_recommendations"][0])
        self.assertIn("rank_score", payload["final_recommendations"][0])
        self.assertIn("diversity_adjustment", payload["final_recommendations"][0])
        self.assertIn("confidence_score", payload["final_recommendations"][0])
        self.assertIn("agreement", payload["final_recommendations"][0])
        self.assertIn("reasons", payload["final_recommendations"][0])
        self.assertIn("diagnostics", payload)
        self.assertIn("diversity", payload["diagnostics"])

    def test_recommendation_feedback_endpoint_persists_feedback(self):
        user_response = self.client.post("/user", json={"username": "feedback-user"})
        user_id = user_response.get_json()["user"]["user_id"]

        response = self.client.post(
            "/recommendations/feedback",
            json={
                "user_id": user_id,
                "movie_id": 1,
                "helpful": True,
                "source": "final",
                "svd_score": 0.91,
                "content_score": 0.12,
                "final_score": 0.87,
                "agreement": "both",
                "rank_score": 0.93,
            },
        )

        self.assertEqual(response.status_code, 201)
        payload = response.get_json()
        self.assertTrue(payload["feedback"]["helpful"])
        self.assertEqual(payload["feedback"]["source"], "final")

        with self.app.app_context():
            self.assertEqual(RecommendationFeedback.query.count(), 1)

    def test_recommendation_feedback_reset_clears_history(self):
        user_response = self.client.post("/user", json={"username": "reset-user"})
        user_id = user_response.get_json()["user"]["user_id"]

        self.client.post(
            "/recommendations/feedback",
            json={
                "user_id": user_id,
                "movie_id": 1,
                "helpful": True,
                "source": "final",
                "svd_score": 0.8,
                "content_score": 0.2,
                "final_score": 0.7,
                "agreement": "both",
                "rank_score": 0.75,
            },
        )

        response = self.client.post("/recommendations/feedback/reset", json={"user_id": user_id})
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["deleted_feedback"], 1)

        with self.app.app_context():
            self.assertEqual(RecommendationFeedback.query.count(), 0)

    def test_feedback_adjusts_hybrid_blend_weights(self):
        user_response = self.client.post("/user", json={"username": "tuning-user"})
        user_id = user_response.get_json()["user"]["user_id"]

        self.client.post(
            "/interact",
            json={
                "user_id": user_id,
                "movie_id": 7,
                "rating": 5,
                "watch_duration_minutes": 120,
                "percent_completed": 100,
                "watched_one_sitting": True,
                "skip_count": 0,
                "would_watch_again": True,
                "time_of_day": "night",
            },
        )
        self.client.post(
            "/interact",
            json={
                "user_id": user_id,
                "movie_id": 6,
                "rating": 4,
                "watch_duration_minutes": 90,
                "percent_completed": 85,
                "watched_one_sitting": True,
                "skip_count": 0,
                "would_watch_again": True,
                "time_of_day": "night",
            },
        )

        before_response = self.client.get(f"/recommendations/final?user_id={user_id}&top_n=5")
        self.assertEqual(before_response.status_code, 200)
        before_payload = before_response.get_json()
        first_recommendation = before_payload["final_recommendations"][0]
        svd_weight_before = before_payload["blend"]["svd_weight"]
        content_weight_before = before_payload["blend"]["content_weight"]

        dominant_engine = "svd" if first_recommendation["svd_score"] >= first_recommendation["content_score"] else "content"

        self.client.post(
            "/recommendations/feedback",
            json={
                "user_id": user_id,
                "movie_id": first_recommendation["movie_id"],
                "helpful": True,
                "source": "final",
                "svd_score": first_recommendation["svd_score"],
                "content_score": first_recommendation["content_score"],
                "final_score": first_recommendation["final_score"],
                "agreement": first_recommendation["agreement"],
                "rank_score": first_recommendation["rank_score"],
            },
        )

        after_response = self.client.get(f"/recommendations/final?user_id={user_id}&top_n=5")
        self.assertEqual(after_response.status_code, 200)
        after_payload = after_response.get_json()

        self.assertGreater(after_payload["diagnostics"]["feedback_count"], 0)
        if dominant_engine == "svd":
            self.assertGreater(after_payload["blend"]["svd_weight"], svd_weight_before)
        else:
            self.assertGreater(after_payload["blend"]["content_weight"], content_weight_before)


if __name__ == "__main__":
    unittest.main()
