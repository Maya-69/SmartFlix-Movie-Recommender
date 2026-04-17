import { useState } from 'react'
import { Navigate } from 'react-router-dom'

function Login({ currentUser, onLogin, loading, error }) {
  const [username, setUsername] = useState('')
  const [localError, setLocalError] = useState('')

  if (currentUser) {
    return <Navigate to="/home" replace />
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    const trimmedUsername = username.trim()

    if (!trimmedUsername) {
      setLocalError('Enter a username to continue.')
      return
    }

    setLocalError('')
    await onLogin(trimmedUsername)
  }

  return (
    <section className="auth-layout">
      <div className="auth-card glass-card">
        <p className="eyebrow mb-2">SmartFlix</p>
        <h1 className="display-5 fw-bold mb-3">Offline movie interaction tracker with a clean, viva-friendly interface.</h1>
        <p className="text-secondary mb-4">Start with username-only login, movie browsing, and structured interaction capture. No playback, just data collection.</p>

        <form onSubmit={handleSubmit} className="d-grid gap-3">
          <div>
            <label className="form-label">Username</label>
            <input
              className="form-control form-control-lg input-dark"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              placeholder="Enter your username"
              autoComplete="username"
            />
          </div>
          {(localError || error) ? <div className="alert alert-danger mb-0">{localError || error}</div> : null}
          <button className="btn btn-warning btn-lg fw-semibold" type="submit" disabled={loading}>
            {loading ? 'Signing in...' : 'Enter SmartFlix'}
          </button>
        </form>
      </div>
    </section>
  )
}

export default Login
