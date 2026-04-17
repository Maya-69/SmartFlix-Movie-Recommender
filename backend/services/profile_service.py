from __future__ import annotations

from collections import Counter

from backend.db import db
from backend.models import Interaction, Movie

DURATION_MAP = {"10": 10.0, "30": 30.0, "60": 60.0, "full": 90.0}
ACTION_GENRES = {"action", "adventure", "crime", "thriller"}
STORY_GENRES = {"drama", "romance", "mystery", "fantasy", "history"}
CASUAL_GENRES = {"comedy", "animation", "family", "music"}
SCI_FI_GENRES = {"sci-fi", "science fiction"}
ANIMATION_GENRES = {"animation", "anime"}


def _completion_ratio(interaction: Interaction) -> float:
    if interaction.percent_completed is not None:
        try:
            return max(0.0, min(1.0, float(interaction.percent_completed) / 100.0))
        except (TypeError, ValueError):
            return 0.0

    try:
        minutes = float(interaction.watch_duration_minutes or 0)
    except (TypeError, ValueError):
        minutes = 0.0
    if minutes <= 0:
        return 0.0
    return max(0.0, min(1.0, minutes / 120.0))


def _rating_value(interaction: Interaction) -> float:
    try:
        return float(interaction.rating or interaction.interest_level or 0)
    except (TypeError, ValueError):
        return 0.0


def _normalize_genres(genres: str) -> list[str]:
    return [genre.strip().lower() for genre in str(genres or "").split("|") if genre.strip()]


def _collect_preferred_genres(interactions: list[Interaction]) -> list[str]:
    counter: Counter[str] = Counter()
    for interaction in interactions:
        if _rating_value(interaction) < 4 and _completion_ratio(interaction) < 0.6:
            continue

        movie = db.session.get(Movie, interaction.movie_id)
        if not movie:
            continue

        weight = 1.0 + (_rating_value(interaction) / 5.0) + _completion_ratio(interaction)
        if interaction.watched_one_sitting:
            weight += 0.25
        if interaction.would_watch_again:
            weight += 0.25
        if int(interaction.skip_count or 0) == 0:
            weight += 0.15

        for genre in _normalize_genres(movie.genres):
            counter[genre] += weight

    return [genre.title() for genre, _ in counter.most_common(3)]


def _collect_profile_tags(interactions: list[Interaction], preferred_genres: list[str]) -> tuple[list[str], dict[str, str]]:
    genre_counter: Counter[str] = Counter()
    time_of_day_counter: Counter[str] = Counter()
    total_duration = 0.0
    total_completion = 0.0
    total_rating = 0.0
    one_sitting_count = 0
    skip_count = 0

    for interaction in interactions:
        movie = db.session.get(Movie, interaction.movie_id)
        if movie:
            for genre in _normalize_genres(movie.genres):
                genre_counter[genre] += 1.0 + (_rating_value(interaction) / 5.0) + _completion_ratio(interaction)

        total_duration += DURATION_MAP.get(getattr(interaction, "watch_duration", "30"), 30.0)
        total_completion += _completion_ratio(interaction)
        total_rating += _rating_value(interaction) or 3.0
        time_of_day_counter[str(interaction.time_of_day or "night").strip().lower()] += 1
        one_sitting_count += 1 if interaction.watched_one_sitting else 0
        skip_count += int(interaction.skip_count or 0)

    interaction_count = max(len(interactions), 1)
    average_duration = total_duration / interaction_count
    average_completion = total_completion / interaction_count
    average_rating = total_rating / interaction_count
    one_sitting_rate = one_sitting_count / interaction_count
    average_skips = skip_count / interaction_count
    top_time_of_day = time_of_day_counter.most_common(1)[0][0].title() if time_of_day_counter else "Night"

    tags: list[str] = []
    reasons: dict[str, str] = {}

    def add_tag(label: str, reason: str):
        if label not in tags:
            tags.append(label)
            reasons[label] = reason

    if any(genre in preferred_genres for genre in ["Animation", "Family", "Music"]):
        add_tag("Animation Enjoyer", "Your strongest preferences cluster around animated and family-friendly movies.")

    if any(genre in preferred_genres for genre in ["Sci-Fi"]):
        add_tag("Sci-Fi Enjoyer", "You repeatedly engage with sci-fi titles.")

    if any(genre in preferred_genres for genre in ["Action", "Adventure", "Crime", "Thriller"]):
        add_tag("Action Lover", "Your history leans toward high-energy action-oriented movies.")

    if any(genre in preferred_genres for genre in ["Drama", "Romance", "Mystery", "Fantasy", "History"]):
        add_tag("Story Focused", "You spend longer with story-driven movies and rarely skip around.")

    if one_sitting_rate >= 0.6 or average_completion >= 0.8:
        add_tag("One-Sitting Watcher", "You usually finish movies in a single session.")

    if average_skips >= 1.0 or sum(1 for interaction in interactions if int(interaction.skip_count or 0) > 0) / interaction_count >= 0.35:
        add_tag("Frequent Skipper", "You tend to move around during playback or skip sections.")

    if top_time_of_day == "Night":
        add_tag("Night Owl", "Most of your viewing activity happens at night.")
    elif top_time_of_day == "Morning":
        add_tag("Early Viewer", "You tend to watch earlier in the day.")

    if average_rating >= 4.5:
        add_tag("High Enthusiasm", "Your ratings stay consistently high across the catalog.")

    if not tags:
        add_tag("Casual Viewer", "Your interactions are still too mixed to lock onto a strong pattern.")

    dominant_genre = None
    if genre_counter:
        dominant_genre = genre_counter.most_common(1)[0][0].title()
        add_tag(f"{dominant_genre} Fan", f"{dominant_genre} appears most often in your preferred genres.")

    return tags, reasons


