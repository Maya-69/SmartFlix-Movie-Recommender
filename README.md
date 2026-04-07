# SmartFlix

SmartFlix is a full-stack movie recommendation app. It uses a Flask backend, a React frontend, SQLite for persistence, and a hybrid recommender built from SVD, a neural network, and fuzzy logic.

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

## Project Structure

`backend/`
: Flask API, database models, routes, services, and scripts.

`backend/app.py`
: Flask app factory and startup wiring.

`backend/models.py`
: SQLAlchemy models for users, movies, and interactions.

`backend/routes/`
: API endpoints for movies, users, interactions, recommendations, profile, metrics, and admin actions.

`backend/services/`
: Recommendation logic, MovieLens mapping, TMDB poster handling, profile classification, and training metrics.

`backend/data/`
: Seed CSVs and MovieLens sample data used for training and catalog building.

`backend/static/posters/`
: Local poster cache served by Flask.

`backend/scripts/`
: Utility scripts such as poster caching and maintenance helpers.

`frontend/`
: React app built with Vite.

`frontend/src/pages/`
: Route-level pages like Home, Explore, Interactions, Recommend, How It Works, Profile, and Visuals.

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

The frontend loads the movie catalog from the backend and shows posters, titles, and genres. Clicking a movie opens an interaction form instead of playback. That form stores structured feedback in SQLite, which becomes training signal for the recommendation pipeline.

The backend then exposes three recommendation layers:

1. SVD learns broad collaborative patterns from the movie ratings data.
2. The neural network learns how user behavior and movie identity interact.
3. Fuzzy logic adds a small final adjustment based on the user’s behavior profile.

The result is a hybrid score that is more flexible than SVD alone and more stable than a raw NN prediction.

## Recommendation Pipeline

### SVD

SVD is the collaborative baseline. It looks for patterns in rating history and recommends items that similar users tended to like. In SmartFlix it is useful because it gives strong ranking signals even when the current user has only a small amount of interaction data.

Why it helps:

- It captures latent taste patterns.
- It works well on sparse user-item matrices.
- It gives a reliable starting score for hybrid ranking.

### Neural Network

The NN adds a nonlinear layer on top of the collaborative signal. It uses:

- user id
- movie id
- normalized watch duration
- skipped scenes
- skipped music
- interest level

Why it helps:

- It can learn interactions SVD cannot express directly.
- It incorporates explicit behavior, not just rating history.
- It adjusts the score when the user’s watch behavior suggests stronger or weaker interest.

In this app the NN is used as a behavior-aware scorer, not as a replacement for SVD. That matters because the catalog is small and sparse, so a pure NN can become unstable. The app therefore keeps the NN grounded by combining it with SVD and calibration logic.

### Fuzzy Logic

Fuzzy logic is the last adjustment layer. It interprets user behavior in human terms like low, medium, and high duration or interest, then turns that into a small positive boost.

Why it helps:

- It makes the recommendation stack easier to explain.
- It adds a small rule-based correction when the behavior profile is clear.
- It avoids overreacting, because the boost is intentionally small.

In SmartFlix, fuzzy logic is not meant to do the heavy lifting. It just nudges the final score when the user’s behavior is consistent.

## Data Sources

- Seed catalog data lives in `backend/data/movies.csv`.
- MovieLens sample data in `backend/data/ml-latest-small/` is used for training and movie-title mapping.
- User interactions stored in SQLite are merged into the training data.
- Poster images are cached locally in `backend/static/posters/` and served by Flask.

## API Overview

- `GET /movies` returns the movie catalog.
- `POST /user` creates or resolves a user.
- `POST /interact` stores structured feedback.
- `GET /interact` returns a user’s stored interactions.
- `GET /recommend/svd` returns SVD-only recommendations.
- `GET /recommend/svd-nn` returns SVD + NN recommendations.
- `GET /recommend/full` returns the full hybrid recommendation with fuzzy adjustment.
- `GET /metrics/nn` returns NN training metrics and plots.
- `GET /profile/user` returns the user behavior profile.

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
- The catalog currently contains 100 movies with locally cached posters.
