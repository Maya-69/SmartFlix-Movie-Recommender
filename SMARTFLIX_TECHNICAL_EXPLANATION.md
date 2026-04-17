# SmartFlix Technical Explanation

This document explains the current SmartFlix recommendation system, the frontend screens that display it, the libraries used, and how each score is produced.

## 1. What SmartFlix Is Doing

SmartFlix is a hybrid movie recommender. It combines:

1. Collaborative filtering with SVD.
2. Content-based matching with TF-IDF.
3. A weighted hybrid merge of the two.
4. Diversity reranking so the results do not all look the same.
5. Explicit helpful / not helpful feedback to adjust future weights.

It is not a playback app. Users browse offline posters, choose a movie, and record structured interaction data that feeds the recommender.

## 2. Libraries And Frameworks

### Backend

- Flask: HTTP routes and API responses.
- Flask-SQLAlchemy: database models and queries.
- SQLite: local persistence for users, interactions, movies, and recommendation feedback.
- pandas: builds interaction tables and ranking frames.
- numpy: vector math and matrix handling.
- scikit-learn:
  - `TruncatedSVD` for collaborative filtering.
  - `TfidfVectorizer` for text features.
  - `linear_kernel` for cosine-style similarity.

### Frontend

- React: page rendering and state management.
- Vite: development server and production build.

### Styling

- Plain CSS in `frontend/src/styles.css`.

## 3. Where The Training Data Comes From

SmartFlix does not train a separate supervised classifier.

The data sources are:

1. Local movie catalog data in `backend/data/movies.csv`.
2. User interactions stored in SQLite in the `interactions` table.
3. Recommendation feedback stored in SQLite in the `recommendation_feedback` table.
4. MovieLens sample ratings in `backend/data/ml-latest-small/ratings.csv`, mapped to the app catalog for extra collaborative signal.

### Important point

The recommender learns from interaction behavior, but there is no manually labeled target like "this movie is the correct answer". That means the system is mainly unsupervised / retrieval-based, with feedback-weighted rules on top.

## 4. Supervised Or Unsupervised?

The project is best described as a hybrid recommender, not a classical supervised ML model.

- SVD collaborative filtering is an unsupervised matrix factorization method.
- TF-IDF is an unsupervised text feature extraction method.
- The final blend is a rule-based combination with learned weights and feedback adjustment.

So the answer is:

- Not a supervised classification project.
- Mostly unsupervised recommendation plus heuristic and feedback-driven tuning.

## 5. The Runtime Flow In Order

At runtime the flow is:

1. The frontend loads the movie catalog through `/movies`.
2. The user logs in or is resolved through `/user`.
3. The user opens a movie and submits an interaction with rating, duration, completion, skip behavior, and watch preference.
4. The backend stores that interaction in SQLite.
5. `classify_user_profile()` groups the user into profile tags such as `Animation Enjoyer`, `Action Lover`, or `Story Focused`.
6. `recommend_movies_svd()` builds the collaborative filter recommendations.
7. `recommend_movies_content_based()` builds the TF-IDF recommendations.
8. `recommend_movies_hybrid()` combines both lists, applies weighting, overlap bonuses, confidence, and diversity reranking.
9. The frontend shows the final results on Home and the comparison tables on Recommendations.
10. Helpful / not helpful votes are saved and then used to shift the blend next time.

## 6. Backend Functions And What They Do

### `backend/models.py`

#### `Movie._offline_poster_url()`

This function forces posters to come from local static files such as `/static/posters/movie_53.jpg`.

That is how SmartFlix stays offline for poster delivery.

#### `Interaction`

This model stores the user signal used by the recommender:

- `watched`
- `watch_duration`
- `completed`
- `skipped_scenes`
- `skipped_music`
- `interest_level`
- `rating`
- `watch_duration_minutes`
- `percent_completed`
- `watched_one_sitting`
- `skip_count`
- `would_watch_again`
- `time_of_day`

#### `RecommendationFeedback`

This model stores the explicit vote a user gives to a recommendation:

- `helpful`
- `source`
- `svd_score`
- `content_score`
- `final_score`
- `agreement`
- `rank_score`

### `backend/services/recommender_svd_service.py`

#### `behavior_weighted_score(interaction)`

This turns one interaction into a numeric score for matrix factorization.

Formula:

$$
\text{score} = r + c + 0.3\,\mathbb{1}(\text{one sitting}) + 0.5\,\mathbb{1}(\text{watch again}) - \min(1, 0.1 \times \text{skip count})
$$

Where:

