import { useEffect, useState } from 'react'

import { api } from '../api'

function Profile({ currentUser }) {
  const [payload, setPayload] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    const loadProfile = async () => {
      setLoading(true)
      setError('')
      try {
        const data = await api.getUserProfile({ user_id: currentUser.user_id })
        setPayload(data.profile)
      } catch (requestError) {
        setError(requestError.message)
      } finally {
        setLoading(false)
      }
    }

    loadProfile()
  }, [currentUser])

  return (
    <div className="page-stack">
      <section className="hero-panel glass-card compact-hero">
        <div>
          <p className="eyebrow mb-2">Profile</p>
          <h1 className="h2 fw-bold mb-2">User profiling</h1>
          <p className="text-secondary mb-0">
            The system classifies your behavior from your saved interactions.
          </p>
        </div>
      </section>

      {error ? <div className="alert alert-danger border-0">{error}</div> : null}

      {loading ? (
        <div className="text-center py-5 text-secondary">Loading profile...</div>
      ) : payload ? (
        <section className="profile-grid">
          <article className="glass-card profile-card">
            <span className="metric-label">Profile</span>
            <span className="metric-value">{payload.profile}</span>
            <p className="text-secondary mb-0 mt-2">{payload.reason}</p>
          </article>
          <article className="glass-card profile-card">
            <span className="metric-label">Interactions</span>
            <span className="metric-value">{payload.interaction_count}</span>
            <p className="text-secondary mb-0 mt-2">Total records used for classification.</p>
          </article>
          <article className="glass-card profile-card">
            <span className="metric-label">Average duration</span>
            <span className="metric-value">{payload.average_duration_minutes} min</span>
          </article>
          <article className="glass-card profile-card">
            <span className="metric-label">Skip rate</span>
            <span className="metric-value">{Math.round(payload.skip_rate * 100)}%</span>
          </article>
          <article className="glass-card profile-card profile-card-wide">
            <span className="metric-label">Behavior tags</span>
            <div className="d-flex flex-wrap gap-2 mt-2 mb-2">
              {(payload.profile_tags || []).map((tag) => (
                <span key={tag} className="badge text-bg-info">{tag}</span>
              ))}
            </div>
            <div className="small text-secondary">
              {Object.entries(payload.profile_tag_reasons || {}).map(([tag, reason]) => (
                <div key={tag} className="mb-1"><strong>{tag}:</strong> {reason}</div>
              ))}
            </div>
          </article>
        </section>
      ) : (
        <div className="alert alert-dark border-0 mb-0">No profile data available yet.</div>
      )}

      {payload ? (
        <section className="glass-card p-3 p-lg-4">
          <div className="section-header mb-3">
            <div>
              <p className="eyebrow mb-1">Filtered preferences</p>
              <h2 className="h4 mb-0">Top genres in your interaction profile</h2>
            </div>
          </div>
          <div className="d-flex flex-wrap gap-2">
            {(payload.filter_genres || []).map((genre) => (
              <span key={genre} className="badge text-bg-info">{genre}</span>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  )
}

export default Profile
