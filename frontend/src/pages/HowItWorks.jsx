import { useEffect, useMemo, useState } from 'react'

import { api } from '../api'

function summarizeInteractions(interactions) {
  if (!interactions.length) {
    return {
      count: 0,
      averageDuration: '0 min',
      averageInterest: '0.0',
      skipRate: '0%',
      profile: 'Not enough interactions yet.',
    }
  }

  const durationMap = { '10': 10, '30': 30, '60': 60, full: 90 }
  const totalDuration = interactions.reduce((sum, interaction) => sum + (durationMap[interaction.watch_duration] || 30), 0)
  const totalInterest = interactions.reduce((sum, interaction) => sum + Number(interaction.interest_level || 0), 0)
  const skipCount = interactions.filter((interaction) => interaction.skipped_scenes || interaction.skipped_music).length
  const averageDuration = Math.round(totalDuration / interactions.length)
  const averageInterest = (totalInterest / interactions.length).toFixed(1)
  const skipRate = `${Math.round((skipCount / interactions.length) * 100)}%`

  let profile = 'Balanced'
  if (averageDuration <= 30) {
    profile = 'Casual'
  } else if (skipCount / interactions.length > 0.5 && totalInterest / interactions.length >= 4) {
    profile = 'Action-focused'
  } else if (averageDuration >= 90 && skipCount / interactions.length < 0.3) {
    profile = 'Story-focused'
  }

  return {
    count: interactions.length,
    averageDuration: `${averageDuration} min`,
    averageInterest,
    skipRate,
    profile,
  }
}

function HowItWorks({ currentUser }) {
  const [interactions, setInteractions] = useState([])
  const [profilePayload, setProfilePayload] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    const loadExplanation = async () => {
      setLoading(true)
      setError('')
      try {
        const [interactionsData, profileData] = await Promise.all([
          api.getInteractions({ user_id: currentUser.user_id }),
          api.getUserProfile({ user_id: currentUser.user_id }),
        ])
        setInteractions(interactionsData.interactions || [])
        setProfilePayload(profileData.profile || null)
      } catch (requestError) {
        setError(requestError.message)
      } finally {
        setLoading(false)
      }
    }

    loadExplanation()
  }, [currentUser])

  const summary = useMemo(() => summarizeInteractions(interactions), [interactions])

  return (
    <div className="page-stack">
      <section className="hero-panel glass-card compact-hero">
        <div>
          <p className="eyebrow mb-2">Overview</p>
          <h1 className="h2 fw-bold mb-2">How it works</h1>
          <p className="text-secondary mb-0">
            SmartFlix captures your movie interactions and builds a behavior profile from local data.
          </p>
        </div>
        <div className="hero-stats">
          <div className="stat-pill">
            <span className="stat-value">{profilePayload?.profile || summary.profile}</span>
            <span className="stat-label">User profile</span>
          </div>
          <div className="stat-pill">
            <span className="stat-value">{summary.count}</span>
            <span className="stat-label">Interactions</span>
          </div>
          <div className="stat-pill">
            <span className="stat-value">{summary.averageInterest}</span>
            <span className="stat-label">Average interest</span>
          </div>
        </div>
      </section>

      {error ? <div className="alert alert-danger border-0">{error}</div> : null}

      {loading ? (
        <div className="text-center py-5 text-secondary">Loading profile and interaction data...</div>
      ) : (
        <>
          <section className="how-grid">
            <article className="glass-card how-card">
              <p className="eyebrow mb-1">1. Login</p>
              <h2 className="h4 mb-3">Create or resolve user</h2>
              <ul className="plain-list mb-0">
                <li>The app stores your username in SQLite.</li>
                <li>If the username already exists, it reuses that account.</li>
                <li>No external identity provider is required.</li>
              </ul>
            </article>

            <article className="glass-card how-card">
              <p className="eyebrow mb-1">2. Interactions</p>
              <h2 className="h4 mb-3">Behavior is captured</h2>
              <div className="score-line">Average duration: <strong>{summary.averageDuration}</strong></div>
              <div className="score-line">Average interest: <strong>{summary.averageInterest}/5</strong></div>
              <p className="text-secondary mb-0">Each interaction stores watched state, duration, completion, skip flags, and interest score.</p>
            </article>

            <article className="glass-card how-card">
              <p className="eyebrow mb-1">3. Profile</p>
              <h2 className="h4 mb-3">Preference classification</h2>
              <div className="score-line">Profile: <strong>{profilePayload?.profile || summary.profile}</strong></div>
              <p className="text-secondary mb-0">The backend classifies user behavior using local interaction history.</p>
            </article>

            <article className="glass-card how-card">
              <p className="eyebrow mb-1">4. Posters</p>
              <h2 className="h4 mb-3">Offline static delivery</h2>
              <div className="score-line">Mode: <strong>Offline only</strong></div>
              <p className="text-secondary mb-0">Posters are served from local static files and never requested from third-party APIs at runtime.</p>
            </article>
          </section>

          <section className="glass-card p-3 p-lg-4">
            <div className="section-header mb-3">
              <div>
                <p className="eyebrow mb-1">Profile Summary</p>
                <h2 className="h4 mb-0">Current user signals</h2>
              </div>
            </div>
            <div className="rule-grid">
              <article className="rule-card">
                <span className="badge text-bg-info">Interactions</span>
                <div className="rule-text">Total events: {summary.count}</div>
              </article>
              <article className="rule-card">
                <span className="badge text-bg-info">Skip rate</span>
                <div className="rule-text">{summary.skipRate}</div>
              </article>
              <article className="rule-card">
                <span className="badge text-bg-info">Genres used for profile</span>
                <div className="rule-text">{(profilePayload?.filter_genres || []).join(', ') || 'All genres'}</div>
              </article>
            </div>
          </section>
        </>
      )}
    </div>
  )
}

export default HowItWorks