- $r$ is the rating or interest level.
- $c$ is completion ratio.
- The score is clipped to the range $[1, 5]$.

#### `_build_svd_model(interactions, n_components)`

This function:

1. Collects interaction rows.
2. Adds mapped MovieLens ratings.
3. Builds a user-by-movie matrix.
4. Fills missing values with $0$.
5. Runs `TruncatedSVD` with `n_components = latent_dims`.
6. Reconstructs approximate preference scores.

#### `recommend_movies_svd(..., top_n, n_components, include_embeddings)`

This is the collaborative recommendation endpoint.

It uses the reconstructed matrix row for the user and then adds a small genre affinity bonus:

$$
\text{adjusted score} = \text{reconstructed score} + \text{genre bonus}
$$

Genre bonus:

$$
\text{genre bonus} = \min(1, 0.25 \times \text{overlap})
$$

If the user has too little data or is missing from the matrix, the function falls back to popular movies.

### `backend/services/recommender_content_service.py`

#### `_interaction_weight(interaction)`

This gives each positive seed interaction a strength value.

Formula:

$$
\text{weight} = 0.5 + \frac{r}{5} + c + 0.2\,\mathbb{1}(\text{one sitting}) + 0.3\,\mathbb{1}(\text{watch again}) - \min(0.5, 0.05 \times \text{skip count})
$$

#### `_collect_seed_movies(user_id)`

This selects up to 3 strong past interactions to use as content seeds.

The seed must usually be:

- rating at least 4, or
- completion at least 70%, or
- marked as would watch again.

#### `recommend_movies_content_based(..., top_n)`

This builds a TF-IDF vector for each movie using the text:

$$
\text{text} = \text{title} + \text{genres}
$$

It then compares each seed to every movie with `linear_kernel`.

Base content score per candidate:

$$
\text{candidate score} = (\text{similarity} \times \text{seed weight}) + \text{genre overlap bonus}
$$

Genre overlap bonus:

$$
\text{genre overlap bonus} = \min(0.6, 0.15 \times \text{overlap})
$$

### `backend/services/profile_service.py`

#### `classify_user_profile(user_id)`

This groups the user into a readable profile based on interaction history.

Examples:

- `Animation Enjoyer`
- `Sci-Fi Enjoyer`
- `Action Lover`
- `Story Focused`
- `One-Sitting Watcher`
- `Frequent Skipper`

It also chooses `filter_genres`, which help content recommendations lean toward the user’s observed taste.

### `backend/services/recommender_hybrid_service.py`

This is the most important service for the final ranking.

#### `_normalize_scores(items, score_key)`

This converts each engine’s raw scores into a comparable $0$ to $1$ scale.

If the score spread is real, it uses min-max normalization:

$$
\hat{x} = \frac{x - x_{min}}{x_{max} - x_{min}}
$$

If all values are flat or unusable, it falls back to rank-based normalization.

#### `_adaptive_blend_weights(profile_tags, interaction_count)`

This starts the blend at:

- SVD = 0.55
- TF-IDF = 0.45

Then it adjusts based on profile and history:

- Fewer than 3 interactions: content gets more weight.
- `Story Focused` or `Animation Enjoyer`: content gets a boost.
- `Action Lover` or `Sci-Fi Enjoyer`: SVD gets a boost.

Weights are clamped between 0.25 and 0.75 before normalization.

#### `_feedback_blend_adjustment(user_id)`

This reads the last 20 final recommendation feedback rows.

If a user marks a movie as helpful, the engine with the higher raw score gets credit.
If the user marks it not helpful, the opposite engine gets credit.

That produces a bias value:

$$
\text{bias} = \frac{\text{engine points}}{\text{total points}} - 0.5
$$

The bias then nudges the blend weights.

#### `_combine_movie_payloads(...)`

This merges the SVD and TF-IDF candidate lists.

For each movie:

1. Take the normalized SVD score.
2. Take the normalized TF-IDF score.
3. Add an overlap bonus if both engines picked the same movie.
4. Compute confidence.
5. Build explanation strings.

Final score formula:

$$
\text{final score} = w_{svd} \cdot s_{svd} + w_{tfidf} \cdot s_{tfidf} + \text{overlap bonus}
$$

Where:

- $w_{svd}$ is the SVD weight.
- $w_{tfidf}$ is the TF-IDF weight.
- $s_{svd}$ and $s_{tfidf}$ are normalized scores.

Overlap bonus:

$$
\text{overlap bonus} = 0.08 \quad \text{if both engines recommend the movie}
$$

