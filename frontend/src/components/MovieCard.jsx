import { useState } from 'react'

function MovieCard({ movie, onClick }) {
  const [posterError, setPosterError] = useState(false)

  const handlePosterError = () => {
    setPosterError(true)
  }

  // Fallback poster: simple dark placeholder with movie title
  const fallbackPoster = `data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='300' height='450'%3E%3Crect width='300' height='450' fill='%230f172a'/%3E%3Ctext x='50%25' y='50%25' font-size='16' fill='%23f8fafc' text-anchor='middle' dominant-baseline='middle' font-family='Arial' font-weight='bold' word-spacing='100vw'%3E${encodeURIComponent(movie.title)}%3C/text%3E%3C/svg%3E`

  return (
    <article className="movie-card card h-100 border-0" role="button" tabIndex={0} onClick={() => onClick(movie)} onKeyDown={(event) => event.key === 'Enter' && onClick(movie)}>
      <div className="movie-poster-wrap">
        <img 
          className="movie-poster" 
          src={posterError ? fallbackPoster : movie.poster_url} 
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
        </div>
        <button className="btn btn-outline-light btn-sm mt-auto align-self-start" type="button" onClick={(event) => {
          event.stopPropagation()
          onClick(movie)
        }}>
          Record interaction
        </button>
      </div>
    </article>
  )
}

export default MovieCard
