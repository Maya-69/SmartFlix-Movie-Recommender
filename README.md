# SmartFlix

SmartFlix is a full-stack movie recommendation app with offline posters, local SQLite storage, and a feedback-driven hybrid recommender.

## How To Run

### 1. Backend

From the repo root:

```bash
pip install -r requirements.txt
python -m backend.app
```

The backend runs on `http://localhost:5000` by default.

### 2. Frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

The frontend runs on `http://localhost:5173` by default.

### 3. Optional checks

```bash
python -m unittest discover backend/tests
cd frontend
npm run build
```

### 4. Development flow

Run the backend and frontend together, then log in, rate a few movies, and use the Home page feedback buttons to refresh the blended recommendations automatically. The Recommendations page compares the SVD, TF-IDF, and final hybrid outputs, and it includes a reset button for clearing your local recommendation feedback.

## Project Structure

`backend/`
: Flask API, database models, routes, services, and scripts.

`backend/app.py`
: Flask app factory and startup wiring.

`backend/models.py`
: SQLAlchemy models for users, movies, interactions, and recommendation feedback.

`backend/routes/`
: API endpoints for movies, users, interactions, profile, admin actions, and recommendation feedback.

`backend/services/`
: Movie loading, MovieLens mapping utilities, profile classification, and hybrid recommendation logic.

`backend/data/`
: Seed CSVs and MovieLens sample data used for training and catalog building.

`backend/static/posters/`
: Local poster cache served by Flask.

`backend/scripts/`
: Utility scripts such as poster caching and maintenance helpers.

`frontend/`
: React app built with Vite.

`frontend/src/pages/`
: Route-level pages like Home, Explore, Interactions, Recommendations, How It Works, Login, and Profile.

`frontend/src/components/`
: Shared UI pieces such as movie cards and interaction modals.

`frontend/src/api.js`
: Frontend API client for talking to the Flask backend.

`instance/` and `backend/instance/`
: SQLite database files created at runtime.

`models/`
: Saved model artifacts and generated assets.

`notebooks/`
: Placeholder location for experiments and analysis.

## How The App Works

The frontend loads the movie catalog from the backend and shows posters, titles, and genres. Clicking a movie opens an interaction form instead of playback. That form stores structured feedback in SQLite.

The Home page shows blended recommendations and lets you mark each one as helpful or not helpful. When you submit feedback, SmartFlix re-fetches the hybrid ranking immediately so the list reflects the latest signal.

The backend supports:

1. User creation and lookup.
2. Interaction capture and retrieval.
3. User behavior profiling from interaction history.
4. Hybrid recommendation blending from SVD, TF-IDF, and learned feedback.
5. Offline local poster delivery from static files.

## Data Sources

- Seed catalog data lives in `backend/data/movies.csv`.
- MovieLens sample data in `backend/data/ml-latest-small/` is available for title mapping utilities.
- User interactions are stored in SQLite.
- Poster images are cached locally in `backend/static/posters/` and served by Flask.

## API Overview

- `GET /movies` returns the movie catalog.
- `POST /user` creates or resolves a user.
- `POST /interact` stores structured feedback.
- `GET /interact` returns a user’s stored interactions.
- `GET /profile/user` returns the user behavior profile.
- `GET /recommendations/svd` returns collaborative recommendations.
- `GET /recommendations/content` returns TF-IDF content recommendations.
- `GET /recommendations/final` returns the blended hybrid recommendations.
- `POST /recommendations/feedback` stores helpful / not helpful feedback.
- `POST /recommendations/feedback/reset` clears recommendation feedback for the current user.
- `POST /admin/users/cleanup` removes users (`mode=all` or `mode=inactive`).

## Poster Storage

Movie posters are downloaded and cached locally instead of being pulled from remote URLs at render time. The backend serves them from `/static/posters/...`, and the database stores those local URLs so the frontend can show posters directly.

## Validation

You can verify the app with:

```bash
python -m unittest discover backend/tests
cd frontend
npm run build
```

## Notes

- Video playback is intentionally not implemented. Clicking a movie opens an interaction form.
- The catalog currently contains locally cached posters only, with no runtime poster API calls.
- Poster display is offline-only at runtime using local static files.
