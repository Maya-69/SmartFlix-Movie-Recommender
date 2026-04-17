import { Link } from 'react-router-dom'
import { useEffect, useMemo, useState } from 'react'

import { api } from '../api'
import MovieCard from '../components/MovieCard'

function Home({ currentUser, movies, loadingMovies, onSelectMovie }) {
  const [recentInteractions, setRecentInteractions] = useState([])
  const [loadingRecent, setLoadingRecent] = useState(false)
  const [recentError, setRecentError] = useState('')
  const [finalRecommendations, setFinalRecommendations] = useState([])
  const [popularRecommendations, setPopularRecommendations] = useState([])
  const [loadingFinal, setLoadingFinal] = useState(false)
  const [finalError, setFinalError] = useState('')
  const [blend, setBlend] = useState(null)
  const [feedbackStatus, setFeedbackStatus] = useState({})
  const [feedbackError, setFeedbackError] = useState('')
  const [featuredIndex, setFeaturedIndex] = useState(0)

  useEffect(() => {
    if (!currentUser) {
      return
    }

    const loadRecentInteractions = async () => {
      setLoadingRecent(true)
      setRecentError('')

      try {
        const payload = await api.getInteractions({ user_id: currentUser.user_id })
        setRecentInteractions((payload.interactions || []).slice(0, 8))
      } catch (requestError) {
        setRecentError(requestError.message)
      } finally {
        setLoadingRecent(false)
      }
    }

    loadRecentInteractions()
  }, [currentUser])

  useEffect(() => {
    if (!currentUser) {
      return
    }

    const loadFinalRecommendations = async () => {
      setLoadingFinal(true)
      setFinalError('')
      try {
        const payload = await api.getFinalRecommendations({ user_id: currentUser.user_id, top_n: 10, latent_dims: 12 })
        setFinalRecommendations(payload.final_recommendations || [])
        setPopularRecommendations(payload.popular_recommendations || movies.slice(0, 6))
        setBlend(payload.blend || null)
      } catch (requestError) {
        setFinalError(requestError.message)
      } finally {
        setLoadingFinal(false)
      }
    }

    loadFinalRecommendations()
  }, [currentUser, recentInteractions.length, movies])

  const featuredMovies = useMemo(() => {
    const source = popularRecommendations.length > 0 ? popularRecommendations : movies
    return source.slice(0, 10)
  }, [popularRecommendations, movies])

  useEffect(() => {
    if (featuredMovies.length <= 1) {
      return undefined
    }

    const timer = window.setInterval(() => {
      setFeaturedIndex((current) => (current + 1) % featuredMovies.length)
    }, 6000)

    return () => window.clearInterval(timer)
  }, [featuredMovies.length])

  useEffect(() => {
    if (featuredIndex >= featuredMovies.length) {
      setFeaturedIndex(0)
    }
  }, [featuredIndex, featuredMovies.length])

  const activeFeaturedMovie = featuredMovies[featuredIndex] || featuredMovies[0] || null

  const goToFeatured = (nextIndex) => {
    if (featuredMovies.length === 0) {
      return
    }

    const normalized = ((nextIndex % featuredMovies.length) + featuredMovies.length) % featuredMovies.length
    setFeaturedIndex(normalized)
  }

  const handleFeedback = async (movie, helpful) => {
    if (!currentUser) {
      return
    }

    setFeedbackError('')
    setFeedbackStatus((previous) => ({ ...previous, [movie.movie_id]: 'saving' }))

    try {
      await api.submitRecommendationFeedback({
        user_id: currentUser.user_id,
        movie_id: movie.movie_id,
        helpful,
        source: 'final',
        svd_score: movie.svd_score,
        content_score: movie.content_score,
        final_score: movie.final_score,
        agreement: movie.agreement || 'single-engine',
        rank_score: movie.rank_score,
      })

      setFeedbackStatus((previous) => ({ ...previous, [movie.movie_id]: helpful ? 'helpful' : 'not-helpful' }))

      const payload = await api.getFinalRecommendations({ user_id: currentUser.user_id, top_n: 10, latent_dims: 12 })
      setFinalRecommendations(payload.final_recommendations || [])
      setPopularRecommendations(payload.popular_recommendations || movies.slice(0, 6))
      setBlend(payload.blend || null)
    } catch (requestError) {
      setFeedbackStatus((previous) => ({ ...previous, [movie.movie_id]: 'error' }))
      setFeedbackError(requestError.message)
    }
  }

  return (
    <div className="page-stack">
      <section className="hero-carousel glass-card animated-panel cinematic-hero">
        <div className="hero-carousel__backdrop" style={activeFeaturedMovie?.poster_url ? { backgroundImage: `linear-gradient(90deg, rgba(5,7,13,0.96) 0%, rgba(5,7,13,0.82) 34%, rgba(5,7,13,0.22) 100%), url(${activeFeaturedMovie.poster_url})` } : undefined} />
        <div className="hero-carousel__content">
          <div className="hero-copy">
            <p className="eyebrow mb-2">Home</p>
            <h1 className="display-5 fw-bold mb-3">{activeFeaturedMovie ? activeFeaturedMovie.title : `Welcome back, ${currentUser.username}.`}</h1>
            <p className="text-secondary mb-4">
              {activeFeaturedMovie
                ? 'Popular picks slide above, then your blended recommendations sit below in the same cinematic style.'
                : 'Browse movies, click any poster, and record your interaction. SmartFlix stores your movie feedback and profile locally.'}
            </p>
            <div className="d-flex flex-wrap gap-2 mb-3">
              <Link to="/recommendations" className="btn btn-cinematic-primary btn-sm">Open recommendation page</Link>
            </div>
            <div className="hero-stats">
              <div className="stat-pill">
                <span className="stat-value">{movies.length}</span>
                <span className="stat-label">Movies loaded</span>
              </div>
            </div>
          </div>

          {activeFeaturedMovie ? (
            <div className="hero-carousel__poster-shell">
              <div className="hero-carousel__poster-frame">
                <img className="hero-carousel__poster" src={activeFeaturedMovie.poster_url} alt={`${activeFeaturedMovie.title} poster`} />
              </div>
              <div className="hero-carousel__meta">
                <div className="hero-carousel__eyebrow">Popular pick</div>
                <div className="hero-carousel__title">{activeFeaturedMovie.title}</div>
                <div className="hero-carousel__genres">{activeFeaturedMovie.genres}</div>
              </div>
            </div>
          ) : null}
        </div>

        {featuredMovies.length > 1 ? (
          <div className="hero-carousel__controls">
            <button className="carousel-nav" type="button" onClick={() => goToFeatured(featuredIndex - 1)} aria-label="Previous featured movie">‹</button>
            <div className="carousel-dots">
              {featuredMovies.map((movie, index) => (
                <button
                  key={movie.movie_id}
                  type="button"
                  className={`carousel-dot ${index === featuredIndex ? 'active' : ''}`}
                  onClick={() => goToFeatured(index)}
                  aria-label={`Show ${movie.title}`}
                />
              ))}
            </div>
            <button className="carousel-nav" type="button" onClick={() => goToFeatured(featuredIndex + 1)} aria-label="Next featured movie">›</button>
          </div>
        ) : null}
      </section>

      <section className="glass-card p-3 p-lg-4 animated-panel shelf-panel">
        <div className="section-header">
          <div>
            <p className="eyebrow mb-1">Featured</p>
            <h2 className="h3 mb-0">Popular picks</h2>
          </div>
        </div>

        {loadingMovies ? (
          <div className="text-center py-5 text-secondary">Loading movies...</div>
        ) : (
          <div className="poster-rail">
            {featuredMovies.map((movie) => (
              <MovieCard key={movie.movie_id} movie={movie} onClick={onSelectMovie} showButton={false} className="movie-card--compact" />
            ))}
          </div>
        )}
      </section>

      <section className="glass-card p-3 p-lg-4 animated-panel recommendation-panel">
        <div className="section-header mb-3">
          <div>
            <p className="eyebrow mb-1">Final recommendation</p>
            <h2 className="h3 mb-0">Blended picks</h2>
            <p className="text-secondary mb-0 small">
              {blend ? `Mixing ${Math.round(blend.svd_weight * 100)}% SVD with ${Math.round(blend.content_weight * 100)}% TF-IDF.` : 'Blending collaborative and content signals into one ranked list.'}
            </p>
          </div>
        </div>

        {finalError ? <div className="alert alert-danger border-0">{finalError}</div> : null}
        {feedbackError ? <div className="alert alert-warning border-0">{feedbackError}</div> : null}

        {loadingFinal ? (
          <div className="text-center py-4 text-secondary">Computing final recommendation...</div>
        ) : finalRecommendations.length === 0 ? (
          <div className="alert alert-dark border-0 mb-0">No blended recommendations yet. Submit more interactions and refresh this page.</div>
        ) : (
          <div className="poster-rail poster-rail--two">
            {finalRecommendations.map((movie) => (
              <MovieCard
                key={`final-${movie.movie_id}`}
                movie={movie}
                onClick={onSelectMovie}
                caption={`Final score ${Number(movie.final_score || 0).toFixed(2)}`}
                badges={[
                  { label: `SVD ${movie.svd_score === null || movie.svd_score === undefined ? 'n/a' : Number(movie.svd_score).toFixed(2)}`, className: 'text-bg-info' },
                  { label: `TF-IDF ${movie.content_score === null || movie.content_score === undefined ? 'n/a' : Number(movie.content_score).toFixed(2)}`, className: 'text-bg-secondary' },
                  feedbackStatus[movie.movie_id] ? { label: feedbackStatus[movie.movie_id] === 'helpful' ? 'Helpful' : feedbackStatus[movie.movie_id] === 'not-helpful' ? 'Not helpful' : 'Saving...', className: feedbackStatus[movie.movie_id] === 'helpful' ? 'text-bg-success' : feedbackStatus[movie.movie_id] === 'not-helpful' ? 'text-bg-warning' : 'text-bg-secondary' } : null,
                ]}
                actions={[
                  {
                    key: `helpful-${movie.movie_id}`,
                    node: (
                      <button
                        className="btn btn-sm btn-feedback-positive"
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation()
                          handleFeedback(movie, true)
                        }}
                      >
                        Helpful
                      </button>
                    ),
                  },
                  {
                    key: `not-helpful-${movie.movie_id}`,
                    node: (
                      <button
                        className="btn btn-sm btn-feedback-negative"
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation()
                          handleFeedback(movie, false)
                        }}
                      >
                        Not helpful
                      </button>
                    ),
                  },
                ]}
                showButton={false}
                className="movie-card--compact movie-card--feedback"
              />
            ))}
          </div>
        )}
      </section>

      <section className="glass-card p-3 p-lg-4 animated-panel">
        <div className="section-header">
          <div>
            <p className="eyebrow mb-1">Popular picks</p>
            <h2 className="h3 mb-0">Catalog highlights</h2>
            <p className="text-secondary mb-0 small">A simple browseable set of movies near the top of the catalog.</p>
          </div>
        </div>

        {loadingMovies ? (
          <div className="text-center py-5 text-secondary">Loading movies...</div>
        ) : popularRecommendations.length === 0 ? (
          <div className="alert alert-dark border-0 mb-0">No catalog highlights yet.</div>
        ) : (
          <div className="poster-rail">
            {popularRecommendations.map((movie) => (
              <MovieCard key={`popular-${movie.movie_id}`} movie={movie} onClick={onSelectMovie} caption="Popular catalog pick" badges={[{ label: 'Popular', className: 'text-bg-success' }]} showButton={false} className="movie-card--compact" />
            ))}
          </div>
        )}
      </section>

      <section className="glass-card p-3 p-lg-4">
        <div className="section-header mb-3">
          <div>
            <p className="eyebrow mb-1">Your Activity</p>
            <h2 className="h3 mb-0">Recent interactions</h2>
          </div>
        </div>

        {recentError ? <div className="alert alert-danger border-0">{recentError}</div> : null}

        {loadingRecent ? (
          <div className="text-center py-4 text-secondary">Loading recent activity...</div>
        ) : recentInteractions.length === 0 ? (
          <div className="alert alert-dark border-0 mb-0">No interactions yet. Open a movie and record your first response.</div>
        ) : (
          <div className="recommendation-strip">
            {recentInteractions.map((item) => (
              <article key={item.interaction_id} className="recommendation-card card border-0 glass-card" role="button" tabIndex={0} onClick={() => {
                const match = movies.find((movie) => movie.movie_id === item.movie_id)
                if (match) {
                  onSelectMovie(match)
                }
              }} onKeyDown={(event) => {
                if (event.key === 'Enter') {
                  const match = movies.find((movie) => movie.movie_id === item.movie_id)
                  if (match) {
                    onSelectMovie(match)
                  }
                }
              }}>
                <div className="card-body d-flex flex-column gap-2">
                  <div>
                    <h5 className="card-title mb-1">{item.movie_title}</h5>
                    <p className="movie-genres mb-0">Interest {item.interest_level}/5</p>
                  </div>
                  <div className="d-flex flex-wrap gap-2">
                    <span className="badge text-bg-info">Duration {item.watch_duration}</span>
                    <span className="badge text-bg-secondary">Completed {item.completed ? 'Yes' : 'No'}</span>
                    <span className="badge text-bg-secondary">Skipped scenes {item.skipped_scenes ? 'Yes' : 'No'}</span>
                  </div>
                  <button className="btn btn-outline-light btn-sm mt-auto align-self-start" type="button" onClick={(event) => {
                    event.stopPropagation()
                    const match = movies.find((movie) => movie.movie_id === item.movie_id)
                    if (match) {
                      onSelectMovie(match)
                    }
                  }}>
                    Update interaction
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}

export default Home
