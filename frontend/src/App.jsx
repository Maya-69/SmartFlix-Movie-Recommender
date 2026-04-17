import { useEffect, useState } from 'react'
import { Link, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'

import { api } from './api'
import MovieInteractionModal from './components/MovieInteractionModal'
import Explore from './pages/Explore'
import Home from './pages/Home'
import Interactions from './pages/Interactions'
import Login from './pages/Login'
import HowItWorks from './pages/HowItWorks'
import Profile from './pages/Profile'
import Recommendations from './pages/Recommendations'

function RequireAuth({ currentUser, children }) {
  if (!currentUser) {
    return <Navigate to="/login" replace />
  }

  return children
}

function App() {
  const navigate = useNavigate()
  const location = useLocation()
  const [currentUser, setCurrentUser] = useState(() => {
    const storedUser = window.localStorage.getItem('smartflix_user')
    return storedUser ? JSON.parse(storedUser) : null
  })
  const [movies, setMovies] = useState([])
  const [interactions, setInteractions] = useState([])
  const [loadingMovies, setLoadingMovies] = useState(false)
  const [loadingInteractions, setLoadingInteractions] = useState(false)
  const [authLoading, setAuthLoading] = useState(false)
  const [interactionSaving, setInteractionSaving] = useState(false)
  const [selectedMovie, setSelectedMovie] = useState(null)
  const [bannerMessage, setBannerMessage] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    if (!currentUser) {
      setMovies([])
      return
    }

    const loadMovies = async () => {
      setLoadingMovies(true)
      setError('')
      try {
        const payload = await api.getMovies()
        setMovies(payload.movies || [])
      } catch (requestError) {
        setError(requestError.message)
      } finally {
        setLoadingMovies(false)
      }
    }

    loadMovies()
  }, [currentUser])

  useEffect(() => {
    if (!currentUser) {
      return
    }

    const loadInteractions = async () => {
      setLoadingInteractions(true)
      setError('')
      try {
        const payload = await api.getInteractions({ user_id: currentUser.user_id })
        setInteractions(payload.interactions || [])
      } catch (requestError) {
        setError(requestError.message)
      } finally {
        setLoadingInteractions(false)
      }
    }

    loadInteractions()
  }, [currentUser])

  useEffect(() => {
    if (!bannerMessage) {
      return undefined
    }

    const timer = window.setTimeout(() => setBannerMessage(''), 3000)
    return () => window.clearTimeout(timer)
  }, [bannerMessage])

  const handleLogin = async (username) => {
    setAuthLoading(true)
    setError('')
    try {
      const payload = await api.createUser(username)
      setCurrentUser(payload.user)
      window.localStorage.setItem('smartflix_user', JSON.stringify(payload.user))
      navigate('/home')
    } catch (requestError) {
      setError(requestError.message)
      throw requestError
    } finally {
      setAuthLoading(false)
    }
  }

  const handleLogout = () => {
    window.localStorage.removeItem('smartflix_user')
    setCurrentUser(null)
    setMovies([])
    setInteractions([])
    setSelectedMovie(null)
    setBannerMessage('')
    navigate('/login')
  }

  const handleSaveInteraction = async (interaction) => {
    if (!currentUser || !selectedMovie) {
      return
    }

    setInteractionSaving(true)
    try {
      await api.saveInteraction({
        ...interaction,
        user_id: currentUser.user_id,
        movie_id: selectedMovie.movie_id,
      })
      const interactionsPayload = await api.getInteractions({ user_id: currentUser.user_id })
      setInteractions(interactionsPayload.interactions || [])
      setSelectedMovie(null)
      setBannerMessage(`Saved your response for ${selectedMovie.title}.`)
    } finally {
      setInteractionSaving(false)
    }
  }

  const brandRoute = currentUser ? '/home' : '/login'

  return (
    <div className="app-shell">
      <header className="topbar navbar navbar-expand-lg navbar-dark">
        <div className="container-fluid px-4 px-lg-5">
          <Link className="navbar-brand brand-mark" to={brandRoute}>SmartFlix</Link>
          <button className="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#smartflix-nav">
            <span className="navbar-toggler-icon" />
          </button>
          <div className="collapse navbar-collapse" id="smartflix-nav">
            <div className="navbar-nav ms-auto align-items-lg-center gap-lg-2">
              {currentUser ? (
                <>
                  <Link className={`nav-link ${location.pathname === '/home' ? 'active' : ''}`} to="/home">Home</Link>
                  <Link className={`nav-link ${location.pathname === '/explore' ? 'active' : ''}`} to="/explore">Explore</Link>
                  <Link className={`nav-link ${location.pathname === '/recommendations' ? 'active' : ''}`} to="/recommendations">Recommendations</Link>
                  <Link className={`nav-link ${location.pathname === '/interactions' ? 'active' : ''}`} to="/interactions">Interactions</Link>
                  <Link className={`nav-link ${location.pathname === '/how-it-works' ? 'active' : ''}`} to="/how-it-works">How It Works</Link>
                  <Link className={`nav-link ${location.pathname === '/profile' ? 'active' : ''}`} to="/profile">Profile</Link>
                  <span className="nav-link user-chip">{currentUser.username}</span>
                  <button className="btn btn-outline-light btn-sm" type="button" onClick={handleLogout}>Logout</button>
                </>
              ) : (
                <Link className="nav-link" to="/login">Login</Link>
              )}
            </div>
          </div>
        </div>
      </header>

      <main className="container-fluid px-3 px-lg-5 py-4 py-lg-5">
        {error ? <div className="alert alert-danger border-0 shadow-sm">{error}</div> : null}
        {bannerMessage ? <div className="alert alert-success border-0 shadow-sm">{bannerMessage}</div> : null}

        <Routes>
          <Route path="/" element={<Navigate to={currentUser ? '/home' : '/login'} replace />} />
          <Route path="/login" element={<Login currentUser={currentUser} onLogin={handleLogin} loading={authLoading} error={error} />} />
          <Route
            path="/home"
            element={(
              <RequireAuth currentUser={currentUser}>
                <Home
                  currentUser={currentUser}
                  movies={movies}
                  loadingMovies={loadingMovies}
                  onSelectMovie={setSelectedMovie}
                />
              </RequireAuth>
            )}
          />
          <Route
            path="/explore"
            element={(
              <RequireAuth currentUser={currentUser}>
                <Explore movies={movies} loadingMovies={loadingMovies} onSelectMovie={setSelectedMovie} />
              </RequireAuth>
            )}
          />
          <Route
            path="/recommendations"
            element={(
              <RequireAuth currentUser={currentUser}>
                <Recommendations currentUser={currentUser} onSelectMovie={setSelectedMovie} />
              </RequireAuth>
            )}
          />
          <Route
            path="/interactions"
            element={(
              <RequireAuth currentUser={currentUser}>
                <Interactions
                  currentUser={currentUser}
                  interactions={interactions}
                  loadingInteractions={loadingInteractions}
                />
              </RequireAuth>
            )}
          />
          <Route
            path="/how-it-works"
            element={(
              <RequireAuth currentUser={currentUser}>
                <HowItWorks currentUser={currentUser} />
              </RequireAuth>
            )}
          />
          <Route
            path="/profile"
            element={(
              <RequireAuth currentUser={currentUser}>
                <Profile currentUser={currentUser} />
              </RequireAuth>
            )}
          />
          <Route path="*" element={<Navigate to={currentUser ? '/home' : '/login'} replace />} />
        </Routes>
      </main>

      {selectedMovie && currentUser ? (
        <MovieInteractionModal
          movie={selectedMovie}
          user={currentUser}
          onClose={() => setSelectedMovie(null)}
          onSubmit={handleSaveInteraction}
          saving={interactionSaving}
        />
      ) : null}
    </div>
  )
}

export default App
