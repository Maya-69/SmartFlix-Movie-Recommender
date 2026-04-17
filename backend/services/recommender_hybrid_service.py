from __future__ import annotations

from backend.models import Interaction, Movie, RecommendationFeedback
from backend.services.recommender_content_service import recommend_movies_content_based
from backend.services.recommender_svd_service import recommend_movies_svd


def _normalize_scores(items: list[dict], score_key: str) -> dict[int, float]:
    scored_items: list[tuple[int, float]] = []
    for item in items:
        score = item.get(score_key)
        if score is None:
            continue
        try:
            scored_items.append((int(item["movie_id"]), float(score)))
        except (TypeError, ValueError, KeyError):
            continue

    if scored_items:
        values = [score for _, score in scored_items]
        min_score = min(values)
        max_score = max(values)
        if max_score > min_score:
            return {
                movie_id: (score - min_score) / (max_score - min_score)
                for movie_id, score in scored_items
            }

    if not items:
        return {}

    denominator = max(len(items) - 1, 1)
    return {
        int(item["movie_id"]): round(1.0 - (index / denominator), 6)
        for index, item in enumerate(items)
        if item.get("movie_id") is not None
    }


def _agreement_label(hit_count: int) -> str:
    return "both" if hit_count > 1 else "single-engine"


def _confidence_score(svd_value: float, content_value: float, hit_count: int) -> float:
    # Confidence grows when scores are strong and both engines support the movie.
    support_bonus = 0.25 if hit_count > 1 else 0.0
    base = (0.45 * svd_value) + (0.30 * content_value)
    return round(min(1.0, base + support_bonus), 4)


def _explanation_reasons(item: dict, svd_value: float, content_value: float, hit_count: int) -> list[str]:
    reasons: list[str] = []
    if hit_count > 1:
        reasons.append("Both SVD and TF-IDF recommended this movie.")
    else:
        reasons.append("Selected by one engine and promoted by hybrid weighting.")

    if svd_value >= 0.7:
        reasons.append("Strong collaborative signal from similar-user behavior.")
    if content_value >= 0.7:
        reasons.append("Strong content similarity signal from watched movie metadata.")

    matched_from = item.get("matched_from")
    if matched_from:
        reasons.append(f"Content model matched this with: {matched_from}.")

    if not reasons:
        reasons.append("Balanced recommendation from hybrid scoring.")

    return reasons


def _genre_tokens(item: dict) -> set[str]:
    genres = str(item.get("genres") or "")
    return {genre.strip().lower() for genre in genres.split("|") if genre.strip()}


def _diversity_rerank(items: list[dict], top_n: int) -> tuple[list[dict], dict]:
    if not items or top_n <= 0:
        return [], {"genre_coverage": 0.0, "unique_genres": []}

    pool = [dict(item) for item in items]
    selected: list[dict] = []
    seen_genres: set[str] = set()

    while pool and len(selected) < top_n:
        best_index = 0
        best_rank_score = float("-inf")

        for index, item in enumerate(pool):
            movie_genres = _genre_tokens(item)
            overlap_count = len(movie_genres.intersection(seen_genres))
            new_count = len(movie_genres.difference(seen_genres))

            diversity_penalty = min(0.24, overlap_count * 0.06)
            diversity_bonus = min(0.12, new_count * 0.03)
            diversity_adjustment = round(diversity_bonus - diversity_penalty, 4)

            rank_score = round(float(item.get("final_score", 0.0)) + diversity_adjustment, 4)
            if rank_score > best_rank_score:
                best_rank_score = rank_score
                best_index = index

        chosen = pool.pop(best_index)
        chosen_genres = _genre_tokens(chosen)
        overlap_count = len(chosen_genres.intersection(seen_genres))
        new_count = len(chosen_genres.difference(seen_genres))
        diversity_penalty = min(0.24, overlap_count * 0.06)
        diversity_bonus = min(0.12, new_count * 0.03)
        diversity_adjustment = round(diversity_bonus - diversity_penalty, 4)

        chosen["diversity_adjustment"] = diversity_adjustment
        chosen["rank_score"] = round(float(chosen.get("final_score", 0.0)) + diversity_adjustment, 4)
        if diversity_adjustment > 0:
            chosen.setdefault("reasons", []).append("Diversity reranking boosted this movie to improve genre variety.")
        elif diversity_adjustment < 0:
            chosen.setdefault("reasons", []).append("Diversity reranking slightly penalized this movie due to genre overlap.")

        selected.append(chosen)
        seen_genres.update(chosen_genres)

    catalog_genres = set()
    for item in items:
        catalog_genres.update(_genre_tokens(item))

    coverage = round(len(seen_genres) / max(len(catalog_genres), 1), 4)
    return selected, {
        "genre_coverage": coverage,
        "unique_genres": sorted(seen_genres),
    }


