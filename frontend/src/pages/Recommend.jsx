import { useEffect, useState } from 'react'

import { api } from '../api'

function Recommend({ currentUser }) {
  const [mode, setMode] = useState('svd')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [payload, setPayload] = useState(null)

  useEffect(() => {
    const loadRecommendations = async () => {
      if (!currentUser) {
        return
      }

      setLoading(true)
      setError('')
      try {
        let data
        if (mode === 'svd') {
          data = await api.getSvdRecommendations({ user_id: currentUser.user_id, top_n: 20 })
        } else if (mode === 'svd-nn') {
          data = await api.getSvdNnRecommendations({ user_id: currentUser.user_id, top_n: 20 })
        } else {
          data = await api.getFullRecommendations({ user_id: currentUser.user_id, top_n: 20 })
        }
        setPayload(data)
      } catch (requestError) {
        setError(requestError.message)
      } finally {
        setLoading(false)
      }
    }

    loadRecommendations()
  }, [currentUser, mode])

  return (
    <div className="page-stack">
      <section className="hero-panel glass-card compact-hero">
        <div>
          <p className="eyebrow mb-2">Recommendations</p>
          <h1 className="h2 fw-bold mb-2">Model output preview</h1>
          <p className="text-secondary mb-0">
            Compare baseline SVD with the SVD + NN stack.
          </p>
        </div>
        <div className="d-flex flex-wrap gap-2">
          <button type="button" className={`btn ${mode === 'svd' ? 'btn-warning' : 'btn-outline-light'}`} onClick={() => setMode('svd')}>
            SVD
          </button>
          <button type="button" className={`btn ${mode === 'svd-nn' ? 'btn-warning' : 'btn-outline-light'}`} onClick={() => setMode('svd-nn')}>
            SVD + NN
          </button>
          <button type="button" className={`btn ${mode === 'full' ? 'btn-warning' : 'btn-outline-light'}`} onClick={() => setMode('full')}>
            Full Hybrid
          </button>
        </div>
      </section>

      {error ? <div className="alert alert-danger border-0">{error}</div> : null}

      <section className="glass-card p-3 p-lg-4">
        {loading ? (
          <div className="text-center py-4 text-secondary">Generating recommendations...</div>
        ) : !payload ? (
          <div className="text-center py-4 text-secondary">No data yet.</div>
        ) : (
          <>
            <div className="how-grid mb-3">
              <article className="glass-card how-card">
                <p className="eyebrow mb-1">SVD</p>
                <h2 className="h5 mb-2">Collaborative baseline</h2>
                <p className="text-secondary mb-0">Learns from MovieLens ratings plus this app's interaction history to predict what similar users liked.</p>
              </article>
              <article className="glass-card how-card">
                <p className="eyebrow mb-1">NN</p>
                <h2 className="h5 mb-2">Behavior-aware scorer</h2>
                <p className="text-secondary mb-0">Uses user_id, movie_id, normalized watch duration, skip flags, and interest level as input features.</p>
              </article>
              <article className="glass-card how-card">
                <p className="eyebrow mb-1">Fuzzy</p>
                <h2 className="h5 mb-2">Small uplift</h2>
                <p className="text-secondary mb-0">Converts the user profile into a positive boost so the final ranking improves instead of being penalized.</p>
              </article>
            </div>

            {payload.training?.profile ? (
              <div className="alert alert-dark border-0 mb-3">
                <strong>{payload.training.profile.profile}</strong> profile detected. {payload.training.profile.reason}
              </div>
            ) : null}

            {payload.training?.explanation ? (
              <div className="formula-box mb-3">
                <div><strong>Why NN:</strong> {payload.training.explanation.why_nn}</div>
                <div><strong>NN inputs:</strong> {payload.training.explanation.what_it_gets}</div>
                <div><strong>Model:</strong> {payload.training.explanation.model}</div>
              </div>
            ) : null}

            <div className="mb-3">
              <span className="badge text-bg-info">Rows: {payload.training?.total_rows || payload.training?.rows || 0}</span>
              {' '}
              <span className="badge text-bg-secondary">Backend: {payload.training?.model_backend || payload.training?.backend || 'unknown'}</span>
            </div>
            <div className="table-responsive">
              <table className="table table-dark table-hover align-middle mb-0">
                <thead>
                  <tr>
                    <th>Movie</th>
                    <th>SVD</th>
                    {mode !== 'svd' ? <th>NN</th> : null}
                    {mode !== 'svd' ? <th>Combined</th> : null}
                    {mode === 'full' ? <th>Fuzzy</th> : null}
                    {mode === 'full' ? <th>Final</th> : null}
                  </tr>
                </thead>
                <tbody>
                  {(payload.recommendations || []).map((row) => (
                    <tr key={row.movie.movie_id}>
                      <td>
                        <div className="fw-semibold">{row.movie.title}</div>
                        <small className="text-secondary">{row.movie.genres}</small>
                      </td>
                      <td>{Number(row.svd_score).toFixed(3)}</td>
                      {mode !== 'svd' ? <td>{Number(row.nn_score).toFixed(3)}</td> : null}
                      {mode !== 'svd' ? <td>{Number(row.combined_score).toFixed(3)}</td> : null}
                      {mode === 'full' ? <td>{Number(row.fuzzy_boost).toFixed(1)}</td> : null}
                      {mode === 'full' ? <td>{Number(row.final_score).toFixed(3)}</td> : null}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </section>
    </div>
  )
}

export default Recommend
