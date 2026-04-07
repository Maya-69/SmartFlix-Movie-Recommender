import { useEffect, useState } from 'react'

import { api } from '../api'
import MovieCard from '../components/MovieCard'

const RECOMMENDATION_MODES = [
  { key: 'svd', label: 'SVD' },
  { key: 'svd-nn', label: 'SVD + NN' },
  { key: 'full', label: 'Full Hybrid' },
]

function Home({ currentUser, movies, loadingMovies, onSelectMovie }) {
  const [recommendationMode, setRecommendationMode] = useState('svd')
  const [recommendations, setRecommendations] = useState([])
  const [loadingRecommendations, setLoadingRecommendations] = useState(false)
  const [recommendationError, setRecommendationError] = useState('')
  const featuredMovies = movies.slice(0, 6)

  useEffect(() => {
    if (!currentUser) {
      return
    }

    const loadRecommendations = async () => {
      setLoadingRecommendations(true)
      setRecommendationError('')

      try {
        let payload
        if (recommendationMode === 'svd') {
          payload = await api.getSvdRecommendations({ user_id: currentUser.user_id, top_n: 6 })
        } else if (recommendationMode === 'svd-nn') {
          payload = await api.getSvdNnRecommendations({ user_id: currentUser.user_id, top_n: 6 })
        } else {
          payload = await api.getFullRecommendations({ user_id: currentUser.user_id, top_n: 6 })
        }

        setRecommendations(payload.recommendations || [])
      } catch (requestError) {
        setRecommendationError(requestError.message)
      } finally {
        setLoadingRecommendations(false)
      }
    }

    loadRecommendations()
  }, [currentUser, recommendationMode])

  const scoreForMode = (item) => {
    if (recommendationMode === 'full') {
      return Number(item.final_score ?? item.combined_score ?? item.svd_score)
    }
    if (recommendationMode === 'svd-nn') {
      return Number(item.combined_score ?? item.svd_score)
    }
    return Number(item.svd_score)
  }

  return (
    <div className="page-stack">
      <section className="hero-panel glass-card">
        <div className="hero-copy">
          <p className="eyebrow mb-2">Home</p>
          <h1 className="display-5 fw-bold mb-3">Welcome back, {currentUser.username}.</h1>
          <p className="text-secondary mb-4">Browse movies, click any poster, and record your interaction. The collected feedback powers SVD, neural network, and fuzzy logic recommendations.</p>
          <div className="hero-stats">
            <div className="stat-pill">
              <span className="stat-value">{movies.length}</span>
              <span className="stat-label">Movies loaded</span>
            </div>
            <div className="stat-pill">
              <span className="stat-value">Login</span>
              <span className="stat-label">Login + browse</span>
            </div>
            <div className="stat-pill">
              <span className="stat-value">SQLite</span>
              <span className="stat-label">Interaction store</span>
            </div>
          </div>
        </div>
      </section>

      <section>
        <div className="section-header">
          <div>
            <p className="eyebrow mb-1">Featured</p>
            <h2 className="h3 mb-0">Popular picks</h2>
          </div>
        </div>

        {loadingMovies ? (
          <div className="text-center py-5 text-secondary">Loading movies...</div>
        ) : (
          <div className="movie-grid">
            {featuredMovies.map((movie) => (
              <MovieCard key={movie.movie_id} movie={movie} onClick={onSelectMovie} />
            ))}
          </div>
        )}
      </section>

      <section className="glass-card p-3 p-lg-4">
        <div className="section-header mb-3">
          <div>
            <p className="eyebrow mb-1">Recommendations</p>
            <h2 className="h3 mb-0">Model comparison</h2>
          </div>
          <div className="d-flex flex-wrap gap-2">
            {RECOMMENDATION_MODES.map((mode) => (
              <button
                key={mode.key}
                type="button"
                className={`btn ${recommendationMode === mode.key ? 'btn-warning' : 'btn-outline-light'}`}
                onClick={() => setRecommendationMode(mode.key)}
              >
                {mode.label}
              </button>
            ))}
          </div>
        </div>

        {recommendationError ? <div className="alert alert-danger border-0">{recommendationError}</div> : null}

        {loadingRecommendations ? (
          <div className="text-center py-4 text-secondary">Loading {RECOMMENDATION_MODES.find((mode) => mode.key === recommendationMode)?.label || 'recommendations'}...</div>
        ) : recommendations.length === 0 ? (
          <div className="alert alert-dark border-0 mb-0">No recommendations yet. Add a few interactions first.</div>
        ) : (
          <div className="recommendation-strip">
            {recommendations.map((item) => (
              <article key={item.movie.movie_id} className="recommendation-card card border-0 glass-card" role="button" tabIndex={0} onClick={() => onSelectMovie(item.movie)} onKeyDown={(event) => event.key === 'Enter' && onSelectMovie(item.movie)}>
                <div className="recommendation-thumb-wrap">
                  <img className="recommendation-thumb" src={item.movie.poster_url} alt={`${item.movie.title} poster`} />
                </div>
                <div className="card-body d-flex flex-column gap-2">
                  <div>
                    <h5 className="card-title mb-1">{item.movie.title}</h5>
                    <p className="movie-genres mb-0">{item.movie.genres}</p>
                  </div>
                  <div className="d-flex flex-wrap gap-2">
                    <span className="badge text-bg-info">Score {scoreForMode(item).toFixed(3)}</span>
                    {recommendationMode !== 'svd' ? <span className="badge text-bg-secondary">SVD {Number(item.svd_score).toFixed(3)}</span> : null}
                    {recommendationMode === 'svd-nn' || recommendationMode === 'full' ? <span className="badge text-bg-secondary">NN {Number(item.nn_score).toFixed(3)}</span> : null}
                    {recommendationMode === 'full' ? <span className="badge text-bg-warning">Fuzzy +{Number(item.fuzzy_boost).toFixed(1)}</span> : null}
                  </div>
                  <button className="btn btn-outline-light btn-sm mt-auto align-self-start" type="button" onClick={(event) => {
                    event.stopPropagation()
                    onSelectMovie(item.movie)
                  }}>
                    Rate this movie
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
