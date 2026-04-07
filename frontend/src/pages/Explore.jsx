import { useState } from 'react'
import MovieCard from '../components/MovieCard'

function Explore({ movies, loadingMovies, onSelectMovie }) {
  const [searchTerm, setSearchTerm] = useState('')
  const [genreFilter, setGenreFilter] = useState('all')

  const genres = ['all', ...new Set(movies.flatMap((movie) => movie.genres.split('|').map((genre) => genre.trim())).filter(Boolean))]
  const filteredMovies = movies.filter((movie) => {
    const searchable = `${movie.title} ${movie.genres}`.toLowerCase()
    const matchesSearch = searchable.includes(searchTerm.toLowerCase())
    const matchesGenre = genreFilter === 'all' || movie.genres.toLowerCase().includes(genreFilter.toLowerCase())
    return matchesSearch && matchesGenre
  })

  return (
    <div className="page-stack">
      <section className="hero-panel glass-card compact-hero">
        <div>
          <p className="eyebrow mb-2">Explore</p>
          <h1 className="h2 fw-bold mb-2">Browse the catalog</h1>
          <p className="text-secondary mb-0">Search by title or genre, then open any movie to submit your interaction form.</p>
        </div>
        <div className="explore-controls">
          <input
            className="form-control input-dark"
            placeholder="Search movies"
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
          />
          <select className="form-select input-dark" value={genreFilter} onChange={(event) => setGenreFilter(event.target.value)}>
            {genres.map((genre) => (
              <option key={genre} value={genre}>{genre === 'all' ? 'All genres' : genre}</option>
            ))}
          </select>
        </div>
      </section>

      {loadingMovies ? (
        <div className="text-center py-5 text-secondary">Loading movies...</div>
      ) : (
        <>
          <div className="section-header mt-2">
            <div>
              <p className="eyebrow mb-1">Results</p>
              <h2 className="h3 mb-0">{filteredMovies.length} matches</h2>
            </div>
          </div>
          <div className="movie-grid">
            {filteredMovies.map((movie) => (
              <MovieCard key={movie.movie_id} movie={movie} onClick={onSelectMovie} />
            ))}
          </div>
        </>
      )}
    </div>
  )
}

export default Explore
