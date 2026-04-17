import { useMemo } from 'react'

function boolTag(value, positiveText = 'Yes', negativeText = 'No') {
  if (value) {
    return <span className="badge rounded-pill text-bg-success">{positiveText}</span>
  }

  return <span className="badge rounded-pill text-bg-secondary">{negativeText}</span>
}

function Interactions({ currentUser, interactions, loadingInteractions }) {
  const interactionRows = useMemo(() => interactions || [], [interactions])

  return (
    <div className="page-stack">
      <section className="hero-panel glass-card compact-hero">
        <div>
            <p className="eyebrow mb-2">History</p>
          <h1 className="h2 fw-bold mb-2">Interaction history</h1>
          <p className="text-secondary mb-0">
            Stored records for <strong>{currentUser.username}</strong>. This verifies that every form submission is persisted and can be retrieved.
          </p>
        </div>
        <div className="hero-stats">
          <div className="stat-pill">
            <span className="stat-value">{interactionRows.length}</span>
            <span className="stat-label">Saved interactions</span>
          </div>
          <div className="stat-pill">
            <span className="stat-value">SQLite</span>
            <span className="stat-label">Persistence ready</span>
          </div>
        </div>
      </section>

      <section className="glass-card interactions-panel p-3 p-lg-4">
        {loadingInteractions ? (
          <div className="text-center py-5 text-secondary">Loading interactions...</div>
        ) : interactionRows.length === 0 ? (
          <div className="alert alert-dark border-0 mb-0">No interactions yet. Open any movie and submit the form to create your first record.</div>
        ) : (
          <div className="table-responsive">
            <table className="table table-dark table-hover align-middle mb-0">
              <thead>
                <tr>
                  <th>Movie</th>
                  <th>Rating</th>
                  <th>Duration</th>
                  <th>Completion</th>
                  <th>One Sitting</th>
                  <th>Skips</th>
                  <th>Watch Again</th>
                  <th>Time of Day</th>
                  <th>Captured At</th>
                </tr>
              </thead>
              <tbody>
                {interactionRows.map((row) => (
                  <tr key={row.interaction_id}>
                    <td>
                      <div className="fw-semibold">{row.movie_title || `Movie #${row.movie_id}`}</div>
                      <small className="text-secondary">ID: {row.movie_id}</small>
                    </td>
                    <td><span className="badge text-bg-warning">{row.rating}/5</span></td>
                    <td>{row.watch_duration_minutes != null ? `${row.watch_duration_minutes} min` : '-'}</td>
                    <td>{row.percent_completed != null ? `${row.percent_completed}%` : '-'}</td>
                    <td>{boolTag(row.watched_one_sitting)}</td>
                    <td>{row.skip_count}</td>
                    <td>{boolTag(row.would_watch_again)}</td>
                    <td className="text-capitalize">{row.time_of_day || '-'}</td>
                    <td>{row.created_at ? new Date(row.created_at).toLocaleString() : '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}

export default Interactions
