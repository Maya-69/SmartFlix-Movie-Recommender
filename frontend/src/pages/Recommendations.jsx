import { useEffect, useMemo, useState } from 'react'

import { api } from '../api'

function formatScore(value) {
  if (value === null || value === undefined) {
    return 'n/a'
  }
  return Number(value).toFixed(3)
}

function titleOnlyTable({ title, subtitle, columns, rows, emptyText }) {
  return (
    <section className="glass-card p-3 p-lg-4">
      <div className="section-header mb-3">
        <div>
          <p className="eyebrow mb-1">{title}</p>
          <h2 className="h4 mb-0">{subtitle}</h2>
        </div>
      </div>

      {rows.length === 0 ? (
        <div className="alert alert-dark border-0 mb-0">{emptyText}</div>
      ) : (
        <div className="table-responsive">
          <table className="table table-dark table-hover align-middle mb-0">
            <thead>
              <tr>
                {columns.map((column) => (
                  <th key={column.key}>{column.label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.key}>
                  {columns.map((column) => (
                    <td key={`${row.key}-${column.key}`}>{column.render(row)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

function Recommendations({ currentUser }) {
  const [payload, setPayload] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [resetting, setResetting] = useState(false)
  const [resetError, setResetError] = useState('')

  const loadRecommendations = async () => {
    setLoading(true)
    setError('')

    try {
      const data = await api.getFinalRecommendations({ user_id: currentUser.user_id, top_n: 12, latent_dims: 12 })
      setPayload(data)
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!currentUser) {
      return undefined
    }

    loadRecommendations()
  }, [currentUser])

  const summary = useMemo(() => {
    if (!payload) {
      return []
    }

    return [
      { label: 'Final picks', value: payload.final_recommendations?.length || 0 },
      { label: 'SVD picks', value: payload.svd_recommendations?.length || 0 },
      { label: 'TF-IDF picks', value: payload.content_recommendations?.length || 0 },
      { label: 'Genre coverage', value: payload.diagnostics?.diversity?.genre_coverage ?? 'n/a' },
      { label: 'Feedback samples', value: payload.diagnostics?.feedback_count ?? 0 },
      { label: 'Blend mode', value: payload.blend?.mode || 'balanced' },
      { label: 'Blend', value: payload.blend ? `${Math.round(payload.blend.svd_weight * 100)} / ${Math.round(payload.blend.content_weight * 100)}` : '55 / 45' },
    ]
  }, [payload])

  const handleResetFeedback = async () => {
    setResetting(true)
    setResetError('')

    try {
      await api.resetRecommendationFeedback({ user_id: currentUser.user_id })
      await loadRecommendations()
    } catch (requestError) {
      setResetError(requestError.message)
    } finally {
      setResetting(false)
    }
  }

  const finalRows = useMemo(() => {
    const items = payload?.final_recommendations || []
    return items.map((movie, index) => ({
      key: `final-${movie.movie_id}`,
      movie_id: movie.movie_id,
      rank: index + 1,
      title: movie.title,
      svd: movie.svd_score,
      tfidf: movie.content_score,
      final: movie.final_score,
      rankScore: movie.rank_score,
      confidence: movie.confidence_score,
      agreement: movie.agreement || 'single-engine',
      diversityAdjustment: movie.diversity_adjustment,
      reason: Array.isArray(movie.reasons) && movie.reasons.length > 0 ? movie.reasons.join(' ') : 'Hybrid score selected this title.',
    }))
  }, [payload])

  const svdRows = useMemo(() => {
    const items = payload?.svd_recommendations || []
    return items.map((movie, index) => ({
      key: `svd-${movie.movie_id}`,
      rank: index + 1,
      title: movie.title,
      score: movie.svd_score,
      reason: movie.source === 'popular-fallback' ? 'Cold-start fallback due to sparse interactions.' : 'Collaborative filtering score from similar-user behavior.',
    }))
  }, [payload])

  const contentRows = useMemo(() => {
    const items = payload?.content_recommendations || []
    return items.map((movie, index) => ({
      key: `content-${movie.movie_id}`,
      rank: index + 1,
      title: movie.title,
      score: movie.content_score,
      matchedFrom: movie.matched_from || 'profile',
      reason: movie.matched_from ? `Matched to text similarity with ${movie.matched_from}.` : 'Matched from profile genre/text similarity.',
    }))
  }, [payload])

  const popularRows = useMemo(() => {
    const items = payload?.popular_recommendations || []
    return items.map((movie, index) => ({
      key: `popular-${movie.movie_id}`,
      rank: index + 1,
      title: movie.title,
      reason: 'Catalog popularity fallback when personalization is limited.',
    }))
  }, [payload])

  return (
    <div className="page-stack">
      <section className="hero-panel glass-card compact-hero">
        <div>
          <p className="eyebrow mb-2">Recommendations</p>
          <h1 className="h2 fw-bold mb-2">Compare the recommendation engines</h1>
          <p className="text-secondary mb-0">This page shows the final blended ranking, the raw SVD output, and the TF-IDF matches side by side with their scores.</p>
        </div>
        <div className="metric-grid">
          {summary.map((item) => (
            <article key={item.label} className="glass-card metric-card">
              <span className="metric-label">{item.label}</span>
              <span className="metric-value">{item.value}</span>
            </article>
          ))}
        </div>
        <div className="d-flex flex-wrap gap-2 align-items-center">
          <button className="btn btn-feedback-reset" type="button" onClick={handleResetFeedback} disabled={resetting}>
            {resetting ? 'Resetting...' : 'Reset feedback'}
          </button>
          <span className="text-secondary small">Clears your local helpful / not helpful history and refreshes the blend.</span>
        </div>
      </section>

      {error ? <div className="alert alert-danger border-0">{error}</div> : null}
      {resetError ? <div className="alert alert-warning border-0">{resetError}</div> : null}

      {loading ? (
        <div className="text-center py-5 text-secondary">Computing blended recommendations...</div>
      ) : payload ? (
        <>
          <section className="glass-card p-3 p-lg-4">
            <div className="section-header mb-2">
              <div>
                <p className="eyebrow mb-1">Scoring logic</p>
                <h2 className="h4 mb-0">Why these movies were chosen</h2>
              </div>
            </div>
            <div className="formula-box">
              <div>
                Final score = ({Math.round((payload.blend?.svd_weight || 0.55) * 100)}% x normalized SVD) + ({Math.round((payload.blend?.content_weight || 0.45) * 100)}% x normalized TF-IDF) + overlap bonus
              </div>
              <div>
                Overlap bonus = {formatScore(payload.blend?.overlap_bonus || 0.08)} when both engines recommend the same movie.
              </div>
              <div>
                Rank score = final score + diversity adjustment, to improve genre variety.
              </div>
              <div className="text-warning-subtle">Feedback controls now live on the Home page.</div>
            </div>
          </section>

          {titleOnlyTable({
            title: 'Final recommendation',
            subtitle: 'Blended ranking',
            rows: finalRows,
            emptyText: 'No final recommendations yet.',
            columns: [
              { key: 'rank', label: '#', render: (row) => row.rank },
              { key: 'title', label: 'Movie', render: (row) => <strong>{row.title}</strong> },
              { key: 'svd', label: 'SVD', render: (row) => formatScore(row.svd) },
              { key: 'tfidf', label: 'TF-IDF', render: (row) => formatScore(row.tfidf) },
              { key: 'final', label: 'Final score', render: (row) => formatScore(row.final) },
              { key: 'diversityAdjustment', label: 'Diversity adj', render: (row) => formatScore(row.diversityAdjustment) },
              { key: 'rankScore', label: 'Rank score', render: (row) => formatScore(row.rankScore) },
              { key: 'confidence', label: 'Confidence', render: (row) => formatScore(row.confidence) },
              { key: 'agreement', label: 'Agreement', render: (row) => row.agreement },
              { key: 'reason', label: 'Why selected', render: (row) => row.reason },
            ],
          })}

          {titleOnlyTable({
            title: 'SVD',
            subtitle: 'Collaborative recommendations',
            rows: svdRows,
            emptyText: 'No SVD recommendations yet.',
            columns: [
              { key: 'rank', label: '#', render: (row) => row.rank },
              { key: 'title', label: 'Movie', render: (row) => <strong>{row.title}</strong> },
              { key: 'score', label: 'SVD score', render: (row) => formatScore(row.score) },
              { key: 'reason', label: 'Why selected', render: (row) => row.reason },
            ],
          })}

          {titleOnlyTable({
            title: 'TF-IDF',
            subtitle: 'Content matches',
            rows: contentRows,
            emptyText: 'No content-based recommendations yet.',
            columns: [
              { key: 'rank', label: '#', render: (row) => row.rank },
              { key: 'title', label: 'Movie', render: (row) => <strong>{row.title}</strong> },
              { key: 'score', label: 'TF-IDF score', render: (row) => formatScore(row.score) },
              { key: 'match', label: 'Matched from', render: (row) => row.matchedFrom },
              { key: 'reason', label: 'Why selected', render: (row) => row.reason },
            ],
          })}

          {titleOnlyTable({
            title: 'Popular fallback',
            subtitle: 'Catalog alternatives',
            rows: popularRows,
            emptyText: 'No popular fallback entries yet.',
            columns: [
              { key: 'rank', label: '#', render: (row) => row.rank },
              { key: 'title', label: 'Movie', render: (row) => <strong>{row.title}</strong> },
              { key: 'reason', label: 'Why selected', render: (row) => row.reason },
            ],
          })}
        </>
      ) : (
        <div className="alert alert-dark border-0 mb-0">No recommendation data available yet.</div>
      )}
    </div>
  )
}

export default Recommendations