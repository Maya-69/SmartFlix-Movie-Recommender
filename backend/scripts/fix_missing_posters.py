#!/usr/bin/env python3
"""
Fix missing poster URLs by enriching placeholders with real TMDB posters.

Usage:
    TMDB_API_KEY=your_key python3 fix_missing_posters.py

This script:
1. Finds all movies with placeholder poster URLs
2. Attempts to fetch real TMDB posters using the TMDB API
3. Updates the database with real poster URLs
"""

import os
import sys
from dotenv import load_dotenv

# Load environment  
load_dotenv("../.env")

def main():
    from backend.app import create_app
    from backend.models import db, Movie
    from backend.services.tmdb_service import enrich_movie_with_tmdb
    
    tmdb_key = os.getenv("TMDB_API_KEY")
    if not tmdb_key:
        print("ERROR: TMDB_API_KEY not set in .env")
        print("Get a free API key at: https://www.themoviedb.org/settings/api")
        return 1
    
    app = create_app()
    
    with app.app_context():
        # Find all placeholder movies
        placeholder_movies = Movie.query.filter(
            Movie.poster_url.like('%placehold%')
        ).all()
        
        if not placeholder_movies:
            print("✓ No placeholder posters found - all movies have real posters!")
            return 0
        
        print(f"Found {len(placeholder_movies)} movies with placeholder posters")
        print("Attempting to enrich with real TMDB posters...\n")
        
        updated_count = 0
        failed_movies = []
        
        for i, movie in enumerate(placeholder_movies, 1):
            print(f"[{i}/{len(placeholder_movies)}] {movie.title}...", end=" ", flush=True)
            
            try:
                result = enrich_movie_with_tmdb(
                    movie.movie_id,
                    movie.title,
                    force_refresh=True
                )
                
                if result and result.get('poster_url'):
                    # Don't update the DB object yet - we'll do it in batch commit
                    new_url = result['poster_url']
                    movie.poster_url = new_url
                    print(f"✓")
                    updated_count += 1
                else:
                    print(f"✗ (No poster found)")
                    failed_movies.append(movie.title)
            except Exception as e:
                print(f"✗ ({str(e)[:40]})")
                failed_movies.append(movie.title)
        
        # Commit all updates
        if updated_count > 0:
            try:
                db.session.commit()
                print(f"\n✓ Successfully updated {updated_count} movies")
            except Exception as e:
                db.session.rollback()
                print(f"\n✗ Database commit failed: {e}")
                return 1
        
        if failed_movies:
            print(f"\n⚠ Failed to enrich {len(failed_movies)} movies:")
            for title in failed_movies[:5]:
                print(f"  - {title}")
            if len(failed_movies) > 5:
                print(f"  ... and {len(failed_movies) - 5} more")
        
        return 0

if __name__ == "__main__":
    sys.exit(main())
