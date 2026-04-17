import { Fragment, useState } from 'react'
import { API_BASE_URL } from '../api'

function MovieCard({ movie, onClick, badges = [], caption = '', actions = [], showButton = true, className = '' }) {
  const [posterError, setPosterError] = useState(false)
  const visibleBadges = badges.filter(Boolean)

  const handlePosterError = () => {
    setPosterError(true)
  }

  // Fallback poster: simple dark placeholder with movie title
  const fallbackPoster = `data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='300' height='450'%3E%3Crect width='300' height='450' fill='%230f172a'/%3E%3Ctext x='50%25' y='50%25' font-size='16' fill='%23f8fafc' text-anchor='middle' dominant-baseline='middle' font-family='Arial' font-weight='bold' word-spacing='100vw'%3E${encodeURIComponent(movie.title)}%3C/text%3E%3C/svg%3E`

  const resolvePosterUrl = (posterUrl) => {
    if (!posterUrl) {
      return fallbackPoster
    }

    if (posterUrl.startsWith('/static/posters/')) {
      return `${API_BASE_URL}${posterUrl}`
    }

    try {
      const parsedPoster = new URL(posterUrl)
      const parsedApi = new URL(API_BASE_URL)
      const isBackendHost = parsedPoster.origin === parsedApi.origin
      const isLocalPosterPath = parsedPoster.pathname.startsWith('/static/posters/')

      if (isBackendHost && isLocalPosterPath) {
        return posterUrl
      }
    } catch {
      return fallbackPoster
    }

    return fallbackPoster
  }

  return (
    <article className={`movie-card card h-100 border-0 ${className}`.trim()} role="button" tabIndex={0} onClick={() => onClick(movie)} onKeyDown={(event) => event.key === 'Enter' && onClick(movie)}>
      <div className="movie-poster-wrap">
        <img 
          className="movie-poster" 
          src={posterError ? fallbackPoster : resolvePosterUrl(movie.poster_url)} 
          alt={`${movie.title} poster`}
          onError={handlePosterError}
        />
        <div className="movie-overlay">
          <span className="movie-overlay-text">Open interaction form</span>
        </div>
      </div>
      <div className="card-body d-flex flex-column gap-2">
        <div>
          <h5 className="card-title mb-1">{movie.title}</h5>
          <p className="movie-genres mb-0">{movie.genres}</p>
          {caption ? <p className="text-secondary small mb-0 mt-1">{caption}</p> : null}
        </div>
        {visibleBadges.length > 0 ? (
          <div className="d-flex flex-wrap gap-2">
            {visibleBadges.map((badge) => (
              <span key={badge.label} className={`badge ${badge.className || 'text-bg-secondary'}`}>
                {badge.label}
              </span>
            ))}
          </div>
        ) : null}
        {actions.length > 0 ? (
          <div className="movie-actions">
            {actions.map((action, index) => (
              <Fragment key={action.key || `${movie.movie_id}-${index}`}>{action.node}</Fragment>
            ))}
          </div>
        ) : null}
        {showButton ? (
          <button className="btn btn-outline-light btn-sm mt-auto align-self-start" type="button" onClick={(event) => {
            event.stopPropagation()
            onClick(movie)
          }}>
            Record interaction
          </button>
        ) : null}
      </div>
    </article>
  )
}

export default MovieCard