def _adaptive_blend_weights(profile_tags: list[str], interaction_count: int) -> tuple[float, float, str]:
    svd_weight = 0.55
    content_weight = 0.45
    mode = "balanced"

    lowered_tags = {str(tag).strip().lower() for tag in profile_tags}

    # Early history: rely more on content/profile signals.
    if interaction_count < 3:
        svd_weight -= 0.15
        content_weight += 0.15
        mode = "content-leaning-cold-start"

    if "story focused" in lowered_tags or "animation enjoyer" in lowered_tags:
        svd_weight -= 0.08
        content_weight += 0.08
        mode = "content-leaning-profile"

    if "action lover" in lowered_tags or "sci-fi enjoyer" in lowered_tags:
        svd_weight += 0.08
        content_weight -= 0.08
        mode = "collaborative-leaning-profile"

    # Clamp weights to avoid extreme outcomes.
    svd_weight = max(0.25, min(0.75, svd_weight))
    content_weight = max(0.25, min(0.75, content_weight))

    total = svd_weight + content_weight
    if total <= 0:
        return 0.55, 0.45, "balanced"

    return round(svd_weight / total, 4), round(content_weight / total, 4), mode


def _feedback_blend_adjustment(user_id: int) -> tuple[float, float, int, str]:
    feedback_rows = (
        RecommendationFeedback.query.filter_by(user_id=user_id, source="final")
        .order_by(RecommendationFeedback.created_at.desc())
        .limit(20)
        .all()
    )

    if not feedback_rows:
        return 0.0, 0.0, 0, "none"

    svd_points = 0.0
    content_points = 0.0

    for row in feedback_rows:
        svd_score = float(row.svd_score or 0.0)
        content_score = float(row.content_score or 0.0)
        svd_dominant = svd_score >= content_score
        if row.helpful:
            if svd_dominant:
                svd_points += 1.0
            else:
                content_points += 1.0
        else:
            if svd_dominant:
                content_points += 1.0
            else:
                svd_points += 1.0

    total = svd_points + content_points
    if total <= 0:
        return 0.0, 0.0, len(feedback_rows), "neutral"

    svd_bias = (svd_points / total) - 0.5
    content_bias = (content_points / total) - 0.5
    mode = "feedback-learned" if len(feedback_rows) >= 3 else "feedback-warmup"
    return round(svd_bias, 4), round(content_bias, 4), len(feedback_rows), mode


def _combine_movie_payloads(
    svd_results: list[dict],
    content_results: list[dict],
    top_n: int,
    svd_weight: float,
    content_weight: float,
) -> list[dict]:
    svd_normalized = _normalize_scores(svd_results, "svd_score")
    content_normalized = _normalize_scores(content_results, "content_score")
    svd_raw_by_id = {int(item["movie_id"]): item.get("svd_score") for item in svd_results if item.get("movie_id") is not None}
    content_raw_by_id = {int(item["movie_id"]): item.get("content_score") for item in content_results if item.get("movie_id") is not None}
    content_match_source_by_id = {
        int(item["movie_id"]): item.get("matched_from")
        for item in content_results
        if item.get("movie_id") is not None
    }

    by_movie_id: dict[int, dict] = {}
    meta_by_movie_id: dict[int, dict] = {}

    for source, items in (("svd", svd_results), ("content", content_results)):
        for index, item in enumerate(items):
            movie_id = int(item["movie_id"])
            combined = by_movie_id.setdefault(movie_id, {"svd": 0.0, "content": 0.0, "hits": 0})
            combined["hits"] += 1
            combined["svd"] = max(combined["svd"], svd_normalized.get(movie_id, 0.0))
            combined["content"] = max(combined["content"], content_normalized.get(movie_id, 0.0))
            combined[f"{source}_rank"] = index + 1
            meta_by_movie_id.setdefault(movie_id, item)

    combined_items: list[dict] = []
    for movie_id, scores in by_movie_id.items():
        item = meta_by_movie_id[movie_id]
        svd_value = scores.get("svd", 0.0)
        content_value = scores.get("content", 0.0)
        hit_count = scores.get("hits", 0)
        overlap_bonus = 0.08 if hit_count > 1 else 0.0
        final_score = round((svd_weight * svd_value) + (content_weight * content_value) + overlap_bonus, 4)
        confidence_score = _confidence_score(svd_value, content_value, hit_count)
        agreement = _agreement_label(hit_count)
        reasons = _explanation_reasons(item, svd_value, content_value, hit_count)

        combined_items.append(
            {
                **item,
                "svd_score": svd_raw_by_id.get(movie_id),
                "content_score": content_raw_by_id.get(movie_id),
                "matched_from": content_match_source_by_id.get(movie_id),
                "svd_normalized": round(svd_value, 4),
                "content_normalized": round(content_value, 4),
                "final_score": final_score,
                "confidence_score": confidence_score,
                "agreement": agreement,
                "reasons": reasons,
                "source": "hybrid" if hit_count > 1 else item.get("source", "hybrid"),
            }
        )

    combined_items.sort(key=lambda item: (item.get("final_score", 0.0), item.get("title", "")), reverse=True)
    return combined_items[:top_n]