def classify_user_profile(user_id: int) -> dict:
    interactions = Interaction.query.filter_by(user_id=user_id).all()
    if not interactions:
        return {
            "user_id": user_id,
            "profile": "Casual",
            "profile_tags": ["Casual Viewer"],
            "profile_tag_reasons": {"Casual Viewer": "No interaction history yet"},
            "interaction_count": 0,
            "average_duration_minutes": 0.0,
            "average_interest_level": 0.0,
            "skip_rate": 0.0,
            "preferred_genres": [],
            "filter_genres": ["Comedy", "Animation", "Family", "Music"],
            "reason": "No interaction history yet",
        }

    duration_minutes = [DURATION_MAP.get(interaction.watch_duration, 30.0) for interaction in interactions]
    skip_rate = sum(1 for interaction in interactions if interaction.skipped_scenes or interaction.skipped_music) / len(interactions)
    average_interest = sum(float(interaction.interest_level) for interaction in interactions) / len(interactions)
    preferred_genres = _collect_preferred_genres(interactions)
    profile_tags, profile_tag_reasons = _collect_profile_tags(interactions, preferred_genres)

    profile = profile_tags[0]
    filter_genres = preferred_genres or ["Drama", "Action", "Comedy"]
    reason = profile_tag_reasons.get(profile, "Dominant behavior pattern in interaction history")

    if sum(duration_minutes) / len(duration_minutes) <= 30:
        filter_genres = ["Comedy", "Animation", "Family", "Music"]
        if "Casual Viewer" not in profile_tags:
            profile_tags.append("Casual Viewer")
            profile_tag_reasons["Casual Viewer"] = "Average watch duration is low"
    elif skip_rate >= 0.5 and average_interest >= 4.0:
        filter_genres = ["Action", "Adventure", "Crime", "Thriller"]
        if "Action Lover" not in profile_tags:
            profile_tags.append("Action Lover")
            profile_tag_reasons["Action Lover"] = "High skipping with high interest points to energetic content"
    elif sum(duration_minutes) / len(duration_minutes) >= 60 and skip_rate <= 0.3:
        filter_genres = ["Drama", "Romance", "Mystery", "Fantasy", "History"]
        if "Story Focused" not in profile_tags:
            profile_tags.append("Story Focused")
            profile_tag_reasons["Story Focused"] = "Long watch duration with low skipping suggests story-driven preference"
    elif preferred_genres:
        filter_genres = preferred_genres
        if "Genre-based" not in profile_tags:
            profile_tags.append("Genre-based")
            profile_tag_reasons["Genre-based"] = f"Repeated interest in {', '.join(preferred_genres)}"

    return {
        "user_id": user_id,
        "profile": profile,
        "profile_tags": profile_tags,
        "profile_tag_reasons": profile_tag_reasons,
        "interaction_count": len(interactions),
        "average_duration_minutes": round(sum(duration_minutes) / len(duration_minutes), 2),
        "average_interest_level": round(average_interest, 2),
        "skip_rate": round(skip_rate, 2),
        "preferred_genres": preferred_genres,
        "filter_genres": filter_genres,
        "reason": reason,
    }


def filter_movies_by_profile(movies, profile_data: dict):
    filter_genres = [genre.lower() for genre in profile_data.get("filter_genres", []) if genre]
    if not filter_genres:
        return movies

    filtered = []
    for movie in movies:
        movie_genres = _normalize_genres(movie.genres)
        if any(genre in movie_genres for genre in filter_genres):
            filtered.append(movie)

    return filtered or movies
