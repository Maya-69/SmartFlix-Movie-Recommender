#!/usr/bin/env python3
"""
Initialize SmartFlix database with seed data and sample user interactions.
Run this script once after deploying to a new machine to enable recommendations.

Usage:
    python -m backend.scripts.init_db
"""

import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.app import create_app, db
from backend.models import User, Interaction, Movie
import random


def seed_initial_interactions(session, num_ratings=15):
    """Create sample user interactions to train the recommendation models."""
    
    # Get or create a default user
    user = session.query(User).filter_by(username="demo_user").first()
    if not user:
        user = User(username="demo_user")
        session.add(user)
        session.flush()  # Flush to get user_id
    
    # Get available movies
    available_movies = session.query(Movie).limit(20).all()
    if not available_movies:
        print("⚠️  No movies found in database. Running movie loader first...")
        from backend.services.movie_loader import ensure_movie_catalog
        ensure_movie_catalog(session, Path(__file__).resolve().parent.parent / "data" / "movies.csv", target_count=50)
        available_movies = session.query(Movie).limit(20).all()
    
    if not available_movies:
        print("❌ Failed to load movies. Check data/movies.csv exists.")
        return False
    
    # Add random ratings if user hasn't rated anything yet
    existing_ratings = session.query(Interaction).filter_by(user_id=user.user_id).count()
    
    if existing_ratings == 0:
        print(f"\n📝 Seeding {num_ratings} demo ratings for user '{user.username}'...")
        for movie in random.sample(available_movies, min(num_ratings, len(available_movies))):
            interaction = Interaction(
                user_id=user.user_id,
                movie_id=movie.movie_id,
                watched=True,
                watch_duration="60",
                completed=random.choice([True, False]),
                interest_level=random.randint(1, 10),
                rating=random.randint(1, 5),
                percent_completed=random.uniform(0.3, 1.0),
                would_watch_again=random.choice([True, False]),
                time_of_day=random.choice(["morning", "afternoon", "evening", "night"]),
            )
            session.add(interaction)
        
        session.commit()
        print(f"✅ Added {num_ratings} ratings for demo_user")
    else:
        print(f"✓ User '{user.username}' already has {existing_ratings} ratings")
    
    return True


def main():
    """Initialize database with seed data."""
    print("🚀 SmartFlix Database Initializer")
    print("=" * 50)
    
    # Create app and initialize database
    app = create_app()
    
    with app.app_context():
        print("\n📦 Creating database tables...")
        db.create_all()
        print("✅ Database tables ready")
        
        # Ensure movies are loaded
        movie_count = db.session.query(Movie).count()
        if movie_count < 50:
            print(f"\n📽️  Loading movies (current: {movie_count})...")
            from backend.services.movie_loader import ensure_movie_catalog
            ensure_movie_catalog(
                db.session,
                Path(__file__).resolve().parent.parent / "data" / "movies.csv",
                target_count=50
            )
        else:
            print(f"✓ Movies already loaded ({movie_count} total)")
        
        # Seed initial interactions
        if seed_initial_interactions(db.session):
            print("\n🎬 Database initialization complete!")
            print("\n📌 Next steps:")
            print("   1. Start backend: python -m backend.app")
            print("   2. Start frontend: cd frontend && npm run dev")
            print("   3. Open browser to http://localhost:5173")
            print("   4. Login as 'demo_user' to see recommendations")
            return 0
        else:
            print("❌ Database initialization failed")
            return 1


if __name__ == "__main__":
    sys.exit(main())
