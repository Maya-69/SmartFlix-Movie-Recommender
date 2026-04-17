# SmartFlix

SmartFlix is a full-stack movie recommendation app with offline posters, local SQLite storage, and a feedback-driven hybrid recommender.

## How To Run

### Prerequisites

- Python 3.8+ with pip
- Node.js 16+ with npm

### 1. Backend Setup & Initialization

From the repo root:

```bash
pip install -r requirements.txt
```

**Initialize database with seed data** (run once per new machine):

```bash
python -m backend.scripts.init_db
```

This creates the SQLite database, loads 50 movies, and creates a demo user with sample ratings so recommendations work immediately.

Then start the backend:

```bash
python -m backend.app
```

The backend runs on `http://localhost:5000` by default.

**Note the IP/hostname and port where your backend is running** – you'll need this for the frontend.

### 2. Frontend Setup

In a second terminal:

```bash
cd frontend
npm install
```

**Configure the backend URL** by creating or editing `.env.local`:

```bash
# For local development on same machine:
echo "VITE_API_BASE_URL=http://localhost:5000" > .env.local

# For different machine on LAN (replace 192.168.1.100 with your backend IP):
echo "VITE_API_BASE_URL=http://192.168.1.100:5000" > .env.local

# For Docker compose or custom setup:
echo "VITE_API_BASE_URL=http://backend:5000" > .env.local
```

Then start the frontend:

```bash
npm run dev
```

The frontend runs on `http://localhost:5173` by default.

**Login with username** `demo_user` to test recommendations immediately.

### 3. Troubleshooting

**Posters show as "unavailable"?**

This happens when the frontend can't reach the backend API. Make sure:
1. The backend is running: `python -m backend.app` (should say "Running on...")
2. The frontend's `.env.local` file is configured with the correct backend URL
3. Your firewall allows connections on port 5000 (backend)
4. If running on LAN, verify the IP with: `hostname -I` (Linux) or check Network Settings (macOS/Windows)

**Example fix for LAN setup:**
```bash
# On the machine running the backend:
hostname -I          # Get backend IP, e.g., 192.168.1.100

# On the machine with the frontend, edit frontend/.env.local:
VITE_API_BASE_URL=http://192.168.1.100:5000
npm run dev
```

**Recommendations endpoint returns 404?**

This means the database hasn't been initialized with seed data. Run:
```bash
python -m backend.scripts.init_db
```

This ensures:
- ✅ Database tables exist
- ✅ Movies are loaded (50 default)
- ✅ Demo user exists
- ✅ Sample ratings exist (recommendations need training data)

After running `init_db`, login with username `demo_user` to see recommendations immediately.

**Python version issues on Windows?**

If `py -m backend.app` doesn't work, use:
```bash
python -m backend.app
```

Make sure `python` is in your PATH. Check with:
```bash
python --version
```

### 4. Optional checks

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
