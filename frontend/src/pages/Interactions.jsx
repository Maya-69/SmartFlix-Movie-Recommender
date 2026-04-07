import { useMemo } from 'react'

const durationLabel = {
  '10': '10 min',
  '30': '30 min',
  '60': '60 min',
  full: 'Full',
}

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
                  <th>Watched</th>
                  <th>Duration</th>
                  <th>Completed</th>
                  <th>Skipped Scenes</th>
                  <th>Skipped Music</th>
                  <th>Interest</th>
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
                    <td>{boolTag(row.watched)}</td>
                    <td>{durationLabel[row.watch_duration] || row.watch_duration}</td>
                    <td>{boolTag(row.completed)}</td>
                    <td>{boolTag(row.skipped_scenes, 'Skipped', 'No')}</td>
                    <td>{boolTag(row.skipped_music, 'Skipped', 'No')}</td>
                    <td><span className="badge text-bg-warning">{row.interest_level}/5</span></td>
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
