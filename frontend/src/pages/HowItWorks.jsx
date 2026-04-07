import { useEffect, useMemo, useState } from 'react'

import { api } from '../api'

const durationLabels = {
  '10': '10 min',
  '30': '30 min',
  '60': '60 min',
  full: 'Full',
}

const clampScore = (value) => Math.max(1, Math.min(5, value))

function getMovieId(row) {
  return row?.movie?.movie_id ?? row?.movie_id ?? null
}

function findRowByMovieId(rows, movieId) {
  return (rows || []).find((row) => getMovieId(row) === movieId) || null
}

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
  const [svdPayload, setSvdPayload] = useState(null)
  const [svdNnPayload, setSvdNnPayload] = useState(null)
  const [fullPayload, setFullPayload] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    const loadExplanation = async () => {
      setLoading(true)
      setError('')
      try {
        const [interactionsData, svdData, svdNnData, fullData] = await Promise.all([
          api.getInteractions({ user_id: currentUser.user_id }),
          api.getSvdRecommendations({ user_id: currentUser.user_id, top_n: 10 }),
          api.getSvdNnRecommendations({ user_id: currentUser.user_id, top_n: 10 }),
          api.getFullRecommendations({ user_id: currentUser.user_id, top_n: 10 }),
        ])
        setInteractions(interactionsData.interactions || [])
        setSvdPayload(svdData)
        setSvdNnPayload(svdNnData)
        setFullPayload(fullData)
      } catch (requestError) {
        setError(requestError.message)
      } finally {
        setLoading(false)
      }
    }

    loadExplanation()
  }, [currentUser])

  const summary = useMemo(() => summarizeInteractions(interactions), [interactions])
  const fullRecommendation = fullPayload?.recommendations?.[0] || null
  const selectedMovieId = getMovieId(fullRecommendation)
  const svdRow = findRowByMovieId(svdPayload?.recommendations, selectedMovieId)
  const svdNnRow = findRowByMovieId(svdNnPayload?.recommendations, selectedMovieId)

  const fuzzy = fullRecommendation?.fuzzy || fullPayload?.training?.fuzzy || null
  const combinedScore = fullRecommendation?.combined_score ?? ((Number(svdRow?.svd_score || 0) + Number(svdNnRow?.nn_score || 0)) / 2)
  const finalScore = fullRecommendation?.final_score ?? clampScore(Number(combinedScore || 0) + Number(fuzzy?.boost || 0))
  const pipeline = fullPayload?.training?.pipeline || {}

  return (
    <div className="page-stack">
      <section className="hero-panel glass-card compact-hero">
        <div>
          <p className="eyebrow mb-2">Overview</p>
          <h1 className="h2 fw-bold mb-2">How it works</h1>
          <p className="text-secondary mb-0">
            This page shows how SmartFlix turns your viewing behavior into SVD, NN, and fuzzy hybrid recommendations.
          </p>
        </div>
        <div className="hero-stats">
          <div className="stat-pill">
            <span className="stat-value">{summary.profile}</span>
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
        <div className="text-center py-5 text-secondary">Loading explainability data...</div>
      ) : fullRecommendation ? (
        <>
          <section className="how-grid">
            <article className="glass-card how-card">
              <p className="eyebrow mb-1">1. User behavior</p>
              <h2 className="h4 mb-3">What the system observes</h2>
              <ul className="plain-list mb-0">
                <li>Average watch duration: {summary.averageDuration}</li>
                <li>Skip rate: {summary.skipRate}</li>
                <li>Interest level: {summary.averageInterest}/5</li>
                <li>Profile: {summary.profile}</li>
              </ul>
            </article>

            <article className="glass-card how-card">
              <p className="eyebrow mb-1">2. SVD prediction</p>
              <h2 className="h4 mb-3">Collaborative filtering score</h2>
              <div className="score-line">SVD score: <strong>{Number(svdRow?.svd_score ?? fullRecommendation.svd_score).toFixed(3)}</strong></div>
              <p className="text-secondary mb-0">Predicted by latent user-item factors trained from MovieLens plus generated interaction ratings.</p>
            </article>

            <article className="glass-card how-card">
              <p className="eyebrow mb-1">3. NN prediction</p>
              <h2 className="h4 mb-3">Feature-based rating</h2>
              <div className="score-line">NN score: <strong>{Number(svdNnRow?.nn_score ?? fullRecommendation.nn_score).toFixed(3)}</strong></div>
              <p className="text-secondary mb-0">The neural model uses user, movie, duration, skips, and interest level features to learn nonlinear patterns.</p>
            </article>

            <article className="glass-card how-card">
              <p className="eyebrow mb-1">4. Fuzzy layer</p>
              <h2 className="h4 mb-3">Decision boost</h2>
              <div className="score-line">Output: <strong>{String(fuzzy?.output || 'medium').toUpperCase()}</strong></div>
              <div className="score-line">Boost: <strong>{Number(fuzzy?.boost ?? fullRecommendation.fuzzy_boost).toFixed(1)}</strong></div>
              <p className="text-secondary mb-0">Rules interpret the user style and add a small positive uplift to the combined score.</p>
            </article>
          </section>

          <section className="glass-card p-3 p-lg-4">
            <div className="section-header mb-3">
              <div>
                <p className="eyebrow mb-1">Pipeline summary</p>
                <h2 className="h4 mb-0">Why each stage exists</h2>
              </div>
            </div>
            <div className="rule-grid">
              <article className="rule-card">
                <span className="badge text-bg-info">SVD</span>
                <div className="rule-text">{pipeline.svd || 'SVD learns collaborative patterns from MovieLens ratings and app interactions.'}</div>
              </article>
              <article className="rule-card">
                <span className="badge text-bg-info">NN</span>
                <div className="rule-text">{pipeline.nn || 'The NN uses user and movie features plus behavior signals to refine the score.'}</div>
              </article>
              <article className="rule-card">
                <span className="badge text-bg-info">Fuzzy</span>
                <div className="rule-text">{pipeline.fuzzy || 'Fuzzy logic converts the behavior profile into a small score uplift.'}</div>
              </article>
            </div>
          </section>

          <section className="glass-card p-3 p-lg-4">
            <div className="section-header mb-3">
              <div>
                <p className="eyebrow mb-1">Recommendation Trace</p>
                <h2 className="h4 mb-0">{fullRecommendation.movie.title}</h2>
              </div>
              <span className="badge text-bg-warning">Final score {Number(finalScore).toFixed(3)}</span>
            </div>

            <div className="trace-grid">
              <div className="trace-panel">
                <span className="trace-label">SVD</span>
                <span className="trace-value">{Number(svdRow?.svd_score ?? fullRecommendation.svd_score).toFixed(3)}</span>
              </div>
              <div className="trace-panel">
                <span className="trace-label">NN</span>
                <span className="trace-value">{Number(svdNnRow?.nn_score ?? fullRecommendation.nn_score).toFixed(3)}</span>
              </div>
              <div className="trace-panel">
                <span className="trace-label">Combined</span>
                <span className="trace-value">{Number(combinedScore).toFixed(3)}</span>
              </div>
              <div className="trace-panel">
                <span className="trace-label">Fuzzy boost</span>
                <span className="trace-value">{Number(fuzzy?.boost ?? fullRecommendation.fuzzy_boost).toFixed(1)}</span>
              </div>
            </div>

            <div className="formula-box mt-3">
              <div>Combined = (SVD + NN) / 2 = ({Number(svdRow?.svd_score ?? fullRecommendation.svd_score).toFixed(3)} + {Number(svdNnRow?.nn_score ?? fullRecommendation.nn_score).toFixed(3)}) / 2</div>
              <div>Final = clamp(Combined + Fuzzy boost, 1, 5) = clamp({Number(combinedScore).toFixed(3)} + {Number(fuzzy?.boost ?? fullRecommendation.fuzzy_boost).toFixed(1)}, 1, 5)</div>
              <div>Final score = <strong>{Number(finalScore).toFixed(3)}</strong></div>
            </div>
          </section>

          <section className="glass-card p-3 p-lg-4">
            <div className="section-header mb-3">
              <div>
                <p className="eyebrow mb-1">Fuzzy rules</p>
                <h2 className="h4 mb-0">Triggered rules for this user</h2>
              </div>
            </div>
            <div className="rule-grid">
              {(fuzzy?.triggered_rules || []).length > 0 ? (
                fuzzy.triggered_rules.map((rule) => (
                  <article key={rule.id} className="rule-card">
                    <span className={`badge ${rule.strength === 'strong' ? 'text-bg-success' : rule.strength === 'medium' ? 'text-bg-secondary' : 'text-bg-danger'}`}>{rule.strength}</span>
                    <div className="rule-text">Rule {rule.id}: {rule.rule}</div>
                  </article>
                ))
              ) : (
                <div className="alert alert-dark border-0 mb-0">No explicit fuzzy rule was triggered; the system used the default medium output.</div>
              )}
            </div>
          </section>

          <section className="glass-card p-3 p-lg-4">
            <div className="section-header mb-3">
              <div>
                <p className="eyebrow mb-1">Support Data</p>
                <h2 className="h4 mb-0">Matched recommendation payloads</h2>
              </div>
            </div>
            <div className="table-responsive">
              <table className="table table-dark table-hover align-middle mb-0">
                <thead>
                  <tr>
                    <th>Stage</th>
                    <th>Score</th>
                    <th>Notes</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>SVD</td>
                    <td>{Number(svdRow?.svd_score ?? fullRecommendation.svd_score).toFixed(3)}</td>
                    <td>Collaborative filtering output</td>
                  </tr>
                  <tr>
                    <td>NN</td>
                    <td>{Number(svdNnRow?.nn_score ?? fullRecommendation.nn_score).toFixed(3)}</td>
                    <td>Feature-based predicted rating</td>
                  </tr>
                  <tr>
                    <td>Combined</td>
                    <td>{Number(combinedScore).toFixed(3)}</td>
                    <td>Averaged score before fuzzy adjustment</td>
                  </tr>
                  <tr>
                    <td>Final</td>
                    <td>{Number(finalScore).toFixed(3)}</td>
                    <td>After fuzzy uplift</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>
        </>
      ) : (
        <div className="alert alert-dark border-0 mb-0">Add a few interactions and generate recommendations to populate the explainability view.</div>
      )}
    </div>
  )
}

export default HowItWorks