def recommend_movies_hybrid(session, user_id: int, top_n: int = 10, n_components: int = 12) -> dict:
    del session

    # Use a stable retrieval pool so ranking stays consistent across pages
    # even when they request different top_n sizes (e.g., 6 on Home, 8 on Recommendations).
    candidate_pool = min(50, max(30, top_n * 3))

    svd_result = recommend_movies_svd(None, user_id=user_id, top_n=candidate_pool, n_components=n_components)
    content_result = recommend_movies_content_based(None, user_id=user_id, top_n=candidate_pool)
    interaction_count = int(Interaction.query.filter_by(user_id=user_id).count())
    profile_tags = content_result.get("profile_tags", [])
    svd_weight, content_weight, blend_mode = _adaptive_blend_weights(profile_tags, interaction_count)
    svd_feedback_bias, content_feedback_bias, feedback_count, feedback_mode = _feedback_blend_adjustment(user_id)
    svd_weight = max(0.25, min(0.75, svd_weight + svd_feedback_bias * 0.2))
    content_weight = max(0.25, min(0.75, content_weight + content_feedback_bias * 0.2))
    total = svd_weight + content_weight
    svd_weight = round(svd_weight / total, 4)
    content_weight = round(content_weight / total, 4)
    if feedback_count > 0:
        blend_mode = feedback_mode

    svd_recommendations = svd_result.get("recommendations", [])
    content_recommendations = content_result.get("recommendations", [])
    combined_candidates = _combine_movie_payloads(
        svd_recommendations,
        content_recommendations,
        candidate_pool,
        svd_weight=svd_weight,
        content_weight=content_weight,
    )
    final_recommendations, diversity_stats = _diversity_rerank(combined_candidates, top_n)

    excluded_movie_ids = {int(item["movie_id"]) for item in svd_recommendations}
    excluded_movie_ids.update(int(item["movie_id"]) for item in content_recommendations)

    popular_movies = []
    for movie in Movie.query.order_by(Movie.title.asc()).all():
        if int(movie.movie_id) in excluded_movie_ids:
            continue
        popular_movies.append(movie.to_dict())
        if len(popular_movies) >= top_n:
            break

    return {
        "algorithm": "hybrid-blend",
        "mode": "hybrid-final",
        "user_id": user_id,
        "top_n": top_n,
        "blend": {
            "svd_weight": svd_weight,
            "content_weight": content_weight,
            "mode": blend_mode,
            "overlap_bonus": 0.08,
            "diversity_rerank": True,
        },
        "final_recommendations": final_recommendations,
        "svd_recommendations": svd_recommendations,
        "content_recommendations": content_recommendations,
        "popular_recommendations": popular_movies,
        "svd_mode": svd_result.get("mode"),
        "content_mode": content_result.get("mode"),
        "profile_tags": content_result.get("profile_tags", []),
        "profile": content_result.get("profile"),
        "diagnostics": {
            "agreement_labels": ["both", "single-engine"],
            "confidence_range": [0.0, 1.0],
            "diversity": diversity_stats,
            "interaction_count": interaction_count,
            "feedback_count": feedback_count,
            "feedback_bias": {
                "svd": svd_feedback_bias,
                "content": content_feedback_bias,
            },
        },
    }