#### `_confidence_score(svd_value, content_value, hit_count)`

Confidence is not the same as final score.

It measures how strongly the movie is supported by the two engines.

Formula:

$$
\text{confidence} = \min(1, 0.45\,s_{svd} + 0.30\,s_{tfidf} + \text{support bonus})
$$

Support bonus is $0.25$ when both engines agree.

#### `_diversity_rerank(items, top_n)`

This prevents the final list from being too repetitive.

It compares the genres already chosen to the genres of each remaining candidate.

Diversity adjustment:

$$
\text{adjustment} = \text{diversity bonus} - \text{diversity penalty}
$$

Where:

$$
\text{diversity penalty} = \min(0.24, 0.06 \times \text{genre overlap})
$$

$$
\text{diversity bonus} = \min(0.12, 0.03 \times \text{new genres})
$$

Then:

$$
\text{rank score} = \text{final score} + \text{diversity adjustment}
$$

## 7. What The Final Recommendation Fields Mean

The Recommendations page shows these values:

### `SVD`

Collaborative filtering score from the SVD model.

### `TF-IDF`

Content similarity score from title and genre text.

### `Final score`

The hybrid blended score before diversity reranking.

### `Diversity adj`

The score change applied to encourage genre variety.

### `Rank score`

The score actually used to sort the final list after diversity reranking.

### `Confidence`

How strongly the system believes the recommendation is supported.

### `Agreement`

Either:

- `both`: both engines picked the movie.
- `single-engine`: only one engine picked it.

### `Why selected`

Human-readable explanation built from the rules in `_explanation_reasons()` and diversity reranking.

## 8. How The 55/45 Split Works

The base split is:

- 55% SVD
- 45% TF-IDF

That is only the starting point.

It changes in three ways:

1. Profile tags can shift the blend.
2. Interaction count can make content matter more at cold start.
3. Helpful / not helpful feedback can push the system toward the engine that performed better for the user.

So the system is not locked to 55/45 forever.

### Example

If the user has very little history, the system leans more toward TF-IDF.

If the user is tagged as `Action Lover`, SVD gets more weight.

If the user keeps marking SVD-heavy recommendations as helpful, the feedback adjustment nudges future ranking toward SVD.

## 9. What The Frontend Does

### `frontend/src/pages/Home.jsx`

This is the main landing page after login.

It:

1. Loads recent interactions.
2. Loads the final hybrid recommendations.
3. Loads popular fallback movies.
4. Rotates a featured poster hero.
5. Lets the user mark final recommendations as helpful or not helpful.
6. Refetches the hybrid recommendations after feedback.

### `frontend/src/pages/Recommendations.jsx`

This is the explainability page.

It shows:

- final hybrid recommendations,
- SVD recommendations,
- TF-IDF recommendations,
- popular fallback results,
- the score formulas,
- and a reset feedback button.

### `frontend/src/pages/Explore.jsx`

This is the catalog browsing page.

It supports:

- searching by title,
- filtering by genre,
- opening a movie interaction form.

### `frontend/src/components/MovieCard.jsx`

This shared component renders posters, titles, genres, badges, actions, and the offline poster fallback.

### `frontend/src/api.js`

This file holds the frontend fetch helpers for:

- `/movies`
- `/user`
- `/interact`
- `/profile/user`
- `/recommendations/svd`
- `/recommendations/content`
- `/recommendations/final`
- `/recommendations/feedback`
- `/recommendations/feedback/reset`

## 10. Why Feedback Changes Future Results

When the user taps Helpful or Not helpful:

1. The feedback is saved in `recommendation_feedback`.
2. The app reloads the final recommendations.
3. `_feedback_blend_adjustment()` reads the last 20 feedback rows.
4. The blend weights are nudged toward the engine that seems to match the user better.

This means the system is not static.

The final ranking learns from the user’s own votes, even though it is still not a supervised model in the classical sense.

## 11. The Current Top-N Choices

The Home page now requests more recommendations than before so the shelves feel fuller.

- Home final recommendations use a larger `top_n` value than the earlier 6-item version.
- The Recommendations page also requests more rows for comparison.
- The poster rail widths were tightened slightly so more cards appear in the visible shelf area.

## 12. Short Summary

SmartFlix is an offline-poster hybrid recommender built from:

- local movie data,
- local user interactions,
- SVD collaborative filtering,
- TF-IDF content matching,
- hybrid score blending,
- diversity reranking,
- and feedback-based weight adjustment.

It is best described as an unsupervised hybrid recommender with rule-based feedback tuning, not a supervised classifier.
